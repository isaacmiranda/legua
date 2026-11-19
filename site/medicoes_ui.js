/* Aba "Medições": cola ou carrega um CSV de campo, ajusta a perda de percurso e o limiar de SNR (medicoes.js), compara com o
 * modelo atual e gera o calibracao.json. Tudo local; colunas de localização são recusadas. */
(function (root) {
  "use strict";
  var doc = root.document, NS = "http://www.w3.org/2000/svg";
  var S = { csv: "", amb: null, p: 14, ganhos: 0, id: "campo-" + new Date().toISOString().slice(0, 10), data: new Date().toISOString().slice(0, 10), hw: "Heltec WiFi LoRa 32 V4", fw: "core-v0.1.1" };

  function el(tag, attrs, kids) {
    var e = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(typeof c === "string" ? doc.createTextNode(c) : c); });
    return e;
  }
  function sv(tag, attrs, pai) { var e = doc.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (pai) pai.appendChild(e); return e; }
  function nf(x, d) { return isFinite(x) ? x.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }) : "–"; }

  /* dispersão da perda de percurso contra a distância (eixo x logarítmico), com a reta ajustada e a do modelo atual */
  function grafico(pontos, aj, atual) {
    var W = 720, H = 300, ml = 52, mr = 12, mt = 12, mb = 38, svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "class": "perfil",
      "aria-label": "Perda de percurso medida contra a distância, com a reta ajustada (pl1km " + nf(aj.pl1km, 1) + " dB, n " + nf(aj.n, 2) + ") e a do modelo atual" });
    var xs = pontos.map(function (p) { return Math.log10(p.d); }), ys = pontos.map(function (p) { return p.pl; });
    var x0 = Math.min.apply(null, xs) - 0.1, x1 = Math.max.apply(null, xs) + 0.1, all = ys.concat([aj.pl1km + aj.n * 10 * x0, aj.pl1km + aj.n * 10 * x1, atual.pl1km + atual.n * 10 * x0, atual.pl1km + atual.n * 10 * x1]);
    var y0 = Math.min.apply(null, all) - 4, y1 = Math.max.apply(null, all) + 4;
    function X(v) { return ml + (W - ml - mr) * (v - x0) / (x1 - x0); } function Y(v) { return mt + (H - mt - mb) * (1 - (v - y0) / (y1 - y0)); }
    sv("rect", { x: 0, y: 0, width: W, height: H, fill: "none" }, svg);
    for (var k = 0; k <= 4; k++) { var yv = y0 + (y1 - y0) * k / 4, g = sv("line", { x1: ml, x2: W - mr, y1: Y(yv), y2: Y(yv), stroke: "var(--grid)" }, svg); var t = sv("text", { x: ml - 6, y: Y(yv) + 4, "text-anchor": "end", "font-size": "11", fill: "var(--text-3)" }, svg); t.textContent = Math.round(yv); }
    var d0 = Math.ceil(x0), tk; for (tk = Math.floor(x0); tk <= x1; tk++) { [1, 2, 5].forEach(function (m) { var v = tk + Math.log10(m); if (v >= x0 && v <= x1) { sv("line", { x1: X(v), x2: X(v), y1: mt, y2: H - mb, stroke: "var(--grid)" }, svg); var tt = sv("text", { x: X(v), y: H - mb + 14, "text-anchor": "middle", "font-size": "11", fill: "var(--text-3)" }, svg); tt.textContent = nf(m * Math.pow(10, tk), tk < 0 ? -tk : 0) + " km"; } }); }
    var yl = sv("text", { x: 12, y: mt + 10, "font-size": "11", fill: "var(--text-3)" }, svg); yl.textContent = "perda de percurso (dB)";
    function linha(l, cor, tracejada) { sv("line", { x1: X(x0), y1: Y(l.pl1km + l.n * 10 * x0), x2: X(x1), y2: Y(l.pl1km + l.n * 10 * x1), stroke: cor, "stroke-width": "2", "stroke-dasharray": tracejada ? "6 4" : "0" }, svg); }
    linha(atual, "var(--s4)", true); linha(aj, "var(--s1)", false);
    pontos.forEach(function (p) { sv("circle", { cx: X(Math.log10(p.d)), cy: Y(p.pl), r: "3.5", fill: "var(--s2)", "fill-opacity": "0.75" }, svg); });
    return svg;
  }

  function painel(panel, DATA) {
    var K = DATA.constantes, M = root.LeguaMedicoes; panel.textContent = "";
    if (!S.amb) S.amb = Object.keys(K.envs)[0];
    var saida = el("div"), aviso = el("span", { "class": "sub", role: "status", "aria-live": "polite" });
    function campo(rot, chave, tipo) {
      var inp = el("input", { type: tipo || "text", autocomplete: "off" }); inp.value = S[chave]; inp.setAttribute("aria-label", rot);
      inp.addEventListener("input", function () { S[chave] = tipo === "number" ? (parseFloat(String(inp.value).replace(",", ".")) || 0) : inp.value; calcula(); });
      return el("label", { "class": "field" }, [el("span", { text: rot }), inp]);
    }
    var ta = el("textarea", { rows: "6", style: "width:100%;font:12px monospace", spellcheck: "false", "aria-label": "CSV de medições" }); ta.value = S.csv;
    ta.addEventListener("input", function () { S.csv = ta.value; calcula(); });
    var arq = el("input", { type: "file", accept: ".csv,.txt,text/csv", "aria-label": "Carregar arquivo CSV" });
    arq.addEventListener("change", function () { var f = arq.files && arq.files[0]; if (!f) return; var rd = new FileReader(); rd.onload = function () { S.csv = String(rd.result).slice(0, 2000000); ta.value = S.csv; calcula(); }; rd.readAsText(f); });
    var exemplo = el("button", { type: "button", "class": "btn", id: "med-exemplo", text: "Carregar exemplo sintético" });
    exemplo.addEventListener("click", function () {
      var linhas = ["# EXEMPLO SINTÉTICO (gerado aqui, não é medição)", "distancia_km;rssi_dbm;potencia_dbm"], s = 7, r = function () { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
      [0.2, 0.3, 0.5, 0.8, 1.2, 1.8, 2.5, 3.5, 5, 7].forEach(function (d) { for (var i = 0; i < 3; i++) { var g = (r() + r() + r() - 1.5) * 4; linhas.push(d + ";" + (14 - (112 + 36 * Math.log10(d) + g)).toFixed(1) + ";14"); } });
      S.csv = linhas.join("\n"); ta.value = S.csv; calcula();
    });
    var ambSel = el("select", { "aria-label": "Ambiente a calibrar" }); Object.keys(K.envs).forEach(function (k) { var o = el("option", { value: k, text: K.envs[k].label || k }); if (k === S.amb) o.selected = true; ambSel.appendChild(o); });
    ambSel.addEventListener("change", function () { S.amb = ambSel.value; calcula(); });
    var c1 = el("section", { "class": "card" }, [el("h2", { text: "1. Suas medições de campo" }),
      el("p", { "class": "note", text: "CSV com cabeçalho. Colunas aceitas: distancia_km, rssi_dbm, potencia_dbm, snr_db, pdr (0 a 1 ou %), sf. Para a perda de percurso: distância e RSSI. Para o limiar de cada SF: snr_db, pdr e sf. Colunas de localização (lat, lon, gnss) são recusadas, e nada sai do seu navegador." }),
      el("div", { "class": "form" }, [el("label", { "class": "field", style: "grid-column:1/-1" }, [el("span", { text: "Colar o CSV" }), ta]), el("label", { "class": "field" }, [el("span", { text: "ou carregar arquivo" }), arq]),
        el("label", { "class": "field" }, [el("span", { text: "Ambiente a calibrar" }), ambSel]), campo("Potência de TX padrão (dBm)", "p", "number"), campo("Soma dos ganhos e perdas (dBi − dB)", "ganhos", "number")]),
      el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:8px" }, [exemplo])]);
    var c2 = el("section", { "class": "card" }, [el("h2", { text: "2. Ajuste" }), saida]);
    var c3 = el("section", { "class": "card" }, [el("h2", { text: "3. Gerar o calibracao.json" }), el("p", { "class": "note", text: "O arquivo traz só o que foi ajustado, com a incerteza de cada constante. O importador do simulador o valida e aplica; não substitui a revisão de quem mediu." }),
      el("div", { "class": "form" }, [campo("Identificador", "id"), campo("Data", "data"), campo("Hardware", "hw"), campo("Firmware (tag do núcleo)", "fw")]), el("div", { id: "med-saida" }), aviso]);
    [c1, c2, c3].forEach(function (c) { panel.appendChild(c); });

    var ultimaCal = null;
    function calcula() {
      saida.textContent = ""; var alvo = c3.querySelector("#med-saida"); alvo.textContent = ""; ultimaCal = null;
      if (!S.csv.trim()) { saida.appendChild(el("p", { "class": "note", text: "Cole um CSV ou carregue um arquivo; o ajuste aparece aqui." })); return; }
      var l = M.lerCsv(S.csv);
      if (l.erro) { saida.appendChild(el("p", {}, [el("span", { "class": "pill bad", text: "não leu" }), " " + l.erro])); return; }
      l.avisos.forEach(function (a) { saida.appendChild(el("p", { "class": "note", text: "Atenção: " + a })); });
      var env = K.envs[S.amb], atual = { pl1km: env.pl1km, n: env.n }, aj = null, lim = null;
      var temRssi = l.linhas.some(function (x) { return x.rssi != null; });
      if (temRssi) {
        aj = M.ajustePercurso(l.linhas, { p: S.p, ganhos: S.ganhos });
        if (aj.erro) saida.appendChild(el("p", {}, [el("span", { "class": "pill bad", text: "perda de percurso" }), " " + aj.erro])); else {
          var pts = l.linhas.filter(function (x) { return x.rssi != null; }).map(function (x) { return { d: x.d, pl: (x.p != null ? x.p : S.p) + S.ganhos - x.rssi }; });
          saida.appendChild(el("p", {}, [el("span", { "class": "pill ok", text: "perda de percurso" }), " " + aj.pontos + " medições de " + nf(aj.d_min, 2) + " a " + nf(aj.d_max, 2) + " km"]));
          saida.appendChild(el("div", { "class": "stats" }, [["pl1km", nf(aj.pl1km, 1) + " dB", "± " + nf(aj.se_pl1km, 1) + " · modelo atual " + nf(atual.pl1km, 1)], ["expoente n", nf(aj.n, 2), "± " + nf(aj.se_n, 2) + " · modelo atual " + nf(atual.n, 2)], ["desvio (σ)", nf(aj.sigma, 1) + " dB", "variação em torno da reta"], ["R²", nf(aj.r2, 2), "quanto da variação a reta explica"]].map(function (i) { return el("div", { "class": "stat" }, [el("div", { "class": "v", text: i[1] }), el("div", { "class": "l", text: i[0] + " (" + i[2] + ")" })]); })));
          aj.avisos.forEach(function (a) { saida.appendChild(el("p", { "class": "note", text: "Atenção: " + a })); });
          saida.appendChild(grafico(pts, aj, atual)); saida.appendChild(el("p", { "class": "note", text: "Pontos: medições. Linha azul: ajuste. Linha tracejada: modelo atual do simulador para “" + (env.label || S.amb) + "”." }));
        }
      }
      if (l.linhas.some(function (x) { return x.snr != null && x.pdr != null && x.sf != null; })) {
        lim = M.ajusteLimiar(l.linhas);
        var sfs = Object.keys(lim.porSf);
        if (sfs.length) {
          var t = el("table"), thead = el("thead", {}, [el("tr", {}, ["SF", "Centro (SNR a 50%)", "± erro-padrão", "Inclinação (dB)", "Pontos", "snr_thr novo", "snr_thr atual"].map(function (h) { return el("th", { text: h }); }))]), tb = el("tbody");
          sfs.forEach(function (sf) { var r = lim.porSf[sf]; tb.appendChild(el("tr", {}, [String(sf), nf(r.c, 2), nf(r.se_c, 2), nf(r.s, 2), String(r.pontos), nf(r.c - K.per_offset_db, 2), nf(K.snr_thr[sf], 2)].map(function (v) { return el("td", { text: v }); }))); });
          t.appendChild(thead); t.appendChild(tb); saida.appendChild(el("h3", { text: "Limiar de SNR por SF" })); saida.appendChild(el("div", { "class": "tbl-wrap", style: "overflow-x:auto" }, [t]));
        }
        lim.erros.forEach(function (e) { saida.appendChild(el("p", { "class": "note", text: "Atenção: " + e })); });
      }
      var cal = M.gerarCalibracao({ id: S.id, data: S.data, hardware: S.hw, firmware: S.fw, ambiente: S.amb, percurso: aj && !aj.erro ? aj : null, limiar: lim, perOffsetDb: K.per_offset_db });
      if (cal.erro) { alvo.appendChild(el("p", { "class": "note", text: cal.erro })); return; }
      ultimaCal = JSON.stringify(cal.obj, null, 2);
      var pre = el("textarea", { readonly: "readonly", rows: "10", style: "width:100%;font:12px monospace", "aria-label": "calibracao.json gerado" }); pre.value = ultimaCal;
      var bt = el("button", { type: "button", "class": "btn", id: "med-baixa", text: "Baixar calibracao.json" });
      bt.addEventListener("click", function () { try { var u = URL.createObjectURL(new Blob([ultimaCal], { type: "application/json" })), a = el("a", { href: u, download: "calibracao.json" }); doc.body.appendChild(a); a.click(); doc.body.removeChild(a); setTimeout(function () { URL.revokeObjectURL(u); }, 2000); aviso.textContent = "Arquivo baixado."; } catch (e) { aviso.textContent = "Não foi possível baixar."; } });
      alvo.appendChild(pre); alvo.appendChild(bt);
      alvo.appendChild(el("p", { "class": "note", text: "Para validar e aplicar no simulador: ~/.venvs/legua/bin/python -m simsuite.analysis.calibracao calibracao.json  e  PYTHONPATH=. ~/.venvs/legua/bin/python -m simsuite.run_suite --escala quick --calibracao calibracao.json" }));
    }
    calcula();
  }
  root.LeguaMedicoesUI = { painel: painel, estado: S };
})(typeof window !== "undefined" ? window : this);
