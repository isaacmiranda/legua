"""Fumaça do site no jsdom: o estado do estimador vai e volta pelo fragmento da URL, a resposta e a exportação
aparecem e nada lança erro. Pula sem node ou sem jsdom."""
import json
import os
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

JS = r"""
const { JSDOM, VirtualConsole } = require("jsdom");
const path = require("path");
const erros = [];
const vc = new VirtualConsole(); vc.on("jsdomError", e => erros.push(String(e.message || e))); vc.on("error", e => erros.push(String(e)));
const fs = require("fs");
// scripts embutidos no HTML e URL http: o replaceState não funciona em file:// no jsdom
const html = fs.readFileSync(path.join(process.argv[2], "index.html"), "utf8").replace(/<script src="([^"]+)"><\/script>/g,
  (_m, f) => "<script>" + fs.readFileSync(path.join(process.argv[2], f), "utf8").replace(/<\/script/g, "<\\/script") + "</script>");
Promise.resolve(new JSDOM(html, { url: "http://localhost/index.html" + process.argv[3], runScripts: "dangerously", virtualConsole: vc, pretendToBeVisual: true })).then(dom => {
  const w = dom.window;
  setTimeout(() => {
    const d = w.document, out = { erros };
    out.hash = w.location.hash;
    out.decisao = !!d.querySelector(".decisao");
    out.botoes = [...d.querySelectorAll(".decisao .btn")].map(b => b.textContent);
    out.ranges = [...d.querySelectorAll("input[type=range]")].map(i => i.value);
    out.titulo = (d.querySelector(".decisao p") || {}).textContent || "";
    const copiar = [...d.querySelectorAll(".decisao .btn")].find(b => /Copiar/.test(b.textContent));
    let copiado = null;
    w.navigator.clipboard = { writeText: t => { copiado = t; return Promise.resolve(); } };
    if (copiar) copiar.click();
    setTimeout(() => { out.copiado = copiado; console.log(JSON.stringify(out)); process.exit(0); }, 50);
  }, 1500);
});
"""


def _roda(tmp_path, frag):
    f = tmp_path / "dom.js"
    f.write_text(JS)
    env = dict(os.environ)
    p = subprocess.run(["node", "-e", "console.log(require.resolve('jsdom'))"], capture_output=True, text=True, cwd=RAIZ)
    env["NODE_PATH"] = p.stdout.strip().split("/node_modules/")[0] + "/node_modules"
    r = subprocess.run(["node", str(f), os.path.join(RAIZ, "site"), frag], capture_output=True, text=True, timeout=120,
                       env=env, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _tem_jsdom():
    if not shutil.which("node"):
        return False
    return subprocess.run(["node", "-e", "require('jsdom')"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_estado_do_estimador_na_url_e_exportacao(tmp_path):
    o = _roda(tmp_path, "#estimativas?d=2.5&sf=9&bw=250&p=20&sig=1&env=rural_aberto")
    assert not o["erros"], o["erros"]
    assert o["decisao"] and "Copiar resumo e link" in o["botoes"] and "Baixar JSON" in o["botoes"]
    assert "2,5" in o["titulo"] and "SF9/250" in o["titulo"] and "20 dBm" in o["titulo"]
    assert "d=2.5" in o["hash"] and "sf=9" in o["hash"] and "env=rural_aberto" in o["hash"]
    assert o["copiado"] and "estimativa analítica" in o["copiado"] and "#estimativas" in o["copiado"]


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_fragmento_invalido_e_ignorado(tmp_path):
    o = _roda(tmp_path, "#estimativas?d=abc&sf=99&bw=7&env=nao_existe&p=1000")
    assert not o["erros"], o["erros"]
    assert o["decisao"] and "d=1" in o["hash"] and "sf=10" in o["hash"]
