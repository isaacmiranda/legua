"""Equivalência do núcleo C (Fase 2) com `simsuite/protocol/endpoint.py` (doc 09 §8).

Os quatro pares Py-Py, C-C, Py-C e C-Py precisam produzir rastros idênticos (mesmos quadros byte a byte, mesmas
trocas de modo, mesmas gravações em NVM, mesmas estatísticas). Py-C e C-Py provam também a interoperabilidade do
formato de fio. Pulado sem compilador C. Mais sementes: LEGUA_EQUIV_SEEDS=200 (cada semente leva ~1 s)."""
import os
import shutil
import subprocess

import pytest

from simsuite.protocol.endpoint import Config
from simsuite.tests import equiv_harness as H

precisa_cc = pytest.mark.skipif(not (shutil.which("gcc") or shutil.which("cc")) or not shutil.which("make"),
                                reason="sem compilador C")


@pytest.fixture(scope="module")
def shim():
    r = subprocess.run(["nice", "-n", "15", "make", "-j1", "-C", H.os.path.join(H.RAIZ, "core"), "build/liblegua_shim.so"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    return True


def _confere(sc, nome):
    base, div = H.comparar(sc)
    assert not div, f"{nome}: divergência {div[0][0]} {div[0][1]}"
    return base


FAST = Config(cooldown_up=30.0, n_up=3, neg_backoff0=10.0, neg_backoff_max=60.0, cooldown_back=20.0)


@precisa_cc
def test_enlace_bom_negocia_e_acelera(shim):
    base = _confere(dict(cfg=FAST, gain=lambda t: -138.0, T=1_800_000, chan_seed=1), "bom")
    s = base["stats"][1]
    assert s["trocas"] >= 1 and s["neg_ok"] >= 1 and s["rollbacks"] == 0


@precisa_cc
def test_degradacao_silencio_e_retorno(shim):
    def g(t):
        return -156.0 if 900_000 <= t < 2_400_000 else (-190.0 if 3_000_000 <= t < 3_500_000 else -138.0)
    base = _confere(dict(cfg=FAST, gain=g, T=4_500_000, chan_seed=2), "degradacao")
    s = base["stats"][1]
    assert s["degradacoes"] + s["quedas_base"] >= 1 and s["desc_silencio"] >= 1


@precisa_cc
def test_reinicio_replay_e_forjado(shim):
    base = _confere(dict(cfg=FAST, gain=lambda t: -140.0, T=2_400_000, chan_seed=3,
                         reboots=[(1_000_000, 2), (1_500_000, 1)],
                         inject=[(700_000, 2, "replay"), (701_000, 1, "forjado"), (1_900_000, 1, "replay"),
                                 (1_950_000, 2, "forjado")]), "reinicio")
    assert base["stats"][1]["rejeitados"] + base["stats"][2]["rejeitados"] >= 2


@precisa_cc
def test_jammer_exercita_validacao_e_rollback(shim):
    wins = [(t0, t0 + 40_000) for t in range(1) for t0 in range(300_000, 3_600_000, 300_000)]
    _confere(dict(cfg=FAST, gain=lambda t: -140.0, T=3_600_000, chan_seed=4, windows=wins), "jammer")


@precisa_cc
def test_rollbacks_repetidos_disparam_alarme(shim):
    """Toda troca falha na validação (só o modo base passa): rollbacks, alarme de jamming e congelamento."""
    cfg = Config(cooldown_up=10.0, n_up=3, neg_backoff0=5.0, neg_backoff_max=20.0, cooldown_back=10.0)
    base_id = H.mode_id_of(H.BASE_MODE)
    base = _confere(dict(cfg=cfg, gain=lambda t: -138.0, T=3_600_000, chan_seed=7,
                         drop_fn=lambda t, m: m != base_id and t > 300_000), "alarme")
    assert base["stats"][1]["rollbacks"] >= 3 and base["stats"][1]["alarmes"] >= 1


@precisa_cc
def test_comparacao_enxerga_diferenca_de_parametro(shim):
    """Sensibilidade do teste: com um parâmetro diferente no lado C, os rastros têm de divergir."""
    sc = dict(cfg=FAST, gain=lambda t: -138.0, T=900_000, chan_seed=1)
    a = H.rodar(sc, ("py", "py"))
    outro = dict(sc, cfg=Config(**{**FAST.__dict__, "margin_up": 30.0}))
    b = H.rodar(outro, ("py", "py"))
    assert H.first_diff(a, b) is not None


@precisa_cc
@pytest.mark.parametrize("seed", range(int(os.environ.get("LEGUA_EQUIV_SEEDS", "6"))))
def test_cenarios_aleatorios(shim, seed):
    sc = H.cenario_aleatorio(seed)
    _confere(sc, f"semente {seed} ({sc['variante']})")


@precisa_cc
def test_perfis_nomeados_iguais_no_c_e_no_python(shim):
    import ctypes
    from simsuite.protocol.perfis import PERFIS, PERFIL_C
    L = H.lib()
    L.shim_profile_get.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(ctypes.c_double)]
    for nome, cfg in PERFIS.items():
        for k, v in H.c_params(cfg).items():
            out = ctypes.c_double()
            assert L.shim_profile_get(PERFIL_C[nome], k.encode(), ctypes.byref(out)) == 0, k
            assert abs(out.value - float(v)) < 1e-4, (nome, k, out.value, v)


@precisa_cc
@pytest.mark.parametrize("horas,reboot", [(4, None), (4, 2), (4, 1)])
def test_ausencia_longa_ressincroniza(shim, horas, reboot):
    """Enlace perdido por horas (com ou sem reinício de um nó ao voltar): os dois voltam a DATA no mesmo modo em
    menos de 10 min, e os quatro pares Py/C continuam idênticos."""
    h0, h1 = 1_200_000, 1_200_000 + horas * 3600 * 1000
    sc = dict(cfg=FAST, gain=lambda t: -200.0 if h0 <= t < h1 else -138.0, T=h1 + 1_800_000, chan_seed=9,
              reboots=[(h1 + 1000, reboot)] if reboot else [])
    base = _confere(sc, f"ausencia{horas}h_{reboot}")
    last, t_ok = {}, None
    for t, nid, _call, _acts, snap in base["trace"]:
        last[nid] = snap
        if t >= h1 and len(last) == 2 and last[1][0] == 1 and last[2][0] == 1 and last[1][1] == last[2][1]:
            t_ok = t - h1
            break
    assert t_ok is not None and t_ok < 600_000, f"reacordo em {t_ok} ms"


@precisa_cc
def test_falhas_de_mic_congelam_a_negociacao(shim):
    """docs/07 §6: n quadros com MIC inválido na janela disparam o alarme; durante o congelamento ninguém troca de
    modo (A não propõe e B vota "não"), e o modo atual é mantido. Os quatro pares Py/C seguem idênticos."""
    from dataclasses import replace
    hold = 900.0
    cfg = replace(FAST, mic_fail_n=3, mic_fail_window=300.0, mic_fail_hold=hold)
    # enlace fraco até 600 s (fica no base) e bom depois; forjados chegam a B (nó 2, que vota) em 300 s
    inj = [(t, 2, "forjado") for t in (300_000, 301_000, 302_000)]

    def g(t):
        return -152.0 if t < 600_000 else -136.0
    base = _confere(dict(cfg=cfg, gain=g, T=2_400_000, chan_seed=11, inject=inj), "mic")
    assert base["stats"][2]["alarmes_mic"] == 1 and base["stats"][1]["alarmes_mic"] == 0
    t_al = next(t for t, nid, _c, acts, _s in base["trace"] if nid == 2 and ("alarme_mic",) in acts)
    trocas = [t for t, _n, _c, acts, _s in base["trace"] for a in acts if a[0] == "modo" and a[3] == 1]
    assert trocas, "o enlace bom deveria acelerar depois do congelamento"
    assert not [t for t in trocas if t_al <= t < t_al + hold * 1000], "trocou de modo durante o congelamento"
    assert base["stats"][1]["neg_fail"] >= 1, "A deveria ter proposto e recebido 'não' durante o congelamento"
    # sem o limite, o mesmo cenário acelera dentro dessa janela
    sem = H.rodar(dict(cfg=replace(cfg, mic_fail_n=0), gain=g, T=2_400_000, chan_seed=11, inject=inj),
                  ("py", "py"))
    assert sem["stats"][2]["alarmes_mic"] == 0
    assert [t for t, _n, _c, acts, _s in sem["trace"] for a in acts
            if a[0] == "modo" and a[3] == 1 and t_al <= t < t_al + hold * 1000]


def _chaves(base, nid):
    """Sequência de estados de chave (key_id, anterior aceita) do nó, tirada dos logs."""
    return [a[1:] for _t, n, _c, acts, _s in base["trace"] if n == nid for a in acts if a[0] == "chave"]


@precisa_cc
def test_rotacao_de_chave_completa_e_sobrevive_a_reinicio(shim):
    """docs/07 §6.2: A roda para a chave 1 (ainda aceita a 0); B segue no primeiro quadro autenticado com a 1 e
    aposenta a 0; A aposenta a 0 ao ouvir B na 1. O estado vai no registro de NVM: um reinício no meio da rotação
    não volta à chave antiga. Nenhum quadro legítimo é recusado."""
    sc = dict(cfg=FAST, gain=lambda t: -140.0, T=1_800_000, chan_seed=21,
              rotations=[(400_000, 1)], reboots=[(400_500, 1)],
              inject=[(380_000, 2, "chave_antiga"), (1_500_000, 2, "chave_antiga")])
    base = _confere(sc, "rotacao")
    assert _chaves(base, 1) == [(1, 1), (1, 0)]
    assert _chaves(base, 2) == [(1, 0)]
    assert base["final"][1][4] == 1 and base["final"][2][4] == 1          # os dois na chave 1, sem a anterior
    # antes da rotação a "chave anterior" de B é a 3, que ele não aceita; depois, a 0 já foi aposentada
    inj = [acts for _t, n, c, acts, _s in base["trace"] if c == "inject_chave_antiga"]
    assert len(inj) == 2 and all(("rej",) in a for a in inj)
    assert base["stats"][1]["rejeitados"] == 0 and base["stats"][2]["rejeitados"] == 2


@precisa_cc
def test_rotacao_sem_chave_no_par_e_recusada_ate_carregar(shim):
    """B só tem a chave 0 quando A roda: B recusa os quadros com a 1 (falhas de MIC, alarme) e A segue aceitando a
    0. Quando a chave 1 chega a B, ele segue o par e a rotação termina. Uma segunda rotação antes da confirmação é
    recusada."""
    from dataclasses import replace
    cfg = replace(FAST, mic_fail_n=3)
    sc = dict(cfg=cfg, gain=lambda t: -140.0, T=2_400_000, chan_seed=22,
              keys=[(0, 2, 0x01), (1_200_000, 2, 0x0F)], rotations=[(400_000, 1), (600_000, 1)])
    base = _confere(sc, "rotacao_sem_chave")
    recusada = [t for t, n, c, acts, _s in base["trace"] if c == "rotate" and ("recusada",) in acts]
    assert recusada == [600_000]
    assert base["stats"][2]["rejeitados"] >= 3 and base["stats"][2]["alarmes_mic"] >= 1
    t_fim = [t for t, n, _c, acts, _s in base["trace"] if n == 1 for a in acts if a[:1] == ("chave",) and a[2] == 0]
    assert t_fim and t_fim[0] > 1_200_000, "A só aposenta a chave 0 depois que B recebe a 1"
    assert base["final"][1][4] == 1 and base["final"][2][4] == 1


@precisa_cc
@pytest.mark.parametrize("caps", [(28.0, 14.0), (14.0, 28.0)])
@pytest.mark.parametrize("ganho,acelera", [(-128.0, True), (-136.0, False)])
def test_tetos_diferentes_o_par_decide_pelo_pior_sentido(shim, caps, ganho, acelera):
    """docs/07 §4: HELLO, PROPOSE e VOTE levam o teto de TX do nó. Com tetos diferentes, cada ponta calcula a margem
    do pior sentido (o próprio TX no ganho eu->par, o TX do par no ganho par->eu) e mede o ganho com a potência real
    do par: ninguém propõe o que o par vai recusar (sem 'não'), nenhuma troca é desfeita, os dois ficam no mesmo modo."""
    base = _confere(dict(cfg=FAST, gain=lambda t: ganho, T=1_800_000, chan_seed=1, cap=caps), f"tetos{caps}{ganho}")
    for nid in (1, 2):
        s = base["stats"][nid]
        assert s["neg_fail"] == 0 and s["rollbacks"] == 0, (nid, s)
        assert (s["trocas"] >= 1) == acelera, (nid, s)
    assert base["final"][1][0] == base["final"][2][0]


@precisa_cc
def test_ressincroniza_o_contador_do_par_perdido(shim):
    """docs/07 §6.3: B volta com o piso do par muito atrás do contador de A (mais de 32767 quadros). Todo quadro de A
    é recusado em B (contador "antigo"); depois de resync_n recusas B pede RESYNC e A responde com o contador completo,
    autenticado pelo nonce. Sem o recurso, o enlace A->B nunca volta. Os quatro pares Py/C seguem idênticos."""
    from dataclasses import replace
    nvm = ({"ctr_block": 3000}, None)                     # A transmite a partir de ~192000; B acha que o par está em 0
    sc = dict(cfg=FAST, gain=lambda t: -138.0, T=1_800_000, chan_seed=3, nvm=nvm)
    base = _confere(sc, "resync")
    b, a = base["stats"][2], base["stats"][1]
    assert b["resync_pedidos"] >= 1 and b["resync_ok"] == 1, b
    assert a["resync_pedidos"] == 0 and a["tx_ctrl"] > 0
    assert b["entregues"] > 0 and b["trocas"] + a["trocas"] >= 1, "o enlace deveria voltar e acelerar"
    sem = H.rodar(dict(sc, cfg=replace(FAST, resync_n=0)), ("py", "py"))
    assert sem["stats"][2]["entregues"] == 0 and sem["stats"][2]["resync_pedidos"] == 0, "sem RESYNC o enlace não volta"


@precisa_cc
def test_resync_recusa_resposta_forjada_antiga_e_sem_pedido(shim):
    """Uma resposta sem pedido pendente não tem nonce para conferir: é recusada nos dois núcleos e não muda o piso do par."""
    from simsuite.protocol import wire
    cfg = FAST
    for kind in ("py", "c"):
        a = H.PyAdapter(2, 1, 5, cfg) if kind == "py" else H.CAdapter(2, 1, 5, cfg, handle=0)
        a.on_timer(0)
        # resposta sem pedido pendente (nonce arbitrário): recusada, contada
        raw = wire.pack(wire.T_RESYNC_RSP, 1, 2, 70000, (70000).to_bytes(4, "big"), extra=(1234).to_bytes(4, "big"))
        a.on_rx(raw, H.mode_id_of(H.BASE_MODE), -900, 100, 1000)
        assert a.stats()["resync_ok"] == 0 and a.stats()["rejeitados"] == 1, kind


def test_replay_em_massa_provoca_resync_mas_nao_prejudica_o_enlace():
    """docs/07 §6.3, limite conhecido: quadros antigos repetidos pelo atacante contam como recusas. Abaixo de ~1 repetição
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
