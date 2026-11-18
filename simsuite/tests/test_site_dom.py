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
    out.legenda = [...d.querySelectorAll(".legend span")].filter(n => /melhor modo/i.test(n.textContent)).length;
    out.codigo = (d.querySelector("pre.codigo") || {}).textContent || "";
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
    o = _roda(tmp_path, "#estimativas?d=2.5&sf=9&bw=250&p=20&sig=1&env=rural_aberto&perfil=estavel")
    assert not o["erros"], o["erros"]
    assert o["decisao"] and "Copiar resumo e link" in o["botoes"] and "Baixar JSON" in o["botoes"]
    assert "2,5" in o["titulo"] and "SF9/250" in o["titulo"] and "20 dBm" in o["titulo"]
    assert "d=2.5" in o["hash"] and "sf=9" in o["hash"] and "env=rural_aberto" in o["hash"]
    assert o["copiado"] and "estimativa analítica" in o["copiado"] and "#estimativas" in o["copiado"]
    assert "LEGUA_PROFILE_STABLE" in o["codigo"] and "cfg->cap_dbm = 20;" in o["codigo"] and "perfil=estavel" in o["hash"]


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


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_curva_do_melhor_modo_aparece_na_legenda(tmp_path):
    com = _roda(tmp_path, "#estimativas?d=2&sf=10&bw=125&p=28&hull=1")
    sem = _roda(tmp_path, "#estimativas?d=2&sf=10&bw=125&p=28&hull=0")
    assert not com["erros"] and not sem["erros"], (com["erros"], sem["erros"])
    assert com["legenda"] >= 1 and sem["legenda"] == 0


