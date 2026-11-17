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
