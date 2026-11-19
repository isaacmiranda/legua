// Extrai os textos visíveis do site (nós de texto e atributos title/aria-label/placeholder/alt), com números normalizados, para
// montar e conferir o dicionário de tradução (site/i18n_en.js). Uso: NODE_PATH=<node_modules do jsdom> node tools/extrair_textos.js [saida.json]
const { JSDOM, VirtualConsole } = require("jsdom"); const path = require("path"), fs = require("fs");
const dir = path.join(__dirname, "..", "site"), saida = process.argv[2] || "/dev/stdout", mapa = {};
const SKIP = /^(SCRIPT|STYLE|TEXTAREA|CODE|PRE|SVG|TITLE)$/i;
const NUM = /\d{1,3}(?:\.\d{3})+,\d+|\d+,\d+|\d+/g;
function norm(t) { return t.replace(/\s+/g, " ").trim().replace(NUM, "#"); }
function coleta(d, rot) {
  const w = d.createTreeWalker(d.body, 4, null); let n;
  while ((n = w.nextNode())) {
    const p = n.parentNode; if (!p || SKIP.test(p.tagName) || (p.closest && p.closest("svg,textarea,pre,code,script,style"))) continue;
    const k = norm(n.nodeValue); if (k.replace(/[#\s\d.,:;()/%×·→←↗–—+\-]/g, "").length < 2) continue;
    (mapa[k] = mapa[k] || { n: 0, onde: rot }).n++;
  }
  d.querySelectorAll("[title],[aria-label],[placeholder],[alt]").forEach(e => ["title", "aria-label", "placeholder", "alt"].forEach(a => { const v = e.getAttribute(a); if (v) { const k = "@" + a + ":" + norm(v); (mapa[k] = mapa[k] || { n: 0, onde: rot }).n++; } }));
}
function abre(arq, frag, pre) {
  const vc = new VirtualConsole(); vc.on("jsdomError", () => {});
  const html = fs.readFileSync(path.join(dir, arq), "utf8").replace(/<script src="([^"]+)"><\/script>/g, (_m, f) => "<script>" + fs.readFileSync(path.join(dir, f), "utf8").replace(/<\/script/g, "<\\/script") + "</script>");
  const w = new JSDOM(html, { url: "http://localhost/" + arq + frag, runScripts: "dangerously", virtualConsole: vc, pretendToBeVisual: true }).window;
  if (pre) w.eval(pre); return w;
}
const esp = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const ids = ["guia","campo","mob","alcance","potencia","tetos","malha","acordo","mecanismos","sintonia","formal","validacao","seg","estimativas","calc","pacote","medicoes","sensib","rastros","spec","modos","escalas"];
  for (const id of ids) {
    const w = abre("index.html", "#" + id, id === "spec" ? fs.readFileSync(path.join(dir, "especificacao.js"), "utf8") : null); await esp(id === "spec" ? 900 : 700);
    const d = w.document; coleta(d, id);
    if (id === "pacote") { [...d.querySelectorAll("button")].find(b => b.textContent === "Exemplo: DATA").click(); await esp(100); coleta(d, id + "+ex"); }
    if (id === "medicoes") { d.getElementById("med-exemplo").click(); await esp(150); coleta(d, id + "+ex"); }
    if (id === "rastros") { d.getElementById("ras-exemplo").click(); await esp(150); coleta(d, id + "+ex"); }
    if (id === "spec") { const q = d.querySelector('input[aria-label="Buscar nos documentos"]'); if (q) { q.value = "RESYNC"; q.dispatchEvent(new w.Event("input")); await esp(150); coleta(d, id + "+busca"); } }
    if (id === "guia") { /* o guia tem passos interativos */ [...d.querySelectorAll("button")].slice(0, 6).forEach(b => b.click && 0); }
    w.close();
  }
  { const w = abre("index.html", "#campo/full"); await esp(700); coleta(w.document, "campo-full"); w.close(); }
  for (const [frag, rot] of [["", "enlace-mapa-vazio"], ["#terreno=plano", "enlace-plano"], ["#terreno=morro&d=8&morro_h=80", "enlace-morro"]]) { const w = abre("enlace.html", frag); await esp(600); coleta(w.document, rot); w.close(); }
  { // enlace com mapa, 3 pontos, elevação e cobertura
    const w = abre("enlace.html", ""); await esp(600); const d = w.document; const ent = (r) => [...d.querySelectorAll("input[type=text]")].filter(i => (i.getAttribute("aria-label") || "").startsWith(r));
    const dig = (i, v) => { i.value = v; i.dispatchEvent(new w.Event("input")); };
    for (let k = 0; k < 3; k++) { d.getElementById("add-ponto").click(); await esp(30); }
    const la = ent("Latitude"), lo = ent("Longitude"); [[-22.9, -43.2], [-22.9, -43.12], [-22.85, -43.05]].forEach((p, k) => { dig(la[k], String(p[0])); dig(lo[k], String(p[1])); }); await esp(200);
    coleta(d, "enlace-rota-plana");
    w.LeguaTerrariumBuscar = () => { const x = new Float32Array(65536); x.fill(120); return Promise.resolve(x); };
    d.getElementById("busca-tiles").click(); await esp(500); coleta(d, "enlace-rota");
    d.getElementById("cob-calcula").click(); await esp(1500); coleta(d, "enlace-cobertura");
    d.getElementById("ativa-mapa").click(); await esp(100); coleta(d, "enlace-mapa-ativo");
    const lat = la[0]; dig(lat, "-120"); await esp(60); coleta(d, "enlace-invalido");
    w.close();
  }
  { const w = abre("consolidado.html", ""); await esp(500); coleta(w.document, "consolidado"); w.close(); }
  fs.writeFileSync(saida, JSON.stringify(mapa, null, 1)); process.exit(0);
})();
