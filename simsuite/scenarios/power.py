"""Varredura da potência de TX (cenário P): teto simétrico, teto assimétrico e controle de potência ligado/desligado.

O teto é o que o integrador permite (regulação, bateria, antena); o protocolo nunca passa dele. Pergunta: quanto custa,
em PDR e em energia por pacote, cada dB de teto a menos, e o que acontece quando os dois nós têm tetos diferentes
(cada um vota com o próprio teto, o ganho do enlace vale o pior sentido). Mesmas sementes de canal em todas as células.
"""
import numpy as np
from ..core.channel_static import ENVS
from ..core.links import FixedLink
from ..protocol.endpoint import Config
from .field import _run_cell

ENV = "urbano_residencial"
CAPS = [2.0, 8.0, 14.0, 20.0, 28.0]


def power_sweep(escala="quick"):
    T = 2 * 3600 if escala == "quick" else 6 * 3600
    seeds = [11, 12] if escala == "quick" else [11, 12, 13, 14, 15]
    dists = [1.0, 2.0, 3.0, 4.0]
    env = ENVS[ENV]
    out = {"ambiente": ENV, "dists_km": dists, "tetos_dbm": CAPS, "T_h": T / 3600, "sementes": seeds,
           "simetrico": {}, "assimetrico": {}, "controle_de_potencia": {}}

    def cell(d, cap, cfg):
        mk = lambda s, d=d: FixedLink(env, d, np.random.default_rng(1000 + s), T + 10)
        return _run_cell(ENV, mk, dict(cfg=cfg), T, seeds, cap=cap)

    for d in dists:
        k = f"{d} km"
        out["simetrico"][k] = {f"{c:g}": cell(d, (c, c), Config()) for c in CAPS}
        # A (nó 0, o que propõe) sempre com 28 dBm; B (nó 1) com o teto da vez
        out["assimetrico"][k] = {f"{c:g}": cell(d, (28.0, c), Config()) for c in CAPS}
        out["controle_de_potencia"][k] = {"ligado": out["simetrico"][k]["28"],
                                          "desligado": cell(d, (28.0, 28.0), Config(power_control=False))}
    out["nota"] = ("Rótulo = teto de TX em dBm. Assimétrico: A=28 dBm e B=teto da coluna. mj_por_pacote_mediana é a energia "
                   "de TX dos dois nós por pacote entregue (modelo de corrente do PA estimado, não medido).")
    return out
