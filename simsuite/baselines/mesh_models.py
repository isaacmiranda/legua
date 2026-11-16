"""Malha (T4-T6): modelos comportamentais de Meshtastic, MeshCore, Reticulum,
LoRaMesher e Légua sobre o mesmo canal e a mesma topologia.

Nível de abstração 2: cada transmissão é sorteada com a curva de PER e o ganho do
enlace no instante; colisões entram como probabilidade a partir da ocupação de
canal medida numa primeira passada (duas passadas). Não roda o firmware real de
nenhum projeto: reproduz o mecanismo de encaminhamento descrito na documentação
de cada um. Presets: Meshtastic LongFast (SF11/250), MeshCore (SF10/250, padrão
US), Reticulum/RNode (SF9/125, suposição), LoRaMesher (SF7/125).
"""
import math
import heapq
import numpy as np
from ..core.radio import p_demod, noise_dbm, i_tx_ma, VCC, toa_s, CR_GAIN_DB
from ..core.channel_static import p_ext_ok
from ..protocol.modes import table, DATA_BYTES

HIDDEN = 0.6
CAPTURE = 0.3


class PHY:
    def __init__(self, sf, bw, cr=1, fhss=False, n_ch=1):
        self.sf, self.bw, self.cr, self.fhss, self.n_ch = sf, bw, cr, fhss, n_ch
        self.name = f"SF{sf}/{bw}" + ("/FH" if fhss else "")

    def toa(self, nb):
        return toa_s(self.sf, self.bw, nb, self.cr)

    def sens(self, nr):
        return noise_dbm(self.bw, nr) + self.sf_thr() + 2.5 - CR_GAIN_DB[self.cr]

    def sf_thr(self):
        from ..core.radio import SNR_THR
        return SNR_THR[self.sf]


PRESETS = {
    "meshtastic": PHY(11, 250),
    "meshcore": PHY(10, 250),
    "reticulum": PHY(9, 125),
    "loramesher": PHY(7, 125),
}


class Net:
    def __init__(self, env, links, n, sink, rng, col_p):
        self.env, self.links, self.n, self.sink, self.rng = env, links, n, sink, rng
        self.col_p = col_p
        self.energy = 0.0
        self.air = 0.0
        self.air_ch = {}

    def link(self, a, b):
        return self.links[(a, b) if a < b else (b, a)]

    def tx(self, phy, nb, p, chkey="fix"):
        t = phy.toa(nb)
        self.energy += VCC * i_tx_ma(p) * t
        self.air += t
        self.air_ch[chkey] = self.air_ch.get(chkey, 0.0) + t
        return t

    def ok(self, u, v, t, phy, nb, p, chkey="fix"):
        rx = self.link(u, v).rx_dbm(t, p)
        snr = rx - noise_dbm(phy.bw, self.env["noise_rise"])
        pr = p_demod(snr + CR_GAIN_DB[phy.cr], phy.sf) * p_ext_ok(self.env, phy.toa(nb), 1.0, phy.cr) * \
            (1 - self.col_p.get(chkey, 0.0))
        return self.rng.random() < pr, rx


# ------------------------------------------------------------------ inundação
def flood(net, src, t, phy, p, nb, hop_limit=3, cancel=True):
    """Inundação gerenciada estilo Meshtastic: contenção por SNR (mais distante repete
    primeiro), cancela o reenvio ao ouvir outro reenvio. Devolve (entregue, latência, saltos)."""
    net.tx(phy, nb, p)
    frontier = [(src, 0, t)]
    seen = {src}
    done = {src}
    got = None
    toa = phy.toa(nb)
    while frontier:
        nxt = []
        for u, h, tu in frontier:
            rcv = []
            for v in range(net.n):
                if v == u:
                    continue
                ok, rx = net.ok(u, v, tu, phy, nb, p)
                if ok:
                    if v == net.sink and got is None:
                        got = (tu + toa - t, h + 1)
                    if v not in seen:
                        seen.add(v)
                        rcv.append((rx, v))
            if h + 1 >= hop_limit:
                continue
            rcv.sort()
            for i, (rx, v) in enumerate(rcv):
                if v == net.sink or v in done:
                    continue
                if cancel and any(w in done and net.ok(w, v, tu, phy, nb, p)[0] for _, w in rcv[:i]):
                    continue
                net.tx(phy, nb, p)
                done.add(v)
                nxt.append((v, h + 1, tu + toa + 0.4 * (i + 1)))
        frontier = nxt
    return got


