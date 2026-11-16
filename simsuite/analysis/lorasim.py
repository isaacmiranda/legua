"""Validação simulação x simulação (Fase 2, parte 1): as regras de colisão e o tempo no ar do LoRaSim.

LoRaSim (Bor, Roedig, Voigt, Alonso; MSWiM 2016; código em github.com/mcbor/lorasim, commit 1eddb96) é um simulador
em Python 2: **não foi executado**. As regras abaixo foram **portadas à mão** de `loraDir.py` (funções `airtime`,
`checkcollision`, `powerCollision`, `timingCollision`, `transmit`) e rodam num laço de eventos próprio. Um erro de
porte é possível; por isso há três referências: a porta do LoRaSim, o simulador de eventos desta suíte
(`simsuite.core.des`, o mesmo usado em todos os cenários) e a expressão analítica do ALOHA puro.

Comparações:
  1. tempo no ar: `airtime` do LoRaSim contra `toa_s` daqui (SF7 a SF12, BW 125/250/500, CR 1 a 4, 1 a 60 B);
  2. colisão em estrela com potências iguais (todo par que se sobrepõe se perde, salvo a exceção do preâmbulo do
     LoRaSim): PDR em função do número de nós, contra e^(-2G);
  3. captura: metade dos nós 10 dB mais fortes; PDR dos fortes e dos fracos;
  4. sensibilidade (informativo): tabela medida do LoRaSim (SX1272) contra o modelo daqui (SX1262).
Também é o cenário `xsim` da suíte (run_suite). Uso avulso: PYTHONPATH=. python3 -m simsuite.analysis.lorasim [--rapido]
"""
import argparse
import heapq
import itertools
import json
import math
import os
import random
import sys

from simsuite.core.des import Node, Sim
from simsuite.core.radio import toa_s, noise_dbm
from simsuite.protocol.endpoint import Frame
from simsuite.protocol.modes import Mode

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- tabela 3 do LoRaSim (sensibilidade medida, SX1272): [SF, BW125, BW250, BW500]
LORASIM_SENS = {7: (-126.5, -124.25, -120.75), 8: (-127.25, -126.75, -124.0), 9: (-131.25, -128.25, -127.5),
                10: (-132.75, -130.25, -128.75), 11: (-134.5, -132.75, -128.75), 12: (-133.25, -132.25, -132.25)}


# ------------------------------------------------------------------ porte do LoRaSim (ms, kHz)
def lorasim_airtime(sf, cr, pl, bw):
    """loraDir.py: airtime(). Cabeçalho explícito (H=0), exceto SF6; DE=1 só para BW125 com SF11/12."""
    H = 1 if sf == 6 else 0
    DE = 1 if (bw == 125 and sf in (11, 12)) else 0
    Tsym = (2.0 ** sf) / bw
    Tpream = (8 + 4.25) * Tsym
    payload = 8 + max(math.ceil((8.0 * pl - 4.0 * sf + 28 + 16 - 20 * H) / (4.0 * (sf - 2 * DE))) * (cr + 4), 0)
    return Tpream + payload * Tsym


class LPkt:
    def __init__(self, nid, sf, bw, rssi, rectime):
        self.nid, self.sf, self.bw, self.rssi, self.rectime = nid, sf, bw, rssi, rectime
        self.collided = False
        self.t0 = 0.0


def lorasim_collide(p, air, now, full=True):
    """loraDir.py: checkcollision() com full_collision (mesma frequência e SF; potência 6 dB; preâmbulo)."""
    for o in air:
        if o is p or o.nid == p.nid or o.sf != p.sf:
            continue
        if not full:
            p.collided = o.collided = True
            continue
        tpream = 2 ** p.sf / (1.0 * p.bw) * (8 - 5)                 # últimos (8-5) símbolos do preâmbulo
        if now + tpream < o.t0 + o.rectime:                          # timingCollision: não chegou tarde o bastante
            if abs(p.rssi - o.rssi) < 6:                             # powerCollision: os dois se perdem
                p.collided = o.collided = True
            elif p.rssi - o.rssi < 6:                                # o outro é mais forte: p se perde
                p.collided = True
            else:
                o.collided = True


