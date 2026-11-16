"""Validação sim×sim com o Meshtasticator (https://github.com/meshtastic/Meshtasticator).

Diferente de `lorasim.py` (regras portadas à mão), aqui o código **original** do Meshtasticator é importado e
executado: `lib.phy.airtime`, `lib.phy.check_collision` e a tabela `MODEM_PRESETS` de `lib.config`. O repositório não
é copiado para cá (licença própria): aponte `LEGUA_MESHTASTICATOR` para o clone, ou deixe em `~/.cache/ext/Meshtasticator`.
Sem o clone o cenário devolve `{"disponivel": False}` e a suíte segue.

O que se compara (só a camada física; o roteamento por inundação do Meshtastic não tem equivalente aqui):
tempo no ar dos presets, sensibilidade dos presets, regra de captura (6 dB) e PDR de uma estrela ALOHA.
"""
import argparse
import heapq
import importlib
import itertools
import json
import math
import os
import random
import sys
from types import SimpleNamespace

from simsuite.core.radio import toa_s
from simsuite.analysis.lorasim import aloha, run_ours, RAIZ

PADRAO = os.path.expanduser("~/.cache/ext/Meshtasticator")


def carregar():
    """Importa `lib.phy` e `lib.config` do clone. Devolve (phy, CONFIG, caminho) ou None."""
    raiz = os.environ.get("LEGUA_MESHTASTICATOR", PADRAO)
    if not os.path.isfile(os.path.join(raiz, "lib", "phy.py")):
        return None
    for nome in [n for n in sys.modules if n == "lib" or n.startswith("lib.")]:
        del sys.modules[nome]                               # outro pacote `lib` não pode atrapalhar
    sys.path.insert(0, raiz)
    try:
        phy = importlib.import_module("lib.phy")
        cfg = importlib.import_module("lib.config").CONFIG
    finally:
        sys.path.remove(raiz)
    return phy, cfg, raiz


def _versao(raiz):
    try:
        with open(os.path.join(raiz, ".git", "HEAD")) as fh:
            h = fh.read().strip()
        if h.startswith("ref:"):
            with open(os.path.join(raiz, ".git", h[5:].strip())) as fh:
                h = fh.read().strip()
        return h[:7]
    except OSError:
        return "?"


def cmp_airtime(phy, cfg):
    """Mesmo preâmbulo (NPREAM do Meshtastic = 16) e cabeçalho do Meshtastic somado ao payload."""
    worst, n, dif = 0.0, 0, set()
    for nome, pr in cfg.MODEM_PRESETS.items():
        sf, bw, cr = pr["sf"], pr["bw"], pr["cr"]
        for pl in range(1, 241):
            a = phy.airtime(cfg, sf, cr - 4, pl, bw)
            b = 1000 * toa_s(sf, bw / 1e3, pl + cfg.HEADERLENGTH, cr - 4, preamble=cfg.NPREAM)
            n += 1
            if abs(a - b) > 1e-6:
                dif.add(nome)
                worst = max(worst, abs(a - b))
    return {"presets": len(cfg.MODEM_PRESETS), "combinacoes": n, "presets_diferentes": sorted(dif),
            "maior_diferenca_ms": worst,
            "explicacao": "Diferença só onde o símbolo passa de 16 ms com BW diferente de 125 kHz (o Meshtasticator liga "
                          "o LDRO apenas em BW125 com SF11/12; aqui vale a regra da Semtech)."}


def cmp_sensibilidade(cfg):
    from simsuite.protocol.modes import _m
    linhas = []
    for nome, pr in cfg.MODEM_PRESETS.items():
        m = _m(pr["sf"], int(pr["bw"] / 1e3), pr["cr"] - 4, False, 28.0, "sem regra")
        linhas.append({"preset": nome, "sf": pr["sf"], "bw": int(pr["bw"] / 1e3), "meshtastic_dbm": pr["sensitivity"],
                       "aqui_dbm": round(m.sens(), 2), "diferenca_db": round(m.sens() - pr["sensitivity"], 2)})
    d = [abs(r["diferenca_db"]) for r in linhas]
    return {"linhas": linhas, "diferenca_media_abs_db": sum(d) / len(d), "maior_diferenca_db": max(d),
            "nota": "A tabela do Meshtastic vem de uma calculadora com NF de 6 dB; a daqui, do limiar de SNR do SX1262 "
                    "com a figura de ruído do modelo."}


def _pkt(nid, seq, sf, bw, rssi, t0, dur):
    return SimpleNamespace(txNodeId=nid, unique_packet_seq=seq, freq=915e6, bw=bw, sf=sf, rssiAtN={0: rssi},
                           collidedAtN={0: False}, startTime=t0, endTime=t0 + dur)


def cmp_captura_regra(phy, cfg):
    """Tabela de decisão: para cada diferença de potência, quem sobrevive. Referência: SIR >= 6 dB captura."""
    linhas, iguais = [], True
    for d in (0, 1, 3, 5, 5.9, 6, 6.1, 8, 10, 20):
        forte, fraco = -80.0, -80.0 - d
        env = SimpleNamespace(now=1.0)
        a = _pkt(1, 1, 9, 250e3, forte, 0.0, 10.0)
        b = _pkt(2, 2, 9, 250e3, fraco, 0.9, 10.0)           # b chega depois, mas a ainda está no ar
        phy.check_collision(cfg, env, b, 0, {0: [a]})
        mesh = (not a.collidedAtN[0], not b.collidedAtN[0])   # (forte sobrevive, fraco sobrevive)
        aqui = (True, False) if d >= 6 else (False, False)
        iguais &= (mesh == aqui)
        linhas.append({"delta_db": d, "meshtastic": {"forte_ok": mesh[0], "fraco_ok": mesh[1]},
                       "aqui": {"forte_ok": aqui[0], "fraco_ok": aqui[1]}})
    return {"linhas": linhas, "iguais": iguais}


