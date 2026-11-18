"""Mede o custo do replay em massa contra o RESYNC (docs/07 §6.3): cenário FAST, ganho -138 dB, 1 h, chan_seed=3, replays no nó 2.
Uso: PYTHONPATH=. ~/.venvs/legua/bin/python tools/medir_replay_resync.py (~1 min)."""
import sys
from simsuite.tests import equiv_harness as H
from simsuite.tests.test_equivalencia import FAST
T=3_600_000
for iv in (None, 60_000, 10_000, 2_000, 500, 100):
    inj=[] if iv is None else [(t,2,"replay") for t in range(100_000,T-100_000,iv)]
    r=H.rodar(dict(cfg=FAST,gain=lambda t:-138.0,T=T,chan_seed=3,inject=inj),("py","py"))
    b,a=r["stats"][2],r["stats"][1]
    print(iv, "inj",len(inj),"| B(alvo): pedidos",b["resync_pedidos"],"ok",b["resync_ok"],"rej",b["rejeitados"],"entregues",b["entregues"],"tx_ctrl",b["tx_ctrl"],"| A: resp tx_ctrl",a["tx_ctrl"],"entregues",a["entregues"],"trocas",a["trocas"]+b["trocas"],"rollbacks",a["rollbacks"]+b["rollbacks"],flush=True)
