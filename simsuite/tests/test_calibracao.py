"""Importador da calibração da bancada (simsuite/analysis/calibracao.py, docs/09 §4)."""
import copy
import json
import os
import subprocess
import sys

import pytest

from simsuite.analysis import calibracao as C
from simsuite.core import channel_static, radio
from simsuite.protocol.modes import table

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CAL = {"versao": 1, "id": "teste-sintetico", "data": "2027-01-15", "hardware": "sintético", "firmware": "core-v0.1.0",
       "constantes": {
           "snr_thr": {"valor": {"7": -6.5, "12": -19.0}, "incerteza": 0.3},
           "per_offset_db": {"valor": 3.5, "incerteza": 0.2},
           "per_slope_db": {"valor": 0.8, "incerteza": 0.1},
           "cr_gain_db": {"valor": {"4": 0.5}, "incerteza": 0.2},
           "nf_db": {"valor": 7.0, "incerteza": 0.3},
           "i_tx_ma": {"valor": [[-9, 20.0], [14, 50.0], [28, 900.0]], "incerteza": 10.0},
           "canal": {"valor": {"rural_aberto": {"pl1km": 118.0, "n": 3.5}}, "incerteza": 2.0}}}


def _sens_base():
    ms, _b, _r = table()
    return [round(m.sens(), 3) for m in ms]


def test_aplicar_muda_sensibilidade_e_restaura():
    antes = (_sens_base(), radio.NF_DB, radio.PER_OFFSET_DB, dict(radio.SNR_THR), dict(radio.CR_GAIN_DB),
             list(radio._I_TX_TABLE), dict(channel_static.ENVS["rural_aberto"]))
    with C.aplicar(CAL):
        dentro = _sens_base()
        assert dentro != antes[0], "a sensibilidade dos modos deveria mudar"
        assert radio.NF_DB == 7.0 and radio.SNR_THR[7] == -6.5 and radio.SNR_THR[8] == antes[3][8]   # só o medido muda
        assert radio.i_tx_ma(14) == 50.0 and channel_static.ENVS["rural_aberto"]["pl1km"] == 118.0
        assert channel_static.ENVS["rural_aberto"]["sigma_static"] == antes[6]["sigma_static"]
        from simsuite.analysis import estimator
        assert estimator.NF_DB == 7.0 and estimator.PER_OFFSET_DB == 3.5     # importados por valor também
    depois = (_sens_base(), radio.NF_DB, radio.PER_OFFSET_DB, dict(radio.SNR_THR), dict(radio.CR_GAIN_DB),
              list(radio._I_TX_TABLE), dict(channel_static.ENVS["rural_aberto"]))
    assert depois == antes


def test_sensibilidade_acompanha_a_conta_com_os_valores_novos():
    with C.aplicar(CAL):
        ms, _b, _r = table()
        m = next(x for x in ms if x.sf == 12 and x.cr == 1)
        esperado = (-174.0 + 10 * __import__("math").log10(m.bw * 1e3) + 7.0) + (-19.0) + 3.5 - 0.0
        assert abs(m.sens() - esperado) < 1e-9


@pytest.mark.parametrize("mut", [
    lambda c: c.update(versao=2),
    lambda c: c.update(id=".."),
    lambda c: c["constantes"]["snr_thr"]["valor"].update({"²": -20.0}),
    lambda c: c.update(latitude_deg=-3.7),
    lambda c: c.update(id="../x"),
    lambda c: c["constantes"].update(nf_db={"valor": 99.0, "incerteza": 1}),
    lambda c: c["constantes"].update(nf_db={"valor": 6.0}),
    lambda c: c["constantes"].update(desconhecida={"valor": 1, "incerteza": 1}),
    lambda c: c["constantes"]["snr_thr"]["valor"].update({"13": -20.0}),
    lambda c: c["constantes"]["i_tx_ma"].update(valor=[[14, 50.0], [0, 24.0]]),
    lambda c: c["constantes"]["canal"]["valor"].update(inexistente={"n": 3.0}),
    lambda c: c["constantes"]["canal"]["valor"]["rural_aberto"].update(lat=1.0),
    lambda c: c.update(gnss={"lat": -3.7, "lon": -38.5}),
    lambda c: c.update(constantes={}),
])
def test_validacao_recusa(mut):
    cal = copy.deepcopy(CAL)
    mut(cal)
    with pytest.raises(C.CalibracaoInvalida):
        C.validar(cal)


def test_descrever_lista_atual_e_novo():
    linhas = {n: (a, v, u) for n, a, v, u in C.descrever(CAL)}
    assert linhas["nf_db"] == (6.0, 7.0, 0.3)
    assert linhas["snr_thr[7]"][:2] == (-7.5, -6.5)
    assert "canal.rural_aberto.pl1km" in linhas and linhas["canal.rural_aberto.pl1km"][0] == 112.0


