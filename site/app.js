(function () {
  "use strict";
  var DATA = window.LEGUA_DATA;
  var ESC = DATA.escalas, scale = "quick", d = ESC.quick.dados;
  var EST = window.LeguaEstimator.make(DATA.constantes);
  var NS = "http://www.w3.org/2000/svg";

  // ------------------------------------------------------------------ utilidades
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "class") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }
  function sv(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k]; else n.setAttribute(k, attrs[k]);
    });
    if (parent) parent.appendChild(n);
    return n;
  }
  var nf = function (v, dg) {
    return v == null ? "–" : v.toLocaleString("pt-BR", { minimumFractionDigits: dg || 0, maximumFractionDigits: dg == null ? 0 : dg });
  };
  var fmtPdr = function (v) { return v == null ? "–" : nf(v, 3); };
  var fmtMj = function (v) {
    if (v == null) return "–";
    return v >= 10000 ? nf(v / 1000, 1) + " J" : nf(v, 0) + " mJ";
  };
  var fmtS = function (v) { return v == null ? "–" : nf(v, 2) + " s"; };
  var fmtPct = function (v) { return v == null ? "–" : nf(100 * v, 1) + "%"; };
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };

  // Entidades fixas -> cor, traço e marcador (a cor segue a entidade, nunca a posição).
  var CFG = {
    "Légua perfil fixo":       { label: "Légua (perfil fixo)",   short: "Légua fixo",  slot: 1, dash: "",        mk: "circle" },
    "Légua perfil móvel":      { label: "Légua (perfil móvel)",  short: "Légua móvel", slot: 2, dash: "",        mk: "diamond" },
    "Fixo SF10/125 salto (base)":  { label: "SF10/125 salto (base)", short: "SF10 base",   slot: 3, dash: "6 3",     mk: "square" },
    "Fixo SF7/125 salto (rápido)": { label: "SF7/125 salto (rápido)",short: "SF7 rápido",  slot: 4, dash: "2 3",     mk: "triangle" },
    "Fixo SF12/500 digital":       { label: "SF12/500 digital",      short: "SF12/500",    slot: 5, dash: "8 3 2 3", mk: "cross" }
  };
  function cfgSeries(names) {
    return names.filter(function (n) { return CFG[n]; })
      .sort(function (a, b) { return CFG[a].slot - CFG[b].slot; })
      .map(function (n) { return Object.assign({ id: n }, CFG[n]); });
  }
  function ordSeries(labels) {      // séries sem identidade fixa: slots 1..n em ordem
    var mk = ["circle", "square", "triangle", "diamond", "cross"], da = ["", "6 3", "2 3", "8 3 2 3", "1 3"];
    return labels.map(function (l, i) { return { id: l.id, label: l.label, short: l.short || l.label, slot: i + 1, dash: da[i % 5], mk: mk[i % 5] }; });
  }

  // ------------------------------------------------------------------ marcadores e legenda
  function marker(parent, kind, x, y, cls, r) {
    r = r || 4.5;
    var n;
    if (kind === "square") n = sv("rect", { x: x - r, y: y - r, width: 2 * r, height: 2 * r, rx: 1 }, parent);
    else if (kind === "triangle") n = sv("polygon", { points: [x, y - r - 1, x + r + 1, y + r, x - r - 1, y + r].join(" ") }, parent);
    else if (kind === "diamond") n = sv("polygon", { points: [x, y - r - 1, x + r + 1, y, x, y + r + 1, x - r - 1, y].join(" ") }, parent);
    else if (kind === "cross") n = sv("path", { d: "M" + (x - r) + " " + (y - r) + "L" + (x + r) + " " + (y + r) + "M" + (x + r) + " " + (y - r) + "L" + (x - r) + " " + (y + r) }, parent);
    else n = sv("circle", { cx: x, cy: y, r: r }, parent);
    n.setAttribute("class", "mk " + cls);
    if (kind === "cross") { n.setAttribute("class", "ln " + cls); n.setAttribute("fill", "none"); }
    return n;
  }
  function keyIcon(s, w) {
    var svg = sv("svg", { width: w || 22, height: 10, viewBox: "0 0 " + (w || 22) + " 10", "aria-hidden": "true" });
    svg.style.overflow = "visible";
    var l = sv("line", { x1: 0, y1: 5, x2: w || 22, y2: 5 }, svg);
    l.setAttribute("class", "ln s" + s.slot);
    if (s.dash) l.setAttribute("stroke-dasharray", s.dash);
    marker(svg, s.mk, (w || 22) / 2, 5, "s" + s.slot, 3.5);
    return svg;
  }
  function legend(series) {
    if (series.length < 2) return null;
    var box = el("div", { class: "legend", role: "list" });
    series.forEach(function (s) {
      var sp = el("span", { role: "listitem" });
      sp.appendChild(keyIcon(s));
      sp.appendChild(document.createTextNode(s.label));
      box.appendChild(sp);
    });
    return box;
  }

  // ------------------------------------------------------------------ escalas e eixos
  function niceTicks(lo, hi, n) {
    var span = hi - lo || 1, step = Math.pow(10, Math.floor(Math.log10(span / n)));
    var err = (span / n) / step;
    step *= err >= 7 ? 10 : err >= 3 ? 5 : err >= 1.5 ? 2 : 1;
    var t = [], v = Math.ceil(lo / step - 1e-9) * step;
    for (; v <= hi + 1e-9; v += step) t.push(+v.toFixed(10));
    return t;
  }
  function logTicks(lo, hi) {
    var t = [], a = Math.floor(Math.log10(lo)), b = Math.ceil(Math.log10(hi));
    for (var k = a; k <= b; k++) t.push(Math.pow(10, k));
    return t;
  }
  function makeScale(lo, hi, p0, p1, log) {
    if (log) {
      var a = Math.log10(lo), b = Math.log10(hi);
      return function (v) { return p0 + (Math.log10(v) - a) / (b - a) * (p1 - p0); };
    }
    return function (v) { return p0 + (v - lo) / (hi - lo) * (p1 - p0); };
  }
  function domain(vals, log, zero) {
    var v = vals.filter(function (x) { return x != null && isFinite(x) && (!log || x > 0); });
    if (!v.length) return log ? [1, 10] : [0, 1];
    var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v);
    if (log) return [Math.pow(10, Math.floor(Math.log10(lo))), Math.pow(10, Math.ceil(Math.log10(hi)))];
    if (zero) lo = Math.min(0, lo);
    if (hi === lo) hi = lo + 1;
    var pad = (hi - lo) * 0.06;
    return [zero ? lo : lo - pad, hi + pad];
  }

  // ------------------------------------------------------------------ tooltip
  function makeTip(host) {
    var tip = el("div", { class: "tip", role: "status" });
    host.appendChild(tip);
    return {
      show: function (px, py, head, rows) {
        tip.textContent = "";
        tip.appendChild(el("div", { class: "th", text: head }));
        rows.forEach(function (r) {
          var row = el("div", { class: "tr" });
          if (r.series) row.appendChild(keyIcon(r.series, 18)).setAttribute("class", "key");
          row.appendChild(el("span", { class: "tv", text: r.value }));
          row.appendChild(el("span", { class: "tn", text: r.name }));
          tip.appendChild(row);
          if (r.extra) tip.appendChild(el("div", { class: "te", text: r.extra }));
        });
        tip.style.display = "block";
        var w = tip.offsetWidth, h = tip.offsetHeight, W = host.clientWidth;
        var x = px + 14; if (x + w > W) x = px - w - 14; if (x < 0) x = 0;
        var y = clamp(py - h / 2, 0, Math.max(0, host.clientHeight - h));
        tip.style.left = x + "px"; tip.style.top = y + "px";
      },
      hide: function () { tip.style.display = "none"; }
    };
  }

  // ------------------------------------------------------------------ gráfico de linhas
  // o: xs[], series[{id,label,short,slot,dash,mk,vals[]}], yFmt, xFmt, ylog, ymin, ymax, xTitle, yTitle, extra(si,i), aria, hline
  function lineChart(host, o) {
    host.textContent = "";
    var W = Math.max(280, host.clientWidth || 640), H = o.height || 300;
    var multi = o.series.length > 1;
    var m = { l: 54, r: multi ? Math.min(96, W * 0.2) : 16, t: 12, b: o.xTitle ? 46 : 30 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var all = [].concat.apply([], o.series.map(function (s) { return s.vals; }));
    var dm = o.ymin != null && o.ymax != null ? [o.ymin, o.ymax] : domain(all, o.ylog, false);
    var xmin = Math.min.apply(null, o.xs), xmax = Math.max.apply(null, o.xs);
    var X = makeScale(xmin, xmax === xmin ? xmin + 1 : xmax, m.l, m.l + iw, false);
    var Y = makeScale(dm[0], dm[1], m.t + ih, m.t, o.ylog);
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": o.aria || "Gráfico de linhas" });
    host.appendChild(svg);

    var g = sv("g", { class: "grid axis" }, svg);
    (o.ylog ? logTicks(dm[0], dm[1]) : niceTicks(dm[0], dm[1], 5)).forEach(function (t) {
      var y = Y(t); if (y < m.t - 1 || y > m.t + ih + 1) return;
      sv("line", { x1: m.l, x2: m.l + iw, y1: y, y2: y }, g);
      sv("text", { x: m.l - 8, y: y + 4, "text-anchor": "end", text: (o.yTick || o.yFmt)(t) }, g);
    });
    var gx = sv("g", { class: "axis" }, svg);
    var lastX = -1e9;
    o.xs.forEach(function (x) {
      var px = X(x);
      if (px - lastX < 46) return; lastX = px;
      sv("text", { x: px, y: m.t + ih + 16, "text-anchor": "middle", text: (o.xTick || o.xFmt || String)(x) }, gx);
    });
    sv("line", { x1: m.l, x2: m.l + iw, y1: m.t + ih, y2: m.t + ih, class: "base-line" }, svg);
    if (o.xTitle) sv("text", { x: m.l + iw / 2, y: H - 6, "text-anchor": "middle", class: "axis-title", text: o.xTitle }, svg);
    if (o.yTitle) sv("text", { x: 12, y: m.t + ih / 2, "text-anchor": "middle", class: "axis-title", transform: "rotate(-90 12 " + (m.t + ih / 2) + ")", text: o.yTitle }, svg);
    if (o.hline != null) {
      var hy = Y(o.hline.v);
      sv("line", { x1: m.l, x2: m.l + iw, y1: hy, y2: hy, class: "hair" }, svg);
      sv("text", { x: m.l + iw - 2, y: hy - 4, "text-anchor": "end", class: "axis-title", text: o.hline.label }, svg);
    }

    // séries
    var ends = [];
    o.series.slice().sort(function (a, b) { return b.slot - a.slot; }).forEach(function (s) {
      var path = "", pen = false;
      s.vals.forEach(function (v, i) {
        if (v == null || (o.ylog && v <= 0)) { pen = false; return; }
        path += (pen ? "L" : "M") + X(o.xs[i]).toFixed(1) + " " + Y(v).toFixed(1); pen = true;
      });
      var p = sv("path", { d: path, class: "ln s" + s.slot }, svg);
      if (s.dash) p.setAttribute("stroke-dasharray", s.dash);
      if (s.slot === 1 && multi) p.setAttribute("stroke-width", "2.5");
      var last = -1;
      s.vals.forEach(function (v, i) {
        if (v == null || (o.ylog && v <= 0)) return;
        last = i;
        if (o.xs.length <= 14) marker(svg, s.mk, X(o.xs[i]), Y(v), "s" + s.slot, 3.8);
      });
      if (last >= 0) ends.push({ s: s, y: Y(s.vals[last]), x: X(o.xs[last]) });
    });

    // rótulos diretos (<= 5 séries), com afastamento anticolisão
    if (multi && o.series.length <= 5) {
      ends.sort(function (a, b) { return a.y - b.y; });
      for (var i = 1; i < ends.length; i++) ends[i].ly = Math.max(ends[i].y, (ends[i - 1].ly != null ? ends[i - 1].ly : ends[i - 1].y) + 13);
      if (ends.length) ends[0].ly = ends[0].y;
      ends.forEach(function (e) {
        if (e.ly == null) e.ly = e.y;
        sv("text", { x: m.l + iw + 8, y: e.ly + 4, class: "lbl", text: e.s.short }, svg);
      });
    }

    // camada de interação: mira vertical + tooltip único
    var tip = makeTip(host);
    var hair = sv("line", { class: "hair", y1: m.t, y2: m.t + ih, style: "display:none" }, svg);
    var hl = sv("g", {}, svg);
    var plot = sv("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent", class: "plot", tabindex: "0",
      "aria-label": "Ler valores: setas esquerda e direita" }, svg);
    var idx = -1;
    function show(i) {
      idx = i; var x = X(o.xs[i]);
      hair.setAttribute("x1", x); hair.setAttribute("x2", x); hair.style.display = "";
      hl.textContent = "";
      var rows = [];
      o.series.forEach(function (s, si) {
        var v = s.vals[i];
        if (v != null) marker(hl, s.mk, x, Y(v), "s" + s.slot, 5);
        rows.push({ series: s, value: o.yFmt(v), name: s.label, extra: o.extra ? o.extra(si, i) : null });
      });
      rows.sort(function (a, b) { return a.series.slot - b.series.slot; });
      tip.show(x, m.t + ih / 2, (o.xFmt || String)(o.xs[i]), rows);
    }
    function near(px) {
      var best = 0, bd = 1e9;
      o.xs.forEach(function (x, i) { var dd = Math.abs(X(x) - px); if (dd < bd) { bd = dd; best = i; } });
      return best;
    }
    plot.addEventListener("pointermove", function (e) {
      var r = svg.getBoundingClientRect(); show(near((e.clientX - r.left) * W / r.width));
    });
    plot.addEventListener("pointerleave", function () { hair.style.display = "none"; hl.textContent = ""; tip.hide(); });
    plot.addEventListener("focus", function () { show(idx < 0 ? 0 : idx); });
    plot.addEventListener("blur", function () { hair.style.display = "none"; hl.textContent = ""; tip.hide(); });
    plot.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { show(Math.min(o.xs.length - 1, idx + 1)); e.preventDefault(); }
      if (e.key === "ArrowLeft") { show(Math.max(0, idx - 1)); e.preventDefault(); }
    });
  }

  // ------------------------------------------------------------------ gráfico de pontos (linhas = categorias)
  // o: cats[], series[], vals[ci][si], xFmt, xlog, xmin, xmax, extra(ci,si), aria, rowLabelW
  function dotPlot(host, o) {
    host.textContent = "";
    var W = Math.max(300, host.clientWidth || 640);
    var rowH = Math.max(24, 14 + o.series.length * 6), rows = o.cats.length;
    var lw = o.rowLabelW || Math.min(190, W * 0.34);
    var m = { l: lw, r: 18, t: 8, b: 30 };
    var iw = W - m.l - m.r, H = m.t + m.b + rows * rowH;
    var flat = [].concat.apply([], o.vals);
    var dm = domain(flat, o.xlog, false);
    if (o.xmin != null) {
      var mx = Math.max.apply(null, flat.filter(function (x) { return x != null; }));
      dm = [o.xmin, o.xmax != null ? o.xmax : (mx > 0 ? mx * 1.1 : 1)];
    }
    var X = makeScale(dm[0], dm[1], m.l, m.l + iw, o.xlog);
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": o.aria || "Gráfico de pontos" });
    host.appendChild(svg);
    var g = sv("g", { class: "grid axis" }, svg);
    (o.xlog ? logTicks(dm[0], dm[1]) : niceTicks(dm[0], dm[1], 5)).forEach(function (t) {
      var x = X(t); if (x < m.l - 1 || x > m.l + iw + 1) return;
      sv("line", { x1: x, x2: x, y1: m.t, y2: m.t + rows * rowH }, g);
      sv("text", { x: x, y: H - 10, "text-anchor": "middle", text: (o.xTick || o.xFmt)(t) }, g);
    });
    var tip = makeTip(host);
    o.cats.forEach(function (c, ci) {
      var y0 = m.t + ci * rowH, yc = y0 + rowH / 2;
      var vs = o.vals[ci].filter(function (v) { return v != null && (!o.xlog || v > 0); });
      if (ci % 2 === 0) sv("rect", { x: 0, y: y0, width: W, height: rowH, fill: "var(--grid)", opacity: "0.35" }, svg);
      sv("text", { x: m.l - 10, y: yc + 4, "text-anchor": "end", class: "lbl", text: c }, svg);
      if (vs.length > 1) sv("line", { x1: X(Math.min.apply(null, vs)), x2: X(Math.max.apply(null, vs)), y1: yc, y2: yc, class: "rowline" }, svg);
      var n = o.series.length;
      o.series.forEach(function (s, si) {
        var v = o.vals[ci][si]; if (v == null || (o.xlog && v <= 0)) return;
        var yy = yc + (si - (n - 1) / 2) * Math.min(6, (rowH - 10) / n);
        marker(svg, s.mk, X(v), yy, "s" + s.slot, 4.2);
      });
      var hit = sv("rect", { x: 0, y: y0, width: W, height: rowH, fill: "transparent", tabindex: "0", class: "plot",
        "aria-label": c }, svg);
      function show() {
        var rws = o.series.map(function (s, si) {
          return { series: s, value: o.xFmt(o.vals[ci][si]), name: s.label, extra: o.extra ? o.extra(ci, si) : null };
        }).sort(function (a, b) { return a.series.slot - b.series.slot; });
        tip.show(m.l + iw / 2, yc, c, rws);
      }
      hit.addEventListener("pointermove", show); hit.addEventListener("focus", show);
      hit.addEventListener("pointerleave", tip.hide); hit.addEventListener("blur", tip.hide);
    });
  }

  // ------------------------------------------------------------------ cartão com alternância gráfico/tabela
  // spec: title, note, build(host) desenha o gráfico, table() -> {head[], rows[][], num[bool]}
  var live = [];
  function card(spec) {
    var host = el("div", { class: "chart" });
    var tbl = el("div", { class: "tw", hidden: "" });
    var btn = el("button", { class: "btn", type: "button", text: "Tabela", "aria-pressed": "false" });
    var showTable = false, drawn = false;
    function render() {
      if (showTable) return;
      spec.build(host); drawn = true;
    }
    function fillTable() {
      tbl.textContent = "";
      var t = spec.table(), tb = el("table"), th = el("thead"), hr = el("tr");
      t.head.forEach(function (h, i) { hr.appendChild(el("th", { text: h, class: t.num && t.num[i] ? "n" : "" })); });
      th.appendChild(hr); tb.appendChild(th);
      var body = el("tbody");
      t.rows.forEach(function (r) {
        var tr = el("tr");
        r.forEach(function (c, i) { tr.appendChild(el("td", { text: c == null ? "–" : String(c), class: t.num && t.num[i] ? "n" : "" })); });
        body.appendChild(tr);
      });
      tb.appendChild(body); tbl.appendChild(tb);
    }
    btn.addEventListener("click", function () {
      showTable = !showTable;
      btn.setAttribute("aria-pressed", String(showTable)); btn.textContent = showTable ? "Gráfico" : "Tabela";
      if (showTable) { fillTable(); tbl.hidden = false; host.hidden = true; if (lg) lg.hidden = true; }
      else { tbl.hidden = true; host.hidden = false; if (lg) lg.hidden = false; render(); }
    });
    var lg = spec.legend ? spec.legend() : null;
    var node = el("section", { class: "card" }, [
      el("div", { class: "card-head" }, [el("div", {}, [el("h2", { text: spec.title }), spec.note ? el("p", { class: "note", text: spec.note }) : null]), btn]),
      lg, host, tbl
    ]);
    live.push(render);
    node._render = render;
    return node;
  }
  function mount(panel, nodes) {
    live = [];
    panel.textContent = "";
    nodes.forEach(function (n) { if (n) panel.appendChild(n); });
    // desenha depois de inserir no DOM, para ter largura
    panel.querySelectorAll(".card").forEach(function (c) { if (c._render) c._render(); });
    appendDiscussion(panel);
    if (window.LeguaExplica) window.LeguaExplica.anotar(panel);
  }
  function plainTable(head, rows, num) {
    var t = el("table"), th = el("thead"), hr = el("tr");
    head.forEach(function (h, i) { hr.appendChild(el("th", { text: h, class: num && num[i] ? "n" : "" })); });
    th.appendChild(hr); t.appendChild(th);
    var tb = el("tbody");
    rows.forEach(function (r) {
      var tr = el("tr");
      r.forEach(function (c, i) {
        var td = el("td", { class: num && num[i] ? "n" : "" });
        if (c && typeof c === "object" && c.pill) td.appendChild(pill(c.pill, c.text));
        else td.textContent = c == null ? "–" : String(c);
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    return el("div", { class: "tw" }, [t]);
  }
  function pill(kind, text) {   // estado = ícone + texto, nunca só cor
    var icon = kind === "ok" ? "✓" : kind === "bad" ? "✕" : "!";
    return el("span", { class: "pill " + kind }, [el("span", { "aria-hidden": "true", text: icon }), el("span", { text: text })]);
  }
  function tableCard(title, note, head, rows, num) {
    return el("section", { class: "card" }, [el("h2", { text: title }), note ? el("p", { class: "note", text: note }) : null, plainTable(head, rows, num)]);
  }
  function stat(v, l) { return el("div", { class: "stat" }, [el("div", { class: "v", text: v }), el("div", { class: "l", text: l })]); }
  function select(label, opts, val, onchange) {
    var s = el("select");
    opts.forEach(function (o) { var op = el("option", { value: o.v, text: o.t }); if (o.v === val) op.selected = true; s.appendChild(op); });
    s.addEventListener("change", function () { onchange(s.value); });
    return el("label", {}, [document.createTextNode(label), s]);
  }
  function keys(o) { return Object.keys(o); }

  // ------------------------------------------------------------------ painéis
  var st = { campo: { cen: null, met: "pdr", log: true }, mob: {}, malha: { cen: null }, alc: {} };

  function panelCampo(panel) {
    var F = d.F, cens = keys(F);
    if (!st.campo.cen) st.campo.cen = cens[0];
    var cen = st.campo.cen, met = st.campo.met;
    var dists = keys(F[cen]);
    var names = keys(F[cen][dists[0]]);
    var series = cfgSeries(names);
    var field = met === "pdr" ? "pdr" : met === "mj" ? "mj_por_pacote_mediana" : "lat_p95_s";
    series.forEach(function (s) { s.vals = dists.map(function (dd) { var r = F[cen][dd][s.id]; return r ? r[field] : null; }); });
    var xs = dists.map(parseFloat);
    var yfmt = met === "pdr" ? fmtPdr : met === "mj" ? fmtMj : fmtS;
    var useLog = met === "mj" && st.campo.log;
    var ctl = el("div", { class: "controls" }, [
      select("Cenário", cens.map(function (c) { return { v: c, t: c }; }), cen, function (v) { st.campo.cen = v; panelCampo(panel); }),
      select("Métrica", [{ v: "pdr", t: "Taxa de entrega (PDR)" }, { v: "mj", t: "Energia por pacote entregue" }, { v: "lat", t: "Latência p95" }], met,
        function (v) { st.campo.met = v; panelCampo(panel); })
    ]);
    if (met === "mj") ctl.appendChild(select("Eixo", [{ v: "1", t: "Logarítmico" }, { v: "0", t: "Linear" }], useLog ? "1" : "0",
      function (v) { st.campo.log = v === "1"; panelCampo(panel); }));
    var title = { pdr: "Taxa de entrega × distância", mj: "Energia por pacote entregue × distância", lat: "Latência p95 × distância" }[met];
    var node = card({
      title: title + " · " + cen,
      note: "Dois nós, mesmas sementes de canal para todas as configurações. Cada ponto é uma distância simulada (quick).",
      legend: function () { return legend(series); },
      build: function (host) {
        lineChart(host, {
          xs: xs, series: series, yFmt: yfmt, ylog: useLog, ymin: met === "pdr" ? 0 : undefined, ymax: met === "pdr" ? 1.02 : undefined,
          yTick: met === "pdr" ? function (v) { return nf(v, 1); } : yfmt,
          xFmt: function (x) { return nf(x, Number.isInteger(x) ? 0 : 1) + " km"; }, xTick: function (x) { return nf(x, Number.isInteger(x) ? 0 : 1); },
          xTitle: "distância (km)", aria: title + ", " + cen,
          extra: function (si, i) {
            var r = F[cen][dists[i]][series[si].id];
            return r ? "PDR " + fmtPdr(r.pdr) + " · " + r.pacotes + " pacotes · " + r.blocos + " blocos" : null;
          }
        });
      },
      table: function () {
        return { head: ["Distância"].concat(series.map(function (s) { return s.label; })), num: [false].concat(series.map(function () { return true; })),
          rows: dists.map(function (dd, i) { return [dd].concat(series.map(function (s) { return yfmt(s.vals[i]); })); }) };
      }
    });
    mount(panel, [ctl, node, el("p", { class: "sub", text: "Com poucos blocos por ponto (1 a 2 em quick) o intervalo de confiança não é confiável; use a escala full para conclusões." })]);
  }

  function panelMob(panel) {
    var M = d.M, cats = keys(M).filter(function (k) { return k.charAt(0) !== "_"; });
    var names = keys(M[cats[0]].configs), series = cfgSeries(names);
    function vals(f) { return cats.map(function (c) { return series.map(function (s) { var r = M[c].configs[s.id]; return r ? r[f] : null; }); }); }
    var dop = M._doppler || {};
    var stats = el("div", { class: "stats" }, [
      stat(nf(dop.doppler_max_hz, 0) + " Hz", "Doppler máximo (M5)"),
      stat(nf(dop.variacao_max_hz_s, 0) + " Hz/s", "variação máxima na passagem"),
      stat("± " + nf(dop.tolerancia_estatica_125k_hz, 0) + " Hz", "tolerância estática (125 kHz)"),
      stat(nf(dop.tolerancia_dinamica_sf10_125_hz, 1) + " Hz", "tolerância dinâmica SF10/125")
    ]);
    function mk(title, note, f, fmt, log, xmin, xmax) {
      var v = vals(f), labels = cats.map(function (c) { return c.replace(/^M\d\s/, function (s) { return s; }); });
      return card({
        title: title, note: note, legend: function () { return legend(series); },
        build: function (host) {
          dotPlot(host, { cats: labels, series: series, vals: v, xFmt: fmt, xlog: log, xmin: xmin, xmax: xmax, aria: title,
            xTick: f === "pdr" ? function (x) { return nf(x, 1); } : fmt, rowLabelW: 170,
            extra: function (ci, si) { var r = M[cats[ci]].configs[series[si].id]; return r ? M[cats[ci]].ambiente + " · " + M[cats[ci]].velocidade + " · " + r.pacotes + " pacotes" : null; } });
        },
        table: function () {
          return { head: ["Cenário"].concat(series.map(function (s) { return s.label; })), num: [false].concat(series.map(function () { return true; })),
            rows: cats.map(function (c, ci) { return [c].concat(series.map(function (s, si) { return fmt(v[ci][si]); })); }) };
        }
      });
    }
    mount(panel, [stats,
      mk("Taxa de entrega por cenário de mobilidade", "Cada linha é um cenário; os pontos são as configurações. Eixo a partir de 0,3, não de zero.", "pdr", fmtPdr, false, 0.3, 1.02),
      mk("Energia por pacote entregue", "Eixo logarítmico: uma década separa o modo rápido do robusto.", "mj_por_pacote_mediana", fmtMj, true)]);
  }

  function panelAlcance(panel) {
    live = [];
    var modes = d.B2.modos, names = keys(modes);
    var nodes = [el("p", { class: "sub", text: "Curva de taxa de entrega × atenuação do enlace (modelo de PER com centro 2,5 dB acima do limiar do datasheet). A bancada real (B2) substitui estes valores." })];
    var gridHost = el("div", { class: "grid2" });
    var cards = names.map(function (nm) {
      var m = modes[nm], cv = m.curva;
      var s = ordSeries([{ id: nm, label: nm }]); s[0].vals = cv.map(function (p) { return p.pdr; });
      return card({
        title: nm, note: "ToA do DATA " + nf(m.toa_dados_ms, 1) + " ms · perda máx. 90%: " + nf(m.perda_max_90_db, 1) + " dB · 50%: " + nf(m.perda_max_50_db, 1) + " dB",
        build: function (host) {
          lineChart(host, { xs: cv.map(function (p) { return p.atenuacao_db; }), series: s, yFmt: fmtPdr, ymin: 0, ymax: 1.02, height: 220,
            yTick: function (v) { return nf(v, 1); }, xFmt: function (x) { return nf(x, 1) + " dB"; }, xTick: function (x) { return nf(x, 0); },
            xTitle: "atenuação (dB)", aria: "PDR × atenuação, " + nm, hline: { v: 0.9, label: "90%" },
            extra: function (si, i) { return "n = " + cv[i].n + " · IC95 " + fmtPdr(cv[i].ic95[0]) + " a " + fmtPdr(cv[i].ic95[1]); } });
        },
        table: function () { return { head: ["Atenuação (dB)", "PDR", "n", "IC 95%"], num: [true, true, true, false],
          rows: cv.map(function (p) { return [nf(p.atenuacao_db, 1), fmtPdr(p.pdr), p.n, fmtPdr(p.ic95[0]) + " a " + fmtPdr(p.ic95[1])]; }) }; }
      });
    });
    cards.forEach(function (c) { gridHost.appendChild(c); });
    // o grid precisa estar no DOM antes de desenhar
    panel.textContent = ""; panel.appendChild(nodes[0]); panel.appendChild(gridHost);
    cards.forEach(function (c) { c._render(); });
    var b9 = d.B9.falhas_com_ldro_auto, seen = {};
    var rows = b9.filter(function (r) { var k = [r.modo, r.cristal, r.p_dbm].join("|"); if (seen[k]) return false; seen[k] = 1; return true; })
      .map(function (r) { return [r.modo, r.cristal, r.p_dbm + " dBm", nf(r.deriva_hz, 1), nf(r.tolerancia_hz, 1)]; });
    panel.appendChild(el("div", { style: "height:16px" }));
    panel.appendChild(tableCard("B9 · deriva térmica acima da tolerância (LDRO automático)", d.B9.nota,
      ["Modo", "Cristal", "Potência", "Deriva (Hz)", "Tolerância (Hz)"], rows, [false, false, false, true, true]));
    var cad = d.B10.varredura_ms || {};
    panel.appendChild(tableCard("B10 · tempo de CAD (varredura SF7–12)", d.B10.nota, ["Largura de banda", "Varredura completa"],
      keys(cad).map(function (k) { return [k.replace("varredura SF7-12 @", "") + " kHz", nf(cad[k], 1) + " ms"]; }), [false, true]));
    appendDiscussion(panel);
  }

  function panelAcordo(panel) {
    var rows = d.B3.por_perda;
    var s = ordSeries([{ id: "rb", label: "Rollbacks por 100 trocas", short: "Rollbacks" }]);
    s[0].vals = rows.map(function (r) { return r.rollbacks_por_100_trocas; });
    var s2 = ordSeries([{ id: "tv", label: "Validação, mediana" }, { id: "tp", label: "Validação, p95" }]);
    s2[0].vals = rows.map(function (r) { return r.tempo_ate_validar_med_s; });
    s2[1].vals = rows.map(function (r) { return r.tempo_ate_validar_p95_s; });
    var c1 = card({
      title: "B3 · rollbacks por 100 trocas × perda de quadros", note: d.B3.nota,
      build: function (host) { lineChart(host, { xs: rows.map(function (r) { return r.perda; }), series: s, yFmt: function (v) { return v == null ? "–" : nf(v, 1); }, ymin: 0, ymax: 40, height: 240,
        xFmt: function (x) { return fmtPct(x) + " de perda"; }, xTick: function (x) { return nf(100 * x, 0) + "%"; }, xTitle: "perda por quadro", aria: "Rollbacks por 100 trocas",
        extra: function (si, i) { return rows[i].negociacoes + " trocas · " + rows[i].rollbacks + " rollbacks"; } }); },
      table: function () { return { head: ["Perda", "Trocas", "Rollbacks", "Por 100 trocas", "Falhas de negociação", "Validar med. (s)", "Validar p95 (s)", "mJ ctrl/neg.", "Airtime ctrl/neg. (ms)"],
        num: [true, true, true, true, true, true, true, true, true],
        rows: rows.map(function (r) { return [fmtPct(r.perda), r.negociacoes, r.rollbacks, nf(r.rollbacks_por_100_trocas, 1), r.falhas_de_negociacao, nf(r.tempo_ate_validar_med_s, 1), nf(r.tempo_ate_validar_p95_s, 1), nf(r.energia_ctrl_por_neg_mj, 2), nf(r.airtime_ctrl_por_neg_ms, 1)]; }) }; }
    });
    var c2 = card({
      title: "B3 · tempo até validar um modo novo × perda", note: "Mediana e p95, em segundos.", legend: function () { return legend(s2); },
      build: function (host) { lineChart(host, { xs: rows.map(function (r) { return r.perda; }), series: s2, yFmt: fmtS, height: 240,
        xFmt: function (x) { return fmtPct(x) + " de perda"; }, xTick: function (x) { return nf(100 * x, 0) + "%"; }, xTitle: "perda por quadro", aria: "Tempo até validar",
        yTick: function (v) { return nf(v, 0); } }); },
      table: function () { return { head: ["Perda", "Mediana (s)", "p95 (s)"], num: [true, true, true],
        rows: rows.map(function (r) { return [fmtPct(r.perda), nf(r.tempo_ate_validar_med_s, 1), nf(r.tempo_ate_validar_p95_s, 1)]; }) }; }
    });
    var b4 = keys(d.B4);
    var t4 = tableCard("B4 · injeção de falhas", "Nenhum caso terminou com desacordo permanente; o limite superior de 95% é a regra dos três sobre o total de trocas.",
      ["Caso", "Trocas", "Reboots", "Rollbacks", "Episódios de desacordo", "Maior episódio (s)", "Desacordo permanente", "Limite sup. 95%"],
      b4.map(function (k) { var r = d.B4[k]; return [k.replace(/_/g, " "), r.negociacoes, r.reboots, r.rollbacks, r.episodios_desacordo, nf(r.max_episodio_s, 1),
        r.desacordo_permanente === 0 ? { pill: "ok", text: "0" } : { pill: "bad", text: String(r.desacordo_permanente) }, r.limite_sup_95_desacordo_permanente == null ? "–" : fmtPct(r.limite_sup_95_desacordo_permanente)]; }),
      [false, true, true, true, true, true, false, true]);
    var b5 = d.B5.resultados;
    var t5 = tableCard("B5 · rendezvous de nó novo", d.B5.nota, ["Caso", "Média (s)", "p95 (s)", "Máx. (s)", "Ocupação do beacon"],
      keys(b5).map(function (k) { var r = b5[k]; return [k.replace(/_/g, " "), nf(r.media_s, 1), nf(r.p95_s, 1), nf(r.max_s, 1), nf(r["duty_beacon_%"], 1) + "%"]; }), [false, true, true, true, true]);
    var f6 = d.F6, f6rows = [];
    keys(f6).forEach(function (en) { keys(f6[en]).forEach(function (cf) { var r = f6[en][cf]; f6rows.push([en, (CFG[cf] || { label: cf }).label, fmtPdr(r.pdr), nf(r.trocas_por_hora, 2), nf(r.rollbacks_por_hora, 2), r.quedas_base, nf(r.desacordo_s_por_hora, 1), fmtMj(r.mj_por_pacote_mediana)]); }); });
    var t6 = tableCard("F6 · longa duração", "Em enlace marginal (urbano denso) a adaptação oscila, com muitas quedas ao modo base e PDR abaixo do modo fixo; a aba Sintonia (F7) testa como reduzir isso. Poucas sementes: sem intervalo de confiança útil.",
      ["Enlace", "Configuração", "PDR", "Trocas/h", "Rollbacks/h", "Quedas ao base", "Desacordo (s/h)", "mJ/pacote"], f6rows, [false, false, true, true, true, true, true, true]);
    var b6 = d.B6, b6k = keys(b6).filter(function (k) { return k !== "nota"; });
    var t6b = tableCard("B6 · traço de campo reproduzido na bancada", b6.nota, ["Execução", "PDR", "Trocas", "Rollbacks", "Quedas ao base"],
      b6k.map(function (k) { var r = b6[k]; return [k, fmtPdr(r.pdr), r.trocas, r.rollbacks, r.quedas_base]; }), [false, true, true, true, true]);
    mount(panel, [c1, c2, t4, t5, t6, t6b]);
  }

  function panelFormal(panel) {
    var ab = d.formal.ablacoes, mk = d.formal.rodada_markov;
    var names = { referencia: "referência", sem_descida_por_silencio: "sem descida por silêncio", sem_validacao: "sem validação", ancora_no_commit: "âncora no COMMIT", dois_reboots: "dois reboots", teto_assimetrico: "teto assimétrico (B nunca aceita)" };
    var tab = tableCard("Verificação de estados (modelo abstrato, perdas adversárias)",
      "P1: sem desacordo permanente. P2: maior desacordo transitório, em ticks. P3: a recuperação é sempre possível. P4: toda âncora gravada é de um modo em que o par já esteve. Cada linha remove ou altera um mecanismo do protocolo.",
      ["Variante", "Estados", "P1", "P2 (ticks)", "P3", "P4"],
      keys(ab).map(function (k) { var r = ab[k];
        return [names[k] || k, nf(r.estados, 0), r.P1_sem_desacordo_permanente ? { pill: "ok", text: "vale" } : { pill: "bad", text: "viola" },
          r.P2_maior_desacordo_ticks == null ? "–" : r.P2_maior_desacordo_ticks, r.P3_recuperacao_sempre_possivel ? { pill: "ok", text: "vale" } : { pill: "bad", text: "viola" },
          r.P4_ancora_confirmada_pelo_par == null ? "–" : (r.P4_ancora_confirmada_pelo_par ? { pill: "ok", text: "vale" } : { pill: "bad", text: "viola" })]; }),
      [false, true, false, true, false, false]);
    var S = ordSeries([{ id: "F", label: "Fica na configuração nova (F)", short: "Fica em F" }, { id: "deg", label: "Degrada", short: "Degrada" },
      { id: "des", label: "Desacordo transitório", short: "Desacordo" }, { id: "d8", label: "Desacordo > 8 ticks", short: "> 8 ticks" }]);
    var keysM = ["P_F", "P_degradou", "P_houve_desacordo", "P_desacordo_maior_8"];
    S.forEach(function (s, i) { s.vals = mk.map(function (r) { return r[keysM[i]]; }); });
    var chart = card({
      title: "Rodada de aceleração com perda independente por quadro",
      note: "Cadeia de Markov exata sobre o modelo. Ticks até assentar: " + mk.map(function (r) { return nf(r.ticks_esperados, 1); }).join(", ") + " (perda 0 a 0,3).",
      legend: function () { return legend(S); },
      build: function (host) { lineChart(host, { xs: mk.map(function (r) { return r.p_perda; }), series: S, yFmt: fmtPct, ymin: 0, ymax: 1.02,
        yTick: function (v) { return nf(100 * v, 0) + "%"; }, xFmt: function (x) { return nf(100 * x, 0) + "% de perda"; }, xTick: function (x) { return nf(100 * x, 0) + "%"; },
        xTitle: "perda por quadro", aria: "Probabilidades da rodada de aceleração × perda" }); },
      table: function () { return { head: ["Perda"].concat(S.map(function (s) { return s.label; })).concat(["Ticks esperados"]), num: [true, true, true, true, true, true],
        rows: mk.map(function (r, i) { return [fmtPct(r.p_perda)].concat(S.map(function (s) { return fmtPct(s.vals[i]); })).concat([nf(r.ticks_esperados, 1)]); }) }; }
    });
    mount(panel, [tab, chart]);
  }

  function panelValidacao(panel) {
    var x = d.xsim, e = d.equiv, cards = [];
    if (e) {
      var ex = e.exercitado || {};
      cards.push(tableCard("Núcleo C × simulador Python (equivalência)",
        "Mesmos cenários nos quatro pares (Py-Py, C-C, Py-C, C-Py), por bytes reais do formato de fio. Os rastros precisam ser idênticos: quadros byte a byte, trocas de modo, gravações em NVM e estatísticas. Py-C e C-Py provam também a interoperabilidade.",
        ["Medida", "Valor"],
        [["Cenários aleatórios (sementes " + e.sementes[0] + " a " + e.sementes[1] + ")", nf(e.cenarios, 0)], ["Divergências entre os pares", e.divergencias === 0 ? { pill: "ok", text: "0" } : { pill: "bad", text: String(e.divergencias) }],
         ["Eventos comparados", nf(e.eventos_comparados, 0)], ["Trocas de modo negociadas", nf(ex.trocas, 0)], ["Validações que terminaram em rollback", nf(ex.rollbacks, 0)],
         ["Degradações pela escada", nf(ex.degradacoes, 0)], ["Quedas ao modo base", nf(ex.quedas_base, 0)], ["Descidas por silêncio", nf(ex.desc_silencio, 0)],
         ["Votos recusados / negociações falhas", nf(ex.neg_recusa, 0) + " / " + nf(ex.neg_fail, 0)], ["Quadros rejeitados (replay, MIC)", nf(ex.rejeitados, 0)],
         ["Variantes do protocolo", keys(e.variantes).map(function (k) { return k + " " + e.variantes[k]; }).join(", ")]], [false, true]));
    }
    if (x) {
      var pts = x.aloha.pontos;
      var S = ordSeries([{ id: "a", label: "ALOHA puro (analítico)", short: "analítico" }, { id: "l", label: "Regras do LoRaSim (porte)", short: "LoRaSim" }, { id: "q", label: "Simulador desta suíte", short: "aqui" }]);
      var kk = ["pdr_analitico", "pdr_lorasim", "pdr_aqui"];
      S.forEach(function (s, i) { s.vals = pts.map(function (r) { return r[kk[i]]; }); });
      cards.push(card({
        title: "Colisão em estrela: PDR × número de nós",
        note: "SF" + x.aloha.sf + "/" + x.aloha.bw + ", " + x.aloha.payload_B + " B (" + nf(x.aloha.tempo_no_ar_ms, 1) + " ms no ar), um envio a cada " + x.aloha.intervalo_medio_s + " s em média, potências iguais, " + x.aloha.horas_por_semente + " h por semente (3 sementes). O LoRaSim tem uma exceção: o pacote que chega nos últimos símbolos de preâmbulo do outro sobrevive, então perde um pouco menos.",
        legend: function () { return legend(S); },
        build: function (host) { lineChart(host, { xs: pts.map(function (r) { return r.nos; }), series: S, yFmt: fmtPct, ymin: 0.5, ymax: 1.0,
          yTick: function (v) { return nf(100 * v, 0) + "%"; }, xFmt: function (v) { return nf(v, 0) + " nós"; }, xTick: function (v) { return nf(v, 0); },
          xTitle: "nós na estrela", aria: "PDR × número de nós, três modelos" }); },
        table: function () { return { head: ["Nós", "Carga G", "Analítico", "LoRaSim (porte)", "Aqui"], num: [true, true, true, true, true],
          rows: pts.map(function (r) { return [nf(r.nos, 0), nf(r.G, 3), fmtPct(r.pdr_analitico), fmtPct(r.pdr_lorasim), fmtPct(r.pdr_aqui)]; }) }; }
      }));
      var cr = x.captura.resultado;
      cards.push(tableCard("Captura (metade dos nós " + x.captura.diferenca_de_potencia_dB + " dB mais forte)", x.captura.nos + " nós na mesma estrela. O forte sobrevive à sobreposição; o fraco, não.",
        ["Modelo", "PDR dos fortes", "PDR dos fracos"],
        [["LoRaSim (porte)", fmtPct(cr.lorasim.pdr_fortes), fmtPct(cr.lorasim.pdr_fracos)], ["Aqui", fmtPct(cr.aqui.pdr_fortes), fmtPct(cr.aqui.pdr_fracos)]], [false, true, true]));
      var ta = x.tempo_no_ar, sn = x.sensibilidade;
      cards.push(tableCard("Tempo no ar e sensibilidade", "Tempo no ar: " + nf(ta.combinacoes, 0) + " combinações de SF, BW, CR e tamanho; " + (ta.combinacoes_sf_bw_diferentes.length ? "só diferem SF" + ta.combinacoes_sf_bw_diferentes.map(function (c) { return c[0] + "/" + c[1]; }).join(", ") + " (regra do LDRO: a Semtech manda ligar acima de 16 ms; o LoRaSim só liga em 125 kHz com SF11/12)." : "todas iguais."),
        ["SF", "BW (kHz)", "LoRaSim (dBm, SX1272 medido)", "Aqui (dBm, modelo SX1262)", "Diferença (dB)"],
        sn.linhas.filter(function (r) { return r.bw === 125; }).map(function (r) { return [r.sf, r.bw, nf(r.lorasim_dbm, 2), nf(r.aqui_dbm, 2), nf(r.diferenca_db, 2)]; }).concat([["todas as 18", "", "", "média |Δ| " + nf(sn.diferenca_media_abs_db, 2), "máx " + nf(sn.maior_diferenca_db, 2)]]),
        [true, true, true, true, true]));
    }
    var lo = x && x.lorasim_original;
    if (lo && lo.disponivel) {
      var po = lo.pontos;
      cards.push(tableCard("LoRaSim original executado (experimento 0, mesma geometria)",
        lo.referencia + ". " + lo.horas_por_semente + " h por semente (3 sementes), um envio a cada " + lo.intervalo_medio_s + " s em média. " + lo.nota,
        ["Nós", "Carga G", "Analítico", "LoRaSim (original)", "Aqui"],
        po.map(function (r) { return [nf(r.nos, 0), nf(r.G, 3), fmtPct(r.pdr_analitico), fmtPct(r.pdr_original), fmtPct(r.pdr_aqui)]; }), [true, true, true, true, true]));
    }
    var m = x && x.meshtasticator;
    if (m && m.disponivel) {
      var pm = m.aloha.pontos, ta2 = m.tempo_no_ar, sn2 = m.sensibilidade;
      cards.push(tableCard("Meshtasticator (código original executado): camada física",
        m.referencia + ". Tempo no ar: " + nf(ta2.combinacoes, 0) + " combinações nos " + ta2.presets + " presets; " + (ta2.presets_diferentes.length ? "só difere em " + ta2.presets_diferentes.join(", ") + " (regra do LDRO)." : "todas iguais.") + " Regra de captura (6 dB): " + (m.regra_de_captura.iguais ? "igual nos 10 casos testados." : "DIFERE em algum caso.") + " Sensibilidade dos presets: média |Δ| " + nf(sn2.diferenca_media_abs_db, 2) + " dB, máx " + nf(sn2.maior_diferenca_db, 2) + " dB (calculadora com NF 6 dB contra o modelo do SX1262). O roteamento por inundação do Meshtastic não tem equivalente aqui e não foi comparado.",
        ["Nós", "Carga G", "Analítico", "Meshtastic (original)", "Aqui"],
        pm.map(function (r) { return [nf(r.nos, 0), nf(r.G, 3), fmtPct(r.pdr_analitico), fmtPct(r.pdr_meshtastic), fmtPct(r.pdr_aqui)]; }), [true, true, true, true, true]));
    }
    mount(panel, cards);
  }

  function panelSeguranca(panel) {
    var b7 = d.B7, k7 = keys(b7).filter(function (k) { return k !== "nota"; });
    var t7 = tableCard("B7 · segurança", "Replay e quadros forjados são rejeitados sem efeito; o jammer reativo é o caso caro em energia, e o alarme limita os rollbacks.",
      ["Caso", "PDR", "Rollbacks", "Alarmes", "Alarmes MIC", "Rejeitados", "mJ/pacote"],
      k7.map(function (k) { var r = b7[k]; return [k.replace(/_/g, " "), fmtPdr(r.pdr), r.rollbacks, r.alarmes, r.alarmes_mic == null ? "–" : r.alarmes_mic, r.rejeitados, nf(r.energia_por_pacote_mj, 1)]; }), [false, true, true, true, true, true, true]);
    var b11 = d.B11, k11 = keys(b11).filter(function (k) { return k !== "nota"; });
    var t11 = tableCard("B11 · registros de TX contra o perfil BR-2026 (nao_verificado)",
      "O verificador roda sobre o registro de transmissões (o mesmo vale para logs reais). O perfil vem de fonte secundária; isto não é prova de conformidade nem de homologação.",
      ["Fonte", "Resultado no modelo", "Pior ocupação por canal", "Violações"],
      k11.map(function (k) { var r = b11[k], v = r.violacoes, tot = 0, det = [];
        keys(v).forEach(function (x) { tot += v[x]; if (v[x]) det.push(x.replace(/_/g, " ") + " = " + v[x]); });
        return [k.replace("Légua", "Légua"), tot === 0 ? { pill: "ok", text: "sem violações" } : { pill: "bad", text: "viola" }, nf(r.pior_ocupacao_s, 3) + " s", det.join("; ") || "–"]; }),
      [false, false, true, false]);
    mount(panel, [t7, t11]);
  }

  function panelModos(panel) {
    var rows = d.modos.modos;
    mount(panel, [tableCard("Tabela de modos BR-2026 (nao_verificado)", "Ordenada do mais rápido ao mais robusto. Orçamento = teto de potência − sensibilidade (modelo).",
      ["Modo", "Enquadramento", "Teto (dBm)", "ToA de 24 B (ms)", "Orçamento (dB)"],
      rows.map(function (r) { return [r.modo, r.enquadramento, nf(r.teto_dbm, 1), nf(r.toa_dados_ms, 1), nf(r.orcamento_db, 1)]; }), [false, false, true, true, true])]);
  }

  function panelMalha(panel) {
    var T23 = d.T23, T = d.T456, envs = keys(T);
    var nodes = [];
    var rows = [];
    keys(T23).forEach(function (cs) { keys(T23[cs]).forEach(function (pol) { var r = T23[cs][pol];
      rows.push([cs, pol, fmtPdr(r.pdr_grupo), fmtPdr(r.pdr_membro_fraco), nf(r.mj_por_pacote, 1), nf(r["negociacoes_ok_%"], 1) + "%", nf(r.espera_agenda_s, 1)]); }); });
    var t23 = tableCard("T2/T3 · estrela com membro fraco", "Política de decisão do grupo: unanimidade, divisão em subgrupos ou relay.",
      ["Caso", "Política", "PDR do grupo", "PDR do membro fraco", "mJ/pacote", "Negociações ok", "Espera de agenda (s)"], rows, [false, false, true, true, true, true, true]);
    var cen = st.malha.cen && T[st.malha.cen] ? st.malha.cen : envs[0];
    st.malha.cen = cen;
    var tops = keys(T[cen]);
    var ctl = el("div", { class: "controls" }, [select("Ambiente", envs.map(function (e) { return { v: e, t: e.replace(/_/g, " ") }; }), cen, function (v) { st.malha.cen = v; panelMalha(panel); })]);
    var trows = [];
    tops.forEach(function (tp) { keys(T[cen][tp]).forEach(function (stack) { var r = T[cen][tp][stack];
      trows.push([tp, stack, fmtPdr(r.pdr), fmtMj(r.mj_por_pacote), nf(r.airtime_por_pacote_ms, 0) + " ms", fmtS(r.lat_p95_s), nf(r.saltos, 1), nf(r["ocupacao_%"], 1) + "%"]); }); });
    var tmal = tableCard("T4–T6 · malha e baselines (modelos comportamentais)",
      "Meshtastic, MeshCore, Reticulum e LoRaMesher são modelos nossos de comportamento, sem regra regulatória (22 dBm). Não são medições das implementações reais: valide os modelos antes de usar como argumento.",
      ["Topologia", "Pilha", "PDR", "Energia/pacote", "Airtime/pacote", "Latência p95", "Saltos", "Ocupação"], trows, [false, false, true, true, true, true, true, true]);
    mount(panel, [t23, ctl, tmal]);
  }

  function panelPotencia(panel) {
    var P = d.P, dists = keys(P.simetrico), caps = keys(P.simetrico[dists[0]]);
    function cell(r) { return r.pdr < 0.02 ? "sem enlace" : fmtPdr(r.pdr) + " · " + fmtMj(r.mj_por_pacote_mediana); }
    var c1 = tableCard("Teto de TX simétrico (os dois nós com o mesmo teto)", "Ambiente " + P.ambiente.replace(/_/g, " ") + ", " + P.T_h + " h por semente, " + P.sementes.length + " sementes. Cada célula: PDR · mJ por pacote entregue; 'sem enlace' = PDR abaixo de 2%.",
      ["Distância"].concat(caps.map(function (c) { return c + " dBm"; })),
      dists.map(function (dk) { return [dk].concat(caps.map(function (c) { return cell(P.simetrico[dk][c]); })); }), [false].concat(caps.map(function () { return true; })));
    var c2 = tableCard("Teto assimétrico: A com 28 dBm, B com o teto da coluna", "Os dois sentidos usam o mesmo modo; cada nó vota com o próprio teto e o ganho do enlace vale o pior sentido.",
      ["Distância"].concat(caps.map(function (c) { return "B = " + c + " dBm"; })),
      dists.map(function (dk) { return [dk].concat(caps.map(function (c) { return cell(P.assimetrico[dk][c]); })); }), [false].concat(caps.map(function () { return true; })));
    var c3 = tableCard("Controle de potência (teto de 28 dBm nos dois nós)", "Ligado: o protocolo reduz a potência quando sobra margem. Desligado: transmite sempre no teto do modo.",
      ["Distância", "Ligado (PDR · mJ/pacote)", "Desligado (PDR · mJ/pacote)"],
      dists.map(function (dk) { var a = P.controle_de_potencia[dk]; return [dk, cell(a.ligado), cell(a.desligado)]; }), [false, true, true]);
    mount(panel, [c1, c2, c3]);
  }

  function panelMecanismos(panel) {
    var V = d.V, S = d.S;
    function cv(r) { return r.pdr < 0.02 ? "sem enlace" : fmtPdr(r.pdr) + " · " + nf(r.rollbacks_por_hora, 2) + " rb/h"; }
    var cards = [];
    keys(V.k_f).forEach(function (dk) {
      var rows = []; V.k_valid.forEach(function (k) { rows.push(["k = " + k].concat(V.f_valid.map(function (f) { return cv(V.k_f[dk]["k" + k + "/f" + f]); }))); });
      cards.push(tableCard("Janela de validação: ACKs (k) × falhas (f), enlace de " + dk,
        "Ambiente " + V.ambiente.replace(/_/g, " ") + ", " + V.T_h + " h por semente, " + V.sementes.length + " sementes. Cada célula: PDR · rollbacks por hora (inclui os falsos). Padrão do protocolo: k = 3, f = 3.",
        ["k (ACKs para confirmar)"].concat(V.f_valid.map(function (f) { return "f = " + f; })), rows, [false].concat(V.f_valid.map(function () { return true; }))));
    });
    var tv = keys(V.t_valid), tcols = keys(V.t_valid[tv[0]]);
    cards.push(tableCard("Janela de validação: duração da janela", "Mesmo enlace e sementes; k = 3, f = 3. Janela curta demais desfaz modos bons.",
      ["Enlace"].concat(tcols), tv.map(function (dk) { return [dk].concat(tcols.map(function (c) { return cv(V.t_valid[dk][c]); })); }), [false].concat(tcols.map(function () { return true; }))));
    keys(S.celulas).forEach(function (dk) {
      var tss = keys(S.celulas[dk]), apps = keys(S.celulas[dk][tss[0]]);
      cards.push(tableCard("Descida por silêncio: tempo de silêncio × intervalo da aplicação, enlace de " + dk,
        "Cada célula: PDR · quedas ao modo base na rodada inteira. Padrão do protocolo: silêncio de 90 s; o heartbeat sai após 60 s sem tráfego.",
        ["Silêncio (s)"].concat(S.app_s.map(function (a) { return "aplicação a cada " + a + " s"; })),
        tss.map(function (t) { return [t.replace("ts", "") + " s"].concat(apps.map(function (a) { var r = S.celulas[dk][t][a]; return fmtPdr(r.pdr) + " · " + r.quedas_base + " quedas"; })); }),
        [false].concat(apps.map(function () { return true; }))));
    });
    mount(panel, cards);
  }

  /* estresses do cenário X (relógio, perda assimétrica, desvanecimento lento, teto × fade_k): aba própria, separada das varreduras V e S */
  function panelEstresses(panel) {
    var cards = [];
    var X = d.X;
    if (X) {
      function cx(r) { return r.pdr < 0.02 ? "sem enlace" : fmtPdr(r.pdr) + " · " + nf(r.trocas_por_hora, 2) + " trocas/h · " + nf(r.rollbacks_por_hora, 2) + " rb/h"; }
      var cab = "Ambiente " + X.ambiente.replace(/_/g, " ") + ", " + X.dist_km + " km, " + X.T_h + " h por semente, " + X.sementes.length + " sementes. ";
      var rk = keys(X.relogio);
      cards.push(tableCard("Estresse: erro de relógio e cristal", cab + "Erro ppm dos dois nós em sinais opostos. Cada célula: PDR · trocas por hora · rollbacks por hora. O cristal comum a 28 dBm perde tudo por deriva térmica no modelo (B9); a 14 dBm a deriva some.",
        ["Cristal / erro de relógio", "Resultado", "Energia (mJ/pacote)"], rk.map(function (k) { return [k, cx(X.relogio[k]), X.relogio[k].mj_por_pacote_mediana == null ? "–" : nf(X.relogio[k].mj_por_pacote_mediana, 0)]; }), [false, true, true]));
      var ak = keys(X.assimetria);
      cards.push(tableCard("Estresse: perda assimétrica entre os sentidos", cab + "Perda extra só de B para A; A para B fica intacto. Cada célula: PDR · trocas por hora · rollbacks por hora.",
        ["Perda extra B→A", "Resultado", "Desacordo (s/h)"], ak.map(function (k) { return [k, cx(X.assimetria[k]), nf(X.assimetria[k].desacordo_s_por_hora, 1)]; }), [false, true, true]));
      if (X.lento) {
        var lk = keys(X.lento);
        cards.push(tableCard("Estresse: desvanecimento lento independente por sentido", cab + "Cada sentido tem seu próprio desvanecimento lento (média zero, correlação de 10 min); o rótulo é o desvio em dB. Cada célula: PDR · trocas por hora · rollbacks por hora.",
          ["Desvio por sentido", "Resultado", "Desacordo (s/h)"], lk.map(function (k) { return [k, cx(X.lento[k]), nf(X.lento[k].desacordo_s_por_hora, 1)]; }), [false, true, true]));
      }
      var tk = keys(X.teto_fade), fk = keys(X.teto_fade[tk[0]]);
      cards.push(tableCard("Estresse: teto de TX × fade_k", cab + "Teto simétrico e margem extra de aceleração proporcional à variabilidade do SNR (fade_k). Cada célula: PDR · trocas por hora · rollbacks por hora.",
        ["Teto"].concat(fk), tk.map(function (k) { return [k].concat(fk.map(function (f) { return cx(X.teto_fade[k][f]); })); }), [false].concat(fk.map(function () { return true; }))));
    }
    mount(panel, cards);
  }

  var GRUPOS = { L: "Légua", F: "modos fixos", O: "outros" };
  function tetoStats(T, cen, g) {
    // PDR: média sobre as células do grupo. Energia: mediana só das células com enlace (PDR >= 2%) em TODOS os tetos,
    // senão o teto baixo pareceria mais barato só porque perdeu as células longas (viés de sobrevivência).
    var rows = T.cenarios[cen].filter(function (r) { return !g || r.g === g; }), out = {}, comuns = rows.filter(function (r) {
      return T.tetos.every(function (c) { var v = r.v[c]; return v && v[0] >= 0.02 && v[1] != null; }); });
    T.tetos.forEach(function (c) {
      var pd = [], mj = comuns.map(function (r) { return r.v[c][1]; });
      rows.forEach(function (r) { var v = r.v[c]; if (v) pd.push(v[0]); });
      mj.sort(function (a, b) { return a - b; });
      out[c] = { n: pd.length, nc: comuns.length, pdr: pd.length ? pd.reduce(function (a, b) { return a + b; }, 0) / pd.length : null, mj: mj.length ? mj[Math.floor(mj.length / 2)] : null };
    });
    return out;
  }
  function tetoGrupos(T, cen) {          // grupos presentes no cenário; um só grupo = sem rótulo
    var gs = ["L", "F", "O"].filter(function (g) { return T.cenarios[cen].some(function (r) { return r.g === g; }); });
    return gs.length > 1 ? gs : [null];
  }
  function tetoMuda(T, cen) {          // o resultado do cenário muda de verdade com o teto?
    var rows = T.cenarios[cen];
    if (!rows.length) return false;
    return rows.some(function (r) { var v = keys(r.v).map(function (c) { return r.v[c]; });
      var lo = Math.min.apply(null, v.map(function (x) { return x[0]; })), hi = Math.max.apply(null, v.map(function (x) { return x[0]; }));
      var e = v.map(function (x) { return x[1]; }).filter(function (x) { return x != null; });
      return hi - lo > 0.005 || (e.length > 1 && Math.max.apply(null, e) > 1.01 * Math.min.apply(null, e)); });
  }
  function panelTetos(panel) {
    var T = ESC[scale].tetos;
    if (!T) { mount(panel, [el("section", { class: "card warn-card" }, [el("h2", { text: "Sem varredura de teto nesta escala" }),
      el("p", { class: "note", text: "Rode tools/varredura_teto.sh " + scale + " e depois python3 tools/build_site.py." })])]); return; }
    var caps = T.tetos.slice().sort(function (a, b) { return a - b; });
    var todos = keys(T.cenarios), cens = todos.filter(function (c) { return tetoMuda(T, c); }), fixos = todos.filter(function (c) { return cens.indexOf(c) < 0; });
    var sel = st.tet && cens.indexOf(st.tet.cen) >= 0 ? st.tet.cen : cens[0];
    st.tet = { cen: sel };
    var head = ["Cenário"].concat(caps.map(function (c) { return c + " dBm"; }));
    var sum = tableCard("Resumo: PDR médio · energia mediana por pacote, por teto de TX",
      "PDR: média simples sobre todas as células do cenário. Energia: mediana só das células que têm enlace (PDR acima de 2%) em todos os tetos, para comparar as mesmas células (as células longas morrem com teto baixo e sumiriam da conta). Os tetos de 8, 14 e 20 dBm vêm da varredura; 28 dBm é a rodada normal. Teto menor limita todos os nós do cenário. " + (fixos.length ? "Sem diferença entre os tetos (não aparecem abaixo): " + fixos.join(", ") + " — cenários de bancada com teto próprio de 0 ou 10 dBm, tabelas ou modelos de terceiros com potência própria." : ""),
      head, [].concat.apply([], cens.map(function (c) { return tetoGrupos(T, c).map(function (g) { var s = tetoStats(T, c, g);
        return [c + (g ? " · " + GRUPOS[g] : "") + " (" + s[caps[0]].n + " células, " + s[caps[0]].nc + " comparáveis em energia)"].concat(caps.map(function (cp) { var x = s[cp]; return x.pdr == null ? "–" : fmtPdr(x.pdr) + " · " + fmtMj(x.mj); })); }); })), [false].concat(caps.map(function () { return true; })));
    var detail = el("section", { class: "card" }, [el("h2", { text: "Detalhe por célula" })]);
    detail.appendChild(el("div", { class: "controls" }, [select("Cenário", cens.map(function (c) { return { v: c, t: c }; }), sel, function (v) { st.tet.cen = v; panelTetos(panel); })]));
    detail.appendChild(el("p", { class: "note", text: "PDR · mJ por pacote entregue. Células sem entrega aparecem como 'sem enlace'." }));
    detail.appendChild(plainTable(["Célula"].concat(caps.map(function (c) { return c + " dBm"; })),
      T.cenarios[sel].map(function (r) { return [r.k || "(único)"].concat(caps.map(function (cp) { var v = r.v[cp]; return !v ? "–" : v[0] < 0.02 ? "sem enlace" : fmtPdr(v[0]) + (v[1] == null ? "" : " · " + fmtMj(v[1])); })); }),
      [false].concat(caps.map(function () { return true; }))));
    mount(panel, [sum, detail]);
  }

  function panelSintonia(panel) {
    var F7 = d.F7, links = keys(F7), variants = keys(F7[links[0]]);
    var S = ordSeries(links.map(function (l, i) { return { id: l, label: l.charAt(0).toUpperCase() + l.slice(1), short: l }; }));
    function mk(title, note, f, fmt, xmin, xmax) {
      var v = variants.map(function (vn) { return links.map(function (l) { var r = F7[l][vn]; return r ? r[f] : null; }); });
      return card({
        title: title, note: note, legend: function () { return legend(S); },
        build: function (host) {
          dotPlot(host, { cats: variants, series: S, vals: v, xFmt: fmt, xmin: xmin, xmax: xmax, aria: title, rowLabelW: 190,
            xTick: f === "pdr" ? function (x) { return nf(x, 2); } : fmt });
        },
        table: function () { return { head: ["Variante"].concat(S.map(function (s) { return s.label; })), num: [false].concat(S.map(function () { return true; })),
          rows: variants.map(function (vn, i) { return [vn].concat(S.map(function (s, j) { return fmt(v[i][j]); })); }) }; }
      });
    }
    var trows = [];
    links.forEach(function (l) { variants.forEach(function (vn) { var r = F7[l][vn];
      trows.push([l, vn, fmtPdr(r.pdr), fmtMj(r.mj_por_pacote_mediana), nf(r.trocas_por_hora, 2), nf(r.rollbacks_por_hora, 2), r.quedas_base, nf(r.desacordo_s_por_hora, 1)]); }); });
    var intro = el("p", { class: "sub", text: "Achado do F6: em enlace marginal a Légua oscila (muitas quedas ao modo base). Aqui varia-se a margem exigida para acelerar: fixa (8 ou 14 dB) ou somada a k vezes o desvio do SNR (fade_k). A melhora de estabilidade custa energia; não há ganho gratuito." });
    mount(panel, [intro,
      mk("Quedas ao modo base", "Menos é melhor. Soma das sementes simuladas; 0 para o modo fixo.", "quedas_base", function (x) { return x == null ? "–" : nf(x, 0); }, 0, null),
      mk("Desacordo entre os nós (s por hora)", "Menos é melhor.", "desacordo_s_por_hora", function (x) { return x == null ? "–" : nf(x, 1); }, 0, null),
      mk("Energia por pacote entregue", "Menos é melhor. O modo fixo SF10 é a referência.", "mj_por_pacote_mediana", fmtMj),
      tableCard("Todas as métricas", "Escala quick: 1 dia por semente de canal, 2 sementes. Mesmas sementes para todas as variantes.",
        ["Enlace", "Variante", "PDR", "mJ/pacote", "Trocas/h", "Rollbacks/h", "Quedas ao base", "Desacordo (s/h)"], trows, [false, false, true, true, true, true, true, true])]);
  }

  // ------------------------------------------------------------------ escalas: orçamento e comparação
  function fmtDur(sec) {
    sec = Math.round(sec);
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), r = sec % 60;
    return h ? h + " h " + (m < 10 ? "0" : "") + m + " min" : m ? m + " min " + (r < 10 ? "0" : "") + r + " s" : r + " s";
  }
  var CELL_FIELDS = [
    { v: "pdr", t: "Taxa de entrega (PDR)", f: fmtPdr, dg: 3 },
    { v: "mj_por_pacote_mediana", t: "Energia por pacote entregue", f: fmtMj, dg: 0 },
    { v: "quedas_base", t: "Quedas ao modo base", f: function (x) { return x == null ? "–" : nf(x, 0); }, dg: 0 },
    { v: "trocas_por_hora", t: "Trocas por hora", f: function (x) { return x == null ? "–" : nf(x, 2); }, dg: 2 },
    { v: "rollbacks_por_hora", t: "Rollbacks por hora", f: function (x) { return x == null ? "–" : nf(x, 2); }, dg: 2 },
    { v: "desacordo_s_por_hora", t: "Desacordo (s por hora)", f: function (x) { return x == null ? "–" : nf(x, 1); }, dg: 1 }
  ];
  var GROUPS = {
    F: { t: "Campo fixo (F1–F5)", cells: function (D) { var o = []; keys(D.F).forEach(function (sc) { keys(D.F[sc]).forEach(function (dd) { keys(D.F[sc][dd]).forEach(function (cf) { o.push({ k: sc + " · " + dd, c: cf, r: D.F[sc][dd][cf] }); }); }); }); return o; } },
    M: { t: "Mobilidade (M1–M7)", cells: function (D) { var o = []; keys(D.M).filter(function (k) { return k.charAt(0) !== "_"; }).forEach(function (sc) { keys(D.M[sc].configs).forEach(function (cf) { o.push({ k: sc, c: cf, r: D.M[sc].configs[cf] }); }); }); return o; } },
    F6: { t: "Longa duração (F6)", cells: function (D) { var o = []; keys(D.F6).forEach(function (en) { keys(D.F6[en]).forEach(function (cf) { o.push({ k: en, c: cf, r: D.F6[en][cf] }); }); }); return o; } },
    F7: { t: "Sintonia da aceleração (F7)", cells: function (D) { var o = []; keys(D.F7).forEach(function (en) { keys(D.F7[en]).forEach(function (vn) { o.push({ k: en, c: vn, r: D.F7[en][vn] }); }); }); return o; } }
  };
  var cmp = { grp: "F", fld: "pdr", cfg: "Légua perfil fixo" };

  function panelEscalas(panel) {
    var O = DATA.orcamento, nodes = [];
    var q = ESC.quick, fl = ESC.full;
    var st = el("div", { class: "stats" }, [
      stat(fl ? fl.meta.escala ? String(keys(fl.dados).length) + " de " + (keys(fl.dados).length + fl.meta.faltando.length) : "?" : "0", "cenários com resultado na escala longa"),
      stat(fmtDur(O.total.central), "orçamento sequencial da escala longa (--procs 1)"),
      stat(fmtDur(O.total.baixo) + " a " + fmtDur(O.total.alto), "faixa estimada")
    ]);
    nodes.push(st);
    var rows = keys(O.linhas).sort(function (a, b) { return O.linhas[b].central_s - O.linhas[a].central_s; }).map(function (n) {
      var r = O.linhas[n], tem = fl && fl.dados[n] !== undefined;
      return [n, fmtDur(r.quick_s), nf(r.fator, 1) + "×", r.origem,
        r.medido_full_s ? { pill: "ok", text: "medido " + fmtDur(r.medido_full_s) } : fmtDur(r.central_s) + " (" + fmtDur(r.baixo_s) + " a " + fmtDur(r.alto_s) + ")",
        tem ? { pill: "ok", text: "disponível" } : { pill: "warn", text: "não gerado" }];
    });
    nodes.push(tableCard("Orçamento de tempo da escala longa (full)",
      "Tempo ≈ quick × fator de trabalho × contenção, calibrado com cenários da escala longa já medidos (contenção mediana " + nf(O.contencao.mediana, 2) +
      ", de " + nf(O.contencao.min, 2) + " a " + nf(O.contencao.max, 2) + "; medidos: " + (O.contencao.medidos.join(", ") || "nenhum") + "). Um processo por vez, para caber em 4 GB de RAM e disco mecânico.",
      ["Cenário", "Rápida", "Fator", "O que muda (rápida → longa)", "Tempo na escala longa", "Resultado"], rows, [false, true, true, false, true, false]));
    // comparação
    if (!fl) {
      nodes.push(el("section", { class: "card warn-card" }, [el("h2", { text: "Comparação rápida × longa" }), el("p", { class: "note", text: "Ainda não há resultados da escala longa. Para gerar: python3 -m simsuite.run_suite --escala full --procs 1 && python3 tools/build_site.py" })]));
      mount(panel, nodes); return;
    }
    var have = keys(GROUPS).filter(function (g) { return q.dados[g] && fl.dados[g]; });
    if (!have.length) {
      nodes.push(el("section", { class: "card warn-card" }, [el("h2", { text: "Comparação rápida × longa" }), el("p", { class: "note", text: "A escala longa ainda não tem F, M, F6 ou F7 para comparar com a rápida." })]));
      mount(panel, nodes); return;
    }
    if (have.indexOf(cmp.grp) < 0) cmp.grp = have[0];
    var G = GROUPS[cmp.grp], fld = CELL_FIELDS.filter(function (x) { return x.v === cmp.fld; })[0] || CELL_FIELDS[0];
    var cq = G.cells(q.dados), cf = G.cells(fl.dados);
    var cfgs = []; cq.forEach(function (c) { if (cfgs.indexOf(c.c) < 0) cfgs.push(c.c); });
    var cfgFilter = cfgs.indexOf(cmp.cfg) >= 0 ? cmp.cfg : "*";
    var idx = {}; cf.forEach(function (c) { idx[c.k + "|" + c.c] = c; });
    var pairs = cq.filter(function (c) { return cfgFilter === "*" || c.c === cfgFilter; }).map(function (c) {
      var o = idx[c.k + "|" + c.c]; return { k: c.k, c: c.c, a: c.r[fld.v], b: o ? o.r[fld.v] : null, ra: c.r, rb: o ? o.r : null };
    });
    var ctl = el("div", { class: "controls" }, [
      select("Grupo", have.map(function (g) { return { v: g, t: GROUPS[g].t }; }), cmp.grp, function (v) { cmp.grp = v; panelEscalas(panel); }),
      select("Métrica", CELL_FIELDS.map(function (x) { return { v: x.v, t: x.t }; }), cmp.fld, function (v) { cmp.fld = v; panelEscalas(panel); }),
      select("Configuração", [{ v: "*", t: "Todas" }].concat(cfgs.map(function (c) { return { v: c, t: (CFG[c] || { label: c }).label }; })), cfgFilter, function (v) { cmp.cfg = v; panelEscalas(panel); })
    ]);
    var S = ordSeries([{ id: "q", label: "Rápida (quick)" }, { id: "f", label: "Longa (full)" }]);
    var table = card({
      title: "Rápida × longa · " + G.t + " · " + fld.t,
      note: "Pontos iguais nas duas escalas indicam resultado estável; afastamento mostra o efeito de mais tempo simulado e mais sementes. Δ = longa − rápida.",
      legend: function () { return legend(S); },
      build: function (host) {
        var ps = pairs.slice(0, 60);
        dotPlot(host, { cats: ps.map(function (p) { return (cfgFilter === "*" ? p.k + " · " + ((CFG[p.c] || { short: p.c }).short) : p.k); }), series: S,
          vals: ps.map(function (p) { return [p.a, p.b]; }), xFmt: fld.f, rowLabelW: 230, aria: "Comparação das escalas",
          extra: function (ci, si) { var r = si ? ps[ci].rb : ps[ci].ra; return r ? r.pacotes + " pacotes · " + r.blocos + " blocos" : null; } });
        if (pairs.length > 60) host.appendChild(el("p", { class: "note", text: "Mostrando 60 de " + pairs.length + " linhas; filtre por configuração. A tabela tem todas." }));
      },
      table: function () { return { head: ["Item", "Configuração", "Rápida", "Longa", "Δ", "Blocos (rápida/longa)"], num: [false, false, true, true, true, true],
        rows: pairs.map(function (p) { return [p.k, (CFG[p.c] || { label: p.c }).label, fld.f(p.a), fld.f(p.b), p.a != null && p.b != null ? nf(p.b - p.a, fld.dg + 1) : "–", p.ra.blocos + " / " + (p.rb ? p.rb.blocos : "–")]; }) }; }
    });
    nodes.push(ctl, table);
    mount(panel, nodes);
  }

  // ------------------------------------------------------------------ estimativas do setup
  var PRESETS = {
    custom: { t: "Personalizado", env: "urbano_residencial", d: 2.0, off: 0, sim: null },
    F1: { t: "F1 urbano denso", env: "urbano_denso", d: 1.0, off: 0, sim: "F1 urbano denso" },
    F2: { t: "F2 urbano residencial", env: "urbano_residencial", d: 3.0, off: 0, sim: "F2 urbano residencial" },
    F3: { t: "F3 indoor-outdoor", env: "urbano_residencial", d: 0.5, off: -15, sim: "F3 indoor-outdoor" },
    F4: { t: "F4 rural aberto (mastro 8 m)", env: "rural_aberto", d: 14, off: 8.5, sim: "F4 rural aberto (mastro 8 m)" },
    F5: { t: "F5 rural com relevo/mata", env: "rural_serra", d: 4, off: 0, sim: "F5 rural com relevo/mata" }
  };
  var SIMCFG = { "10|125|1|1": "Fixo SF10/125 salto (base)", "7|125|1|1": "Fixo SF7/125 salto (rápido)", "12|500|1|0": "Fixo SF12/500 digital" };
  var plan = { preset: "F1", env: "urbano_denso", d: 1.0, off: 0, sf: 10, bw: 125, cr: 1, p: 28, retries: 3, interval: 60, load: 1, target: 0.95, sig: "0", perfil: "padrao", hull: 0 };
  var PLAN0 = JSON.parse(JSON.stringify(plan));            // para “Restaurar padrões”

  function fld(label, ctl, valNode) {
    return el("label", { class: "field" }, [el("span", {}, [document.createTextNode(label + ": "), valNode || null]), ctl]);
  }
  function rng(min, max, step, key, fmt, redraw) {
    var inp = el("input", { type: "range", min: min, max: max, step: step, value: plan[key] }), out = el("span", { class: "val", text: fmt(plan[key]) });
    inp.addEventListener("input", function () { plan[key] = parseFloat(inp.value); out.textContent = fmt(plan[key]); redraw(); });
    return fld(label_of[key], inp, out);
  }
  var label_of = { d: "Distância", off: "Ganho extra (mastro +, parede −)", p: "Potência de TX", retries: "Retransmissões", interval: "Intervalo entre pacotes", load: "Tráfego de terceiros (× do ambiente)", target: "Entrega confirmada alvo" };


  // ---- estado do estimador no fragmento da URL (#estimativas/full?d=1.2&sf=10...), exportação e cópia.
  // Tudo local: nada é enviado a lugar nenhum; o fragmento da URL não vai ao servidor.
  var PLAN_KEYS = ["preset", "env", "d", "off", "sf", "bw", "cr", "p", "retries", "interval", "load", "target", "sig", "perfil", "hull"];
  function planQuery() {
    return PLAN_KEYS.map(function (k) { return k + "=" + encodeURIComponent(String(plan[k])); }).join("&");
  }
  function planFromQuery(q) {                // valida cada campo; o que não for válido fica como está
    var m = {};
    String(q || "").split("&").forEach(function (kv) { var i = kv.indexOf("="); if (i > 0) { try { m[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1)); } catch (e) { /* ignora */ } } });
    function num(k, lo, hi) { var v = parseFloat(m[k]); if (isFinite(v) && v >= lo && v <= hi) plan[k] = v; }
    function one(k, ok) { if (m[k] !== undefined && ok.indexOf(m[k]) >= 0) plan[k] = m[k]; }
    function oneNum(k, ok) { var v = parseFloat(m[k]); if (ok.indexOf(v) >= 0) plan[k] = v; }
    one("preset", keys(PRESETS)); one("env", keys(DATA.constantes.envs));
    num("d", 0.05, 40); num("off", -25, 15); num("p", -9, 28); num("retries", 0, 6); num("interval", 1, 600);
    num("load", 0, 3); num("target", 0.5, 0.999); num("hull", 0, 1);
    oneNum("sf", [7, 8, 9, 10, 11, 12]); oneNum("bw", [125, 250, 500]); oneNum("cr", [1, 2, 3, 4]);
    one("sig", ["-1", "0", "1", "2"]); one("perfil", ["padrao", "estavel", "cauteloso"]);
  }
  function syncHash() {
    if (!curTab || curTab.id !== "estimativas") return;
    try { history.replaceState(null, "", "#estimativas" + (scale === "full" ? "/full" : "") + "?" + planQuery()); } catch (e) { /* ignore */ }
  }
  function baixar(nome, tipo, texto) {
    try {
      var url = URL.createObjectURL(new Blob([texto], { type: tipo })), a = el("a", { href: url, download: nome });
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
      return true;
    } catch (e) { return false; }
  }
  function copiar(texto, aviso) {
    function fim(ok) { aviso.textContent = ok ? "Copiado." : "Não foi possível copiar; selecione o texto abaixo."; }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texto).then(function () { fim(true); }, function () { fim(false); });
    else { var t = el("textarea", { readonly: "readonly" }); t.value = texto; document.body.appendChild(t); t.select(); var ok = false; try { ok = document.execCommand("copy"); } catch (e) { /* ignore */ } document.body.removeChild(t); fim(ok); }
  }
  function csvCell(v) { var t = v == null ? "" : String(v); return /[;"\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t; }
  function csvDe(head, rows) { return [head].concat(rows).map(function (r) { return r.map(csvCell).join(";"); }).join("\r\n") + "\r\n"; }
  function nomeModo(r) { return "SF" + r.sf + "/" + r.bw + (r.cr > 1 ? "/CR4" + (r.cr + 4) : "") + (r.fhss ? "/FH" : ""); }

  function panelEstimativas(panel) {
    var host = el("div");
    function simFor() {
      var P = PRESETS[plan.preset]; if (!P || !P.sim || plan.env !== P.env || plan.off !== P.off) return null;
      var cfg = SIMCFG[[plan.sf, plan.bw, plan.cr, plan.bw < 500 ? 1 : 0].join("|")]; if (!cfg) return null;
      var sc = ["full", "quick"].filter(function (k) { return ESC[k] && ESC[k].dados.F && ESC[k].dados.F[P.sim]; })[0];
      if (!sc) return null;
      var tab = ESC[sc].dados.F[P.sim], pts = keys(tab).map(function (k) { var r = tab[k][cfg]; return r ? { d: parseFloat(k), pdr: r.pdr, mj: r.mj_por_pacote_mediana } : null; }).filter(Boolean);
      return { scale: sc, cfg: cfg, pts: pts, caveat: plan.p !== 28 };
    }
    function draw() {
      host.textContent = "";
      var fhss = plan.bw < 500;
      var o = { env: plan.env, d_km: plan.d, sf: plan.sf, bw: plan.bw, cr: plan.cr, p_dbm: plan.p, fhss: fhss, retries: plan.retries,
        interval_s: plan.interval, offset_db: plan.off, load: plan.load };
      var e = EST.estimate(o), ref = e.cenarios[1], sig = parseFloat(plan.sig);
      var r90 = EST.rangeKm(o, 0.9, 0.0), r90b = EST.rangeKm(o, 0.9, 1.0);
      var cards = el("div", { class: "stats" }, [
        stat(nf(e.toa_dados_ms, 1) + " ms", "tempo no ar do DATA (24 B)"),
        stat(nf(e.margem_db, 1) + " dB", "margem do enlace típico (RX " + nf(e.rx_tipico_dbm, 1) + " dBm, sens. " + nf(e.sens_dbm, 1) + " dBm)"),
        stat(r90 == null ? "< 0,02 km" : nf(r90, r90 < 10 ? 2 : 1) + " km", "alcance com 90% confirmado (enlace típico)"),
        stat(r90b == null ? "< 0,02 km" : nf(r90b, r90b < 10 ? 2 : 1) + " km", "idem, enlace com +1σ de perda"),
        stat(nf(e.duty_pct, 2) + "%", "ocupação de tempo no ar (" + nf(e.airtime_hora_s, 1) + " s/h)"),
        stat(nf(e.energia_dia_j, 1) + " J", "energia de TX por dia (só transmissão)")
      ]);
      var dw = el("p", { class: "sub" }, [e.dwell_ok ? pill("ok", "cabe na ocupação de 0,4 s por canal") : pill("bad", "passa de 0,4 s por canal com salto"),
        document.createTextNode("  (regra do perfil BR-2026, nao_verificado)")]);
      var lab = ["Enlace favorável (−1σ de perda)", "Enlace típico (mediana)", "Enlace desfavorável (+1σ)", "Enlace muito desfavorável (+2σ)"];
      var rows = e.cenarios.map(function (c, i) { return [lab[i], fmtPct(c.entregue), fmtPct(c.confirmado), nf(c.tentativas, 2), fmtMj(c.energia_mj_entregue), fmtS(c.latencia_s)]; });
      var m = e.media_enlaces; rows.push(["Média entre enlaces", fmtPct(m.entregue), fmtPct(m.confirmado), nf(m.tentativas, 2), fmtMj(m.entregue > 1e-9 ? m.energia_mj_pacote / m.entregue : null), "–"]);
      var t1 = tableCard("Estimativa para o setup", "Cada linha é um enlace com sombreamento estático diferente (σ = " + nf(K_env().sigma_static, 1) + " dB no ambiente). \"Entregue\": o receptor ouviu o DATA; \"confirmada\": o emissor recebeu o ACK. Retransmissões: " + plan.retries + ".",
        ["Situação do enlace", "Entregue", "Confirmada", "Tentativas por pacote", "Energia por pacote entregue", "Latência média"], rows, [false, true, true, true, true, true]);
      // curva distância
      var sim = simFor();
      var dmax = Math.max(r90b || 0.1, r90 || 0.1) * 2.2, xs = [], i;
      if (sim) sim.pts.forEach(function (p) { dmax = Math.max(dmax, p.d * 1.05); });
      for (i = 0; i < 28; i++) xs.push(0.05 * Math.pow(dmax / 0.05, i / 27));
      var sims = sim ? sim.pts.map(function (p) { return p.d; }) : [];
      var allx = xs.concat(sims).sort(function (a, b) { return a - b; });
      function curve(sg) { return allx.map(function (dd) { var c = {}; Object.keys(o).forEach(function (k) { c[k] = o[k]; }); c.d_km = dd; return EST.estimateOne(c, sg).entregue; }); }
      var S = ordSeries([{ id: "a", label: "Estimativa, enlace típico", short: "típico" }, { id: "b", label: "Estimativa, +1σ de perda", short: "+1σ" }, { id: "c", label: "Estimativa, −1σ de perda (enlace favorável)", short: "−1σ" }].concat(sim ? [{ id: "s", label: "Simulação (" + (sim.scale === "full" ? "longa" : "rápida") + ")", short: "simulação" }] : []).concat(plan.hull ? [{ id: "m", label: "Melhor modo da tabela em cada distância (limite que a adaptação alcança)", short: "melhor modo" }] : []));
      var iH = plan.hull ? S.length - 1 : -1;
      S[0].vals = curve(0.0); S[1].vals = curve(1.0); S[2].vals = curve(-1.0);
      if (plan.hull) S[iH].vals = allx.map(function (dd) {      // melhor modo fixo em cada distância: menor energia que atinge o alvo; senão, o de maior entrega confirmada
        var best = null, bestOk = null;
        EST.modeList().forEach(function (m) {
          var c = {}; Object.keys(o).forEach(function (k) { c[k] = o[k]; }); c.d_km = dd; c.sf = m.sf; c.bw = m.bw; c.cr = m.cr; c.fhss = m.fhss;
          var r = EST.estimateOne(c, 0.0);
          if (!best || r.confirmado > best.confirmado) best = r;
          if (r.confirmado >= plan.target && r.energia_mj_entregue != null && (!bestOk || r.energia_mj_entregue < bestOk.energia_mj_entregue)) bestOk = r;
        });
        return (bestOk || best).entregue;
      });
      if (sim) S[3].vals = allx.map(function (dd) { var p = sim.pts.filter(function (q) { return q.d === dd; })[0]; return p ? p.pdr : null; });
      if (sim) { S[3].dash = "1 5"; S[3].mk = "diamond"; }
      var chart = card({
        title: "Entrega do receptor × distância", note: "Mesmo modo e potência; linhas calculadas ao vivo" + (sim ? ". Pontos: simulação de " + sim.cfg + " em " + PRESETS[plan.preset].t + ", escala " + (sim.scale === "full" ? "longa" : "rápida") + (sim.caveat ? " (a simulação usa 28 dBm; a estimativa usa " + plan.p + " dBm)" : "") + "." : "."),
        legend: function () { return legend(S); },
        build: function (h) { lineChart(h, { xs: allx, series: S, yFmt: fmtPdr, ymin: 0, ymax: 1.02, yTick: function (v) { return nf(v, 1); }, xFmt: function (x) { return nf(x, x < 1 ? 2 : 1) + " km"; },
          xTick: function (x) { return nf(x, x < 10 ? 1 : 0); }, xTitle: "distância (km)", aria: "Entrega estimada × distância", hline: { v: 0.9, label: "90%" }, height: 280 }); },
        table: function () { return { head: ["Distância (km)", "Típico", "+1σ", "−1σ"].concat(sim ? ["Simulação"] : []).concat(plan.hull ? ["Melhor modo"] : []), num: [true, true, true, true, true, true],
          rows: allx.map(function (dd, j) { return [nf(dd, 2), fmtPdr(S[0].vals[j]), fmtPdr(S[1].vals[j]), fmtPdr(S[2].vals[j])].concat(sim ? [fmtPdr(S[3].vals[j])] : []).concat(plan.hull ? [fmtPdr(S[iH].vals[j])] : []); }) }; }
      });
      // ranking de modos
      var rk = EST.rankModes(o, plan.target, sig), sel = rk.good.slice(0, 6);
      var rrows = (sel.length ? sel : []).map(function (r, j) { return [j + 1, "SF" + r.sf + "/" + r.bw + (r.cr > 1 ? "/CR4" + (r.cr + 4) : "") + (r.fhss ? "/FH" : ""), fmtPct(r.confirmado), fmtMj(r.energia_mj_entregue), fmtS(r.latencia_s)]; });
      var t2 = tableCard("Modos que atingem " + fmtPct(plan.target) + " de entrega confirmada neste setup", sel.length ? "Ordenados pela menor energia por pacote entregue (enlace " + ({ "-1": "favorável", "0": "típico", "1": "desfavorável (+1σ)", "2": "muito desfavorável (+2σ)" })[plan.sig] + "; potência de " + plan.p + " dBm). Modos fixos; a Légua negocia entre eles em campo." : "Nenhum modo da tabela BR-2026 atinge o alvo nesta distância e potência: aumente a potência, o ganho, ou reduza a distância.",
        ["#", "Modo", "Entrega confirmada", "Energia por entregue", "Latência média"], rrows, [true, false, true, true, true]);
      // comparação com simulação
      var t3 = null;
      if (sim) {
        var cr = sim.pts.map(function (p) { var c = {}; Object.keys(o).forEach(function (k) { c[k] = o[k]; }); c.d_km = p.d; var a = EST.estimate(c);
          return [nf(p.d, p.d < 1 ? 1 : 0) + " km", fmtPdr(p.pdr), fmtPdr(a.cenarios[1].entregue), fmtPdr(a.media_enlaces.entregue), fmtMj(p.mj), fmtMj(a.cenarios[1].energia_mj_entregue)]; });
        t3 = tableCard("Estimativa × simulação (" + (sim.scale === "full" ? "escala longa" : "escala rápida") + ")", "A simulação usa poucos enlaces (sombreamento estático sorteado por semente), então fica entre o típico e a média; as diferenças maiores aparecem perto do limite de alcance. Não é validação em campo.",
          ["Distância", "PDR simulado", "PDR estimado (típico)", "PDR estimado (média)", "mJ simulado", "mJ estimado (típico)"], cr, [false, true, true, true, true, true]);
      }
      var warn = el("section", { class: "card warn-card" }, [el("p", { class: "note", text: "Isto é um estimador analítico do enlace (um modo fixo, DATA/ACK com retransmissão), calculado no navegador com o mesmo canal e a mesma curva de demodulação da simulação. Não inclui colisão entre os dois nós, CAD/LBT, salto sincronizado nem a negociação de modo; parâmetros estimados, sem medição em hardware. Contra o simulador de eventos, com sombreamento estático controlado, a entrega estimada erra 1,1 ponto percentual em média (máximo 4,9; 42 pontos); energia e latência não foram comparadas ponto a ponto. Serve para comparar setups e dimensionar, não para prever o campo." })]);
      var alvo = plan.target, tip = e.cenarios[1], melhor = rk.good[0];
      var linha = "Neste setup (" + nomeModo({ sf: plan.sf, bw: plan.bw, cr: plan.cr, fhss: fhss }) + ", " + plan.p + " dBm, " + nf(plan.d, 2) + " km, " + K_env().label + ") o enlace típico tem margem de " + nf(e.margem_db, 1) + " dB e entrega confirmada de " + fmtPct(tip.confirmado) +
        (melhor ? ". O modo de menor energia que atinge " + fmtPct(alvo) + " é " + nomeModo(melhor) + " (" + fmtMj(melhor.energia_mj_entregue) + " por pacote entregue)." : ". Nenhum modo da tabela atinge " + fmtPct(alvo) + " neste enlace.");
      var resumo = ["Légua, estimativa analítica (não é previsão de campo; parâmetros estimados)", linha,
        "Parâmetros: ambiente " + plan.env + "; " + nf(plan.d, 2) + " km; ganho extra " + nf(plan.off, 1) + " dB; SF" + plan.sf + "/" + plan.bw + "/CR4" + (plan.cr + 4) + "; " + plan.p + " dBm; " + plan.retries + " retransmissões; pacote a cada " + plan.interval + " s; tráfego de terceiros " + nf(plan.load, 1) + "×.",
        "Típico: entregue " + fmtPct(tip.entregue) + ", confirmada " + fmtPct(tip.confirmado) + ", energia " + fmtMj(tip.energia_mj_entregue) + ", latência " + fmtS(tip.latencia_s) + ".",
        "Alcance com 90% confirmado: " + (r90 == null ? "< 0,02 km" : nf(r90, 2) + " km") + " (típico), " + (r90b == null ? "< 0,02 km" : nf(r90b, 2) + " km") + " (+1σ).",
        "Escala dos dados: " + (scale === "full" ? "longa" : "rápida") + "; gerado em " + DATA.meta.gerado_em + (DATA.meta.commit ? "; commit " + DATA.meta.commit : "") + ".",
        location.href.split("#")[0] + "#estimativas" + (scale === "full" ? "/full" : "") + "?" + planQuery()].join("\n");
      var aviso = el("span", { class: "sub", role: "status", "aria-live": "polite" });
      function btn(txt, fn) { var b = el("button", { type: "button", class: "btn", text: txt }); b.addEventListener("click", fn); return b; }
      var tags = ["Típico", "+1σ", "−1σ"];
      var decisao = el("section", { class: "card decisao" }, [el("h2", { text: "Resposta para este setup" }),
        el("p", {}, [pill(tip.confirmado >= alvo ? "ok" : "bad", tip.confirmado >= alvo ? "atinge o alvo no enlace típico" : "não atinge o alvo no enlace típico"), document.createTextNode(" " + linha)]),
        el("div", { class: "controls sem-impressao" }, [
          btn("Copiar resumo e link", function () { copiar(resumo, aviso); }),
          btn("Baixar CSV (modos)", function () {
            var csv = csvDe(["modo", "entrega_confirmada", "energia_mj_por_entregue", "latencia_s", "atinge_alvo"],
              rk.rows.map(function (r) { return [nomeModo(r), r.confirmado == null ? "" : r.confirmado.toFixed(4), r.energia_mj_entregue == null ? "" : r.energia_mj_entregue.toFixed(2), r.latencia_s == null ? "" : r.latencia_s.toFixed(2), r.ok ? "sim" : "nao"]; }));
            aviso.textContent = baixar("legua-modos.csv", "text/csv;charset=utf-8", "\ufeff" + csv) ? "CSV baixado." : "Não foi possível baixar.";
          }),
          btn("Baixar CSV (curva)", function () {
            var csv = csvDe(["distancia_km", "entregue_tipico", "entregue_mais_1sigma", "entregue_menos_1sigma"], allx.map(function (dd, j) { return [dd.toFixed(3), S[0].vals[j].toFixed(4), S[1].vals[j].toFixed(4), S[2].vals[j].toFixed(4)]; }));
            aviso.textContent = baixar("legua-curva.csv", "text/csv;charset=utf-8", "\ufeff" + csv) ? "CSV baixado." : "Não foi possível baixar.";
          }),
          btn("Baixar JSON", function () {
            var js = JSON.stringify({ aviso: "Estimativa analítica; parâmetros estimados; não é previsão de campo nem prova de conformidade regulatória.", gerado_em: DATA.meta.gerado_em, commit: DATA.meta.commit || null, escala_dos_dados: scale,
              parametros: o, estimativa: { margem_db: e.margem_db, toa_dados_ms: e.toa_dados_ms, duty_pct: e.duty_pct, energia_dia_j: e.energia_dia_j, cenarios: e.cenarios, media_enlaces: e.media_enlaces, alcance90_km: { tipico: r90, mais1sigma: r90b } },
              ranking_modos: rk.rows.map(function (r) { return { modo: nomeModo(r), confirmado: r.confirmado, energia_mj_entregue: r.energia_mj_entregue, latencia_s: r.latencia_s, atinge_alvo: r.ok }; }) }, null, 2);
            aviso.textContent = baixar("legua-estimativa.json", "application/json", js) ? "JSON baixado." : "Não foi possível baixar.";
          }),
          btn("Imprimir", function () { window.print(); }),
          el("a", { class: "btn", href: "enlace.html#" + ["env", "d", "sf", "bw", "cr", "p", "retries", "interval", "load"].map(function (k) { return (k === "d" ? "d" : k) + "=" + encodeURIComponent(String(plan[k])); }).join("&"), text: "Meu enlace fecha? (testador de terreno)" }), aviso])]);
      syncHash();
      var perfilCard = null;
      if (window.LeguaPerfilC) {
        var PC = window.LeguaPerfilC, pre = el("pre", { class: "codigo", tabindex: "0", "aria-label": "Trecho C gerado" }), paviso = el("span", { class: "sub", role: "status", "aria-live": "polite" }), psel = el("select");
        keys(PC.PERFIS).forEach(function (k) { var op = el("option", { value: k, text: k + ": " + PC.PERFIS[k].resumo }); if (k === plan.perfil) op.selected = true; psel.appendChild(op); });
        var pgera = function () { plan.perfil = psel.value; pre.textContent = PC.gerar({ perfil: psel.value, cap_dbm: plan.p, ruido_db: K_env().noise_rise }); };
        psel.addEventListener("change", pgera); pgera();
        perfilCard = el("section", { class: "card" }, [el("h2", { text: "Do resultado ao produto: configuração do núcleo C" }),
          el("p", { class: "note", text: "Gera o trecho que configura o núcleo C99 com o perfil escolhido, o teto de TX de " + plan.p + " dBm e a elevação de ruído do ambiente (" + nf(K_env().noise_rise, 1) + " dB) deste setup. O perfil é pedido por legua_params_profile: nenhum parâmetro é copiado para o site. Estimativa para comparar e dimensionar; o perfil BR-2026 é nao_verificado." }),
          el("label", { class: "field" }, [el("span", { text: "Perfil" }), psel]), pre,
          el("div", { class: "controls sem-impressao" }, [btn("Copiar trecho", function () { copiar(pre.textContent, paviso); }),
            btn("Baixar .c", function () { paviso.textContent = baixar("legua_config.c", "text/x-csrc;charset=utf-8", pre.textContent) ? "Arquivo baixado." : "Não foi possível baixar."; }), paviso])]);
      }
      [warn, decisao, cards, dw, chart, t1, t2, t3, perfilCard].forEach(function (n) { if (n) host.appendChild(n); });
      host.querySelectorAll(".card").forEach(function (c) { if (c._render) c._render(); });
    }
    function K_env() { return DATA.constantes.envs[plan.env]; }
    var tm; function redraw() { clearTimeout(tm); tm = setTimeout(draw, 40); }
    function build() {
      var P = PRESETS[plan.preset];
      var presetSel = select("Cenário", keys(PRESETS).map(function (k) { return { v: k, t: PRESETS[k].t }; }), plan.preset, function (v) {
        plan.preset = v; plan.env = PRESETS[v].env; plan.d = PRESETS[v].d; plan.off = PRESETS[v].off; panelEstimativas(panel); });
      var envSel = select("Ambiente", keys(DATA.constantes.envs).map(function (k) { return { v: k, t: DATA.constantes.envs[k].label }; }), plan.env, function (v) { plan.env = v; draw(); });
      var sfSel = select("SF", [7, 8, 9, 10, 11, 12].map(function (x) { return { v: String(x), t: "SF" + x }; }), String(plan.sf), function (v) { plan.sf = +v; draw(); });
      var bwSel = select("Largura de banda", [125, 250, 500].map(function (x) { return { v: String(x), t: x + " kHz" + (x < 500 ? " (salto)" : " (digital)") }; }), String(plan.bw), function (v) { plan.bw = +v; draw(); });
      var crSel = select("Taxa de código", [1, 2, 3, 4].map(function (x) { return { v: String(x), t: "4/" + (x + 4) }; }), String(plan.cr), function (v) { plan.cr = +v; draw(); });
      var sigSel = select("Enlace para o ranking", [{ v: "-1", t: "Favorável (−1σ)" }, { v: "0", t: "Típico" }, { v: "1", t: "Desfavorável (+1σ)" }, { v: "2", t: "Muito desfavorável (+2σ)" }], plan.sig, function (v) { plan.sig = v; draw(); });
      var envF = fld("Ambiente", envSel.querySelector("select")), pF = fld("Cenário", presetSel.querySelector("select"));
      var sfF = fld("Fator de espalhamento", sfSel.querySelector("select")), bwF = fld("Largura de banda", bwSel.querySelector("select")), crF = fld("Taxa de código", crSel.querySelector("select"));
      var sgF = fld("Enlace para o ranking", sigSel.querySelector("select"));
      var hk = el("input", { type: "checkbox" }); hk.checked = !!plan.hull;
      hk.addEventListener("change", function () { plan.hull = hk.checked ? 1 : 0; draw(); });
      var hullF = el("label", { class: "field" }, [el("span", { text: "Curva do melhor modo em cada distância (mais lento)" }), hk]);
      var form = el("section", { class: "card" }, [el("h2", { text: "Parâmetros do setup" }), el("p", { class: "note", text: "Escolha um cenário base e ajuste os parâmetros; os resultados abaixo se atualizam na hora. Os presets F1–F5 liberam a comparação com a simulação." }),
        el("div", { class: "form" }, [pF, envF,
          rng(0.05, 40, 0.05, "d", function (v) { return nf(v, 2) + " km"; }, function () { plan.preset = plan.preset; redraw(); }), rng(-25, 15, 0.5, "off", function (v) { return nf(v, 1) + " dB"; }, redraw),
          sfF, bwF, crF, rng(-9, 28, 1, "p", function (v) { return nf(v, 0) + " dBm"; }, redraw), rng(0, 6, 1, "retries", function (v) { return String(v); }, redraw),
          rng(1, 600, 1, "interval", function (v) { return nf(v, 0) + " s"; }, redraw), rng(0, 3, 0.1, "load", function (v) { return nf(v, 1) + "×"; }, redraw),
          rng(0.5, 0.999, 0.005, "target", function (v) { return fmtPct(v); }, redraw), sgF, hullF])]);
      var rest = el("button", { type: "button", class: "btn sem-impressao", id: "restaura-plano", text: "Restaurar padrões", title: "Volta todos os parâmetros do setup ao estado inicial" });
      rest.addEventListener("click", function () { Object.keys(PLAN0).forEach(function (k) { plan[k] = PLAN0[k]; }); build(); });
      form.appendChild(rest);
      panel.textContent = ""; live = [];
      panel.appendChild(form); panel.appendChild(host); draw();
      appendDiscussion(panel);
    }
    build();
  }

  // ------------------------------------------------------------------ discussão dos resultados
  // Cada aba tem uma leitura: características, vantagens, desvantagens, aplicações e críticas. Os números citados
  // são lidos dos dados da escala escolhida (mudam com ela); o texto interpretativo vale para as duas escalas.
  var LG = "Légua perfil fixo", LM = "Légua perfil móvel", SB = "Fixo SF10/125 salto (base)", S7 = "Fixo SF7/125 salto (rápido)";
  function pp(a, b) { return nf(100 * Math.abs(a - b), 1); }              // diferença em pontos percentuais
  function rel(a, b) { return nf(100 * Math.abs(a / b - 1), 0) + "%"; }   // diferença relativa
  var DISC = {
    mecanismos: function () {
      var V = d.V, S = d.S, dk = keys(V.k_f)[0], kf = V.k_f[dk];
      return {
        car: ["Duas varreduras de um mecanismo de cada vez, com o resto no padrão: a janela de validação (k ACKs confirmam, f falhas desfazem, duração da janela) e o tempo de silêncio antes de descer um degrau.",
          "Enlaces marginais de " + V.dists_km.join(" e ") + " km, onde o ACK se perde de verdade; " + V.T_h + " h por semente, " + V.sementes.length + " sementes."],
        van: ["Com f ≥ 3 os rollbacks falsos ficam raros (a " + dk + ", k = 3: " + nf(kf["k3/f3"].rollbacks_por_hora, 2) + " por hora contra " + nf(kf["k3/f1"].rollbacks_por_hora, 2) + " com f = 1); o padrão k = 3, f = 3 está na faixa segura.",
          "Silêncio de 90 s ou mais evita as descidas falsas mesmo com tráfego esparso; 180 s e 300 s dão o mesmo resultado, porque o heartbeat limita o silêncio observável."],
        des: ["Janela de 15 s desfaz modos bons (mais rollbacks e PDR menor); com f = 1 um único fracasso já desfaz o modo.",
          "Silêncio de 30 s ou 60 s com aplicação esparsa derruba o par ao modo base várias vezes sem motivo, e o PDR cai."],
        apl: ["Regra de sintonia: t_silence ≥ 1,5 × hb_interval; janela de validação de pelo menos 45 s; f ≥ 3.", "Justificar os padrões do protocolo com números, em vez de só dizer que são razoáveis."],
        cri: ["Não use a escala rápida para ajustar k e f: com 2 h e 2 sementes o ruído é do tamanho do efeito (k = 1 parecia ótimo na rápida e não é na longa).",
          "A 3 km o efeito do silêncio some sob o ruído do enlace marginal; a regra vale para enlace bom e médio.",
          "Só dois enlaces e um ambiente; os valores ótimos podem mudar com o ambiente."]
      };
    },
    tetos: function () {
      var T = ESC[scale].tetos;
      if (!T) return { car: ["Sem dados."], van: [], des: [], apl: [], cri: [] };
      var caps = T.tetos.slice().sort(function (a, b) { return a - b; }), lo = caps[0], hi = caps[caps.length - 1];
      var cens = keys(T.cenarios).filter(function (c) { return tetoMuda(T, c); }), perdas = [], ganhos = [];
      cens.forEach(function (c) { var g0 = tetoGrupos(T, c).indexOf("L") >= 0 ? "L" : null, s = tetoStats(T, c, g0); if (s[lo].pdr != null && s[hi].pdr != null) {
        perdas.push(c + (g0 ? " (Légua)" : "") + " " + pp(s[lo].pdr, s[hi].pdr) + " pontos"); if (s[lo].mj != null && s[hi].mj != null && s[lo].mj < s[hi].mj) ganhos.push(c + (g0 ? " (Légua)" : "") + " (" + fmtMj(s[lo].mj) + " contra " + fmtMj(s[hi].mj) + ")"); } });
      return {
        car: ["A mesma bateria de cenários foi rodada com o teto de TX limitado a " + caps.join(", ") + " dBm em todos os nós; 28 dBm é o padrão. Diferença de PDR médio entre " + lo + " e " + hi + " dBm, por cenário: " + perdas.join("; ") + ".",
          "Cada célula é um enlace (distância, ambiente ou configuração) fixo; por isso, reduzir o teto desloca o alcance e não a qualidade de todos os enlaces por igual."],
        van: [ganhos.length ? "Onde o teto menor gasta menos energia por pacote (mediana das células comparáveis, vivas em todos os tetos; a Légua isolada quando o cenário tem modos fixos): " + ganhos.join("; ") + "." : "Nenhum cenário gastou menos energia com o teto menor, na mediana das células com enlace.",
          "O protocolo se adapta: com teto menor ele escolhe modos mais lentos em vez de transmitir mais alto."],
        des: ["Teto baixo derruba as células de maior distância; a média do PDR mistura enlaces mortos com enlaces saudáveis, então a leitura correta é a tabela de detalhe.",
          "Os cenários de bancada (B*) já têm tetos fixos de 0 e 10 dBm e quase não mudam."],
        apl: ["Escolher o teto de TX do produto por cenário de uso (bateria, regulação, antena) antes da bancada.", "Ver, por cenário, onde o protocolo mais depende da folga de potência."],
        cri: ["Mesma ressalva da aba Potência de TX: a corrente do PA é estimada e a posição do mínimo de energia depende dela.",
          "Distâncias e ambientes dos cenários não foram reescalados para cada teto: células mortas com teto baixo são esperadas.",
          "A média simples de PDR por cenário dá o mesmo peso a células de natureza diferente."]
      };
    },
    potencia: function () {
      var P = d.P, ds = keys(P.simetrico);
      function need(src, dk, lim) { var ok = keys(src[dk]).filter(function (c) { return src[dk][c].pdr >= lim; }); return ok.length ? ok[0] : null; }
      var near = ds[0], far = ds[ds.length - 1], a = P.assimetrico[near], sm = P.simetrico[near];
      var c0 = keys(a)[0], cN = keys(a)[keys(a).length - 1];
      var lig = P.controle_de_potencia[near].ligado, des = P.controle_de_potencia[near].desligado;
      var minC = null, minE = Infinity;
      keys(sm).forEach(function (c) { var e = sm[c].mj_por_pacote_mediana; if (e != null && sm[c].pdr >= 0.95 && e < minE) { minE = e; minC = c; } });
      return {
        car: ["O teto de TX é o que o integrador permite; o protocolo nunca passa dele. Cada distância tem um teto mínimo para fechar o enlace: com PDR de pelo menos 90%, " + ds.map(function (dk) { var c = need(P.simetrico, dk, 0.9); return dk + (c ? " pede " + c + " dBm" : " não fecha com os tetos testados"); }).join("; ") + ".",
          "Com teto assimétrico, os dois sentidos usam o mesmo modo, então o nó de teto menor decide o modo do par."],
        van: ["A 1 km, com PDR de pelo menos 95%, a energia por pacote é mínima com teto de " + (minC || "–") + " dBm (" + fmtMj(minE) + "); subir o teto além disso não melhora a entrega e custa energia no modelo.",
          "O controle de potência quase não muda o PDR (a " + near + ": " + fmtPdr(lig.pdr) + " ligado, " + fmtPdr(des.pdr) + " desligado)."],
        des: ["Um teto menor encolhe o alcance: a " + far + " " + (need(P.simetrico, far, 0.9) ? "só o teto de " + need(P.simetrico, far, 0.9) + " dBm ou mais entrega 90%." : "nenhum dos tetos testados entrega 90% (o melhor chega a " + fmtPdr(P.simetrico[far][keys(P.simetrico[far]).slice(-1)[0]].pdr) + ")."),
          "Com B em " + c0 + " dBm e A em 28 dBm, a " + near + " o PDR segue " + fmtPdr(a[c0].pdr) + ", mas a energia por pacote sobe para " + fmtMj(a[c0].mj_por_pacote_mediana) + " contra " + fmtMj(a[cN].mj_por_pacote_mediana) + " com os dois em " + cN + " dBm: o nó fraco arrasta o par para modos lentos."],
        apl: ["Dimensionar o teto de TX de um produto (bateria, antena, regulação) antes da bancada: a tabela diz o teto mínimo por distância.",
          "Decidir se vale misturar nós de potências diferentes num mesmo par (por exemplo, um nó a pilha e outro na tomada)."],
        cri: ["A corrente do PA é um modelo estimado, não medida; a posição do mínimo de energia depende dela. A bancada precisa medir a curva de corrente por potência.",
          "Um só ambiente (urbano residencial) e enlace fixo; sem mobilidade, sem interferência externa. O tráfego de dados vai só de A para B (B responde com ACK), por isso o teto de B pesa menos na entrega do que pesaria com tráfego nos dois sentidos.",
          "O teto assimétrico foi testado com A em 28 dBm; o simulador e o núcleo C ainda supõem o mesmo teto nos dois lados no cálculo da margem do vizinho."]
      };
    },
    campo: function () {
      function c(sc, dist, cf) { return d.F[sc][dist][cf]; }
      var F1 = "F1 urbano denso", F4 = "F4 rural aberto (mastro 8 m)", F2 = "F2 urbano residencial";
      var a = c(F1, "0.3 km", LG), b = c(F1, "0.3 km", SB), a1 = c(F1, "1.0 km", LG), b1 = c(F1, "1.0 km", SB), s1 = c(F1, "1.0 km", S7);
      var a15 = c(F1, "1.5 km", LG), b15 = c(F1, "1.5 km", SB), r = c(F4, "14 km", LG), rb = c(F4, "14 km", SB), r20 = c(F4, "20 km", LG), rb20 = c(F4, "20 km", SB);
      var a23 = c(F2, "3.0 km", LG), b23 = c(F2, "3.0 km", SB);
      return {
        car: ["A Légua parte do modo base e acelera quando a margem permite; com enlace folgado ela termina em modos rápidos e de baixa potência, com enlace no limite ela volta ao modo robusto.",
          "No F1 a 0,3 km a Légua gasta " + fmtMj(a.mj_por_pacote_mediana) + " por pacote contra " + fmtMj(b.mj_por_pacote_mediana) + " do SF10 fixo (" + nf(b.mj_por_pacote_mediana / a.mj_por_pacote_mediana, 0) + "× menos), com " + pp(a.pdr, b.pdr) + " ponto percentual de diferença no PDR.",
          "No rural aberto (F4) a 14 km a economia é de " + rel(r.mj_por_pacote_mediana, rb.mj_por_pacote_mediana) + " com PDR " + fmtPdr(r.pdr) + "; a 20 km os dois empatam em energia (" + fmtMj(r20.mj_por_pacote_mediana) + " contra " + fmtMj(rb20.mj_por_pacote_mediana) + ")."],
        van: ["Grande economia de energia em enlaces folgados, comuns em instalações rurais, sem perda relevante de entrega.",
          "Evita o colapso do modo rápido fixo: no F1 a 1 km o SF7 entrega " + fmtPdr(s1.pdr) + ", a Légua " + fmtPdr(a1.pdr) + " (SF10 fixo: " + fmtPdr(b1.pdr) + ").",
          "Não exige o integrador escolher o modo na instalação: a escolha acompanha o enlace."],
        des: ["Perto do limite de alcance a Légua gasta mais que o SF10 fixo: F1 a 1,5 km " + fmtMj(a15.mj_por_pacote_mediana) + " contra " + fmtMj(b15.mj_por_pacote_mediana) + " (+" + rel(a15.mj_por_pacote_mediana, b15.mj_por_pacote_mediana) + "); F2 a 3 km " + fmtMj(a23.mj_por_pacote_mediana) + " contra " + fmtMj(b23.mj_por_pacote_mediana) + ". A explicação provável é o custo de controle e as trocas desfeitas (não isolada nestes resultados).",
          "No meio da faixa urbana perde entre 1 e 2 pontos percentuais de PDR contra o modo robusto fixo (F1 a 1 km: " + pp(a1.pdr, b1.pdr) + " pontos).",
          "Oscila em enlace marginal: no F1 são " + a.quedas_base + " quedas ao modo base a 0,3 km e " + a15.quedas_base + " a 1,5 km (soma das sementes; aba Sintonia)."],
        apl: ["Sensores fixos com enlace folgado (agro, medição de água e energia, telemetria rural), onde a energia por pacote decide a vida útil da bateria.",
          "Em enlace no limite do alcance (borda urbana, rural distante), prefira um modo robusto fixo ou o perfil estável da aba Sintonia.",
          "Use a tabela como ponto de partida para escolher o perfil por tipo de instalação, não como garantia por enlace."],
        cri: ["O canal é um modelo com parâmetros estimados (perda de percurso, sombreamento, desvanecimento); não houve medição em hardware.",
          "Cada ponto vale por poucos enlaces: o sombreamento estático é sorteado por semente (2 na rápida, 5 na longa), então ordens de grandeza são confiáveis e diferenças de 1 ponto percentual não são.",
          "Energia conta só a transmissão: sem recepção, sono e CAD, o ganho real em bateria é menor que o mostrado.",
          "Os baselines são modos fixos; não há comparação com outros algoritmos de adaptação (por exemplo o ADR de terceiros)."]
      };
    },
    mob: function () {
      var M = d.M, dp = M._doppler || {};
      function c(k, cf) { return M[k].configs[cf]; }
      var u = "M1 pedestre urbano", u3 = "M3 carro urbano NLoS", h = "M4 carro rodovia", dr = "M6 drone rural 60m", g = "M7 gado";
      return {
        car: ["Dois perfis da Légua: o fixo e o móvel, que congela a aceleração quando alguma ponta passa de 2 m/s ou o SNR oscila.",
          "Doppler máximo de " + nf(dp.doppler_max_hz, 0) + " Hz, longe da tolerância estática de ±" + nf(dp.tolerancia_estatica_125k_hz, 0) + " Hz; a variação máxima de " + nf(dp.variacao_max_hz_s, 0) + " Hz/s equivale a ~" + nf(dp.variacao_max_hz_s * 0.3707, 0) + " Hz ao longo de um DATA de 371 ms, abaixo da tolerância dinâmica de " + nf(dp.tolerancia_dinamica_sf10_125_hz, 1) + " Hz do SF10/125 sem LDRO.",
          "No M1 urbano o PDR é " + fmtPdr(c(u, SB).pdr) + " (SF10 fixo), " + fmtPdr(c(u, LM).pdr) + " (Légua móvel) e " + fmtPdr(c(u, LG).pdr) + " (Légua fixa)."],
        van: ["Em rural, rodovia e drone o perfil fixo economiza muito: drone rural a 60 m gasta " + fmtMj(c(dr, LG).mj_por_pacote_mediana) + " contra " + fmtMj(c(dr, SB).mj_por_pacote_mediana) + ", com PDR " + fmtPdr(c(dr, LG).pdr) + ".",
          "O perfil móvel mantém o PDR próximo do modo base na maioria dos cenários, com exceção do M1 urbano (M4 rodovia: " + fmtPdr(c(h, LM).pdr) + " contra " + fmtPdr(c(h, SB).pdr) + ").",
          "A separação entre perfis é simples de explicar e de testar."],
        des: ["O perfil fixo perde muito PDR em ambiente urbano em movimento (M3 carro: " + fmtPdr(c(u3, LG).pdr) + " contra " + fmtPdr(c(u3, SB).pdr) + " do SF10 fixo).",
          "O perfil móvel recupera o PDR mas **não economiza energia** onde congela: M4 rodovia " + fmtMj(c(h, LM).mj_por_pacote_mediana) + " contra " + fmtMj(c(h, SB).mj_por_pacote_mediana) + ". Na prática vira o modo base.",
          "No M7 (gado) o perfil móvel entrega menos que o fixo (" + fmtPdr(c(g, LM).pdr) + " contra " + fmtPdr(c(g, LG).pdr) + "): não é uniformemente melhor."],
        apl: ["Rastreamento de gado e ativos lentos: o perfil fixo entrega " + fmtPdr(c(g, LG).pdr) + " com " + rel(c(g, LG).mj_por_pacote_mediana, c(g, SB).mj_por_pacote_mediana) + " menos energia que o SF10 base (M7).",
          "Drones e veículos em rodovia: perfil móvel por padrão acima de 2 m/s; a economia vem de outras fontes (sono, intervalo), não do modo.",
          "Pedestres e veículos em área urbana densa: o SF10 base fixo é a escolha segura."],
        cri: ["O modelo de mobilidade (LoS/NLoS de Markov, sombreamento de Gudmundson, trajetórias sintéticas) é estimado; o campo T3 é que valida.",
          "A margem entre a variação de frequência dentro do pacote (~" + nf(dp.variacao_max_hz_s * 0.3707, 0) + " Hz) e a tolerância dinâmica (" + nf(dp.tolerancia_dinamica_sf10_125_hz, 1) + " Hz) é curta (" + nf(dp.tolerancia_dinamica_sf10_125_hz / (dp.variacao_max_hz_s * 0.3707), 1) + "×). O simulador aplica esse limite, mas a deriva real do cristal e o Doppler dinâmico dependem de medição (B9).",
          "O limiar de 2 m/s do perfil móvel é heurístico, sem otimização."]
      };
    },
    alcance: function () {
      var B2 = d.B2, m = B2.modos, s7 = m["SF7/125/FH"], s10 = m["SF10/125/FH"], s12 = m["SF12/500"];
      return {
        car: ["A curva de entrega × atenuação é um degrau estreito: no SF7/125 o PDR vai de 90% a 50% em " + nf(s7.perda_max_50_db - s7.perda_max_90_db, 1) + " dB.",
          "Alcance (perda máxima com 90% de entrega): SF7/125 " + nf(s7.perda_max_90_db, 1) + " dB, SF10/125 " + nf(s10.perda_max_90_db, 1) + " dB, SF12/500 " + nf(s12.perda_max_90_db, 1) + " dB; o salto de SF7 a SF10 vale " + nf(s10.perda_max_90_db - s7.perda_max_90_db, 1) + " dB.",
          "O CR 4/8 rende cerca de " + nf(B2.ganho_cr48_sf9_db, 1) + " dB no SF9 ao custo de ~36% a mais de tempo no ar. B9: " + d.B9.falhas_com_ldro_auto.length + " combinações excedem a tolerância de deriva com LDRO automático."],
        van: ["Previsível: cada passo de SF dá ordem de 2 a 2,5 dB, o que permite dimensionar margem com a tabela de orçamento.",
          "O SF12/500 digital chega perto do SF10/125 com salto (diferença de " + nf(s10.perda_max_90_db - s12.perda_max_90_db, 1) + " dB) sem a regra de salto.",
          "Mostra onde medir: passos de 1 dB em torno do limiar bastam."],
        des: ["Quase não há aviso antes da queda: a margem útil entre 'tudo chega' e 'nada chega' é de poucos dB, o que torna a adaptação por degraus delicada.",
          "Sem TCXO, as combinações de B9 (todas com cristal comum, 22 a 28 dBm, SF9 a SF12) perdem o sincronismo por deriva térmica dentro do pacote.",
          "O CAD varre SF7–12 em ~129 ms a 125 kHz: caro para detecção multi-SF em dispositivos que dormem."],
        apl: ["Escolher TCXO ou forçar LDRO antes de qualquer campanha de campo (recomendação já no doc 06).",
          "Planejar o teste de bancada B2 com passos de 1 dB em torno do limiar previsto.",
          "Dimensionar margem de enlace por ambiente com a aba Estimativas."],
        cri: ["A curva de PER é logística com centro 2,5 dB acima do limiar do datasheet e inclinação de 0,6 dB: parâmetros estimados que a bancada B2 substitui.",
          "O ganho do CR 4/8 (1 dB) e as taxas de deriva térmica (TCXO ~5 Hz/s, cristal ~400 Hz/s) não foram medidos.",
          "O B10 só modela o tempo de CAD; detecção e falso alarme no SX1262 não têm dado publicado."]
      };
    },
    acordo: function () {
      var rows = d.B3.por_perda, b4 = d.B4, k4 = keys(b4), b5 = d.B5.resultados;
      var r0 = rows[0], r2 = rows[2], mxEp = Math.max.apply(null, k4.map(function (k) { return b4[k].max_episodio_s; }));
      var n4 = b4[k4[0]].negociacoes, lim = b4[k4[0]].limite_sup_95_desacordo_permanente;
      var q = b5["beacon_10.0s_perda_0%"], f = b5["beacon_0.4s_perda_0%"];
      return {
        car: ["Em " + k4.length + " casos de falha (perdas de controle, reboots, salto de relógio, âncora no COMMIT) com cerca de " + nf(Math.round(n4 / 100) * 100, 0) + " negociações cada, nenhum terminou em desacordo permanente (limite superior de 95%: " + fmtPct(lim) + ").",
          "A validação leva ~" + nf(r0.tempo_ate_validar_med_s, 0) + " s (p95 " + nf(r0.tempo_ate_validar_p95_s, 0) + " s); o controle custa " + nf(r0.energia_ctrl_por_neg_mj, 1) + " a " + nf(r2.energia_ctrl_por_neg_mj, 1) + " mJ por negociação a 10 dBm.",
          "O desacordo transitório mais longo chega a " + nf(mxEp, 0) + " s (com reboots); o rendezvous de um nó novo vai de " + nf(f.media_s, 0) + " s (beacon de 0,4 s, " + nf(f["duty_beacon_%"], 0) + "% de ocupação) a " + nf(q.media_s / 60, 1) + " min (beacon de 10 s)."],
        van: ["Convergência empírica robusta mesmo com 20 a 30% de perda de quadros de controle e reinícios no meio da troca.",
          "Custo de controle da ordem de miliJoules por negociação, desprezível perto do pacote de dados.",
          "O compromisso do rendezvous é explícito e dimensionável: menos beacon, menos ocupação, mais espera."],
        des: ["A convergência é lenta: dezenas de segundos para validar e, com reboots, episódios de desacordo de minutos.",
          "Os rollbacks por 100 trocas variam entre sementes e não crescem de forma monótona com a perda (B3), o que dificulta prever o custo real.",
          "No F6 urbano a oscilação em enlace marginal aparece como quedas ao modo base e segundos por hora de desacordo."],
        apl: ["Redes em que a troca de modo é rara (de hora em hora) e um desacordo de minutos é tolerável.",
          "Nós que dormem: escolher o intervalo de beacon pelo compromisso do B5 e agendar janelas de encontro.",
          "Serve de critério de aceite da Fase 2 no núcleo C: zero desacordo permanente nos mesmos casos."],
        cri: ["Zero eventos em N negociações dá só um limite estatístico (regra dos três), não uma prova.",
          "Reboots, relógio e flash são modelados, não reais; a bancada precisa repetir B4 com reinício forçado.",
          "O resultado depende da descida por silêncio: sem ela o verificador formal acha desacordo permanente (aba Verificação formal).",
          "O alarme anti-jamming congela as negociações por 1 h, o que distorce as contagens do B3 em corridas curtas."]
      };
    },
    sintonia: function () {
      var F7 = d.F7, lk = keys(F7), A = F7[lk[0]], R = F7[lk[1]], ks = keys(A);
      var at = ks[1], f3 = ks[ks.length - 1], m14 = ks[2], fx = ks[0];
      return {
        car: ["Compara a margem fixa de 8 dB (atual), a de 14 dB e a margem proporcional ao desvio do SNR (fade_k de 1 a 3) em dois enlaces marginais.",
          "Urbano denso 1 km: a Légua atual gasta " + fmtMj(A[at].mj_por_pacote_mediana) + " contra " + fmtMj(A[fx].mj_por_pacote_mediana) + " do SF10 fixo; com fade_k 3 gasta " + fmtMj(A[f3].mj_por_pacote_mediana) + ".",
          "As quedas ao modo base caem de " + A[at].quedas_base + " para " + A[f3].quedas_base + " e o desacordo de " + nf(A[at].desacordo_s_por_hora, 1) + " para " + nf(A[f3].desacordo_s_por_hora, 1) + " s/h (urbano denso)."],
        van: ["A margem proporcional é um único parâmetro e deixa o padrão intocado (fade_k = 0).",
          "Reduz de forma consistente as quedas, os rollbacks e o desacordo, recuperando o PDR do modo fixo.",
          "Torna explícito o compromisso estabilidade × energia, em vez de escondê-lo."],
        des: ["Estabilidade custa energia: no residencial 3 km, fade_k 3 gasta " + fmtMj(R[f3].mj_por_pacote_mediana) + " contra " + fmtMj(R[at].mj_por_pacote_mediana) + " da Légua atual e " + fmtMj(R[fx].mj_por_pacote_mediana) + " do SF10 fixo.",
          "Com margem alta a Légua passa a gastar mais que o modo fixo: a vantagem de energia some.",
          "A margem de 14 dB (" + fmtMj(A[m14].mj_por_pacote_mediana) + " no urbano denso) é um meio-termo sem justificativa teórica."],
        apl: ["Perfil `estavel` (fade_k = 3): aplicações em que oscilar entre modos é inaceitável (ordenação, alarmes, auditoria de comunicação).",
          "Perfil `padrao` (fade_k = 0, margem 8 dB): sensores a bateria em enlaces folgados, aceitando oscilar no limite. Perfil `cauteloso` (margem fixa de 14 dB): meio-termo sem estatística.",
          "Os três perfis existem no simulador (`simsuite/protocol/perfis.py`) e no núcleo C (`legua_params_profile`), com um teste que confere que são iguais; o integrador escolhe por instalação."],
        cri: ["Só dois enlaces e dois ambientes; não generaliza para outros desvanecimentos.",
          "fade_k é heurística; controles com histerese temporal ou por estimador de quantil não foram testados.",
          "Estas diferenças dependem do canal estimado e precisam de confirmação na bancada e no campo."]
      };
    },
    formal: function () {
      var ab = d.formal.ablacoes, mk = d.formal.rodada_markov, ref = ab.referencia, sd = ab.sem_descida_por_silencio, dr = ab.dois_reboots;
      var sv = ab.sem_validacao, ac = ab.ancora_no_commit;
      var m10 = mk[2], m30 = mk[4];
      var temP4 = ref.P4_ancora_confirmada_pelo_par != null;
      return {
        car: ["Na referência (" + nf(ref.estados, 0) + " estados), P1 e P3 valem e o maior desacordo transitório é de " + ref.P2_maior_desacordo_ticks + " ticks." + (temP4 ? " P4 (âncora confirmada pelo par) também vale." : ""),
          "Sem a descida por silêncio, P1 e P3 são violadas: o verificador acha o ciclo A em DATA no modo 2, B no base, repetido para sempre.",
          temP4 ? "Sem a validação e com a âncora gravada no COMMIT, P1 e P3 continuam valendo, mas P4 é violada: o verificador acha A com a âncora num modo em que B nunca esteve." : "Sem a validação e com a âncora no COMMIT, P1 continua valendo.",
          "Com 10% de perda por quadro a rodada de aceleração termina no modo novo em " + fmtPct(m10.P_F) + " dos casos e degrada em " + fmtPct(m10.P_degradou) + "; com 30%, " + fmtPct(m30.P_F) + " e " + fmtPct(m30.P_degradou) + "."],
        van: ["Dá uma resposta exata (exaustiva) para o modelo abstrato, não uma amostra.",
          "A ablação identifica o mecanismo indispensável (descida por silêncio) e dá um contraexemplo executável.",
          "Dois reboots mantêm P1 (desacordo máximo " + dr.P2_maior_desacordo_ticks + " ticks)." + (temP4 ? " P4 separa os dois mecanismos de segurança (validação e âncora tardia) da descida por silêncio, que P1 e P3 já cobrem." : "")],
        des: ["O modelo é abstrato (ticks discretos, dois nós, perdas adversárias); não é o código C nem o tempo real.",
          "Cobre só um adversário de perda; jamming adaptativo e relógio fora de sincronia não entram.",
          "Com perda de 20 a 30% a rodada de aceleração raramente termina no modo novo e a degradação predomina (Markov)."],
        apl: ["Especificação executável para a Fase 2 no núcleo C: cada contraexemplo vira teste de regressão.",
          "Critério de aceite do protocolo: P1 e P3 em todas as variantes de implementação.",
          "Base para os modelos TLA+/UPPAAL/PRISM do plano, que ainda não existem."],
        cri: [temP4 ? "P1 e P3 valem sem a validação e com a âncora no COMMIT; só P4 as discrimina. P4 usa um histórico fantasma (o par já esteve no modo) e não garante que o par ainda o aceite: A pode gravar um modo que B já abandonou (Dois Generais; o estado é alcançável na referência e P1 o resolve). Além disso, o maior desacordo transitório é menor sem a validação (" + sv.P2_maior_desacordo_ticks + " contra " + ref.P2_maior_desacordo_ticks + " ticks): o modelo não captura o ganho de voltar rápido ao modo anterior em vez de cair ao base." : "Sem validação e com a âncora no COMMIT, P1 continua valendo: o modelo não mostra o que esses mecanismos protegem. Falta uma propriedade que as discrimine.",
          "A verificação é em Python, de estados explícitos; não usa TLC, UPPAAL nem PRISM.",
          "Provar o modelo não prova o código; a equivalência entre o C e o Python é trabalho da Fase 2."]
      };
    },
    validacao: function () {
      var x = d.xsim, e = d.equiv, ex = e.exercitado || {}, pts = x.aloha.pontos, ult = pts[pts.length - 1], cr = x.captura.resultado, ta = x.tempo_no_ar, sn = x.sensibilidade;
      return {
        car: ["Núcleo C e simulador Python: " + nf(e.cenarios, 0) + " cenários aleatórios nos quatro pares (Py-Py, C-C, Py-C, C-Py), " + nf(e.eventos_comparados, 0) + " eventos comparados e " + (e.divergencias === 0 ? "nenhuma divergência" : e.divergencias + " divergência(s)") + ". Os cenários exercitam " + nf(ex.trocas, 0) + " trocas de modo, " + nf(ex.rollbacks, 0) + " rollbacks, " + nf(ex.desc_silencio, 0) + " descidas por silêncio e " + nf(ex.rejeitados, 0) + " quadros rejeitados.",
          "Colisão em estrela com " + nf(ult.nos, 0) + " nós: PDR " + fmtPct(ult.pdr_aqui) + " aqui, " + fmtPct(ult.pdr_analitico) + " pelo ALOHA analítico e " + fmtPct(ult.pdr_lorasim) + " pelas regras do LoRaSim (a exceção do preâmbulo faz o LoRaSim perder menos).",
          "Tempo no ar igual ao do LoRaSim em todas as combinações, exceto " + (ta.combinacoes_sf_bw_diferentes.length ? ta.combinacoes_sf_bw_diferentes.map(function (c) { return "SF" + c[0] + "/" + c[1]; }).join(", ") + " (regra do LDRO)" : "nenhuma") + "; na captura, fortes " + fmtPct(cr.aqui.pdr_fortes) + " e fracos " + fmtPct(cr.aqui.pdr_fracos) + " aqui, contra " + fmtPct(cr.lorasim.pdr_fortes) + " e " + fmtPct(cr.lorasim.pdr_fracos) + " no LoRaSim."],
        van: ["Mostra que o formato de fio e a máquina de estados do C fazem o que a referência faz, inclusive entre os dois (Py-C e C-Py), sem depender de inspeção.",
          "O teste é sensível: um parâmetro diferente num dos lados faz os rastros divergirem (há um teste que confere isso).",
          "O simulador de eventos reproduz a expressão analítica do ALOHA e concorda com as regras do LoRaSim dentro de ~1 ponto percentual."],
        des: ["A equivalência cobre a lógica do protocolo e o fio, não o modelo de rádio: o canal do teste é simplificado (um canal, sem salto, sem colisão de terceiros, sem escuta antes de transmitir).",
          "O LoRaSim original é Python 2 e não foi executado: o que se compara é um porte à mão das regras de `loraDir.py`. Um erro de porte é possível.",
          "Só tempo no ar, colisão e captura em estrela foram comparados; Meshtasticator e as topologias de malha não.",
          "A tabela de sensibilidade do LoRaSim é medida num SX1272 e a daqui vem do SX1262: diferença média de " + nf(sn.diferenca_media_abs_db, 1) + " dB (máxima " + nf(sn.maior_diferenca_db, 1) + " dB), o que desloca os limiares de alcance."],
        apl: ["Teste de regressão: qualquer mudança em `endpoint.py` ou `endpoint.c` que quebre a equivalência derruba o CI.",
          "Autoriza usar o núcleo C no firmware com a garantia de que os resultados de simulação descrevem o mesmo protocolo.",
          "Ponto de partida para validar contra outros simuladores e, depois, contra a bancada."],
        cri: ["C usa float e Python usa double: um empate de limiar poderia divergir. Nenhum apareceu, mas isso não prova que não existe.",
          "O canal do teste usa a mesma curva de PER do simulador; a equivalência não valida essa curva (é calibração de bancada).",
          "Simulação contra simulação não substitui medida: dois modelos podem errar juntos."]
      };
    },
    seg: function () {
      var b7 = d.B7, b11 = d.B11, j = b7.jammer_reativo_validacao, jn = b7.jammer_sem_alarme, rp = b7.replay_e_forjado, sa = b7.sem_ataque;
      var ls = b11["LongFast fixo 22 dBm (estilo Meshtastic)"];
      return {
        car: ["Replay e quadros forjados: " + nf(rp.rejeitados, 0) + " quadros rejeitados, PDR " + fmtPdr(rp.pdr) + " e nenhum rollback induzido." +
            (rp.alarmes_mic != null ? " A forja contínua dispara o limite de falhas de MIC (" + rp.alarmes_mic + " alarmes), que congela a negociação sem mudar de modo; aqui o enlace já estava no modo mais rápido, então o congelamento não custou PDR nem energia." : ""),
          "Jammer reativo na janela de validação: PDR " + fmtPdr(j.pdr) + ", " + j.rollbacks + " rollbacks e " + j.alarmes + " alarmes; sem o alarme, PDR " + fmtPdr(jn.pdr) + " e " + jn.rollbacks + " rollbacks.",
          "O perfil BR-2026 modelado não tem violações para a Légua nem para os modos fixos; o LongFast fixo a 22 dBm tem " + nf(ls.violacoes.potencia, 0) + " violações de potência."],
        van: ["A autenticação com contador barra replay e forja. O limite de falhas de MIC fecha a margem do MIC de 4 B; o preço é que quem forja com frequência impede novas acelerações, algo que o mesmo atacante já conseguiria com interferência.",
          "O alarme de rollbacks repetidos sem queda de SNR reduz os rollbacks e recupera parte do PDR sob jamming.",
          "O verificador B11 roda igual sobre logs reais, então o mesmo critério vale na bancada."],
        des: ["O jammer reativo é caro: " + nf(j.energia_por_pacote_mj, 0) + " mJ por pacote contra " + nf(sa.energia_por_pacote_mj, 1) + " sem ataque, porque cada troca desfeita retransmite no modo robusto.",
          "O alarme só limita o dano: o enlace continua degradado enquanto o ataque dura.",
          "O MIC de 4 B dá 2^-32 de chance de forja por tentativa."],
        apl: ["Lista de verificação para a consulta ao OCD e para o experimento (UTE).",
          "Usar o B11 em todos os logs de bancada antes de qualquer transmissão em potência plena.",
          "Dimensionar o limiar do alarme conforme o ambiente (jamming × interferência real)."],
        cri: ["O perfil BR-2026 vem de fonte secundária e está nao_verificado: 'sem violações' neste modelo **não** é conformidade nem homologação.",
          "Só um jammer simples foi simulado; ataques ao contador, à âncora ou ao relógio e análise de sigilo não foram feitos.",
          "A cripto é um MIC de teste no núcleo; a escolha do algoritmo real segue em aberto."]
      };
    },
    modos: function () {
      var rows = d.modos.modos, toas = rows.map(function (r) { return r.toa_dados_ms; }), orc = rows.map(function (r) { return r.orcamento_db; });
      var mn = Math.min.apply(null, toas), mx = Math.max.apply(null, toas), omin = Math.min.apply(null, orc), omax = Math.max.apply(null, orc);
      var nh = rows.filter(function (r) { return r.enquadramento === "salto"; }).length;
      return {
        car: [rows.length + " modos de dados: " + nh + " com salto em frequência e " + (rows.length - nh) + " digitais de 500 kHz; tempo no ar de " + nf(mn, 1) + " a " + nf(mx, 1) + " ms para 24 B (" + nf(mx / mn, 0) + "×).",
          "O orçamento de enlace vai de " + nf(omin, 1) + " a " + nf(omax, 1) + " dB, uma dinâmica de " + nf(omax - omin, 1) + " dB entre o modo mais rápido e o mais robusto.",
          "Modo base SF10/125 com salto (24 B em 371 ms, perto do limite de 400 ms por canal) e modo de recuperação SF11/250 com salto."],
        van: ["A restrição de 0,4 s por canal define a tabela de forma objetiva, sem escolhas arbitrárias.",
          "Há modos digitais de 500 kHz com SF12 quase tão robustos quanto o SF10/125 (aba Alcance) e sem a regra de salto.",
          "Tempo no ar curto nos modos rápidos reduz energia e ocupação."],
        des: ["SF11 e SF12 em 125 kHz ficam de fora: o pacote de 24 B passa de 0,4 s, o que corta justamente os modos de maior alcance.",
          "O limite de 24 B (carga útil de 9 B por DATA) restringe a aplicação e exige fragmentação para mais.",
          "Muitos modos próximos entre si: a escada de degradação usa degraus de 6 dB e ignora o resto."],
        apl: ["Tabela de partida para o firmware e para a configuração do integrador.",
          "Escolha do modo base e de recuperação por região regulatória (a tabela é por perfil).",
          "Referência para calcular ocupação e vida útil de bateria por tamanho de pacote."],
        cri: ["O perfil BR-2026 (ocupação por canal, classes de salto, PSD digital) vem de fonte secundária: nao_verificado.",
          "O teto de 28 dBm é do hardware; a Heltec V4 mediu 25,6 dBm configurada para 27 (fonte secundária).",
          "O orçamento depende de sensibilidade modelada e da figura de ruído estimada; a bancada B1/B2 é quem fecha."]
      };
    },
    malha: function () {
      var T23 = d.T23, T = d.T456, w10 = T23["T3 membro fraco -10 dB"], u = T.urbano_residencial, t4 = u["T4 linha 6 nós"], t5 = u["T5 malha 14 nós"], t6 = u["T6 malha com 2 móveis"];
      var FR = " (sem regra (22 dBm))", BR = " (BR-2026)";
      return {
        car: ["Estrela com um membro 10 dB mais fraco: o PDR dele é " + fmtPdr(w10.unanimidade.pdr_membro_fraco) + " na unanimidade, " + fmtPdr(w10.divisao.pdr_membro_fraco) + " dividindo o grupo e " + fmtPdr(w10.relay.pdr_membro_fraco) + " com relay; o relay gasta " + fmtMj(w10.relay.mj_por_pacote) + " contra " + fmtMj(w10.unanimidade.mj_por_pacote) + " e fecha " + nf(w10.relay["negociacoes_ok_%"], 0) + "% das negociações contra " + nf(w10.unanimidade["negociacoes_ok_%"], 0) + "%.",
          "Malha urbana de 14 nós em regime livre (22 dBm, sem regra): Meshtastic entrega " + fmtPdr(t5["meshtastic" + FR].pdr) + ", Légua " + fmtPdr(t5["legua" + FR].pdr) + " e Légua com inundação " + fmtPdr(t5["legua+ff" + FR].pdr) + "; a Légua gasta " + fmtMj(t5["legua" + FR].mj_por_pacote) + " por pacote contra " + fmtMj(t5["meshtastic" + FR].mj_por_pacote) + " e ocupa " + nf(t5["legua" + FR]["ocupacao_%"], 0) + "% do canal contra " + nf(t5["meshtastic" + FR]["ocupacao_%"], 0) + "%.",
          "No regime BR-2026 os modelos de terceiros, obrigados a respeitar o envelope sem trocar de preset, entregam no máximo " + fmtPdr(Math.max(t5["meshtastic" + BR].pdr, t5["meshcore" + BR].pdr)) + " na malha de 14 nós; a Légua entrega " + fmtPdr(t5["legua" + BR].pdr) + ". Na linha de 6 nós em regime livre a Légua entrega " + fmtPdr(t4["legua" + FR].pdr) + " contra " + fmtPdr(t4["meshtastic" + FR].pdr) + " do Meshtastic."],
        van: ["Em estrela, o relay evita que o membro fraco trave o grupo inteiro na pior velocidade e, com membro fraco, é a política mais barata em energia.",
          "Em malha livre, a Légua (com inundação) entrega próximo dos concorrentes modelados com cerca de um terço da energia por pacote e da ocupação do canal.",
          "O fallback por inundação no modo base dá robustez a custo baixo, e o mesmo acordo P2P escala para grupos pequenos."],
        des: ["O relay concentra tráfego e é ponto único de falha; adiciona um salto de latência.",
          "A unanimidade é a pior política: o membro mais fraco define o modo de todos e a maioria das negociações falha.",
          "Em malha livre a Légua sem inundação entrega menos que o Meshtastic: " + pp(t5["legua" + FR].pdr, t5["meshtastic" + FR].pdr) + " pontos na malha de 14 nós e " + pp(t6["legua" + FR].pdr, t6["meshtastic" + FR].pdr) + " na malha com 2 nós móveis; a inundação fecha a diferença. A vantagem está em energia e ocupação, não em entrega.",
          "A inundação eleva a ocupação do canal (até ~15% no regime livre), o que pesa na regra de ocupação do BR-2026."],
        apl: ["Estrelas com membros em enlaces desiguais (um nó atrás de parede ou em mata): usar relay.",
          "Malhas pequenas sob a regra BR-2026, onde presets nativos de terceiros não cabem no envelope sem adaptação, e onde ocupação e energia limitam.",
          "Linhas de vários saltos sob a regra BR-2026: a inundação eleva o PDR de " + fmtPdr(t4["legua" + BR].pdr) + " para " + fmtPdr(t4["legua+ff" + BR].pdr) + " na linha urbana de 6 nós; em regime livre ela é neutra (" + fmtPdr(t4["legua" + FR].pdr) + " e " + fmtPdr(t4["legua+ff" + FR].pdr) + ")."],
        cri: ["**Os baselines são modelos comportamentais nossos** (nível 2), não as implementações reais do Meshtastic, MeshCore, Reticulum e LoRaMesher. Nenhum resultado aqui é uma afirmação sobre esses produtos.",
          "A coluna BR-2026 mostra o que acontece ao impor a regra a presets que não foram feitos para ela; isso diz que o preset padrão não cabe no envelope, não que o produto seja ruim. A comparação justa de desempenho é a do regime livre, onde a vantagem da Légua é pequena em entrega e grande em energia e ocupação.",
          "Os cenários foram dimensionados para o alcance da Légua; falta a validação simulação × simulação (Meshtasticator, LoRaSim) e a bancada com 3 e 4 placas (T2/T3)."]
      };
    },
    escalas: function () {
      var O = DATA.orcamento, fl = ESC.full;
      return {
        car: ["Escala rápida: ~9,5 min com um processo, 2 sementes e 1 a 2 h por ponto. Escala longa: " + fmtDur(O.total.central) + " com um processo, mais sementes e tempo simulado (docs/09).",
          "A previsão feita antes da rodada foi de 4100 s; o total " + (fl && fl.meta.completa ? "medido" : "orçado") + " é " + nf(O.total.central, 0) + " s. A contenção mediana (medido/extrapolado) é " + nf(O.contencao.mediana, 2) + ".",
          fl ? "A longa tem " + keys(fl.dados).length + " cenários" + (fl.meta.completa ? ", todos os que o site exibe." : " (parcial).") : "A escala longa ainda não foi gerada."],
        van: ["Mostra quando uma conclusão da rápida se sustenta: " + (function () {
          try { var k = "urbano denso 1 km", a = "Légua atual (margem 8 dB)", b = "Fixo SF10/125 salto (base)", q = ESC.quick.dados.F7[k], f = ESC.full.dados.F7[k];
            return "Légua atual × SF10 fixo no F7 urbano denso vai de " + nf(100 * (q[a].mj_por_pacote_mediana / q[b].mj_por_pacote_mediana - 1), 0) + "% de energia na rápida a " + nf(100 * (f[a].mj_por_pacote_mediana / f[b].mj_por_pacote_mediana - 1), 0) + "% na longa."; }
          catch (e) { return "compare as duas escalas na tabela acima."; } })(),
          "O custo é previsível e foi validado, o que permite decidir quando vale rodar a longa.",
          "Um processo por vez cabe em 4 GB de RAM e disco mecânico."],
        des: ["Uma hora de CPU a cada mudança de protocolo: não serve como ciclo de desenvolvimento.",
          "O tempo depende da trajetória simulada; um laço no protocolo já multiplicou o custo por 6 antes de ser corrigido.",
          "A longa ainda tem 5 sementes: pouco para intervalos de confiança estreitos."],
        apl: ["Rápida para desenvolver e para regressão (CI); longa antes de fixar parâmetros ou de publicar números.",
          "Rodar a longa de novo sempre que `protocol/` ou `core/` mudarem o comportamento.",
          "Usar o orçamento para agendar a rodada fora do expediente."],
        cri: ["A 'longa' não é o tamanho de amostra completo do plano (≥ 3 dias distintos por enlace, rodízio intercalado); é um ponto intermediário.",
          "Tempo medido vale para esta máquina; em outra, repita a calibração com `--procs 1`.",
          "Mesmo na longa, o sombreamento estático é sorteado por semente: poucos enlaces independentes."]
      };
    },
    estimativas: function () {
      return {
        car: ["Estimador analítico de um modo fixo com DATA/ACK e retransmissão: calcula, no navegador, entrega, energia, latência, alcance e ranking de modos para o setup escolhido.",
          "Usa o mesmo canal e a mesma curva de demodulação da simulação, integrados por quadratura em vez de sorteados.",
          "Contra o simulador de eventos, com o sombreamento estático controlado, a entrega estimada erra 1,1 ponto percentual em média (máximo 4,9; 42 pontos)."],
        van: ["Resposta instantânea para qualquer combinação de parâmetros, sem rodar a simulação.",
          "Separa o efeito do sombreamento do enlace (favorável, típico, desfavorável) do efeito do modo e da potência.",
          "O ranking de modos e a curva por distância orientam onde medir na bancada."],
        des: ["Só modo fixo: não inclui a negociação, o que a Légua ganha ou perde ao adaptar.",
          "Não modela colisão entre os nós, CAD/LBT nem o salto sincronizado; a energia é só de transmissão.",
          "Energia e latência não foram validadas ponto a ponto, só a entrega."],
        apl: ["Pré-dimensionamento de um enlace: modo, potência e distância máxima para uma meta de entrega.",
          "Comparar instalações (urbano × rural, com e sem ganho extra) antes de um campo.",
          "Escolher os pontos da bancada B2 e do campo T3."],
        cri: ["Validado só contra a simulação, não contra o campo: os parâmetros de ambiente são ordens de grandeza estimadas.",
          "A fonte regulatória do teto de 0,4 s e da ocupação é secundária (nao_verificado).",
          "Um resultado 'bom' aqui é condição necessária, não suficiente: ainda falta a medição em hardware."]
      };
    }
  };
  function appendDiscussion(panel) {
    var f = curTab && DISC[curTab.id];
    if (!f) return;
    var o;
    try { o = f(); } catch (e) { return; }
    var sec = el("section", { class: "card disc" }, [el("h2", { text: "Discussão dos resultados" }),
      el("p", { class: "note", text: "Interpretação dos números desta aba na escala " + (scale === "full" ? "longa" : "rápida") + ". Os valores citados vêm dos dados exibidos e mudam com a escala; as conclusões são leitura do modelo, não medição em hardware." })]);
    var grid = el("div", { class: "dgrid" });
    [["car", "Características principais"], ["van", "Vantagens"], ["des", "Desvantagens"], ["apl", "Aplicações práticas"], ["cri", "Críticas e limitações"]].forEach(function (b) {
      var ul = el("ul");
      (o[b[0]] || []).forEach(function (t) {
        var li = el("li"), parts = t.split("**");
        parts.forEach(function (part, i) { li.appendChild(i % 2 ? el("strong", { text: part }) : document.createTextNode(part)); });
        ul.appendChild(li);
      });
      grid.appendChild(el("div", { class: "dblock" + (b[0] === "cri" ? " crit" : "") }, [el("h3", { text: b[1] }), ul]));
    });
    sec.appendChild(grid);
    panel.appendChild(sec);
  }

  // ------------------------------------------------------------------ navegação
  var TABS = [
    { id: "guia", t: "Comece aqui", f: function (panel) { mount(panel, window.LeguaExplica ? window.LeguaExplica.guia() : [el("p", { class: "note", text: "O guia não carregou (explica.js ausente)." })]); }, need: [], anyScale: true },
    { id: "campo", t: "Campo fixo", f: panelCampo, need: ["F"] }, { id: "mob", t: "Mobilidade", f: panelMob, need: ["M"] },
    { id: "alcance", t: "Alcance e deriva", f: panelAlcance, need: ["B2", "B9", "B10"] }, { id: "acordo", t: "Acordo e falhas", f: panelAcordo, need: ["B3", "B4", "B5", "F6", "B6"] },
    { id: "sintonia", t: "Sintonia (F7)", f: panelSintonia, need: ["F7"] },
    { id: "potencia", t: "Potência de TX", f: panelPotencia, need: ["P"] },
    { id: "mecanismos", t: "Mecanismos (V, S)", f: panelMecanismos, need: ["V", "S"] },
    { id: "estresses", t: "Estresses (X)", f: panelEstresses, need: ["X"] },
    { id: "tetos", t: "Teto × cenários", f: panelTetos, need: [], anyScale: true },
    { id: "formal", t: "Verificação formal", f: panelFormal, need: ["formal"] },
    { id: "validacao", t: "Validação cruzada", f: panelValidacao, need: ["xsim", "equiv"] }, { id: "seg", t: "Segurança e regulação", f: panelSeguranca, need: ["B7", "B11"] },
    { id: "modos", t: "Modos", f: panelModos, need: ["modos"] }, { id: "malha", t: "Grupos e malha", f: panelMalha, need: ["T23", "T456"] },
    { id: "escalas", t: "Escalas e orçamento", f: panelEscalas, need: [], anyScale: true },
    { id: "estimativas", t: "Estimativas", f: panelEstimativas, need: [], anyScale: true },
    { id: "rastros", t: "Rastros", f: function (panel) { live = []; if (window.LeguaRastrosUI && window.LeguaRastros) window.LeguaRastrosUI.painel(panel); else mount(panel, [el("p", { class: "note", text: "O reprodutor de rastros não carregou." })]); }, need: [], anyScale: true },
    { id: "sensib", t: "Sensibilidade", f: function (panel) { live = []; if (window.LeguaSensibilidadeUI && window.LeguaSensibilidade) window.LeguaSensibilidadeUI.painel(panel, DATA); else mount(panel, [el("p", { class: "note", text: "A aba de sensibilidade não carregou." })]); }, need: [], anyScale: true },
    { id: "medicoes", t: "Medições", f: function (panel) { live = []; if (window.LeguaMedicoesUI && window.LeguaMedicoes) window.LeguaMedicoesUI.painel(panel, DATA); else mount(panel, [el("p", { class: "note", text: "A aba de medições não carregou." })]); }, need: [], anyScale: true },
    { id: "pacote", t: "Pacotes", f: function (panel) { live = []; if (window.LeguaPacoteUI && window.LeguaPacote) window.LeguaPacoteUI.painel(panel, DATA); else mount(panel, [el("p", { class: "note", text: "O decodificador não carregou." })]); }, need: [], anyScale: true },
    { id: "spec", t: "Especificação", f: function (panel) { live = []; if (window.LeguaSpecUI) window.LeguaSpecUI.painel(panel); else mount(panel, [el("p", { class: "note", text: "O navegador de documentos não carregou." })]); }, need: [], anyScale: true },
    { id: "calc", t: "Calculadoras", f: function (panel) { live = []; if (window.LeguaCalcUI && window.LeguaCalc) window.LeguaCalcUI.painel(panel, DATA); else mount(panel, [el("p", { class: "note", text: "As calculadoras não carregaram." })]); }, need: [], anyScale: true }
  ];
  var gnav = document.getElementById("gnav"), panel = document.getElementById("panel"), scaleEl = document.getElementById("scale"), bar = document.getElementById("scalebar");
  var curTab = null;

  function missingCard(t, miss) {
    var O = DATA.orcamento, tot = 0;
    miss.forEach(function (m) { if (O.linhas[m]) tot += O.linhas[m].central_s; });
    return el("section", { class: "card warn-card" }, [el("h2", { text: "Sem resultado da escala longa para esta seção" }),
      el("p", { class: "note", text: "Falta: " + miss.join(", ") + ". Tempo estimado para gerar (um processo): " + fmtDur(tot) + ". Comando: python3 -m simsuite.run_suite --escala full --procs 1 --so " + miss.join(" ") + " && python3 tools/build_site.py" }),
      (function () { var b = el("button", { class: "btn", type: "button", text: "Ver a escala rápida" }); b.addEventListener("click", function () { setScale("quick"); }); return b; })()]);
  }
  function updateBar(t) {
    bar.textContent = "";
    var e = ESC[scale], isFull = scale === "full";
    bar.appendChild(el("span", { class: "badge" + (isFull ? " full" : ""), text: isFull ? "Escala longa (full)" : "Escala rápida (quick)" }));
    var txt = "";
    if (t && t.need && t.need.length) {
      var c0 = t.need[0], o = DATA.orcamento.linhas[c0], seg = e.meta.cenarios[c0] && e.meta.cenarios[c0].segundos;
      txt = (o ? c0 + ": " + (isFull ? "longa" : "rápida") + (o.origem && o.origem !== "fixo" && o.origem !== "independe da escala" ? " (rápida → longa: " + o.origem + ")" : "") : "")
        + (seg != null ? " · rodou em " + fmtDur(seg) : "");
    } else txt = "As seções de estimativas e escalas independem da escala escolhida.";
    bar.appendChild(document.createTextNode(txt));
  }
  function go(id, focus) {
    var t = TABS.filter(function (x) { return x.id === id; })[0] || TABS[0];
    curTab = t;
    d = ESC[scale].dados;
    window.LeguaNav.montar(gnav, { ativo: t.id, ir: function (id) { go(id, false); } });
    try { history.replaceState(null, "", "#" + t.id + (scale === "full" ? "/full" : "") + (t.id === "estimativas" ? "?" + planQuery() : "")); } catch (e) { /* ignore */ }
    updateBar(t);
    var miss = (t.need || []).filter(function (n) { return d[n] === undefined; });
    if (miss.length && !t.anyScale) { live = []; panel.textContent = ""; panel.appendChild(missingCard(t, miss)); }
    else t.f(panel);
    if (["modos", "alcance", "campo", "potencia"].indexOf(t.id) >= 0 && !(miss.length && !t.anyScale)) {
      panel.appendChild(el("section", { class: "card" }, [el("h2", { text: "Meu enlace fecha?" }),
        el("p", { class: "note", text: "Os números desta aba valem para o ambiente médio. Para um terreno específico (morro, mastro, vegetação), informe o perfil e veja a margem de cada modo." }),
        el("a", { class: "btn", href: "enlace.html", text: "Abrir o testador de enlaces" })]));
    }
    var ev = window.LeguaEvidencia && !(miss.length && !t.anyScale) ? window.LeguaEvidencia.faixa(t.id) : null;
    if (ev) panel.insertBefore(ev, panel.firstChild);
    var bd = !(miss.length && !t.anyScale) ? barraDados(t) : null;
    if (bd) panel.appendChild(bd);
    var passo = window.LeguaNav.rodape(t.id, function (id) { go(id, false); window.scrollTo(0, 0); });
    if (passo) panel.appendChild(passo);
    if (focus) panel.focus({ preventScroll: true });
  }
  /* barra "Citar e reproduzir / dados": citação e BibTeX, comando de reprodução, dados brutos da aba (JSON) e tabelas (CSV) */
  function barraDados(t) {
    if (!t.need || !t.need.length || !window.LeguaCitar) return null;
    var C = window.LeguaCitar, sem = null;
    t.need.forEach(function (c) { if (sem == null && d[c] && d[c].sementes != null) sem = d[c].sementes; });
    var inp = { aba: t.t, abaId: t.id, escala: scale, cenarios: t.need, meta: DATA.meta, sementes: sem, url: location.href.split("#")[0] + "#" + t.id + (scale === "full" ? "/full" : "") };
    var b = C.bloco(inp), aviso = el("span", { class: "sub", role: "status", "aria-live": "polite" });
    var area = el("div", { class: "citar-area", hidden: "hidden", style: "margin-top:8px" });
    function caixa(rot, txt) {
      var ta = el("textarea", { readonly: "readonly", rows: String(Math.min(6, txt.split("\n").length + 1)), style: "width:100%;font:12px monospace", "aria-label": rot }); ta.value = txt;
      var bt = el("button", { type: "button", class: "btn", text: "Copiar" }); bt.addEventListener("click", function () { copiar(txt, aviso); });
      return el("div", { style: "margin:6px 0" }, [el("div", { class: "sub", text: rot }), ta, bt]);
    }
    area.appendChild(caixa("Citação (texto)", b.texto)); area.appendChild(caixa("BibTeX", b.bibtex)); area.appendChild(caixa("Para reproduzir estes números", b.comando));
    function bt(txt, fn, id) { var x = el("button", { type: "button", class: "btn", text: txt }); if (id) x.id = id; x.addEventListener("click", fn); return x; }
    var base = "legua-" + t.id + "-" + scale;
    var barra = el("section", { class: "card sem-impressao dados-aba" }, [el("h2", { text: "Citar, reproduzir e baixar os dados desta aba" }),
      el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;align-items:center" }, [
        bt("Citar e reproduzir", function () { area.hidden = !area.hidden; }, "citar-abre"),
        bt("Dados brutos (JSON)", function () { aviso.textContent = baixar(base + ".json", "application/json", C.jsonDaAba(inp, d)) ? "JSON baixado." : "Não foi possível baixar."; }, "baixa-json"),
        bt("Tabelas visíveis (CSV)", function () {
          var proc = "Légua núcleo " + (DATA.meta.versao_nucleo || "?") + ", aba " + t.t + ", escala " + scale + ", commit " + (DATA.meta.commit || "?") + ", gerado em " + (DATA.meta.gerado_em || "?") + "; estimativa de simulação, sem medição em hardware";
          var tabs = C.tabelasCsv(panel, proc);
          if (!tabs.length) { aviso.textContent = "Esta aba não tem tabela visível; use o JSON."; return; }
          aviso.textContent = baixar(base + ".csv", "text/csv;charset=utf-8", tabs.map(function (x) { return x.csv; }).join("\r\n")) ? tabs.length + " tabela(s) baixada(s)." : "Não foi possível baixar.";
        }, "baixa-csv"), aviso]), area]);
    return barra;
  }
  function drawScaleSwitch() {
    scaleEl.textContent = "";
    [["quick", "Rápida"], ["full", "Longa"]].forEach(function (s) {
      var avail = !!ESC[s[0]], b = el("button", { type: "button", role: "radio", text: s[1], "aria-checked": String(scale === s[0]) });
      if (!avail) { b.disabled = true; b.title = "Ainda não há resultados desta escala"; }
      else if (s[0] === "full" && !ESC.full.meta.completa) b.title = "Escala longa parcial: " + keys(ESC.full.dados).length + " cenários";
      b.addEventListener("click", function () { setScale(s[0]); });
      scaleEl.appendChild(b);
    });
  }
  function setScale(s) {
    if (!ESC[s]) return;
    scale = s; try { localStorage.setItem("legua-escala", s); } catch (e) { /* ignore */ }
    drawScaleSwitch(); go(curTab ? curTab.id : TABS[0].id, false);
  }
  var qm = ESC.quick.meta, fm = ESC.full && ESC.full.meta;
  document.getElementById("meta").textContent = "Gerado em " + DATA.meta.gerado_em + (DATA.meta.commit ? " · commit " + DATA.meta.commit : "") +
    " · rápida: " + keys(ESC.quick.dados).length + " cenários" + (fm ? " · longa: " + keys(ESC.full.dados).length + " cenários" + (fm.completa ? "" : " (parcial)") : " · longa: ainda não gerada");

  // o tema é tratado por nav.js, comum às três páginas

  if (window.MutationObserver && window.LeguaExplica) {          // painéis que se redesenham sozinhos (Alcance, Estimativas)
    new MutationObserver(function () { window.LeguaExplica.anotar(panel); }).observe(panel, { childList: true, subtree: true });
  }
  document.addEventListener("legua:ir", function (ev) { go(ev.detail, true); window.scrollTo(0, 0); });
  var btnEx = document.getElementById("expl");
  function setExpl(on) {
    document.body.classList.toggle("sem-expl", !on);
    btnEx.setAttribute("aria-pressed", String(on));
    btnEx.textContent = "Explicações: " + (on ? "ligadas" : "desligadas");
    try { localStorage.setItem("legua-expl", on ? "1" : "0"); } catch (e) { /* ignore */ }
  }
  var exOn = true;
  try { exOn = localStorage.getItem("legua-expl") !== "0"; } catch (e) { /* ignore */ }
  setExpl(exOn);
  btnEx.addEventListener("click", function () { setExpl(btnEx.getAttribute("aria-pressed") !== "true"); });

  var rz;
  window.addEventListener("resize", function () { clearTimeout(rz); rz = setTimeout(function () { live.forEach(function (r) { r(); }); }, 150); });
  var hq = (location.hash || "").slice(1).split("?"), hp = hq[0].split("/");
  if (hp[0] === "estimativas" && hq[1]) planFromQuery(hq.slice(1).join("?"));
  try { var se = localStorage.getItem("legua-escala"); if (se && ESC[se]) scale = se; } catch (e) { /* ignore */ }
  if (hp[1] === "full" && ESC.full) scale = "full"; else if (hp[1] === "quick") scale = "quick";
  drawScaleSwitch();
  go(hp[0], false);
})();