# ------------------------------------------------------------------ roteamento por tabela
def dijkstra(n, cost, sink):
    dist = [math.inf] * n
    nh = [None] * n
    dist[sink] = 0.0
    pq = [(0.0, sink)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v in range(n):
            c = cost.get((v, u))
            if c is None:
                continue
            if d + c < dist[v]:
                dist[v] = d + c
                nh[v] = u
                heapq.heappush(pq, (d + c, v))
    return nh


def hop(net, u, v, t, phy, p, nb, retries, ack_nb=12, chkey="fix"):
    dur = 0.0
    for a in range(retries + 1):
        dur += net.tx(phy, nb, p, chkey)
        ok, _ = net.ok(u, v, t + dur, phy, nb, p, chkey)
        if ok:
            if retries > 0:
                dur += net.tx(phy, ack_nb, p, chkey)
            return True, dur
        dur += net.rng.uniform(0.5, 2.0)
    return False, dur


def run(method, env, links, n, sink, T, interval, rng, p_tx, col_p, regime="BR-2026", mobile=()):
    flood_fallback = method == "legua+ff"
    if flood_fallback:
        method = "legua"
    net = Net(env, links, n, sink, rng, col_p)
    gen = deliv = 0
    lat, hops = [], []
    nb = DATA_BYTES + (8 if not method.startswith("legua") else 2)
    phy = PRESETS.get(method)
    route = {}             # meshcore: caminhos aprendidos
    nh = [None] * n
    last_ref = -1e9
    modes, base, rec = table("BR-2026" if regime == "BR-2026" else "sem-regra")
    base_phy = PHY(base.sf, base.bw, 1, base.fhss)
    gest = {}
    link_mode = {}
    for k in range(int(T / interval)):
        for src in range(n):
            if src == sink:
                continue
            t = k * interval + rng.uniform(0, interval)
            gen += 1
            # --- manutenção periódica de rotas
            if method in ("loramesher", "reticulum", "legua") and t - last_ref >= \
                    {"loramesher": 120.0, "reticulum": 1800.0, "legua": 300.0}[method]:
                last_ref = t
                cost = {}
                for i in range(n):
                    for j in range(n):
                        if i == j:
                            continue
                        if method == "loramesher":
                            net.tx(phy, 20, p_tx) if j == 0 else None
                            okc = sum(net.ok(i, j, t, phy, 20, p_tx)[0] for _ in range(2))
                            if okc >= 1:
                                cost[(i, j)] = 1.0
                        elif method == "reticulum":
                            if j == 0:
                                net.tx(phy, 40, p_tx)      # anúncio (inundado) por destino
                            if net.ok(i, j, t, phy, 40, p_tx)[0]:
                                cost[(i, j)] = 1.0
                        else:  # legua: beacon no modo base e modo por enlace
                            if j == 0:
                                net.tx(base_phy, 20, min(p_tx, base.cap), "base")
                            ok, rx = net.ok(i, j, t, base_phy, 20, min(p_tx, base.cap), "base")
                            if ok:
                                g = rx - min(p_tx, base.cap)
                                gest[(i, j)] = g if (i, j) not in gest else 0.7 * gest[(i, j)] + 0.3 * g
                            g = gest.get((i, j))
                            if g is None:
                                continue
                            best = None
                            for m in modes:
                                cap = min(p_tx, m.cap)
                                if cap + g - m.sens(env["noise_rise"]) < 6.0:
                                    continue
                                e = m.toa(nb) * i_tx_ma(cap)
                                if best is None or e < best[0]:
                                    best = (e, m, cap)
                            if best is None and min(p_tx, base.cap) + g - base.sens(env["noise_rise"]) > 0:
                                best = (base.toa(nb) * i_tx_ma(min(p_tx, base.cap)) * 3, base, min(p_tx, base.cap))
                            if best:
                                if link_mode.get((i, j), (None, None))[1] != best[1]:
                                    net.tx(base_phy, 20, min(p_tx, base.cap), "base")   # negociação
                                link_mode[(i, j)] = best
                                cost[(i, j)] = best[0] + 1.0
                nh = dijkstra(n, cost, sink)
            # --- encaminhamento
            if method == "meshtastic":
                r = None
                for attempt in range(3):
                    r = flood(net, src, t, phy, p_tx, nb, hop_limit=3)
                    if r:
                        break
                if r:
                    deliv += 1
                    lat.append(r[0])
                    hops.append(r[1])
                continue
            if method == "meshcore":
                path = route.get(src)
                ok_path = False
                if path:
                    u, tt = src, t
                    ok_path = True
                    for v in path:
                        good, dur = hop(net, u, v, tt, phy, p_tx, nb, retries=0)
                        tt += dur
                        if not good:
                            ok_path = False
                            break
                        u = v
                    if ok_path:
                        # ACK fim a fim pelo caminho reverso
                        deliv += 1
                        lat.append(tt - t)
                        hops.append(len(path))
                        for _ in path:
                            net.tx(phy, 12, p_tx)
                        continue
                    route.pop(src, None)
                r = flood(net, src, t, phy, p_tx, nb, hop_limit=8, cancel=True)
                if r:
                    deliv += 1
                    lat.append(r[0])
                    hops.append(r[1])
                    route[src] = _greedy_path(net, src, t, phy, p_tx, nb, r[1])
                continue
            # roteamento hop-a-hop (loramesher, reticulum, legua)
            u, tt, h, okp = src, t, 0, True
            visited = {src}
            while u != sink and h < 10:
                v = nh[u]
                if v is None or v in visited:
                    okp = False
                    break
                if method == "legua":
                    _, m, cap = link_mode.get((u, v), (0, base, min(p_tx, base.cap)))
                    mp = PHY(m.sf, m.bw, m.cr, m.fhss)
                    tt += rng.uniform(0, 1.0)                 # agenda de escuta
                    good, dur = hop(net, u, v, tt, mp, cap, nb, retries=3, chkey="adapt")
                    if not good:                              # recuperação no modo base
                        good, d2 = hop(net, u, v, tt + dur, base_phy, min(p_tx, base.cap), nb, retries=2,
                                       chkey="base")
                        dur += d2
                else:
                    good, dur = hop(net, u, v, tt, phy, p_tx, nb, retries=3 if method == "loramesher" else 0)
                tt += dur
                if not good:
                    okp = False
                    break
                visited.add(v)
                u = v
                h += 1
            if method == "reticulum" and not okp:
                okp = False      # sem prova fim a fim: o emissor reenvia uma vez
                u, tt2, h2, ok2 = src, tt + 5.0, 0, True
                visited = {src}
                while u != sink and h2 < 10:
                    v = nh[u]
                    if v is None or v in visited:
                        ok2 = False
                        break
                    good, dur = hop(net, u, v, tt2, phy, p_tx, nb, retries=0)
                    tt2 += dur
                    if not good:
                        ok2 = False
                        break
                    visited.add(v)
                    u = v
                    h2 += 1
                okp, tt, h = ok2 and u == sink, tt2, h2
            if method == "legua" and not okp and flood_fallback:
                # rota quebrou (nó móvel, enlace caiu): inundação gerenciada no modo base
                r = flood(net, src, tt, base_phy, min(p_tx, base.cap), nb, hop_limit=4)
                if r:
                    okp, u, h = True, sink, r[1]
                    tt += r[0]
            if okp and u == sink:
                deliv += 1
                lat.append(tt - t)
                hops.append(h)
    return {"gerados": gen, "entregues": deliv, "pdr": deliv / gen if gen else 0.0,
            "energia_mj": net.energy, "mj_por_pacote": net.energy / deliv if deliv else None,
            "airtime_por_pacote_ms": 1000 * net.air / deliv if deliv else None,
            "ocupacao": {k: v / T for k, v in net.air_ch.items()},
            "lat_mediana_s": float(np.median(lat)) if lat else None,
            "lat_p95_s": float(np.percentile(lat, 95)) if lat else None,
            "saltos": float(np.mean(hops)) if hops else None}


def _greedy_path(net, src, t, phy, p, nb, hops):
    """Caminho aprendido pelo MeshCore: aproximação pelo melhor vizinho em direção ao sink."""
    path, u = [], src
    for _ in range(max(1, hops)):
        best = None
        for v in range(net.n):
            if v == u or v in path:
                continue
            g = net.link(u, v).gain_db(t)
            gs = net.link(v, net.sink).gain_db(t) if v != net.sink else 0.0
            score = min(g, gs + 3)
            if g + p - phy.sens(net.env["noise_rise"]) > 3 and (best is None or score > best[0]):
                best = (score, v)
        if best is None:
            break
        path.append(best[1])
        u = best[1]
        if u == net.sink:
            break
    if not path or path[-1] != net.sink:
        path.append(net.sink)
    return path


def run_two_pass(method, env, links, n, sink, T, interval, seed, p_tx, regime):
    col = {}
    out = None
    for _ in range(2):
        out = run(method, env, links, n, sink, T, interval, np.random.default_rng(seed), p_tx, col, regime)
        if out is None:
            break
        col = {}
        for k, u in out["ocupacao"].items():
            share = u / (8 if k in ("adapt",) else (35 if k == "base" else 1))
            col[k] = (1 - math.exp(-2 * share * HIDDEN)) * (1 - CAPTURE)
    out["perda_colisao"] = col
    return out