def test_cli_valida_e_a_suite_rotula_o_resultado(tmp_path):
    arq = tmp_path / "cal.json"
    arq.write_text(json.dumps(CAL))
    env = dict(os.environ, PYTHONPATH=RAIZ)
    r = subprocess.run([sys.executable, "-m", "simsuite.analysis.calibracao", str(arq)], capture_output=True, text=True,
                       env=env)
    assert r.returncode == 0 and "teste-sintetico" in r.stdout and "nf_db" in r.stdout, r.stdout + r.stderr
    ruim = tmp_path / "ruim.json"
    ruim.write_text(json.dumps(dict(CAL, versao=9)))
    r = subprocess.run([sys.executable, "-m", "simsuite.analysis.calibracao", str(ruim)], capture_output=True, text=True,
                       env=env)
    assert r.returncode == 1 and "inválida" in r.stdout
    saida = tmp_path / "saida"
    r = subprocess.run([sys.executable, "-m", "simsuite.run_suite", "--escala", "quick", "--so", "modos", "amostras",
                        "--procs", "1", "--calibracao", str(arq), "--saida", str(saida)],
                       capture_output=True, text=True, env=env, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.load(open(saida / "modos.json"))
    assert d["calibracao"] == "teste-sintetico"
    base = tmp_path / "base"                                          # a mesma rodada sem calibração (não depende de results/ versionado)
    r = subprocess.run([sys.executable, "-m", "simsuite.run_suite", "--escala", "quick", "--so", "modos", "--procs", "1", "--saida", str(base)],
                       capture_output=True, text=True, env=env, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    sem = json.load(open(base / "modos.json"))
    assert "calibracao" not in sem
    assert d["resultado"]["modos"] != sem["resultado"]["modos"], "o orçamento dos modos deveria mudar com a calibração"


def test_arquivo_modelo_valida_e_nao_muda_nada():
    cal, cs = C.carregar(os.path.join(RAIZ, "docs", "calibracao.exemplo.json"))
    antes = _sens_base()
    with C.aplicar(cal):
        assert _sens_base() == antes
    assert all(a == v for _n, a, v, _u in C.descrever(cal, cs))


def test_variantes_deslocam_no_sentido_que_piora_e_respeitam_as_faixas():
    cal = copy.deepcopy(CAL)
    for ent in cal["constantes"].values():
        ent["incerteza"] = 0.5
    pes, oti = C.variantes(cal)
    k = cal["constantes"]
    assert pes["constantes"]["nf_db"]["valor"] == pytest.approx(k["nf_db"]["valor"] + 0.5) and oti["constantes"]["nf_db"]["valor"] == pytest.approx(k["nf_db"]["valor"] - 0.5)
    for sf, v in k["snr_thr"]["valor"].items():                          # limiar de SNR maior = enlace pior
        assert pes["constantes"]["snr_thr"]["valor"][sf] == pytest.approx(v + 0.5) and oti["constantes"]["snr_thr"]["valor"][sf] == pytest.approx(v - 0.5)
    for amb, c in k["canal"]["valor"].items():                           # perda a 1 km e expoente maiores = pior; sigma não decide o enlace
        assert pes["constantes"]["canal"]["valor"][amb]["pl1km"] == pytest.approx(c["pl1km"] + 0.5) and pes["constantes"]["canal"]["valor"][amb].get("sigma_static") == c.get("sigma_static")
        assert oti["constantes"]["canal"]["valor"][amb]["n"] == pytest.approx(c["n"] - 0.5)
    assert pes["constantes"]["per_slope_db"] == k["per_slope_db"] and pes["id"].endswith("-pessimista") and oti["id"].endswith("-otimista")
    C.validar(pes), C.validar(oti)                                       # as variantes continuam válidas
    grande = copy.deepcopy(cal)
    for ent in grande["constantes"].values():
        ent["incerteza"] = 50.0                                          # incerteza absurda: os valores são limitados às faixas válidas
    p2, o2 = C.variantes(grande)
    C.validar(p2), C.validar(o2)


def test_propagar_incerteza_gera_faixas_e_resumo(tmp_path):
    sys.path.insert(0, os.path.join(RAIZ, "tools"))
    import propagar_incerteza as P
    est, mud = P.faixas({"a": {"x": 1.0, "y": [2.0, 5.0]}, "z": "t"}, {"a": {"x": 1.5, "y": [2.0, 4.0]}, "z": "t"}, {"a": {"x": 0.5, "y": [2.0, 6.0]}, "z": "t"})
    assert est["a"]["x"] == {"nom": 1.0, "min": 0.5, "max": 1.5} and est["a"]["y"][0] == 2.0 and est["a"]["y"][1] == {"nom": 5.0, "min": 4.0, "max": 6.0} and est["z"] == "t"
    assert [m[0] for m in mud] == ["/a/x", "/a/y[1]"]
    cal = copy.deepcopy(CAL)
    for ent in cal["constantes"].values():
        ent["incerteza"] = 0.5
    arq = tmp_path / "cal.json"
    arq.write_text(json.dumps(cal))
    saida = tmp_path / "inc"
    assert P.main([str(arq), "--escala", "quick", "--so", "modos", "--saida", str(saida)]) == 0
    resumo = (saida / "resumo.md").read_text()
    assert "Não é intervalo de confiança" in resumo and "/modos" in resumo
    f = json.load(open(saida / "faixas" / "modos.json"))
    assert "não é intervalo de confiança" in f["aviso"]
    sem = tmp_path / "sem.json"
    zero = copy.deepcopy(CAL)
    for ent in zero["constantes"].values():
        ent["incerteza"] = 0.0
    sem.write_text(json.dumps(zero))                                       # incerteza zero: recusa, em vez de gerar faixas vazias
    with pytest.raises(SystemExit):
        P.main([str(sem), "--escala", "quick", "--so", "modos", "--saida", str(tmp_path / "x")])
