"""Gerador de dados do site (tools/build_site.py): NaN vira null e a saída é JSON estrito."""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "tools"))
import build_site  # noqa: E402


def test_build_site_sanitiza_e_gera_js(tmp_path):
    res = tmp_path / "res"
    res.mkdir()
    (res / "F.json").write_text(json.dumps({"cenario": "F", "escala": "quick", "resultado": {"x": {"efeito_desenho": float("nan"), "pdr": 0.123456789}}}))
    (res / "B9.json").write_text(json.dumps({"cenario": "B9", "escala": "quick", "resultado": {"linhas": [1] * 200, "falhas_com_ldro_auto": [], "nota": "n"}}))
    (res / "M.json").write_text(json.dumps({"cenario": "M", "erro": "boom"}))
    out = tmp_path / "site" / "data.json"
    assert build_site.main(["--resultados", str(res), "--saida", str(out)]) == 0
    dado = json.loads(out.read_text())                       # JSON estrito: NaN seria erro aqui
    assert dado["dados"]["F"]["x"]["efeito_desenho"] is None
    assert dado["dados"]["F"]["x"]["pdr"] == 0.12346
    assert "linhas" not in dado["dados"]["B9"]
    assert "M (erro)" in dado["meta"]["faltando"]
    js = (tmp_path / "site" / "data.js").read_text()
    assert js.startswith("window.LEGUA_DATA=") and js.rstrip().endswith(";")