def run_lorasim(nodes, mean_ms, T_ms, sf, bw, cr, pl, rssi_of, seed):
    """Estrela ALOHA: intervalos exponenciais (transmit()), chegada ao BS = início da transmissão."""
    rnd = random.Random(seed)
    rect = lorasim_airtime(sf, cr, pl, bw)
    ev = []                                               # (t, ordem, tipo, nó)
    cnt = itertools.count()
    for i in range(nodes):
        heapq.heappush(ev, (rnd.expovariate(1.0 / mean_ms), next(cnt), "start", i))
    air, sent, ok = [], [0] * nodes, [0] * nodes
    cur = {}
    while ev:
        t, _, kind, i = heapq.heappop(ev)
        if t > T_ms:
            break
        if kind == "start":
            sent[i] += 1
            p = LPkt(i, sf, bw, rssi_of(i), rect)
            p.t0 = t
            lorasim_collide(p, air, t)
            air.append(p)
            cur[i] = p
            heapq.heappush(ev, (t + rect, next(cnt), "end", i))
        else:
            p = cur.pop(i)
            air.remove(p)
            if not p.collided:
                ok[i] += 1
            heapq.heappush(ev, (t + rnd.expovariate(1.0 / mean_ms), next(cnt), "start", i))
    return sent, ok


# ------------------------------------------------------------------ simulador desta suíte
class _Link:
    def __init__(self, gain):
        self.gain = gain

    def gain_db(self, t):
        return self.gain

    def rx_dbm(self, t, p):
        return p + self.gain

    def radial(self, t):
        return 0.0, 0.0


class _StarSim(Sim):
    def channel(self, node, mode, peer, t_local):          # um canal só (o LoRaSim usa uma frequência)
        return ("fix", mode.bw, 0)


def run_ours(nodes, mean_s, T_s, sf, bw, cr, pl, gain_of, seed, p_dbm=14.0):
    rng = random.Random(seed)
    env = {"noise_rise": 0.0, "G_ext": 0.0}
    links = {(0, i + 1): _Link(gain_of(i)) for i in range(nodes)}
    sim = _StarSim(env, rng, T_s, links)
    sim.lbt = False                                         # sem escuta antes de transmitir (ALOHA puro)
    sink = Node(0)
    m = Mode(f"SF{sf}/{bw}", sf, float(bw), cr, False, 28.0, "sem regra")
    sink.rx_mode = m                                        # o sorvedouro escuta nesse modo
    sim.add(sink)
    for i in range(nodes):
        sim.add(Node(i + 1))
    seqs = [0] * nodes

    def fire(i):
        seqs[i] += 1
        sim.send(sim.nodes[i + 1], Frame("DATA", i + 1, 0, m, p_dbm, seq=seqs[i], nbytes=pl))
        nxt = sim.now + rng.expovariate(1.0 / mean_s)
        if nxt < T_s:
            sim.at(nxt, fire, i)
    for i in range(nodes):
        sim.at(rng.expovariate(1.0 / mean_s), fire, i)
    sim.run()
    got = [0] * nodes
    for (src, seq, _tg, _tr) in sim.deliveries:
        got[src - 1] += 1
    return seqs, got


# ------------------------------------------------------------------ comparações
def cmp_airtime():
    """Diferenças só podem vir de SF12/250 (símbolo de 16,4 ms: o LoRaSim só liga o LDRO em BW125 com SF11/12; a
    Semtech manda ligar acima de 16 ms, que é o que o simulador daqui faz)."""
    worst, n, dif = 0.0, 0, set()
    for sf in range(7, 13):
        for bw in (125, 250, 500):
            for cr in range(1, 5):
                for pl in range(1, 61):
                    a, b = lorasim_airtime(sf, cr, pl, bw), 1000 * toa_s(sf, bw, pl, cr)
                    n += 1
                    if abs(a - b) > 1e-6:
                        dif.add((sf, bw))
                        worst = max(worst, abs(a - b))
    return {"combinacoes": n, "combinacoes_sf_bw_diferentes": sorted(dif), "maior_diferenca_ms": worst,
            "explicacao": "LDRO: o LoRaSim só o liga em BW125 com SF11/12; aqui vale a regra da Semtech (símbolo > 16 ms), "
                          "que inclui SF12/250."}


def aloha(nodes, mean_s, toa):
    G = nodes * toa / mean_s
    return math.exp(-2 * G)


