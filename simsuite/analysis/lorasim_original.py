"""Executa o `loraDir.py` ORIGINAL do LoRaSim (Bor et al., 2016; https://github.com/mcbor/lorasim) e compara com o
simulador desta suíte na mesma geometria.

O original é Python 2. Aqui só a **sintaxe** é convertida, numa cópia em memória (`print x` vira `print(x)`; as
mensagens são descartadas). A lógica não é tocada. Precisa de `simpy` (pip install simpy==3.0.10) e do clone em
`LEGUA_LORASIM` ou `~/.cache/ext/lorasim` (commit 1eddb96); sem eles o cenário devolve `{"disponivel": False}`.

Experimento 0 do LoRaSim: uma frequência, SF12, BW125, CR 4/8, 20 B, nós em posições aleatórias no disco de alcance, perda de
percurso log-distância. Para a comparação, o simulador daqui recebe o RSSI que o original sorteou para cada nó.
"""
import argparse
import json
import os
import re
import sys
import tempfile

from simsuite.analysis.lorasim import RAIZ, aloha, run_ours
from simsuite.core.radio import toa_s

PADRAO = os.path.expanduser("~/.cache/ext/lorasim")


def _fonte(raiz):
    """Converte a sintaxe Python 2 de `print` (instruções, inclusive em várias linhas) para chamadas."""
    with open(os.path.join(raiz, "loraDir.py")) as fh:
        linhas = fh.read().split("\n")
    out, i = [], 0
    while i < len(linhas):
        ln = linhas[i]
        m = re.match(r"^(\s*)print\s+(?!\()(.*)$", ln)
        if not m:
            out.append(ln)
            i += 1
            continue
        resto, bal = m.group(2), 0
        bloco = [resto]
        bal = resto.count("(") - resto.count(")")
        while bal > 0 and i + 1 < len(linhas):
            i += 1
            bloco.append(linhas[i])
            bal += linhas[i].count("(") - linhas[i].count(")")
        out.append(m.group(1) + "print(" + "\n".join(bloco) + ")")
        i += 1
    return "\n".join(out)


def disponivel():
    try:
        import simpy  # noqa: F401
    except ImportError:
        return None
    raiz = os.environ.get("LEGUA_LORASIM", PADRAO)
    return raiz if os.path.isfile(os.path.join(raiz, "loraDir.py")) else None


def rodar(nodes, avg_ms, simtime_ms, seed, full_collision=True, raiz=None):
    """Roda o original uma vez. Devolve estatísticas e o RSSI de cada nó."""
    import random
    raiz = raiz or disponivel()
    codigo = compile(_fonte(raiz), "loraDir.py", "exec")
    import matplotlib
    matplotlib.use("Agg")
    g = {"__name__": "lorasim_original", "print": lambda *a, **k: None}
    argv, cwd = sys.argv, os.getcwd()
    random.seed(seed)
    import numpy as np
    np.random.seed(seed)
    sys.argv = ["loraDir.py", str(nodes), str(int(avg_ms)), "0", str(int(simtime_ms)), str(int(full_collision))]
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            exec(codigo, g)
        finally:
            os.chdir(cwd)
            sys.argv = argv
    ns = g["nodes"]
    return {"enviados": sum(n.sent for n in ns), "recebidos": g["nrReceived"], "colisoes": g["nrCollisions"],
            "perdidos_sensibilidade": g["nrLost"], "rssi": [n.packet.rssi for n in ns],
            "rectime_ms": ns[0].packet.rectime, "alcance_m": g["maxDist"]}


def comparar(rapido):
    raiz = disponivel()
    if raiz is None:
        return {"disponivel": False, "motivo": "LoRaSim original ou simpy ausentes (LEGUA_LORASIM, pip install simpy==3.0.10)"}
    T_s = 2 * 3600.0 if rapido else 6 * 3600.0
    mean_s = 600.0                                            # SF12: ~1,3 s no ar
    Ns = [50, 200, 400] if rapido else [50, 100, 200, 400, 800]
    pontos = []
    for N in Ns:
        env = {"enviados": 0, "recebidos": 0, "colisoes": 0, "perdidos": 0, "rec_a": 0, "env_a": 0}
        rect = None
        for seed in range(3):
            r = rodar(N, mean_s * 1000, T_s * 1000, 700 + seed, True, raiz)
            rect = r["rectime_ms"]
            env["enviados"] += r["enviados"]
            env["recebidos"] += r["recebidos"]
            env["colisoes"] += r["colisoes"]
            env["perdidos"] += r["perdidos_sensibilidade"]
            rssi = r["rssi"]
            s, o = run_ours(N, mean_s, T_s, 12, 125, 4, 20, lambda i, rs=rssi: rs[i] - 14.0, 800 + seed)
            env["env_a"] += sum(s)
            env["rec_a"] += sum(o)
        toa = toa_s(12, 125, 20, 4)
        pontos.append({"nos": N, "G": N * (rect / 1000) / mean_s, "pdr_analitico": aloha(N, mean_s, rect / 1000),
                       "pdr_original": env["recebidos"] / env["enviados"],
                       "perdidos_sensibilidade_original": env["perdidos"] / env["enviados"],
                       "pdr_aqui": env["rec_a"] / env["env_a"], "pacotes_original": env["enviados"],
                       "pacotes_aqui": env["env_a"], "tempo_no_ar_original_ms": rect,
                       "tempo_no_ar_aqui_ms": 1000 * toa})
    return {"disponivel": True, "referencia": "LoRaSim loraDir.py original (commit 1eddb96), sintaxe convertida de Python 2; "
            "experimento 0 (SF12, BW125, CR 4/8, 20 B, uma frequência, colisão completa)",
            "horas_por_semente": T_s / 3600, "intervalo_medio_s": mean_s, "pontos": pontos,
            "nota": "Mesma geometria nos dois: o RSSI de cada nó é o que o original sorteou. As diferenças vêm da "
                    "sensibilidade (tabela do SX1272 contra o modelo do SX1262: o original descarta o que está abaixo dela), "
                    "do tempo no ar e da regra de colisão do original (o pacote que chega nos últimos símbolos do preâmbulo "
                    "do outro sobrevive)."}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--saida", default=os.path.join(RAIZ, "simsuite", "results", "sim_x_sim_lorasim_original.json"))
    a = ap.parse_args(argv)
    out = comparar(a.rapido)
    os.makedirs(os.path.dirname(a.saida), exist_ok=True)
    with open(a.saida, "w") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    if not out["disponivel"]:
        print(out["motivo"])
        return 0
    for p in out["pontos"]:
        print(f"N={p['nos']:4d} G={p['G']:.3f} analítico={p['pdr_analitico']:.4f} original={p['pdr_original']:.4f} "
              f"(perda sens. {p['perdidos_sensibilidade_original']:.3f}) aqui={p['pdr_aqui']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
