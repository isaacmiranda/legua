"""Validação sim x sim (regras do LoRaSim portadas à mão): ver simsuite/analysis/lorasim.py."""
import pytest
from simsuite.analysis import lorasim as L
from simsuite.core.radio import toa_s


def test_tempo_no_ar_igual_ao_lorasim_exceto_ldro_sf12_250():
    r = L.cmp_airtime()
    assert r["combinacoes_sf_bw_diferentes"] == [(12, 250)]
    assert abs(1000 * toa_s(7, 125, 20, 1) - L.lorasim_airtime(7, 1, 20, 125)) < 1e-6


def test_aloha_nos_dois_simuladores_proximo_do_analitico():
    N, mean, T = 40, 60.0, 1800.0
    s, o = L.run_lorasim(N, mean * 1000, T * 1000, 7, 125, 1, 20, lambda i: -76.0, 5)
    pdr_l = sum(o) / sum(s)
    s2, o2 = L.run_ours(N, mean, T, 7, 125, 1, 20, lambda i: -90.0, 6)
    pdr_o = sum(o2) / sum(s2)
    esperado = L.aloha(N, mean, toa_s(7, 125, 20, 1))
    assert pdr_o == pytest.approx(esperado, abs=0.03)
    assert pdr_l == pytest.approx(esperado, abs=0.04)


def test_captura_o_forte_sobrevive():
    N = 20
    s, o = L.run_ours(N, 20.0, 1200.0, 7, 125, 1, 20, lambda i: -80.0 if i % 2 == 0 else -90.0, 7)
    fortes = sum(o[i] for i in range(N) if i % 2 == 0) / sum(s[i] for i in range(N) if i % 2 == 0)
    fracos = sum(o[i] for i in range(N) if i % 2) / sum(s[i] for i in range(N) if i % 2)
    assert fortes > fracos


def test_lorasim_original_executado_proximo_do_daqui():
    """O loraDir.py original (sintaxe convertida) deve dar PDR de ordem igual à do simulador daqui na mesma geometria."""
    from simsuite.analysis import lorasim_original as LO
    if LO.disponivel() is None:
        pytest.skip("LoRaSim original ou simpy ausentes")
    r = LO.rodar(100, 600000, 1800000, 1)
    assert r["enviados"] > 0 and r["recebidos"] <= r["enviados"]
    s, o = L.run_ours(100, 600.0, 1800.0, 12, 125, 4, 20, lambda i: r["rssi"][i] - 14.0, 2)
    assert abs(r["recebidos"] / r["enviados"] - sum(o) / sum(s)) < 0.1
