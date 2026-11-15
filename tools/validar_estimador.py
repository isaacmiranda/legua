#!/usr/bin/env python3
"""Valida o estimador analítico contra o simulador de eventos com sombreamento estático controlado.

Uso (a partir da raiz):  PYTHONPATH=. ~/.venvs/legua/bin/python tools/validar_estimador.py   # ~3 min
Compara a entrega do receptor (estimativa x simulação) em 3 modos fixos, 2 ambientes, sombreamento 0 e +1 sigma,
3 sementes de 6 h por ponto. Resultado de 15/11/2026: 42 pontos, erro absoluto médio 0,011, máximo 0,049, viés -0,007.
"""
import numpy as np, json
from simsuite.core.channel_static import ENVS
from simsuite.core.links import FixedLink
from simsuite.protocol.modes import table, by_name
from simsuite.protocol.variants import locked_factory
from simsuite.scenarios.common import make_pair, summarize
from simsuite.analysis import estimator as E
modes, base, rec = table()
cfgs = {"SF10/125 FH": (base, 10, 125, 1, True), "SF7/125 FH": (by_name(modes, "SF7/125/FH"), 7, 125, 1, True),
        "SF12/500": (by_name(modes, "SF12/500"), 12, 500, 1, False)}
T = 6 * 3600; seeds = [1, 2, 3]
rows = []
for env_id, dists in (("urbano_denso", [0.6, 1.0, 1.5, 2.0]), ("rural_aberto", [14, 20, 26])):
    env = ENVS[env_id]
    off = 8.5 if env_id == "rural_aberto" else 0.0
    for sig in (0.0, 1.0):
        for cn, (mode, sf, bw, cr, fh) in cfgs.items():
            for d in dists:
                dl = ge = 0
                for s in seeds:
                    link = FixedLink(env, d, np.random.default_rng(300 + s), T + 10, static_shadow=sig * env["sigma_static"])
                    link = type("O", (), {"inner": link, "gain_db": lambda self, t: self.inner.gain_db(t) + off,
                                          "fade": lambda self, t=None: self.inner.fade(t), "radial": lambda self, t: (0.0, 0.0),
                                          "distance": lambda self, t: self.inner.distance(t),
                                          "rx_dbm": lambda self, t, p: p + self.gain_db(t) + self.fade(t)})()
                    sim = make_pair(env_id, link, T, s * 7 + 1, app_interval=20.0, endpoint_cls=locked_factory(mode))
                    sim.nodes[1].app_interval = None
                    sim.start(); sim.run()
                    r = summarize(sim); dl += r["entregues"]; ge += r["gerados"]
                est = E.estimate_one(env_id, d, sf, bw, cr, 28.0, fh, sig, offset_db=off)["entregue"]
                rows.append((env_id, sig, cn, d, dl / ge, est))
                print(f"{env_id[:8]} σ={sig:+.0f} {cn:12s} d={d:5} sim={dl/ge:.3f} est={est:.3f} Δ={est-dl/ge:+.3f}", flush=True)
err = np.array([abs(r[5] - r[4]) for r in rows]); bias = np.mean([r[5] - r[4] for r in rows])
print(f"\nN={len(rows)}  erro absoluto médio={err.mean():.3f}  máx={err.max():.3f}  viés médio (est−sim)={bias:+.3f}")
json.dump(rows, open("/tmp/validacao_estimador.json", "w"))
