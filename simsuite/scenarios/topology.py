"""Topologias T2-T6 (doc 05, Fase 6) em simulação."""
import math
import numpy as np
from ..core.channel_static import ENVS
from ..core.links import FixedLink, MobileLink
from ..core import mobility as mob
from ..core.radio import p_demod, noise_dbm, i_tx_ma, VCC, CR_GAIN_DB
from ..protocol.modes import table, DATA_BYTES, CTRL_BYTES
from ..baselines import mesh_models as MM
from .common import r7_km, teto


# ------------------------------------------------------------------ estrela T2/T3
def _p_ok(link, t, m, p, nr, nb=DATA_BYTES):
    rx = link.rx_dbm(t, p)
    return p_demod(rx - noise_dbm(m.bw, nr) + CR_GAIN_DB[m.cr], m.sf)


def star(escala="quick", seed=41):
    """Coordenador + 4 membros. T2: membros homogêneos; T3: um membro 5 ou 10 dB mais fraco.
    Políticas: unanimidade (modo único do grupo), divisão (membro fraco em subgrupo próprio,
    com agenda), relay (membro fraco retransmitido pelo membro mais forte)."""
    env_id = "urbano_residencial"
    env = ENVS[env_id]
    nr = env["noise_rise"]
    R = r7_km(env)
    modes, base, rec = table()
    T = 6 * 3600 if escala == "quick" else 24 * 3600
    rng = np.random.default_rng(seed)
    dists = [0.4 * R, 0.6 * R, 0.8 * R, 1.0 * R]
    out = {}
    for case, weak_db in (("T2 homogênea", 0.0), ("T3 membro fraco -5 dB", 5.0), ("T3 membro fraco -10 dB", 10.0)):
        links = [FixedLink(env, d, np.random.default_rng(seed + i), T + 10, static_shadow=0.0) for i, d in enumerate(dists)]
        weak = 3

        def margin(i, m, t, extra=0.0):
            g = links[i].gain_db(t) - (weak_db if i == weak else 0.0) + extra
            return min(teto(28.0), m.cap) + g - m.sens(nr)

        def best_mode(margins_fn):
            for m in modes:                      # do mais rápido ao mais lento
                if margins_fn(m) >= 6.0:
                    return m
            return base
        res = {}
        for pol in ("unanimidade", "divisao", "relay"):
            rr = np.random.default_rng(seed + 7)
            gen = {i: 0 for i in range(4)}
            dl = {i: 0 for i in range(4)}
            energy = 0.0
            neg_ok = neg_try = 0
            lat_add = []
            for k in range(int(T / 60.0)):
                t = k * 60.0
                # renegociação a cada 30 min
                if k % 30 == 0:
                    if pol == "unanimidade":
                        group = {0: [0, 1, 2, 3]}
                    elif pol == "divisao":
                        group = {0: [0, 1, 2], 1: [3]}
                    else:
                        group = {0: [0, 1, 2]}
                    gmode = {}
                    for gid, mem in group.items():
                        cand = best_mode(lambda m: min(margin(i, m, t) for i in mem))
                        # unanimidade: PROPOSE e COMMIT a todos, VOTE de todos (no modo atual = base)
                        neg_try += 1
                        succ = True
                        for i in mem:
                            for _ in range(3):
                                energy += VCC * i_tx_ma(28.0) * base.toa(CTRL_BYTES)
                                if rr.random() > _p_ok(links[i], t, base, 28.0 - (weak_db if i == weak else 0), nr,
                                                       CTRL_BYTES):
                                    succ = False
                        if succ:
                            neg_ok += 1
                            gmode[gid] = cand
                        else:
                            gmode[gid] = gmode.get(gid, base)
                    frac = {gid: 1.0 / len(group) for gid in group}
                for i in range(4):
                    gen[i] += 1
                    if pol == "relay" and i == weak:
                        # fraco -> membro forte (0) -> coordenador, em modo robusto no 1º salto
                        m1 = best_mode(lambda m: margin(weak, m, t, extra=6.0))
                        ok1 = any(rr.random() < _p_ok(links[weak], t, m1, m1.cap, nr - 6) for _ in range(4))
                        energy += VCC * i_tx_ma(m1.cap) * m1.toa(DATA_BYTES) * 1.5
                        m2 = gmode[0]
                        ok2 = ok1 and any(rr.random() < _p_ok(links[0], t, m2, m2.cap, nr) for _ in range(4))
                        energy += VCC * i_tx_ma(m2.cap) * m2.toa(DATA_BYTES) * 1.5
                        dl[i] += ok2
                        continue
                    gid = next(g for g, mem in group.items() if i in mem)
                    m = gmode[gid]
                    p = teto(28.0) - (weak_db if i == weak else 0.0)
                    okp = False
                    for _ in range(4):
                        energy += VCC * i_tx_ma(min(teto(28.0), m.cap)) * m.toa(DATA_BYTES)
                        if rr.random() < _p_ok(links[i], t, m, min(p, m.cap), nr):
                            okp = True
                            break
                    dl[i] += okp
                    lat_add.append((1 - frac[gid]) * 10.0 / 2)     # espera pela janela do subgrupo
            tot = sum(dl.values())
            res[pol] = {"pdr_grupo": round(tot / sum(gen.values()), 4),
                        "pdr_membro_fraco": round(dl[weak] / gen[weak], 4),
                        "mj_por_pacote": round(energy / max(1, tot), 1),
                        "negociacoes_ok_%": round(100 * neg_ok / max(1, neg_try), 1),
                        "latencia_media_agenda_s": round(float(np.mean(lat_add)), 2) if lat_add else 0.0}
        out[case] = res
    return out


