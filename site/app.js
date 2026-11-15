(function () {
  "use strict";
  var DATA = window.LEGUA_DATA;
  var d = DATA.dados;
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
    "AdaptLoRa perfil fixo":       { label: "Légua (perfil fixo)",   short: "Légua fixo",  slot: 1, dash: "",        mk: "circle" },
    "AdaptLoRa perfil móvel":      { label: "Légua (perfil móvel)",  short: "Légua móvel", slot: 2, dash: "",        mk: "diamond" },
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
    var names = { referencia: "referência", sem_descida_por_silencio: "sem descida por silêncio", sem_validacao: "sem validação", ancora_no_commit: "âncora no COMMIT", dois_reboots: "dois reboots" };
    var tab = tableCard("Verificação de estados (modelo abstrato, perdas adversárias)",
      "P1: sem desacordo permanente. P2: maior desacordo transitório, em ticks. P3: a recuperação é sempre possível. Cada linha remove ou altera um mecanismo do protocolo.",
      ["Variante", "Estados", "P1", "P2 (ticks)", "P3"],
      keys(ab).map(function (k) { var r = ab[k];
        return [names[k] || k, nf(r.estados, 0), r.P1_sem_desacordo_permanente ? { pill: "ok", text: "vale" } : { pill: "bad", text: "viola" },
          r.P2_maior_desacordo_ticks == null ? "–" : r.P2_maior_desacordo_ticks, r.P3_recuperacao_sempre_possivel ? { pill: "ok", text: "vale" } : { pill: "bad", text: "viola" }]; }),
      [false, true, false, true, false]);
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

  function panelSeguranca(panel) {
    var b7 = d.B7, k7 = keys(b7).filter(function (k) { return k !== "nota"; });
    var t7 = tableCard("B7 · segurança", "Replay e quadros forjados são rejeitados sem efeito; o jammer reativo é o caso caro em energia, e o alarme limita os rollbacks.",
      ["Caso", "PDR", "Rollbacks", "Alarmes", "Rejeitados", "mJ/pacote"],
      k7.map(function (k) { var r = b7[k]; return [k.replace(/_/g, " "), fmtPdr(r.pdr), r.rollbacks, r.alarmes, r.rejeitados, nf(r.mj_por_pacote, 1)]; }), [false, true, true, true, true, true]);
    var b11 = d.B11, k11 = keys(b11).filter(function (k) { return k !== "nota"; });
    var t11 = tableCard("B11 · registros de TX contra o perfil BR-2026 (nao_verificado)",
      "O verificador roda sobre o registro de transmissões (o mesmo vale para logs reais). O perfil vem de fonte secundária; isto não é prova de conformidade nem de homologação.",
      ["Fonte", "Resultado no modelo", "Pior ocupação por canal", "Violações"],
      k11.map(function (k) { var r = b11[k], v = r.violacoes, tot = 0, det = [];
        keys(v).forEach(function (x) { tot += v[x]; if (v[x]) det.push(x.replace(/_/g, " ") + " = " + v[x]); });
        return [k.replace("AdaptLoRa", "Légua"), tot === 0 ? { pill: "ok", text: "sem violações" } : { pill: "bad", text: "viola" }, nf(r.pior_ocupacao_s, 3) + " s", det.join("; ") || "–"]; }),
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

  // ------------------------------------------------------------------ navegação
  var TABS = [
    { id: "campo", t: "Campo fixo", f: panelCampo }, { id: "mob", t: "Mobilidade", f: panelMob },
    { id: "alcance", t: "Alcance e deriva", f: panelAlcance }, { id: "acordo", t: "Acordo e falhas", f: panelAcordo }, { id: "sintonia", t: "Sintonia (F7)", f: panelSintonia },
    { id: "formal", t: "Verificação formal", f: panelFormal }, { id: "seg", t: "Segurança e regulação", f: panelSeguranca },
    { id: "modos", t: "Modos", f: panelModos }, { id: "malha", t: "Grupos e malha", f: panelMalha }
  ];
  var tabsEl = document.getElementById("tabs"), panel = document.getElementById("panel"), current = null;
  function go(id, focus) {
    var t = TABS.filter(function (x) { return x.id === id; })[0] || TABS[0];
    current = t;
    Array.prototype.forEach.call(tabsEl.children, function (b) { b.setAttribute("aria-selected", String(b.dataset.id === t.id)); b.tabIndex = b.dataset.id === t.id ? 0 : -1; });
    try { history.replaceState(null, "", "#" + t.id); } catch (e) { /* ignore */ }
    t.f(panel);
    if (focus) panel.focus({ preventScroll: true });
  }
  TABS.forEach(function (t, i) {
    var b = el("button", { class: "tab", role: "tab", type: "button", text: t.t });
    b.dataset.id = t.id;
    b.addEventListener("click", function () { go(t.id, false); });
    b.addEventListener("keydown", function (e) {
      var n = i + (e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0);
      if (n !== i && n >= 0 && n < TABS.length) { go(TABS[n].id, false); tabsEl.children[n].focus(); e.preventDefault(); }
    });
    tabsEl.appendChild(b);
  });

  var meta = DATA.meta;
  document.getElementById("meta").textContent = "Escala " + meta.escalas.join(", ") + " · gerado em " + meta.gerado_em +
    (meta.commit ? " · commit " + meta.commit : "") + (meta.faltando.length ? " · faltando: " + meta.faltando.join(", ") : "");

  // tema: claro/escuro com preferência do sistema como padrão
  var root = document.documentElement;
  try { var sv0 = localStorage.getItem("legua-tema"); if (sv0 === "light" || sv0 === "dark") root.setAttribute("data-theme", sv0); } catch (e) { /* sem storage */ }
  document.getElementById("theme").addEventListener("click", function () {
    var dark = root.getAttribute("data-theme") === "dark" || (!root.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    var next = dark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("legua-tema", next); } catch (e) { /* ignore */ }
  });

  var rz;
  window.addEventListener("resize", function () { clearTimeout(rz); rz = setTimeout(function () { live.forEach(function (r) { r(); }); }, 150); });
  go((location.hash || "").slice(1), false);
})();
