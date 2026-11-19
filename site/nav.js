/* Navegação comum às três páginas (index, enlace, consolidado): barra de seções, linha de subseções, tema claro/escuro,
 * "anterior/próxima" e a lembrança da última subseção de cada seção. Uma só fonte do mapa do site (MAPA): o app.js usa
 * os ids para roteamento dentro de index.html; as outras páginas viram links. Sem rede, sem dependências. */
(function (root) {
  "use strict";
  var doc = root.document;

  /* seção -> subseções. `id` de página index = id da aba em app.js; `href` = outra página. */
  var MAPA = [
    { id: "comeco", t: "Começar", d: "O que é a Légua, o que os números significam e por onde começar.",
      itens: [{ id: "guia", t: "Comece aqui" }] },
    { id: "desempenho", t: "Desempenho", d: "Quanto entrega, quanto gasta e até onde chega: campo fixo, movimento, alcance, potência e grupos.",
      itens: [{ id: "campo", t: "Campo fixo" }, { id: "mob", t: "Mobilidade" }, { id: "alcance", t: "Alcance e deriva" }, { id: "potencia", t: "Potência de TX" },
        { id: "tetos", t: "Teto × cenários" }, { id: "malha", t: "Grupos e malha" }] },
    { id: "protocolo", t: "Protocolo", d: "Como os dois lados combinam o modo, o que acontece nas falhas e como afinar os parâmetros.",
      itens: [{ id: "acordo", t: "Acordo e falhas" }, { id: "mecanismos", t: "Mecanismos (V, S)" }, { id: "sintonia", t: "Sintonia (F7)" }] },
    { id: "garantias", t: "Garantias", d: "O que foi provado e conferido: verificação formal, validação contra outros simuladores, segurança e regulação.",
      itens: [{ id: "formal", t: "Verificação formal" }, { id: "validacao", t: "Validação cruzada" }, { id: "seg", t: "Segurança e regulação" }] },
    { id: "ferramentas", t: "Ferramentas", d: "Para usar os resultados no seu caso: estimativas por modo e testador de enlaces com terreno.",
      itens: [{ id: "estimativas", t: "Estimativas" }, { id: "calc", t: "Calculadoras" }, { id: "pacote", t: "Pacotes" }, { id: "medicoes", t: "Medições" }, { id: "sensib", t: "Sensibilidade" }, { id: "rastros", t: "Rastros" }, { id: "enlace", t: "Testador de enlaces", href: "enlace.html" }] },
    { id: "referencia", t: "Referência", d: "Tabela de modos, escalas e orçamento de tempo, e o consolidado com discussões e trabalhos futuros.",
      itens: [{ id: "modos", t: "Modos" }, { id: "spec", t: "Especificação" }, { id: "escalas", t: "Escalas e orçamento" }, { id: "consolidado", t: "Consolidado e trabalhos futuros", href: "consolidado.html" }] }
  ];

  function secaoDe(id) { for (var i = 0; i < MAPA.length; i++) for (var j = 0; j < MAPA[i].itens.length; j++) if (MAPA[i].itens[j].id === id) return MAPA[i]; return MAPA[0]; }
  function sequencia() { var s = []; MAPA.forEach(function (g) { g.itens.forEach(function (i) { if (!i.href) s.push(i); }); }); return s; }
  function destino(it) { return it.href ? it.href : "index.html#" + it.id; }

  function lembrar(secao, id) { try { sessionStorage.setItem("legua-sub-" + secao, id); } catch (e) { /* sem storage */ } }
  function lembrado(g) {
    var v = null; try { v = sessionStorage.getItem("legua-sub-" + g.id); } catch (e) { /* sem storage */ }
    for (var i = 0; i < g.itens.length; i++) if (g.itens[i].id === v) return g.itens[i];
    return g.itens[0];
  }

  function el(tag, attrs, kids) {
    var e = doc.createElement(tag), k;
    Object.keys(attrs || {}).forEach(function (a) { if (a === "text") e.textContent = attrs[a]; else e.setAttribute(a, attrs[a]); });
    (kids || []).forEach(function (c) { e.appendChild(c); });
    return e;
  }

  /* tema: um só tratamento para todas as páginas */
  function tema(botao) {
    var r = doc.documentElement;
    try { var v = localStorage.getItem("legua-tema"); if (v === "light" || v === "dark") r.setAttribute("data-theme", v); } catch (e) { /* sem storage */ }
    function escuro() { return r.getAttribute("data-theme") === "dark" || (!r.getAttribute("data-theme") && root.matchMedia && root.matchMedia("(prefers-color-scheme: dark)").matches); }
    function rotulo() { botao.textContent = escuro() ? "Tema: escuro" : "Tema: claro"; botao.title = "Trocar para o tema " + (escuro() ? "claro" : "escuro"); }
    rotulo();
    botao.addEventListener("click", function () {
      var prox = escuro() ? "light" : "dark";
      r.setAttribute("data-theme", prox); rotulo();
      try { localStorage.setItem("legua-tema", prox); } catch (e) { /* ignore */ }
    });
  }

  /* opções: { ativo: id do item atual, ir: function(id) (só no index; sem ela os itens viram links) } */
  function montar(host, op) {
    op = op || {};
    var g = secaoDe(op.ativo);
    host.textContent = "";
    var barra = el("nav", { "class": "gnav", "aria-label": "Seções do site" });
    barra.appendChild(el("a", { "class": "gnav-marca", href: "index.html#guia", text: "Légua" }));
    var lista = el("div", { "class": "gnav-secoes" });
    MAPA.forEach(function (s) {
      var alvo = lembrado(s), a = el("a", { "class": "gnav-sec", href: destino(alvo), text: s.t });
      if (s.id === g.id) a.setAttribute("aria-current", "true");
      if (op.ir && !alvo.href) a.addEventListener("click", function (ev) { ev.preventDefault(); op.ir(alvo.id); });
      lista.appendChild(a);
    });
    barra.appendChild(lista);
    var tb = el("button", { "class": "btn", id: "theme", type: "button", "aria-label": "Alternar tema claro e escuro", text: "Tema" });
    tema(tb); barra.appendChild(tb);
    host.appendChild(barra);

    var sub = el("nav", { "class": "tabs", id: "tabs", role: "tablist", "aria-label": g.t });
    g.itens.forEach(function (it, i) {
      var atual = it.id === op.ativo, b;
      if (op.ir && !it.href) {
        b = el("button", { "class": "tab", role: "tab", type: "button", text: it.t, "aria-selected": String(atual) });
        b.dataset.id = it.id; b.tabIndex = atual ? 0 : -1;
        b.addEventListener("click", function () { op.ir(it.id); });
        b.addEventListener("keydown", function (e) {
          var n = i + (e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0), alvo = g.itens[n];
          if (n !== i && alvo && !alvo.href) { op.ir(alvo.id); var nb = sub.querySelector('[data-id="' + alvo.id + '"]'); if (nb) nb.focus(); e.preventDefault(); }
        });
      } else {
        b = el("a", { "class": "tab", href: destino(it), text: it.t + (it.href && op.ir ? " ↗" : "") });
        if (atual) b.setAttribute("aria-current", "page");
      }
      sub.appendChild(b);
    });
    host.appendChild(sub);
    host.appendChild(el("p", { "class": "gnav-desc", text: g.d }));
    if (op.ativo) lembrar(g.id, op.ativo);
  }

  /* "anterior / próxima" entre as abas de index.html, na ordem do mapa */
  function vizinhos(id) {
    var s = sequencia(), i = -1, j;
    for (j = 0; j < s.length; j++) if (s[j].id === id) i = j;
    return { ant: i > 0 ? s[i - 1] : null, prox: i >= 0 && i < s.length - 1 ? s[i + 1] : null };
  }
  function rodape(id, ir) {
    var v = vizinhos(id);
    if (!v.ant && !v.prox) return null;
    var n = el("nav", { "class": "passo", "aria-label": "Anterior e próxima seção" });
    function lk(it, rot, cls) {
      var a = el("a", { "class": "btn " + cls, href: destino(it), text: rot }); a.addEventListener("click", function (ev) { ev.preventDefault(); ir(it.id); }); return a;
    }
    n.appendChild(v.ant ? lk(v.ant, "← " + v.ant.t, "ant") : el("span"));
    n.appendChild(v.prox ? lk(v.prox, v.prox.t + " →", "prox") : el("span"));
    return n;
  }

  /* uso offline: registra o service worker (só em https ou localhost; o sw.js guarda apenas arquivos do próprio site) */
  try {
    var nav = root.navigator, loc = root.location;
    if (nav && nav.serviceWorker && loc && (loc.protocol === "https:" || loc.hostname === "localhost" || loc.hostname === "127.0.0.1")) nav.serviceWorker.register("sw.js").catch(function () { /* sem offline; o site segue normal */ });
  } catch (e) { /* ignore */ }

  var api = { MAPA: MAPA, secaoDe: secaoDe, montar: montar, rodape: rodape, vizinhos: vizinhos, destino: destino };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaNav = api;
})(typeof window !== "undefined" ? window : this);
