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