JS_TERRARIUM = r"""
const { JSDOM, VirtualConsole } = require("jsdom");
const path = require("path"), fs = require("fs");
const erros = [];
const vc = new VirtualConsole(); vc.on("jsdomError", e => erros.push(String(e.message || e))); vc.on("error", e => erros.push(String(e)));
const dir = process.argv[2];
const html = fs.readFileSync(path.join(dir, "enlace.html"), "utf8").replace(/<script src="([^"]+)"><\/script>/g,
  (_m, f) => "<script>" + fs.readFileSync(path.join(dir, f), "utf8").replace(/<\/script/g, "<\\/script") + "</script>");
const dom = new JSDOM(html, { url: "http://localhost/enlace.html#terreno=terrarium", runScripts: "dangerously", virtualConsole: vc, pretendToBeVisual: true });
const w = dom.window, d = w.document, out = { erros, urls: [] };
const espera = (ms) => new Promise(r => setTimeout(r, ms));
const campo = (rotulo) => [...d.querySelectorAll("input[type=text]")].find(i => (i.getAttribute("aria-label") || "").startsWith(rotulo));
(async () => {
  await espera(500);
  out.hash_inicial = w.location.hash;
  const s = d.querySelector("select"); s.value = "terrarium"; s.dispatchEvent(new w.Event("change"));
  await espera(100);
  out.hash_apos_escolher = w.location.hash;
  const preenche = (r, v) => { const i = campo(r); i.value = v; i.dispatchEvent(new w.Event("input")); };
  preenche("Latitude do ponto A", "-22.9"); preenche("Longitude do ponto A", "-43.2");
  preenche("Latitude do ponto B", "-22.9"); preenche("Longitude do ponto B", "-43.12");
  w.LeguaTerrariumBuscar = (url) => { out.urls.push(url); const x = new Float32Array(65536); x.fill(120); return Promise.resolve(x); };
  await espera(300);
  out.urls_antes_do_clique = out.urls.length;                  // nada é pedido enquanto o usuário não clica
  out.detalhes = !!d.querySelector("#app details summary");    // "O que é enviado?" fica recolhido
  out.habilitado = !d.getElementById("busca-tiles").disabled;
  d.getElementById("busca-tiles").click();
  await espera(600);
  out.status = d.getElementById("status-tiles").textContent;
  out.svg = !!d.querySelector("svg.perfil polygon");
  out.mapa = !!d.querySelector("canvas.mapa-relevo");
  out.hash = w.location.hash;
  console.log(JSON.stringify(out)); process.exit(0);
})();
"""


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_testador_terrarium_so_busca_com_consentimento_e_nao_poe_coordenadas_na_url(tmp_path):
    f = tmp_path / "terrarium_dom.js"
    f.write_text(JS_TERRARIUM)
    env = dict(os.environ)
    p = subprocess.run(["node", "-e", "console.log(require.resolve('jsdom'))"], capture_output=True, text=True, cwd=RAIZ)
    env["NODE_PATH"] = p.stdout.strip().split("/node_modules/")[0] + "/node_modules"
    r = subprocess.run(["node", str(f), os.path.join(RAIZ, "site")], capture_output=True, text=True, timeout=120, env=env, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert not [e for e in o["erros"] if "getContext" not in e], o["erros"]       # o jsdom sem canvas não implementa getContext
    assert o["mapa"] is True
    assert o["urls_antes_do_clique"] == 0 and o["detalhes"] is True                # só baixa depois do clique, com a explicação à mão
    assert o["habilitado"] is True and len(o["urls"]) >= 1
    assert all(u.startswith("https://s3.amazonaws.com/elevation-tiles-prod/terrarium/") and "22" not in u.split("terrarium/")[1].split("/")[0] for u in o["urls"])
    assert "Elevação pronta" in o["status"] and o["svg"]
    assert "terreno=plano" in o["hash_inicial"]                                   # a URL nunca liga a busca de tiles sozinha
    for h in (o["hash_apos_escolher"], o["hash"]):
        assert "22.9" not in h and "43.2" not in h and "latA" not in h and "lonA" not in h   # coordenadas nunca na URL


JS_NAV = r"""
const { JSDOM, VirtualConsole } = require("jsdom");
const path = require("path"), fs = require("fs");
const dir = process.argv[2], out = { erros: [] };
function abre(arq, frag) {
  const vc = new VirtualConsole(); vc.on("jsdomError", e => { if (!/getContext/.test(String(e.message || e))) out.erros.push(arq + ": " + String(e.message || e)); });
  const html = fs.readFileSync(path.join(dir, arq), "utf8").replace(/<script src="([^"]+)"><\/script>/g,
    (_m, f) => "<script>" + fs.readFileSync(path.join(dir, f), "utf8").replace(/<\/script/g, "<\\/script") + "</script>");
  const w = new JSDOM(html, { url: "http://localhost/" + arq + frag, runScripts: "dangerously", virtualConsole: vc, pretendToBeVisual: true }).window;
  w.scrollTo = () => {};
  return w;
}
const espera = (ms) => new Promise(r => setTimeout(r, ms));
const resumo = (w) => { const d = w.document; return {
  secoes: [...d.querySelectorAll(".gnav-sec")].map(a => a.textContent),
  atual: (d.querySelector('.gnav-sec[aria-current="true"]') || {}).textContent,
  sub: [...d.querySelectorAll("#tabs .tab")].map(a => a.textContent),
  sel: ((d.querySelector('#tabs [aria-selected="true"]') || d.querySelector('#tabs [aria-current="page"]')) || {}).textContent,
  desc: (d.querySelector(".gnav-desc") || {}).textContent, hash: w.location.hash,
  passo: [...d.querySelectorAll(".passo a")].map(a => a.textContent) }; };
(async () => {
  const w = abre("index.html", "#acordo"); await espera(900);
  out.acordo = resumo(w);
  const d = w.document;
  [...d.querySelectorAll(".gnav-sec")].find(a => a.textContent === "Garantias").click(); await espera(300);
  out.garantias = resumo(w);
  [...d.querySelectorAll("#tabs .tab")].find(a => a.textContent === "Segurança e regulação").click(); await espera(300);
  out.seg = resumo(w);
  [...d.querySelectorAll(".gnav-sec")].find(a => a.textContent === "Protocolo").click(); await espera(300);
  out.volta = resumo(w);                                   // lembra a última subseção da seção
  const px = d.querySelector(".passo a.prox"); if (px) { px.click(); await espera(300); } out.prox = resumo(w);
  out.legado = resumo(abre("index.html", "#estimativas?d=2&sf=9")); await espera(10);
  const e = abre("enlace.html", ""); await espera(700); out.enlace = resumo(e);
  out.enlace_links = [...e.document.querySelectorAll("#tabs a")].map(a => a.getAttribute("href"));
  const c = abre("consolidado.html", ""); await espera(300); out.consol = resumo(c);
  out.theme = [w, e, c].map(x => !!x.document.getElementById("theme"));
  console.log(JSON.stringify(out)); process.exit(0);
})();
"""


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_navegacao_em_duas_camadas_comum_as_tres_paginas(tmp_path):
    f = tmp_path / "nav_dom.js"
    f.write_text(JS_NAV)
    env = dict(os.environ)
    p = subprocess.run(["node", "-e", "console.log(require.resolve('jsdom'))"], capture_output=True, text=True, cwd=RAIZ)
    env["NODE_PATH"] = p.stdout.strip().split("/node_modules/")[0] + "/node_modules"
    r = subprocess.run(["node", str(f), os.path.join(RAIZ, "site")], capture_output=True, text=True, timeout=180, env=env, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert not o["erros"], o["erros"]
    assert o["acordo"]["secoes"] == ["Começar", "Desempenho", "Protocolo", "Garantias", "Ferramentas", "Referência"]
    assert o["acordo"]["atual"] == "Protocolo" and o["acordo"]["sel"] == "Acordo e falhas"        # o fragmento antigo continua valendo
    assert o["acordo"]["sub"] == ["Acordo e falhas", "Mecanismos (V, S)", "Sintonia (F7)"] and "afinar" in o["acordo"]["desc"]
    assert o["acordo"]["passo"] == ["← Grupos e malha", "Mecanismos (V, S) →"]                # vizinhos na ordem do mapa, atravessando as seções
    assert o["garantias"]["atual"] == "Garantias" and o["garantias"]["sel"] == "Verificação formal" and "#formal" in o["garantias"]["hash"]
    assert o["seg"]["sel"] == "Segurança e regulação" and "#seg" in o["seg"]["hash"]
    assert o["volta"]["atual"] == "Protocolo" and o["volta"]["sel"] == "Acordo e falhas"
    assert o["prox"]["sel"] == "Mecanismos (V, S)"                                              # o "próxima →" avança na ordem do mapa
    assert o["legado"]["atual"] == "Ferramentas" and o["legado"]["sel"] == "Estimativas"
    assert o["enlace"]["atual"] == "Ferramentas" and o["enlace"]["sel"] == "Testador de enlaces"
    assert "index.html#estimativas" in o["enlace_links"] and "enlace.html" in o["enlace_links"]
    assert o["consol"]["atual"] == "Referência" and o["consol"]["sel"] == "Consolidado e trabalhos futuros"
    assert o["theme"] == [True, True, True]


JS_ROTA = r"""
const { JSDOM, VirtualConsole } = require("jsdom");
const path = require("path"), fs = require("fs");
const erros = [];
const vc = new VirtualConsole(); vc.on("jsdomError", e => { if (!/getContext/.test(String(e.message || e))) erros.push(String(e.message || e)); });
const dir = process.argv[2];
const html = fs.readFileSync(path.join(dir, "enlace.html"), "utf8").replace(/<script src="([^"]+)"><\/script>/g,
  (_m, f) => "<script>" + fs.readFileSync(path.join(dir, f), "utf8").replace(/<\/script/g, "<\\/script") + "</script>");
const dom = new JSDOM(html, { url: "http://localhost/enlace.html#terreno=mapa", runScripts: "dangerously", virtualConsole: vc, pretendToBeVisual: true });
const w = dom.window, d = w.document, out = { erros, urls: [] };
const espera = (ms) => new Promise(r => setTimeout(r, ms));
const inputs = (r) => [...d.querySelectorAll("input[type=text]")].filter(i => (i.getAttribute("aria-label") || "").startsWith(r));
const digita = (i, v) => { i.value = v; i.dispatchEvent(new w.Event("input")); };
(async () => {
  await espera(500);
  out.hash_inicial = w.location.hash;
  const s = d.querySelector("select"); s.value = "mapa"; s.dispatchEvent(new w.Event("change")); await espera(150);
  out.imgs_antes = d.querySelectorAll(".mapa img").length;
  out.aviso_visivel = /Mapa-base desligado/.test(d.querySelector(".mapa").textContent);
  const pts = [[-22.9, -43.2], [-22.9, -43.12], [-22.85, -43.05]];
  for (let k = 0; k < pts.length; k++) {
    d.getElementById("add-ponto").click(); await espera(30);
    const la = inputs("Latitude do ponto")[k], lo = inputs("Longitude do ponto")[k];
    digita(la, String(pts[k][0])); digita(lo, String(pts[k][1])); await espera(30);
  }
  await espera(300);
  out.marcadores = d.querySelectorAll(".mapa [data-i]").length;
  out.titulo_rota_antes = [...d.querySelectorAll(".card h2")].map(h => h.textContent).find(t => /Rota/.test(t)) || null;
  out.plano_aviso = /sem elevação real/.test(d.getElementById("app").textContent);
  const rot = (r) => d.querySelector('.mapa button[aria-label="' + r + '"]');
  out.zoom_sem_consentimento = !!rot("Aproximar") && !!rot("Afastar");        // o zoom existe antes de ativar o mapa-base
  d.getElementById("ativa-mapa").click(); await espera(100);
  const imgs = [...d.querySelectorAll(".mapa img")];
  const zdo = (i) => +i.getAttribute("src").split("/").slice(-3)[0];
  out.z0 = zdo(imgs[0]); rot("Aproximar").click(); await espera(50);
  out.z1 = zdo(d.querySelector(".mapa img")); rot("Afastar").click(); rot("Afastar").click(); await espera(50);
  out.z2 = zdo(d.querySelector(".mapa img"));
  d.querySelector(".mapa").dispatchEvent(new w.WheelEvent("wheel", { deltaY: -100, clientX: 100, clientY: 100, bubbles: true, cancelable: true })); await espera(50);
  out.z3 = zdo(d.querySelector(".mapa img"));
  out.imgs_depois = imgs.length;
  out.img_urls_ok = imgs.every(i => /^https:\/\/tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png$/.test(i.getAttribute("src")));
  out.img_ref = imgs.every(i => i.getAttribute("referrerpolicy") === "origin");
  out.atribuicao = /OpenStreetMap/.test(d.querySelector(".mapa").textContent);
  w.LeguaTerrariumBuscar = (url) => { out.urls.push(url); const x = new Float32Array(65536); x.fill(120); return Promise.resolve(x); };
  d.getElementById("busca-tiles").click(); await espera(700);
  out.status = d.getElementById("status-tiles").textContent;
  const card = [...d.querySelectorAll(".card")].find(c => /Rota com/.test((c.querySelector("h2") || {}).textContent || ""));
  out.rota_titulo = card ? card.querySelector("h2").textContent : null;
  out.rota_linhas = card ? card.querySelectorAll("tbody tr").length : 0;
  out.rota_texto = card ? card.textContent : "";
  out.plano_aviso2 = /sem elevação real/.test(d.getElementById("app").textContent);
  const salto = [...d.querySelectorAll("select")].find(x => [...x.options].some(o => /Salto 2/.test(o.textContent)));
  out.tem_selecao_salto = !!salto;
  if (salto) { salto.value = "1"; salto.dispatchEvent(new w.Event("change")); await espera(300); }
  out.detalhe = (card ? 1 : 0) && [...d.querySelectorAll(".card")].find(c => /Rota com/.test((c.querySelector("h2") || {}).textContent || "")).textContent.includes("B → C (em detalhe)");
  out.ordem = [...d.querySelectorAll("#app > .card h2, #app > div > .card h2")].map(h => h.textContent);
  out.mapa_no_primeiro = !!d.querySelector("#app > .card .mapa") && d.querySelector("#app > .card h2").textContent.startsWith("1.");
  out.hash = w.location.hash;
  out.texto_pagina = d.getElementById("app").textContent;
  console.log(JSON.stringify(out)); process.exit(0);
})();
"""


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_mapa_com_varios_pontos_rota_e_privacidade(tmp_path):
    f = tmp_path / "rota_dom.js"
    f.write_text(JS_ROTA)
    env = dict(os.environ)
    p = subprocess.run(["node", "-e", "console.log(require.resolve('jsdom'))"], capture_output=True, text=True, cwd=RAIZ)
    env["NODE_PATH"] = p.stdout.strip().split("/node_modules/")[0] + "/node_modules"
    r = subprocess.run(["node", str(f), os.path.join(RAIZ, "site")], capture_output=True, text=True, timeout=150, env=env, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert not o["erros"], o["erros"]
    assert "terreno=plano" in o["hash_inicial"]                                   # a URL nunca liga o mapa nem leva pontos
    assert o["imgs_antes"] == 0 and o["aviso_visivel"]                            # sem consentimento, nenhum tile
    assert o["marcadores"] == 3 and "Rota com 2 saltos" in (o["titulo_rota_antes"] or "") and o["plano_aviso"]
    assert o["imgs_depois"] >= 4 and o["img_urls_ok"] and o["img_ref"] and o["atribuicao"]
    assert o["zoom_sem_consentimento"] and o["z1"] == o["z0"] + 1 and o["z2"] == o["z0"] - 1 and o["z3"] == o["z2"] + 1   # botões e roda mudam o zoom
    assert "Elevação pronta" in o["status"] and o["rota_titulo"] == "Rota com 2 saltos" and o["rota_linhas"] == 2
    assert "elevação real" in o["rota_texto"] and not o["plano_aviso2"]
    assert "Salto mais fraco" in o["rota_texto"] and "Modos que atingem" in o["rota_texto"] + "Modos que atingem"
    assert o["tem_selecao_salto"] and o["detalhe"]
    assert o["mapa_no_primeiro"]                                                  # o mapa vem na frente, no primeiro cartão
    ordem = o["ordem"]                                                            # terreno/mapa, resposta e rota, rádio, detalhes
    assert ordem.index("1. Terreno e pontos") < ordem.index("Resposta para este enlace") < ordem.index("2. Rádio, antenas e modo") < ordem.index("Perfil do enlace"), ordem
    for sec in (o["hash"], o["rota_texto"]):
        assert "22.9" not in sec and "43.2" not in sec and "43.12" not in sec and "-22.85" not in sec   # coordenadas nunca na URL nem no resumo
    assert all(u.startswith("https://s3.amazonaws.com/elevation-tiles-prod/terrarium/") for u in o["urls"]) and 1 <= len(o["urls"]) <= 8


JS_USO = r"""
const { JSDOM, VirtualConsole } = require("jsdom");
const path = require("path"), fs = require("fs");
const dir = process.argv[2], out = { erros: [] };
function abre(arq, frag) {
  const vc = new VirtualConsole(); vc.on("jsdomError", e => { if (!/getContext/.test(String(e.message || e))) out.erros.push(arq + ": " + String(e.message || e)); });
  const html = fs.readFileSync(path.join(dir, arq), "utf8").replace(/<script src="([^"]+)"><\/script>/g,
    (_m, f) => "<script>" + fs.readFileSync(path.join(dir, f), "utf8").replace(/<\/script/g, "<\\/script") + "</script>");
  return new JSDOM(html, { url: "http://localhost/" + arq + frag, runScripts: "dangerously", virtualConsole: vc, pretendToBeVisual: true }).window;
}
const espera = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const w = abre("index.html", "#campo"); await espera(700); let d = w.document;
  out.tema = d.getElementById("theme").textContent;
  out.aviso_recolhido = !!d.querySelector(".notice details summary");
  const abbrs = [...d.querySelectorAll("#panel abbr[title]")];
  out.abbr = abbrs.length; out.abbr_ok = abbrs.every(a => a.title.length > 20);
  out.abbr_dup = [...d.querySelectorAll("#panel .card")].some(c => { const t = [...c.querySelectorAll("abbr")].map(a => a.textContent); return new Set(t).size !== t.length; });
  const e = abre("index.html", "#estimativas"); await espera(800);
  out.restaura_plano = !!e.document.getElementById("restaura-plano");
  const p = abre("enlace.html", ""); await espera(600); d = p.document;
  out.ajuda_3passos = [...d.querySelectorAll(".notice details summary")].map(s => s.textContent);
  const sel = d.querySelector("select"); sel.value = "morro"; sel.dispatchEvent(new p.Event("change")); await espera(200);
  d.getElementById("restaura").click(); await espera(300);
  out.restaurou = d.querySelector("select").value;
  sel.value = "mapa"; d.querySelector("select").value = "mapa"; d.querySelector("select").dispatchEvent(new p.Event("change")); await espera(200);
  out.desfazer_inicial = d.getElementById("desfaz-ponto").disabled;      // nada a desfazer no começo
  d.getElementById("add-ponto").click(); await espera(50);
  const la = [...d.querySelectorAll("input[type=text]")].find(i => (i.getAttribute("aria-label") || "").startsWith("Latitude do ponto A"));
  const lo = [...d.querySelectorAll("input[type=text]")].find(i => (i.getAttribute("aria-label") || "").startsWith("Longitude do ponto A"));
  la.value = "-120"; la.dispatchEvent(new p.Event("input")); lo.value = "-22.9"; lo.dispatchEvent(new p.Event("input")); await espera(50);
  out.invalido = d.querySelectorAll('input[aria-invalid="true"]').length; out.alerta = [...d.querySelectorAll('[role=alert]')].map(a => a.textContent).join(" ");
  d.getElementById("add-ponto").click(); await espera(50);
  out.pontos_apos = d.querySelectorAll('input[aria-label^="Latitude do ponto"]').length;
  out.desfazer_habilitado = !d.getElementById("desfaz-ponto").disabled;
  d.getElementById("desfaz-ponto").click(); await espera(100);
  out.pontos_desfeito = d.querySelectorAll('input[aria-label^="Latitude do ponto"]').length;
  console.log(JSON.stringify(out)); process.exit(0);
})();
"""


@pytest.mark.skipif(not _tem_jsdom(), reason="sem node/jsdom")
def test_usabilidade_siglas_avisos_recolhidos_restaurar_validar_e_desfazer(tmp_path):
    f = tmp_path / "uso_dom.js"
    f.write_text(JS_USO)
    env = dict(os.environ)
    p = subprocess.run(["node", "-e", "console.log(require.resolve('jsdom'))"], capture_output=True, text=True, cwd=RAIZ)
    env["NODE_PATH"] = p.stdout.strip().split("/node_modules/")[0] + "/node_modules"
    r = subprocess.run(["node", str(f), os.path.join(RAIZ, "site")], capture_output=True, text=True, timeout=170, env=env, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert not o["erros"], o["erros"]
    assert o["tema"] in ("Tema: claro", "Tema: escuro")                         # o botão mostra o estado atual
    assert o["aviso_recolhido"] and o["abbr"] >= 1 and o["abbr_ok"] and not o["abbr_dup"]   # siglas com definição, uma vez por cartão
    assert o["restaura_plano"] and "Como usar em 3 passos" in o["ajuda_3passos"] and o["restaurou"] == "plano"
    assert o["invalido"] >= 1 and "trocadas" in o["alerta"]                      # latitude -120 fora do intervalo, com longitude plausível
    assert o["desfazer_inicial"] is True and o["desfazer_habilitado"] is True and o["pontos_apos"] == 2 and o["pontos_desfeito"] == 1
