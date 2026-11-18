"""Replay em massa contra o RESYNC (docs/07 §6.3). Só Python: a equivalência Py/C do RESYNC está em test_equivalencia.py."""
from simsuite.tests import equiv_harness as H
from simsuite.tests.test_equivalencia import FAST


def test_replay_em_massa_provoca_resync_mas_nao_prejudica_o_enlace():
    """Limite conhecido: quadros antigos repetidos pelo atacante contam como recusas. Abaixo de ~1 repetição
    a cada 3 s (menos de 8 entre dois quadros válidos) nada acontece; acima, o alvo pede RESYNC e o par responde, mas a
    entrega e o modo do enlace não mudam. Só Python (a equivalência com o C já cobre RESYNC); mede o custo em quadros."""
    T = 1_800_000
    base = dict(cfg=FAST, gain=lambda t: -138.0, T=T, chan_seed=3)
    sem = H.rodar(base, ("py", "py"))
    raro = H.rodar(dict(base, inject=[(t, 2, "replay") for t in range(100_000, T - 100_000, 60_000)]), ("py", "py"))
    forte = H.rodar(dict(base, inject=[(t, 2, "replay") for t in range(100_000, T - 100_000, 1_000)]), ("py", "py"))
    assert raro["stats"][2]["resync_pedidos"] == 0
    b = forte["stats"][2]
    assert b["resync_pedidos"] >= 10 and b["resync_ok"] >= 5, b       # o alvo é induzido a pedir
    assert b["resync_ok"] <= T / 1000 / 30 + 1                         # no máximo uma resposta por t_resync_min
    for k in ("entregues", "trocas", "rollbacks"):                     # o enlace legítimo não sofre
        assert forte["stats"][2][k] == sem["stats"][2][k], k