# ------------------------------------------------------------------ malha T4-T6
def _mesh_links(env, pos_or_tracks, T, seed, mobile_idx=()):
    n = len(pos_or_tracks)
    links = {}
    k = 0
    for i in range(n):
        for j in range(i + 1, n):
            if i in mobile_idx or j in mobile_idx:
                links[(i, j)] = MobileLink(env, pos_or_tracks[i], pos_or_tracks[j], np.random.default_rng(seed + k))
            else:
                a, b = pos_or_tracks[i].xyz[0], pos_or_tracks[j].xyz[0]
                d = float(np.hypot(*(a[:2] - b[:2]))) / 1000.0
                links[(i, j)] = FixedLink(env, max(d, 0.05), np.random.default_rng(seed + k), T + 10)
            k += 1
    return links


def mesh(escala="quick", seed=51):
    T = 2 * 3600 if escala == "quick" else 6 * 3600
    methods = ["meshtastic", "meshcore", "reticulum", "loramesher", "adaptlora", "adaptlora+ff"]
    out = {}
    for env_id in ("urbano_residencial", "rural_aberto"):
        env = ENVS[env_id]
        R = r7_km(env) * 1000
        rng = np.random.default_rng(seed)
        topo = {}
        # T4: linha de 6 nós (ponte estreita), espaçamento 0,7 x R7, coletor no fim
        line = [mob.static(i * 0.7 * R, 0, 3, T + 60) for i in range(6)]
        topo["T4 linha 6 nós"] = (line, 5, ())
        # T5: 14 nós aleatórios em 3 x R7, coletor no centro
        pts = rng.uniform(0, 3 * R, (14, 2))
        pts[0] = [1.5 * R, 1.5 * R]
        grid = [mob.static(x, y, 3, T + 60) for x, y in pts]
        topo["T5 malha 14 nós"] = (grid, 0, ())
        # T6: T5 + 2 nós móveis (pedestre e carro)
        mobt = list(grid)
        mobt[12] = mob.random_waypoint_area(3 * R, 1.4, T=T + 60, rng=np.random.default_rng(seed + 3))
        mobt[13] = mob.random_waypoint_area(3 * R, 11.0, T=T + 60, rng=np.random.default_rng(seed + 4))
        topo["T6 malha com 2 móveis"] = (mobt, 0, (12, 13))
        envres = {}
        for tname, (tracks, sink, mobi) in topo.items():
            links = _mesh_links(env, tracks, T + 60, seed + 100, mobi)
            row = {}
            for regime, p_base in (("sem regra (22 dBm)", 22.0), ("BR-2026", None)):
                for m in methods:
                    if regime == "BR-2026":
                        p = 28.0 if m.startswith("adaptlora") else -3.0      # canal fixo estreito: baixa potência
                    else:
                        p = p_base
                    r = MM.run_two_pass(m, env, links, len(tracks), sink, T, 120.0, seed + 7, p,
                                        "BR-2026" if (regime == "BR-2026" or m.startswith("adaptlora")) else "sem-regra")
                    row[f"{m} ({regime})"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()
                                              if k not in ("ocupacao", "perda_colisao")}
                    row[f"{m} ({regime})"]["ocupacao_%"] = round(100 * sum(r["ocupacao"].values()), 2)
            envres[tname] = row
        out[env_id] = envres
    return out
