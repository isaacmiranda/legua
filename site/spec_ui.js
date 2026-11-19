/* Aba "Especificação": navegador dos documentos de especificação (docs/*.md convertidos por tools/build_docs.py), com índice por
 * seção e busca no texto de todos os documentos. O arquivo especificacao.js só é baixado ao abrir a aba. */
(function (root) {
  "use strict";
  var doc = root.document, S = { doc: "07", q: "", sec: "" }, carregado = false, indice = null;

  function el(tag, attrs, kids) {
    var e = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(typeof c === "string" ? doc.createTextNode(c) : c); });
    return e;
  }
  function carrega(cb) {
    if (root.LEGUA_DOCS) return cb(true);
    var s = doc.createElement("script"); s.src = "especificacao.js"; s.onload = function () { cb(!!root.LEGUA_DOCS); }; s.onerror = function () { cb(false); }; doc.head.appendChild(s);
  }
  /* índice de busca: [{doc, docTitulo, id, titulo, texto}] por seção */
  function montaIndice() {
    if (indice) return indice;
    indice = [];
    root.LEGUA_DOCS.forEach(function (d) {
      var t = doc.createElement("div"); t.innerHTML = d.html;
      var atual = { doc: d.id, docTitulo: d.titulo, id: "", titulo: d.titulo, texto: "" };
      Array.prototype.forEach.call(t.children, function (n) {
        if (/^H[2-5]$/.test(n.tagName)) { if (atual.texto.trim()) indice.push(atual); atual = { doc: d.id, docTitulo: d.titulo, id: n.id, titulo: n.textContent, texto: "" }; }
        else atual.texto += " " + n.textContent;
      });
      if (atual.texto.trim()) indice.push(atual);
    });
    return indice;
  }
  function busca(q) {
    var termos = q.toLowerCase().split(/\s+/).filter(function (x) { return x.length > 1; }), out = [];
    if (!termos.length) return out;
    montaIndice().forEach(function (s) {
      var low = (s.titulo + " " + s.texto).toLowerCase(), ok = termos.every(function (t) { return low.indexOf(t) >= 0; });
      if (!ok) return;
      var i = low.indexOf(termos[0]), ini = Math.max(0, i - 50), snip = (s.titulo + " — " + s.texto).replace(/\s+/g, " ");
      var j = snip.toLowerCase().indexOf(termos[0]); snip = (j > 60 ? "…" : "") + snip.slice(Math.max(0, j - 60), j + 140) + "…";
      out.push({ s: s, snippet: snip, peso: (s.titulo.toLowerCase().indexOf(termos[0]) >= 0 ? 0 : 1) });
    });
    out.sort(function (a, b) { return a.peso - b.peso; });
    return out.slice(0, 40);
  }

  function painel(panel) {
    panel.textContent = "";
    var corpo = el("div"); panel.appendChild(el("section", { "class": "card" }, [el("h2", { text: "Especificação e documentos do projeto" }), corpo]));
    corpo.appendChild(el("p", { "class": "note", text: "Carregando os documentos…" }));
    carrega(function (ok) {
      corpo.textContent = "";
      if (!ok) { corpo.appendChild(el("p", {}, [el("span", { "class": "pill bad", text: "não carregou" }), " Não consegui baixar especificacao.js. Os mesmos documentos estão em docs/ no repositório."])); return; }
      var docs = root.LEGUA_DOCS;
      var q = el("input", { type: "search", placeholder: "Buscar em todos os documentos…", "aria-label": "Buscar nos documentos", style: "width:100%;max-width:420px" }); q.value = S.q;
      var sel = el("select", { "aria-label": "Documento" }); docs.forEach(function (d) { var o = el("option", { value: d.id, text: "docs/" + d.id + " · " + d.titulo }); if (d.id === S.doc) o.selected = true; sel.appendChild(o); });
      var resultados = el("div"), leitor = el("div", { "class": "spec-leitor", style: "display:grid;grid-template-columns:minmax(0,230px) minmax(0,1fr);gap:16px;align-items:start;margin-top:12px" });
      var toc = el("nav", { "aria-label": "Índice do documento", style: "position:sticky;top:60px;max-height:70vh;overflow:auto;font-size:13px" }), texto = el("div", { "class": "spec-texto", style: "min-width:0" });
      leitor.appendChild(toc); leitor.appendChild(texto);
      corpo.appendChild(el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;align-items:center" }, [q, sel]));
      corpo.appendChild(resultados); corpo.appendChild(leitor);
      function abre(did, sid) {
        S.doc = did; sel.value = did; var d = docs.filter(function (x) { return x.id === did; })[0]; if (!d) return;
        texto.innerHTML = d.html; toc.textContent = "";
        toc.appendChild(el("p", { "class": "sub", text: d.arquivo }));
        d.secoes.filter(function (s) { return s.nivel <= 3; }).forEach(function (s) {
          var a = el("a", { href: "#", style: "display:block;padding:2px 0 2px " + ((s.nivel - 1) * 10) + "px;color:var(--accent);text-decoration:none", text: s.titulo });
          a.addEventListener("click", function (ev) { ev.preventDefault(); var alvo = texto.querySelector("#" + (root.CSS && CSS.escape ? CSS.escape(s.id) : s.id)); if (alvo && alvo.scrollIntoView) alvo.scrollIntoView({ behavior: "smooth", block: "start" }); });
          toc.appendChild(a);
        });
        if (sid) { var alvo = texto.querySelector("#" + (root.CSS && CSS.escape ? CSS.escape(sid) : sid)); if (alvo && alvo.scrollIntoView) alvo.scrollIntoView({ block: "start" }); }
      }
      function pesquisa() {
        S.q = q.value; resultados.textContent = "";
        if (S.q.trim().length < 2) return;
        var r = busca(S.q);
        resultados.appendChild(el("p", { "class": "sub", role: "status", "aria-live": "polite", text: r.length ? r.length + " seção(ões) com todos os termos:" : "Nada encontrado para “" + S.q + "”. Tente menos termos." }));
        var ul = el("ul", { style: "padding-left:18px" });
        r.forEach(function (x) {
          var a = el("a", { href: "#", text: "docs/" + x.s.doc + " · " + x.s.titulo, style: "color:var(--accent)" });
          a.addEventListener("click", function (ev) { ev.preventDefault(); abre(x.s.doc, x.s.id); });
          ul.appendChild(el("li", {}, [a, el("div", { "class": "sub", text: x.snippet })]));
        });
        resultados.appendChild(ul);
      }
      q.addEventListener("input", pesquisa); sel.addEventListener("change", function () { abre(sel.value); });
      abre(S.doc); pesquisa();
    });
  }
  root.LeguaSpecUI = { painel: painel, busca: busca, estado: S };
})(typeof window !== "undefined" ? window : this);
