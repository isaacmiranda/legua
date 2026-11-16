"""Explicações do site (site/explica.js): cada explicação aponta para um diagrama que existe, todo diagrama é XML válido
e o texto não está vazio. Roda com node puro (sem DOM); pula sem node."""
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

JS = r"""
const fs = require("fs"), vm = require("vm");
const ctx = { window: {}, document: {} }; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const L = ctx.window.LeguaExplica;
const dg = {}; for (const k of Object.keys(L.diagramas)) dg[k] = L.diagramas[k]();
console.log(JSON.stringify({ dg, ex: L.explicacoes.map(e => ({ re: e.re.source, d: e.d, oque: e.oque, ler: e.ler })), gl: L.glossario }));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="sem node")
def test_explicacoes_e_diagramas_consistentes(tmp_path):
    f = tmp_path / "dump.js"
    f.write_text(JS)
    r = subprocess.run(["node", str(f), os.path.join(RAIZ, "site", "explica.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert len(d["dg"]) >= 10
    for nome, svg in d["dg"].items():
        root = ET.fromstring(svg)                       # XML bem formado
        assert root.tag.endswith("svg") and root.get("aria-label"), nome
    for e in d["ex"]:
        assert e["d"] in d["dg"], e["re"]
        assert len(e["oque"]) > 30 and len(e["ler"]) > 30, e["re"]
    assert len({e["re"] for e in d["ex"]}) == len(d["ex"])
    assert len(d["gl"]) >= 15 and all(len(t) == 2 and t[1] for t in d["gl"])
