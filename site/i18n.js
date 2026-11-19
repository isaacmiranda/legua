/* Idioma do site: português do Brasil e inglês, alternáveis SEM recarregar e SEM refazer a tela. A troca só reescreve os textos dos
 * nós que já estão no DOM (e os novos, por observador), então campos digitados, pontos do mapa, rolagem, abas e resultados
 * calculados continuam como estão. O inglês vem de um dicionário (i18n_en.js) com chave em português, números trocados por #
 * (os números são reformatados: 1.234,5 vira 1,234.5). Texto sem tradução fica em português; o aviso do modo inglês diz isso.
 * Voltar ao português restaura os textos originais. Nada sai do navegador; só a escolha do idioma fica em localStorage. */
(function (root) {
  "use strict";
  var doc = root.document, DIC = root.LEGUA_EN || {}, NUM = /\d{1,3}(?:\.\d{3})+,\d+|\d+,\d+|\d+/g;
  var PULA = /^(SCRIPT|STYLE|TEXTAREA|CODE|PRE|NOSCRIPT)$/i, ATRS = ["title", "aria-label", "placeholder", "alt"];
  var TITULOS = { "Légua · Resultados": "Légua · Results", "Légua · Testador de enlaces": "Légua · Link tester", "Légua · Consolidado": "Légua · Consolidated report" };
  var lang = "pt", registros = [], obs = null, ouvintes = [];

  function ler() { try { var v = root.localStorage.getItem("legua-idioma"); if (v === "pt" || v === "en") return v; } catch (e) { /* sem storage */ } return "pt"; }   // o padrão é o português do Brasil; a escolha do usuário fica salva
  function gravar(l) { try { root.localStorage.setItem("legua-idioma", l); } catch (e) { /* ignore */ } }

  function converte(tok) {
    if (/^\d{1,3}(\.\d{3})+,\d+$/.test(tok)) { var p = tok.split(","), i = p[0].replace(/\./g, ""); return i.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + p[1]; }
    if (/^\d+,\d+$/.test(tok)) return tok.replace(",", ".");
    return tok;
  }
  /* traduz um texto em português; devolve null se não há tradução (ou se os números não casam com os marcadores) */
  function traduzTexto(pt) {
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(pt), nucleo = m[2].replace(/\s+/g, " ");
    if (!nucleo) return null;
    var toks = nucleo.match(NUM) || [], chave = nucleo.replace(NUM, "#"), v = DIC[chave];
    if (v === undefined) return null;
    var vazios = v.split("#").length - 1;
    if (vazios !== toks.length) return null;
    var i = 0, out = v.replace(/#/g, function () { return converte(toks[i++]); });
    return m[1] + out + m[3];
  }

  function aplicaNo(no) {
    if (no.nodeType === 3) {
      var p = no.parentNode;
      if (!p || PULA.test(p.tagName || "") || (p.closest && p.closest("svg,textarea,pre,code,script,style"))) return;
      if (no.__en === no.nodeValue) return;                                  // já traduzido por nós
      var en = traduzTexto(no.nodeValue);
      if (en != null && en !== no.nodeValue) { registros.push({ n: no, a: null, pt: no.nodeValue, en: en }); no.__en = en; no.nodeValue = en; }
    } else if (no.nodeType === 1) {
      if (PULA.test(no.tagName)) return;
      ATRS.forEach(function (a) {
        var v = no.getAttribute(a);
        if (v == null || (no.__enA && no.__enA[a] === v)) return;
        var chave = "@" + a + ":" + v, e2 = traduzTexto(chave);
        var final = e2 != null ? e2.replace(new RegExp("^@" + a + ":"), "") : null;
        if (final != null && final !== v) { registros.push({ n: no, a: a, pt: v, en: final }); (no.__enA = no.__enA || {})[a] = final; no.setAttribute(a, final); }
      });
    }
  }
  function aplica(raiz) {
    raiz = raiz || doc.body; if (!raiz) return;
    if (raiz.nodeType === 3) { aplicaNo(raiz); return; }
    if (raiz.nodeType !== 1) return;
    aplicaNo(raiz);
    var w = doc.createTreeWalker(raiz, 1 | 4, null), n;
    while ((n = w.nextNode())) aplicaNo(n);
  }
  function restaura() {
    registros.forEach(function (r) {
      if (r.a) { if (r.n.getAttribute && r.n.getAttribute(r.a) === r.en) r.n.setAttribute(r.a, r.pt); if (r.n.__enA) delete r.n.__enA[r.a]; }
      else if (r.n.nodeValue === r.en) { r.n.nodeValue = r.pt; r.n.__en = null; }
    });
    registros = [];
  }
  function observa() {
    if (obs || !root.MutationObserver || !doc.body) return;
    obs = new root.MutationObserver(function (ms) {
      if (lang !== "en") return;
      ms.forEach(function (m) {
        if (m.type === "childList") Array.prototype.forEach.call(m.addedNodes, function (n) { aplica(n); });
        else if (m.type === "characterData") aplicaNo(m.target);
        else if (m.type === "attributes") aplicaNo(m.target);
      });
    });
    obs.observe(doc.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATRS });
  }
  function aviso() {
    var a = doc.getElementById("i18n-aviso");
    if (lang === "en" && !a && doc.body) {
      a = doc.createElement("p"); a.id = "i18n-aviso"; a.className = "gnav-desc sem-impressao"; a.setAttribute("role", "note"); a.setAttribute("lang", "en");
      a.textContent = "English view: the interface, explanations, tools and the consolidated report are translated. Identifiers, trace examples and some text built from variable names stay as they are. Your inputs and results are unchanged when you switch language.";
      var g = doc.getElementById("gnav"); if (g) g.appendChild(a); else doc.body.insertBefore(a, doc.body.firstChild);
    } else if (lang !== "en" && a) a.parentNode.removeChild(a);
  }

  function definir(l, semGravar) {
    if (l !== "pt" && l !== "en") return lang;
    lang = l; if (!semGravar) gravar(l);
    doc.documentElement.setAttribute("lang", l === "en" ? "en" : "pt-BR");
    restaura();
    if (l === "en") { aplica(doc.body); observa(); var t = TITULOS[doc.title]; if (t) { doc.__tituloPt = doc.title; doc.title = t; } }
    else if (doc.__tituloPt) { doc.title = doc.__tituloPt; doc.__tituloPt = null; }
    aviso();
    ouvintes.forEach(function (f) { f(lang); });
    return lang;
  }
  function iniciar() { definir(ler(), true); }

  var api = { definir: definir, atual: function () { return lang; }, iniciar: iniciar, traduzTexto: traduzTexto, converte: converte, aplica: aplica, aoMudar: function (f) { ouvintes.push(f); }, DIC: DIC,
    aviso: aviso, locale: function () { return lang === "en" ? "en-US" : "pt-BR"; } };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaI18n = api;
})(typeof window !== "undefined" ? window : this);
