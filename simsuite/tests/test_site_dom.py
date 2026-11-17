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


JS_ENLACE = r"""
const { JSDOM, VirtualConsole } = require("jsdom");
const path = require("path"), fs = require("fs");
const erros = [];
const vc = new VirtualConsole(); vc.on("jsdomError", e => erros.push(String(e.message || e))); vc.on("error", e => erros.push(String(e)));
const dir = process.argv[2];
const html = fs.readFileSync(path.join(dir, "enlace.html"), "utf8").replace(/<script src="([^"]+)"><\/script>/g,
  (_m, f) => "<script>" + fs.readFileSync(path.join(dir, f), "utf8").replace(/<\/script/g, "<\\/script") + "</script>");
const dom = new JSDOM(html, { url: "http://localhost/enlace.html" + process.argv[3], runScripts: "dangerously", virtualConsole: vc, pretendToBeVisual: true });
const w = dom.window, d = w.document;
setTimeout(() => {
  const out = { erros, hash: w.location.hash };
  out.titulo = (d.querySelector(".card p") || {}).textContent;
  out.resposta = [...d.querySelectorAll(".card")].map(c => (c.querySelector("h2") || {}).textContent);
  out.svg = !!d.querySelector("svg.perfil polygon");
  out.linhas = d.querySelectorAll("table tbody tr").length;
  out.frase = [...d.querySelectorAll(".card p")].map(p => p.textContent).find(t => /sinal chega/.test(t)) || "";
  if (process.argv[4]) {                                   // troca o terreno para CSV pela interface
    const s = d.querySelector("select"); s.value = "csv"; s.dispatchEvent(new w.Event("change"));
  }
  const ta = d.querySelector("textarea");
  out.tem_textarea = !!ta;
  if (ta) { ta.value = process.argv[4] || ""; ta.dispatchEvent(new w.Event("input")); }
  setTimeout(() => {
    out.apos_csv = [...d.querySelectorAll(".card h2")].map(h => h.textContent);
    out.frase2 = [...d.querySelectorAll(".card p")].map(p => p.textContent).find(t => /sinal chega/.test(t)) || "";
    out.hash2 = w.location.hash;
    console.log(JSON.stringify(out)); process.exit(0);
  }, 150);
}, 800);
"""


def _roda_enlace(tmp_path, frag, csv=""):
    f = tmp_path / "enlace_dom.js"
    f.write_text(JS_ENLACE)
    env = dict(os.environ)
    p = subprocess.run(["node", "-e", "console.log(require.resolve('jsdom'))"], capture_output=True, text=True, cwd=RAIZ)
    env["NODE_PATH"] = p.stdout.strip().split("/node_modules/")[0] + "/node_modules"
    r = subprocess.run(["node", str(f), os.path.join(RAIZ, "site"), frag, csv], capture_output=True, text=True,
                       timeout=120, env=env, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_testador_de_enlaces_desenha_e_guarda_so_parametros(tmp_path):
    o = _roda_enlace(tmp_path, "#terreno=morro&d=8&morro_h=80&p=22&sf=9&env=rural_serra")
    assert not o["erros"], o["erros"]
    assert o["svg"] and o["linhas"] == 18 and "sinal chega" in o["frase"] and "8,00 km" in o["frase"]
    assert "terreno=morro" in o["hash"] and "d=8" in o["hash"] and "p=22" in o["hash"]
    assert "Margem e entrega por modo" in o["resposta"]


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_testador_csv_colado_nao_vai_para_a_url(tmp_path):
    o = _roda_enlace(tmp_path, "#terreno=csv&d=4", csv="distancia_km;altitude_m\n0;100\n1;110\n2;180\n3;120\n4;100")
    assert not o["erros"], o["erros"]
    assert "terreno=plano" in o["hash"]                           # o CSV nunca vem pela URL: cai em "plano"
    assert o["tem_textarea"] and "sinal chega" in o["frase2"] and "4,00 km" in o["frase2"]
    assert "terreno=csv" in o["hash2"] and "180" not in o["hash2"] and "distancia" not in o["hash2"]
    assert "Perfil inválido" not in o["apos_csv"]


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_testador_parametros_invalidos_usam_o_padrao(tmp_path):
    o = _roda_enlace(tmp_path, "#d=9999&sf=3&p=abc&env=nao_existe&terreno=xyz")
    assert not o["erros"], o["erros"]
    assert o["svg"] and "d=5" in o["hash"] and "sf=10" in o["hash"] and "terreno=plano" in o["hash"]


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_testador_csv_invalido_mostra_erro(tmp_path):
    o = _roda_enlace(tmp_path, "#d=4", csv="0;100\n2;110\n1;120")
    assert not o["erros"], o["erros"]
    assert "Perfil inválido" in o["apos_csv"]


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_testador_hgt_pede_arquivo_e_nao_poe_coordenadas_na_url(tmp_path):
    o = _roda_enlace(tmp_path, "#terreno=hgt&d=4")
    assert not o["erros"], o["erros"]
    assert "terreno=plano" in o["hash"]                              # coordenadas e grades nunca vêm pela URL