def run_mesh(phy, cfg, nodes, mean_ms, T_ms, sf, bw, cr, pl, rssi_of, seed):
    """Estrela ALOHA com a decisão de colisão original do Meshtasticator (`check_collision`)."""
    rnd = random.Random(seed)
    rect = phy.airtime(cfg, sf, cr - 4, pl, bw)
    ev, cnt = [], itertools.count()
    for i in range(nodes):
        heapq.heappush(ev, (rnd.expovariate(1.0 / mean_ms), next(cnt), "start", i))
    air, sent, ok, cur = [], [0] * nodes, [0] * nodes, {}
    env = SimpleNamespace(now=0.0)
    saved = random.getstate()
    try:
        while ev:
            t, _, kind, i = heapq.heappop(ev)
            if t > T_ms:
                break
            env.now = t
            if kind == "start":
                sent[i] += 1
                p = _pkt(i, sent[i], sf, bw, rssi_of(i), t, rect)
                phy.check_collision(cfg, env, p, 0, {0: list(air)})
                air.append(p)
                cur[i] = p
                heapq.heappush(ev, (t + rect, next(cnt), "end", i))
            else:
                p = cur.pop(i)
                air.remove(p)
                if not p.collidedAtN[0]:
                    ok[i] += 1
                heapq.heappush(ev, (t + rnd.expovariate(1.0 / mean_ms), next(cnt), "start", i))
    finally:
        random.setstate(saved)
    return sent, ok


def cmp_aloha(phy, cfg, rapido):
    """SF9/250 kHz CR 4/5, payload 20 B. Cada simulador usa o próprio tempo no ar; compara-se com ALOHA analítico
    calculado a partir desse tempo (a colisão pura, sem captura, vale e^(-2G))."""
    sf, bw, cr, pl, mean_s = 9, 250e3, 5, 20, 120.0
    T = 3600.0 if rapido else 4 * 3600.0
    toa_m = phy.airtime(cfg, sf, cr - 4, pl, bw) / 1000
    toa_a = toa_s(sf, bw / 1e3, pl + cfg.HEADERLENGTH, cr - 4, preamble=cfg.NPREAM)
    Ns = [20, 60, 120] if rapido else [20, 40, 80, 120, 200, 300]
    pontos = []
    for N in Ns:
        sm = om = sa = oa = 0
        for seed in range(3):
            s, o = run_mesh(phy, cfg, N, mean_s * 1000, T * 1000, sf, bw, cr, pl, lambda i: -100.0, 500 + seed)
            sm += sum(s)
            om += sum(o)
            s, o = run_ours(N, mean_s, T, sf, int(bw / 1e3), cr - 4, pl + cfg.HEADERLENGTH, lambda i: -90.0, 600 + seed)
            sa += sum(s)
            oa += sum(o)
        pontos.append({"nos": N, "G": N * toa_m / mean_s, "pdr_analitico": aloha(N, mean_s, toa_m),
                       "pdr_meshtastic": om / sm, "pdr_aqui": oa / sa, "pacotes_meshtastic": sm, "pacotes_aqui": sa})
    return {"sf": sf, "bw_khz": bw / 1e3, "cr": cr, "payload_B": pl, "intervalo_medio_s": mean_s,
            "tempo_no_ar_meshtastic_ms": 1000 * toa_m, "tempo_no_ar_aqui_ms": 1000 * toa_a,
            "horas_por_semente": T / 3600, "pontos": pontos,
            "nota": "Aqui o preâmbulo do simulador desta suíte é o padrão (8); a diferença de tempo no ar acima vem daí e "
                    "do cabeçalho, por isso a coluna analítica usa o tempo de cada um."}


def comparar(rapido):
    c = carregar()
    if c is None:
        return {"disponivel": False,
                "motivo": "clone do Meshtasticator não encontrado (defina LEGUA_MESHTASTICATOR)"}
    phy, cfg, raiz = c
    return {"disponivel": True, "referencia": f"Meshtasticator (commit {_versao(raiz)}), código original executado",
            "tempo_no_ar": cmp_airtime(phy, cfg), "sensibilidade": cmp_sensibilidade(cfg),
            "regra_de_captura": cmp_captura_regra(phy, cfg), "aloha": cmp_aloha(phy, cfg, rapido)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--saida", default=os.path.join(RAIZ, "simsuite", "results", "sim_x_sim_mesh.json"))
    a = ap.parse_args(argv)
    out = comparar(a.rapido)
    out["escala"] = "rapido" if a.rapido else "completo"
    os.makedirs(os.path.dirname(a.saida), exist_ok=True)
    with open(a.saida, "w") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    if not out["disponivel"]:
        print(out["motivo"])
        return 0
    print("tempo no ar:", json.dumps(out["tempo_no_ar"], ensure_ascii=False))
    s = out["sensibilidade"]
    print(f"sensibilidade: média |Δ| {s['diferenca_media_abs_db']:.2f} dB, máx {s['maior_diferenca_db']:.2f} dB")
    print("captura iguais:", out["regra_de_captura"]["iguais"])
    for p in out["aloha"]["pontos"]:
        print(f"N={p['nos']:4d} G={p['G']:.3f} analítico={p['pdr_analitico']:.4f} meshtastic={p['pdr_meshtastic']:.4f} "
              f"aqui={p['pdr_aqui']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
