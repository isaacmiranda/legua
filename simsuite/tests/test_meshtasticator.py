"""Validação sim x sim com o código original do Meshtasticator (se o clone existir): simsuite/analysis/meshtasticator.py."""
import pytest
from simsuite.analysis import meshtasticator as M

pytestmark = pytest.mark.skipif(M.carregar() is None, reason="clone do Meshtasticator ausente")


def test_tempo_no_ar_igual_exceto_ldro():
    phy, cfg, _ = M.carregar()
    r = M.cmp_airtime(phy, cfg)
    assert r["presets_diferentes"] in ([], ["VERY_LONG_SLOW"])


def test_regra_de_captura_de_6_db_igual():
    phy, cfg, _ = M.carregar()
    assert M.cmp_captura_regra(phy, cfg)["iguais"]


def test_aloha_mesh_proximo_do_analitico():
    phy, cfg, _ = M.carregar()
    r = M.cmp_aloha(phy, cfg, True)
    for p in r["pontos"]:
        assert p["pdr_meshtastic"] == pytest.approx(p["pdr_analitico"], abs=0.03)