def cmp_aloha(rapido):
    sf, bw, cr, pl, mean_s = 7, 125, 1, 20, 60.0
    T = 3600.0 if rapido else 4 * 3600.0
    toa = toa_s(sf, bw, pl, cr)
    Ns = [10, 40, 100] if rapido else [10, 25, 50, 100, 150, 200]
    out = []
    for N in Ns:
        sent_l = ok_l = sent_o = ok_o = 0
        for seed in range(3):
            s, o = run_lorasim(N, mean_s * 1000, T * 1000, sf, bw, cr, pl, lambda i: -76.0, 100 + seed)
            sent_l += sum(s)
            ok_l += sum(o)
            s, o = run_ours(N, mean_s, T, sf, bw, cr, pl, lambda i: -90.0, 200 + seed)
            sent_o += sum(s)
            ok_o += sum(o)
        out.append({"nos": N, "G": N * toa / mean_s, "pdr_analitico": aloha(N, mean_s, toa),
                    "pdr_lorasim": ok_l / sent_l, "pdr_aqui": ok_o / sent_o, "pacotes_lorasim": sent_l,
                    "pacotes_aqui": sent_o})
    return {"sf": sf, "bw": bw, "cr": cr, "payload_B": pl, "intervalo_medio_s": mean_s, "horas_por_semente": T / 3600,
            "tempo_no_ar_ms": 1000 * toa, "pontos": out}


def cmp_captura(rapido):
    sf, bw, cr, pl, mean_s, N = 7, 125, 1, 20, 60.0, 100
    T = 3600.0 if rapido else 4 * 3600.0
    strong = lambda i: i % 2 == 0
    res = {}
    for nome, fl, fo in (("lorasim", lambda i: -66.0 if strong(i) else -76.0, None),
                         ("aqui", None, lambda i: -80.0 if strong(i) else -90.0)):
        sent = [0] * N
        got = [0] * N
        for seed in range(3):
            if nome == "lorasim":
                s, o = run_lorasim(N, mean_s * 1000, T * 1000, sf, bw, cr, pl, fl, 300 + seed)
            else:
                s, o = run_ours(N, mean_s, T, sf, bw, cr, pl, fo, 400 + seed)
            sent = [a + b for a, b in zip(sent, s)]
            got = [a + b for a, b in zip(got, o)]
        f = lambda sel: sum(got[i] for i in range(N) if sel(i)) / max(1, sum(sent[i] for i in range(N) if sel(i)))
        res[nome] = {"pdr_fortes": f(strong), "pdr_fracos": f(lambda i: not strong(i))}
    return {"nos": N, "diferenca_de_potencia_dB": 10, "resultado": res}


def cmp_sensibilidade():
    from simsuite.protocol.modes import _m
    rows = []
    for sf in range(7, 13):
        for k, bw in enumerate((125, 250, 500)):
            m = _m(sf, bw, 1, False, 28.0, "sem regra")
            rows.append({"sf": sf, "bw": bw, "lorasim_dbm": LORASIM_SENS[sf][k], "aqui_dbm": round(m.sens(), 2),
                         "diferenca_db": round(m.sens() - LORASIM_SENS[sf][k], 2)})
    d = [abs(r["diferenca_db"]) for r in rows]
    return {"linhas": rows, "diferenca_media_abs_db": sum(d) / len(d), "maior_diferenca_db": max(d),
            "nota": "A tabela do LoRaSim é medida num SX1272; a daqui vem do limiar de SNR + figura de ruído do SX1262."}


def comparar(rapido):
    """Resultado completo (cenário `xsim`): rápido = 1 h por semente e 3 tamanhos; completo = 4 h e 6 tamanhos."""
    return {"referencia": "LoRaSim loraDir.py (commit 1eddb96), regras portadas à mão; não executado (Python 2)",
            "tempo_no_ar": cmp_airtime(), "aloha": cmp_aloha(rapido), "captura": cmp_captura(rapido),
            "sensibilidade": cmp_sensibilidade()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--saida", default=os.path.join(RAIZ, "simsuite", "results", "sim_x_sim.json"))
    a = ap.parse_args(argv)
    out = comparar(a.rapido)
    out["escala"] = "rapido" if a.rapido else "completo"
    os.makedirs(os.path.dirname(a.saida), exist_ok=True)
    with open(a.saida, "w") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print(json.dumps({k: out[k] for k in ("tempo_no_ar",)}, ensure_ascii=False))
    for p in out["aloha"]["pontos"]:
        print(f"N={p['nos']:4d} G={p['G']:.3f} analítico={p['pdr_analitico']:.4f} lorasim={p['pdr_lorasim']:.4f} "
              f"aqui={p['pdr_aqui']:.4f}")
    print("captura:", json.dumps(out["captura"]["resultado"]))
    s = out["sensibilidade"]
    print(f"sensibilidade: média |Δ| {s['diferenca_media_abs_db']:.2f} dB, máx {s['maior_diferenca_db']:.2f} dB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
