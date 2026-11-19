/* Aba "Sensibilidade": tornado do estimador e propagação de incertezas (sensibilidade.js). Estado fica na página. */
(function (root) {
  "use strict";
  var doc = root.document, NS = "http://www.w3.org/2000/svg";
  var S = { env: null, d: 3, sf: 10, bw: 125, cr: 1, p: 20, off: 0, qual: "margem", alvo: 0.95, inc: { pl1km: 3, n: 0.3, snr_thr: 1, nf_db: 1, p_dbm: 1, offset_db: 3 }, nmc: 300 };

  function el(tag, attrs, kids) {
    var e = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(typeof c === "string" ? doc.createTextNode(c) : c); });
    return e;
  }
  function sv(tag, attrs, pai) { var e = doc.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (pai) pai.appendChild(e); return e; }
  function nf(x, d) { return isFinite(x) ? x.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }) : "–"; }

  function tornadoSvg(t) {
    var linhas = t.linhas, W = 720, rowH = 26, H = 30 + rowH * linhas.length, ml = 230, mr = 20, un = t.qual === "margem" ? " dB" : "";
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "class": "perfil", "aria-label": "Tornado: variação da " + (t.qual === "margem" ? "margem" : "entrega confirmada") + " ao variar cada parâmetro. O maior efeito é " + linhas[0].rot + "." });
    var lo = Math.min.apply(null, linhas.map(function (l) { return l.baixo; }).concat([t.base])), hi = Math.max.apply(null, linhas.map(function (l) { return l.alto; }).concat([t.base])), pad = (hi - lo) * 0.05 || 1;
    lo -= pad; hi += pad;
    function X(v) { return ml + (W - ml - mr) * (v - lo) / (hi - lo); }
    linhas.forEach(function (l, i) {
      var y = 20 + i * rowH, tx = sv("text", { x: ml - 8, y: y + 15, "text-anchor": "end", "font-size": "12", fill: "var(--text)" }, svg); tx.textContent = l.rot + " (±" + nf(l.variacao, l.variacao < 1 ? 1 : 0) + (l.un ? " " + l.un : "") + ")";
      sv("rect", { x: X(l.baixo), y: y + 3, width: Math.max(1, X(l.alto) - X(l.baixo)), height: rowH - 8, fill: "var(--s1)", "fill-opacity": "0.8", rx: "2" }, svg);
      var v = sv("text", { x: X(l.alto) + 4, y: y + 15, "font-size": "11", fill: "var(--text-2)" }, svg); v.textContent = nf(l.baixo, t.qual === "margem" ? 1 : 3) + " a " + nf(l.alto, t.qual === "margem" ? 1 : 3) + un;
    });
    sv("line", { x1: X(t.base), x2: X(t.base), y1: 10, y2: H - 6, stroke: "var(--s2)", "stroke-width": "2", "stroke-dasharray": "4 3" }, svg);
    var b = sv("text", { x: X(t.base), y: 8, "text-anchor": "middle", "font-size": "11", fill: "var(--s2)" }, svg); b.textContent = "base " + nf(t.base, t.qual === "margem" ? 1 : 3) + un;
    return svg;
  }

  function painel(panel, DATA) {
    var K = DATA.constantes, SS = root.LeguaSensibilidade; panel.textContent = "";
    if (!S.env) S.env = Object.keys(K.envs)[0];
    var out1 = el("div"), out2 = el("div");
    function campo(rot, obj, chave, op, tipo) {
      var inp;
      if (op && op.opcoes) { inp = el("select"); op.opcoes.forEach(function (o) { var x = el("option", { value: o[0], text: o[1] }); if (String(o[0]) === String(obj[chave])) x.selected = true; inp.appendChild(x); }); }
      else { inp = el("input", { type: "number", step: String(op.passo || 1), min: String(op.min), max: String(op.max) }); inp.value = obj[chave]; }
      inp.setAttribute("aria-label", rot);
      inp.addEventListener(op.opcoes ? "change" : "input", function () {
        if (op.opcoes) obj[chave] = isNaN(+inp.value) ? inp.value : +inp.value; else { var v = parseFloat(String(inp.value).replace(",", ".")); if (isFinite(v)) obj[chave] = Math.min(op.max, Math.max(op.min, v)); }
        calcula();
      });
      return el("label", { "class": "field" }, [el("span", { text: rot }), inp]);
    }
    function base() { return { env: S.env, d_km: S.d, sf: S.sf, bw: S.bw, cr: S.cr, p_dbm: S.p, fhss: S.bw < 500, retries: 3, interval_s: 60, load: 1, offset_db: S.off }; }
    var envs = Object.keys(K.envs).map(function (k) { return [k, K.envs[k].label || k]; });
    var c1 = el("section", { "class": "card" }, [el("h2", { text: "Cenário" }), el("p", { "class": "note", text: "Escolha o enlace e a grandeza. O tornado mostra quanto cada parâmetro move o resultado quando varia na faixa indicada, um de cada vez; os parâmetros do canal e do rádio são estimativas, e as faixas são as que você acha plausíveis." }),
      el("div", { "class": "form" }, [campo("Ambiente", S, "env", { opcoes: envs }), campo("Distância (km)", S, "d", { min: 0.05, max: 40, passo: 0.05 }), campo("SF", S, "sf", { opcoes: [7, 8, 9, 10, 11, 12].map(function (x) { return [x, "SF" + x]; }) }),
        campo("Largura de banda", S, "bw", { opcoes: [[125, "125 kHz"], [250, "250 kHz"], [500, "500 kHz"]] }), campo("Taxa de código", S, "cr", { opcoes: [[1, "4/5"], [2, "4/6"], [3, "4/7"], [4, "4/8"]] }), campo("Potência de TX (dBm)", S, "p", { min: -9, max: 28 }),
        campo("Offset de terreno (dB)", S, "off", { min: -25, max: 15, passo: 0.5 }), campo("Grandeza", S, "qual", { opcoes: [["margem", "Margem (dB)"], ["confirmado", "Entrega confirmada típica"]] })])]);
    var c2 = el("section", { "class": "card" }, [el("h2", { text: "O que mais move o resultado" }), out1]);
    var rotInc = { pl1km: "Perda a 1 km (dB)", n: "Expoente de perda n", snr_thr: "Limiar de SNR (dB)", nf_db: "Figura de ruído (dB)", p_dbm: "Potência real de TX (dB)", offset_db: "Terreno e obstrução (dB)" };
    var c3 = el("section", { "class": "card" }, [el("h2", { text: "Incerteza propagada (Monte Carlo)" }), el("p", { "class": "note", text: "Informe o desvio-padrão de cada incerteza (os da sua calibração, se houver). O site sorteia " + S.nmc + " combinações com semente fixa e mostra a faixa de 90% da margem e da entrega, e a chance de atingir o alvo." }),
      el("div", { "class": "form" }, Object.keys(rotInc).map(function (k) { return campo(rotInc[k], S.inc, k, { min: 0, max: 30, passo: 0.1 }); }).concat([campo("Entrega alvo", S, "alvo", { min: 0.5, max: 0.999, passo: 0.005 })])), out2]);
    [c1, c2, c3].forEach(function (c) { panel.appendChild(c); });
    function calcula() {
      out1.textContent = ""; out2.textContent = "";
      var t = SS.tornado(K, base(), S.qual);
      out1.appendChild(el("p", { "class": "note", text: "Base: " + (S.qual === "margem" ? nf(t.base, 1) + " dB de margem" : nf(t.base, 3) + " de entrega confirmada") + ". Maior efeito: " + t.linhas[0].rot + " (" + nf(t.linhas[0].amplitude, S.qual === "margem" ? 1 : 3) + (S.qual === "margem" ? " dB" : "") + " de amplitude). Os parâmetros do alto da lista são os que mais valem a pena medir na bancada." }));
      out1.appendChild(tornadoSvg(t));
      var mc = SS.monteCarlo(K, base(), S.inc, S.nmc, S.alvo, 20261119);
      out2.appendChild(el("div", { "class": "stats" }, [[nf(mc.margem.p50, 1) + " dB", "margem mediana (90%: " + nf(mc.margem.p5, 1) + " a " + nf(mc.margem.p95, 1) + ")"], [nf(mc.entrega.p50, 3), "entrega mediana (90%: " + nf(mc.entrega.p5, 3) + " a " + nf(mc.entrega.p95, 3) + ")"],
        [nf(100 * mc.probAtingeAlvo, 0) + " %", "chance de atingir " + nf(100 * mc.alvo, 1) + " % de entrega"]].map(function (i) { return el("div", { "class": "stat" }, [el("div", { "class": "v", text: i[0] }), el("div", { "class": "l", text: i[1] })]); })));
    }
    calcula();
  }
  root.LeguaSensibilidadeUI = { painel: painel, estado: S };
})(typeof window !== "undefined" ? window : this);
