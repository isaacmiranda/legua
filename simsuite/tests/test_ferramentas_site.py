"""Ferramentas novas do site (citação, calculadoras, decodificador de pacotes, rastros, medições, cobertura...): lógica pura
em Node e, onde cabe, paridade com a referência Python. Pula sem node."""
import json
import os
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(RAIZ, "site")
precisa_node = pytest.mark.skipif(not shutil.which("node"), reason="sem node")


def _node(js, *args, entrada=None):
    r = subprocess.run(["node", "-e", js, SITE, *args], capture_output=True, text=True, timeout=120, input=entrada)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@precisa_node
def test_citar_bloco_comando_json_e_csv():
    o = _node(r"""
    const C = require(process.argv[1] + '/citar.js'), out = {};
    const meta = { gerado_em: '2026-11-19', commit: 'abc1234', versao_nucleo: '0.1.1', repositorio: 'https://github.com/isaacmiranda/legua' };
    const b = C.bloco({ aba: 'Campo fixo', abaId: 'campo', escala: 'full', cenarios: ['F'], meta, sementes: [1, 2, 3], url: 'https://x/#campo/full' });
    out.texto = b.texto; out.bib = b.bibtex; out.cmd = b.comando;
    out.json = JSON.parse(C.jsonDaAba({ aba: 'Campo fixo', escala: 'quick', cenarios: ['F', 'Z'], meta }, { F: { a: 1 }, G: { b: 2 } }));
    const tab = { querySelectorAll: () => [{ closest: () => ({ querySelector: () => ({ textContent: ' Meu  título ' }) }), querySelectorAll: () => [
      { children: [{ textContent: 'a' }, { textContent: 'b;c' }] }, { children: [{ textContent: '1' }, { textContent: '2' }] }] }] };
    out.csv = C.tabelasCsv(tab, 'proc')[0].csv; out.slug = C.slug('Verificação formal (P1)');
    console.log(JSON.stringify(out));
    """)
    assert "núcleo 0.1.1" in o["texto"] and "longa (full)" in o["texto"] and "commit abc1234" in o["texto"] and "sem medição em hardware" in o["texto"]
    assert "Sementes: 1, 2, 3" in o["texto"] and o["bib"].startswith("@misc{legua2026campo,") and "Miranda, Isaac" in o["bib"]
    assert "--escala full" in o["cmd"] and "--so F" in o["cmd"] and "build_site.py" in o["cmd"]
    assert o["json"]["dados"] == {"F": {"a": 1}} and o["json"]["procedencia"]["commit"] == "abc1234" and "aviso" in o["json"]["procedencia"]
    assert "# proc" in o["csv"] and '"b;c"' in o["csv"] and "# tabela: Meu título" in o["csv"] and o["slug"] == "verificacao-formal-p1"


def test_citation_cff_coerente_com_a_versao_do_nucleo():
    cff = open(os.path.join(RAIZ, "CITATION.cff"), encoding="utf-8").read()
    versao = open(os.path.join(RAIZ, "core", "VERSION")).read().strip()
    assert f'version: "{versao}"' in cff and "Apache-2.0" in cff and "medição em hardware" in cff and "@" not in cff   # sem e-mail


@precisa_node
def test_calculadoras_paridade_com_o_python():
    from simsuite.analysis import estimator as E
    from simsuite.core import radio, regulatory as R
    K = E.constantes()
    casos = [(sf, bw, pl, cr, pre, crc, ex) for sf in (5, 6, 7, 9, 12) for bw in (125, 250, 500) for pl in (1, 14, 24, 51) for cr in (1, 4)
             for pre in (8, 12) for crc in (True, False) for ex in (True, False)]
    js = r"""
    const C = require(process.argv[1] + '/calculadoras.js'), E = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    const out = { toa: E.casos.map(c => C.toaS(c[0], c[1], c[2], c[3], c[4], c[5], c[6])),
      sens: [7, 10, 12].map(sf => C.sensibilidadeDbm(E.K, sf, 125, 1)), itx: [-9, 14, 21, 28].map(p => C.iTxMa(E.K, p)),
      plano: [125, 250, 500].map(bw => C.planoCanais(E.K.regulatorio.faixas_hz, bw).length),
      salto: C.regraSalto(E.K.regulatorio, 125, 40, 2.15), salto2: C.regraSalto(E.K.regulatorio, 125, 20, 8.15), digital: C.regraSalto(E.K.regulatorio, 500, 20, 2.15),
      ciclo: C.cicloUtil(0.4, 36), minimo: C.intervaloMinimoS(0.4, 0.01), bat: C.bateria(E.K, { capMah: 1000, pDbm: 14, toaS: 0.4, pph: 60, rxPorPacoteS: 1, sonoUa: 20 }) };
    console.log(JSON.stringify(out));
    """
    o = _node(js, entrada=json.dumps({"casos": casos, "K": K}))
    for c, t in zip(casos, o["toa"]):
        assert t == pytest.approx(radio.toa_s(c[0], c[1], c[2], c[3], c[4], c[5], c[6]), rel=1e-12), c
    for sf, s in zip((7, 10, 12), o["sens"]):
        assert s == pytest.approx(radio.noise_dbm(125) + radio.SNR_THR[sf] - radio.CR_GAIN_DB[1], abs=1e-9)
    assert o["itx"][0] == pytest.approx(18.0) and o["itx"][1] == pytest.approx(45.0) and o["itx"][3] == pytest.approx(950.0)
    assert o["plano"] == [len(R.channel_plan(R.BR2026, bw)) for bw in (125, 250, 500)]
    assert o["salto"]["ok"] and o["salto"]["tetoDbm"] == pytest.approx(R.BR2026.hop_cap_dbm(40, 2.15, 125), abs=1e-9)
    assert not o["salto2"]["ok"] and o["salto2"]["tetoDbm"] == pytest.approx(R.BR2026.hop_cap_dbm(20, 8.15, 125), abs=1e-9)
    assert o["digital"]["classe"]["canais_min"] == 17 and o["ciclo"] == pytest.approx(0.004) and o["minimo"] == pytest.approx(40.0)
    b = o["bat"]
    assert b["ativoTx"] == pytest.approx(0.4 * 60 / 3600) and 90 < b["dias"] < 120 and b["energiaPacoteMj"] == pytest.approx(45.0 * 3.3 * 0.4)
