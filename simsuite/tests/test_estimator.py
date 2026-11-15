"""Estimador analítico: propriedades físicas e paridade entre a referência Python e o site/estimator.js (node)."""
import json
import os
import shutil
import subprocess
import pytest
from simsuite.analysis import estimator as E

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETUPS = [
    dict(env="urbano_denso", d_km=1.0, sf=10, bw=125, cr=1, p_dbm=28.0, fhss=True),
    dict(env="urbano_residencial", d_km=3.0, sf=7, bw=125, cr=1, p_dbm=14.0, fhss=True, retries=2, offset_db=-6.0),
    dict(env="rural_aberto", d_km=20.0, sf=12, bw=500, cr=1, p_dbm=22.0, fhss=False, interval_s=30.0, load=2.0),
    dict(env="rural_serra", d_km=6.0, sf=9, bw=125, cr=4, p_dbm=28.0, fhss=True),
]


def _py(o):
    return E.estimate(o["env"], o["d_km"], o["sf"], o["bw"], o["cr"], o["p_dbm"], o["fhss"],
                      retries=o.get("retries", 3), interval_s=o.get("interval_s", 60.0),
                      offset_db=o.get("offset_db", 0.0), load=o.get("load", 1.0))


def test_mais_distancia_reduz_entrega_e_modo_robusto_alcanca_mais():
    base = dict(env="urbano_denso", sf=10, bw=125, cr=1, p_dbm=28.0, fhss=True)
    c = [E.estimate_one(base["env"], d, 10, 125, 1, 28.0, True)["confirmado"] for d in (0.3, 1.0, 2.0, 3.0)]
    assert c == sorted(c, reverse=True) and c[0] > 0.99 and c[-1] < 0.5
    r7 = E.range_km("urbano_denso", 7, 125, 1, 28.0, True)
    r10 = E.range_km("urbano_denso", 10, 125, 1, 28.0, True)
    assert r10 > r7


def test_energia_cresce_com_potencia_e_toa_bate_com_a_suite():
    from simsuite.core.radio import toa_s
    e14 = E.estimate("rural_aberto", 1.0, 10, 125, 1, 14.0, True)
    e28 = E.estimate("rural_aberto", 1.0, 10, 125, 1, 28.0, True)
    assert e28["cenarios"][1]["energia_mj_pacote"] > e14["cenarios"][1]["energia_mj_pacote"]
    assert abs(e28["toa_dados_ms"] - 1000 * toa_s(10, 125, 24, 1)) < 1e-9
    assert e28["dwell_ok"] and not E.estimate("rural_aberto", 1.0, 11, 125, 1, 28.0, True)["dwell_ok"]


def test_ranking_de_modos_respeita_o_alvo():
    good, rows = E.rank_modes("urbano_residencial", 2.0, 28.0, target=0.95)
    assert good and all(r["confirmado"] >= 0.95 for r in good)
    assert [r["energia_mj_entregue"] for r in good] == sorted(r["energia_mj_entregue"] for r in good)


@pytest.mark.skipif(not shutil.which("node"), reason="sem node")
def test_paridade_python_javascript():
    js = r"""
    const est = require(process.argv[2]).make(JSON.parse(require('fs').readFileSync(0, 'utf8')).K);
    const input = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
    const out = input.setups.map(o => ({e: est.estimate(o), r: est.rangeKm(o, 0.9, 0.0),
      k: est.rankModes(o, 0.95, 0.0).good.map(g => [g.sf, g.bw, g.cr])}));
    console.log(JSON.stringify(out));
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sj, sp = os.path.join(td, "run.js"), os.path.join(td, "in.json")
        open(sj, "w").write(js)
        json.dump({"setups": SETUPS}, open(sp, "w"))
        r = subprocess.run(["node", sj, os.path.join(RAIZ, "site", "estimator.js"), sp],
                           input=json.dumps({"K": E.constantes()}), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    saida = json.loads(r.stdout)
    for o, s in zip(SETUPS, saida):
        py = _py(o)
        for chave in ("toa_dados_ms", "toa_ack_ms", "sens_dbm", "rx_tipico_dbm", "margem_db", "duty_pct", "energia_dia_j"):
            assert s["e"][chave] == pytest.approx(py[chave], rel=1e-9, abs=1e-9), chave
        for a, b in zip(py["cenarios"], s["e"]["cenarios"]):
            for k in ("entregue", "confirmado", "tentativas", "energia_mj_pacote"):
                assert b[k] == pytest.approx(a[k], rel=1e-9, abs=1e-12), k
        pr = E.range_km(o["env"], o["sf"], o["bw"], o["cr"], o["p_dbm"], o["fhss"], 0.9, 0.0,
                        retries=o.get("retries", 3), offset_db=o.get("offset_db", 0.0), load=o.get("load", 1.0))
        assert (s["r"] is None) == (pr is None)
        if pr is not None:
            assert s["r"] == pytest.approx(pr, rel=1e-6)
        good, _ = E.rank_modes(o["env"], o["d_km"], o["p_dbm"], 0.95, 0.0, retries=o.get("retries", 3),
                               offset_db=o.get("offset_db", 0.0), load=o.get("load", 1.0))
        assert [[g["sf"], g["bw"], g["cr"]] for g in good] == s["k"]
