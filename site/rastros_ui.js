/* Aba "Rastros": carrega um JSONL de telemetria, remove a localização, mostra a linha do tempo de modos por nó e a lista de eventos. */
(function (root) {
  "use strict";
  var doc = root.document, NS = "http://www.w3.org/2000/svg";
  var S = { texto: "", node: "", ev: "", busca: "" }, CORES = { 5: "#8e6bbf", 6: "#6b8ebf", 7: "#2a9d8f", 8: "#5cb85c", 9: "#9acd32", 10: "#e9c46a", 11: "#f4a261", 12: "#e76f51" };

  function el(tag, attrs, kids) {
    var e = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(typeof c === "string" ? doc.createTextNode(c) : c); });
    return e;
  }
  function sv(tag, attrs, pai) { var e = doc.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (pai) pai.appendChild(e); return e; }
  function nf(x, d) { return isFinite(x) ? x.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }) : "–"; }
  function corModo(m) { var x = /SF(\d+)/.exec(m); return x ? (CORES[+x[1]] || "#888") : "#888"; }

  function linhaDoTempo(res) {
    var ids = Object.keys(res.nos).sort(), W = 760, ml = 70, mr = 14, rowH = 34, H = 26 + rowH * ids.length + 26, d = Math.max(res.duracao, 1e-9);
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "class": "perfil", "aria-label": "Linha do tempo dos modos de cada nó, em " + nf(res.duracao, 0) + " s, com " + res.marcas.length + " marcas (rollback, reboot, ressincronização)." });
    function X(t) { return ml + (W - ml - mr) * (t - res.t0) / d; }
    ids.forEach(function (id, i) {
      var y = 14 + i * rowH, t = sv("text", { x: ml - 8, y: y + 17, "text-anchor": "end", "font-size": "12", fill: "var(--text)" }, svg); t.textContent = "nó " + id;
      res.nos[id].modos.forEach(function (m) {
        var r = sv("rect", { x: X(m.t0), y: y, width: Math.max(1.5, X(m.t1) - X(m.t0)), height: 22, fill: corModo(m.modo), rx: "2", "fill-opacity": m.estado === "VALIDANDO" ? "0.55" : "0.95" }, svg);
        var ti = sv("title", {}, r); ti.textContent = m.modo + " · " + m.estado + (m.motivo ? " · " + m.motivo : "") + " · " + nf(m.t0, 1) + " a " + nf(m.t1, 1) + " s";
      });
    });
    res.marcas.forEach(function (m) {
      var i = ids.indexOf(m.node); if (i < 0) return;
      var y = 14 + i * rowH, cor = m.tipo === "rollback" ? "#c0392b" : m.tipo === "reboot" ? "#222" : "#1b6ca8";
      var l = sv("line", { x1: X(m.t), x2: X(m.t), y1: y - 6, y2: y + 28, stroke: cor, "stroke-width": "2" }, svg); var ti = sv("title", {}, l); ti.textContent = m.tipo + " em " + nf(m.t, 1) + " s";
    });
    var ax = sv("text", { x: ml, y: H - 6, "font-size": "11", fill: "var(--text-3)" }, svg); ax.textContent = nf(res.t0, 0) + " s";
    var bx = sv("text", { x: W - mr, y: H - 6, "text-anchor": "end", "font-size": "11", fill: "var(--text-3)" }, svg); bx.textContent = nf(res.t1, 0) + " s";
    return svg;
  }

  function painel(panel) {
    var R = root.LeguaRastros; panel.textContent = "";
    var out = el("div"), aviso = el("span", { "class": "sub", role: "status", "aria-live": "polite" });
    var ta = el("textarea", { rows: "6", style: "width:100%;font:12px monospace", spellcheck: "false", "aria-label": "Rastro JSONL" }); ta.value = S.texto;
    ta.addEventListener("input", function () { S.texto = ta.value; S.node = ""; S.ev = ""; calcula(); });
    var arq = el("input", { type: "file", accept: ".jsonl,.json,.txt,application/json", "aria-label": "Carregar arquivo JSONL" });
    arq.addEventListener("change", function () { var f = arq.files && arq.files[0]; if (!f) return; var rd = new FileReader(); rd.onload = function () { S.texto = String(rd.result).slice(0, 20000000); ta.value = S.texto.length > 200000 ? S.texto.slice(0, 200000) : S.texto; S.node = ""; S.ev = ""; calcula(); }; rd.readAsText(f); });
    var ex = el("button", { type: "button", "class": "btn", id: "ras-exemplo", text: "Carregar exemplo sintético" });
    ex.addEventListener("click", function () {
      var e = [{ v: 1, t: 0, node: 1, ev: "modo", modo: "SF10/125/FH", estado: "BASE", motivo: "boot" }, { v: 1, t: 0, node: 2, ev: "modo", modo: "SF10/125/FH", estado: "BASE", motivo: "boot" }, { v: 1, t: 5, node: 1, ev: "tx", tipo: "DATA", seq: 1 }, { v: 1, t: 5.4, node: 2, ev: "rx", tipo: "DATA", src: 1, seq: 1, rssi: -101, snr: -5 },
        { v: 1, t: 60, node: 1, ev: "propose", modo: "SF9/125/FH" }, { v: 1, t: 70, node: 1, ev: "modo", modo: "SF9/125/FH", estado: "VALIDANDO", motivo: "commit" }, { v: 1, t: 70, node: 2, ev: "modo", modo: "SF9/125/FH", estado: "VALIDANDO", motivo: "commit" },
        { v: 1, t: 130, node: 1, ev: "modo", modo: "SF9/125/FH", estado: "BASE", motivo: "validado" }, { v: 1, t: 130, node: 2, ev: "modo", modo: "SF9/125/FH", estado: "BASE", motivo: "validado" }, { v: 1, t: 200, node: 1, ev: "alarme_rollback" }, { v: 1, t: 200, node: 1, ev: "modo", modo: "SF10/125/FH", estado: "BASE", motivo: "rollback" },
        { v: 1, t: 300, node: 2, ev: "reboot" }, { v: 1, t: 320, node: 2, ev: "resync", arg: 0 }, { v: 1, t: 340, node: 2, ev: "modo", modo: "SF10/125/FH", estado: "BASE", motivo: "resync" }];
      S.texto = "# EXEMPLO SINTÉTICO (não é medição)\n" + e.map(function (x) { return JSON.stringify(x); }).join("\n") + "\n"; ta.value = S.texto; S.node = ""; S.ev = ""; calcula();
    });
    var c1 = el("section", { "class": "card" }, [el("h2", { text: "1. Carregar um rastro" }), el("p", { "class": "note", text: "Um evento JSON por linha (v, t em segundos, node, ev e os campos do evento), como em simsuite/analysis/telemetry.py. Campos de localização (lat, lon, alt, GNSS) são removidos na leitura e nunca aparecem nem são exportados. Nada sai do navegador." }),
      el("div", { "class": "form" }, [el("label", { "class": "field", style: "grid-column:1/-1" }, [el("span", { text: "Colar o JSONL" }), ta]), el("label", { "class": "field" }, [el("span", { text: "ou carregar arquivo" }), arq])]), el("div", { style: "margin-top:8px" }, [ex])]);
    var c2 = el("section", { "class": "card" }, [el("h2", { text: "2. Linha do tempo e resumo" }), out]);
    [c1, c2].forEach(function (c) { panel.appendChild(c); });

    function calcula() {
      out.textContent = "";
      if (!S.texto.trim()) { out.appendChild(el("p", { "class": "note", text: "Carregue um rastro para ver a linha do tempo." })); return; }
      var l = R.ler(S.texto);
      if (l.erro) { out.appendChild(el("p", {}, [el("span", { "class": "pill bad", text: "não leu" }), " " + l.erro])); return; }
      l.avisos.forEach(function (a) { out.appendChild(el("p", { "class": "note", text: "Atenção: " + a })); });
      var res = R.resumo(l.recs), ids = Object.keys(res.nos).sort();
      out.appendChild(el("p", {}, [el("span", { "class": "pill ok", text: l.recs.length + " eventos" }), " " + ids.length + " nó(s), " + nf(res.duracao, 1) + " s."]));
      var t = el("table"), th = el("thead", {}, [el("tr", {}, ["Nó", "Eventos", "TX", "RX", "Trocas de modo", "Rollbacks", "Rejeitados", "Reboots", "Resync"].map(function (h) { return el("th", { text: h }); }))]), tb = el("tbody");
      ids.forEach(function (id) { var n = res.nos[id]; tb.appendChild(el("tr", {}, [id, n.eventos, n.tx, n.rx, Math.max(0, n.modos.length - 1), n.rollbacks, n.rejeitados, n.reboots, n.resync].map(function (v) { return el("td", { text: String(v) }); }))); });
      t.appendChild(th); t.appendChild(tb); out.appendChild(el("div", { "class": "tbl-wrap", style: "overflow-x:auto" }, [t]));
      if (ids.some(function (id) { return res.nos[id].modos.length; })) { out.appendChild(linhaDoTempo(res)); out.appendChild(el("p", { "class": "note", text: "Cores por SF (roxo = SF5 a laranja = SF12); mais claro = em validação. Linha vermelha: rollback; preta: reboot; azul: ressincronização. Passe o mouse para ver o motivo." })); }
      // eventos filtrados
      var evs = Object.keys(res.contagem).sort();
      function selecao(rot, valor, opcoes, aoMudar) { var s = el("select", { "aria-label": rot }); s.appendChild(el("option", { value: "", text: "todos" })); opcoes.forEach(function (o) { var x = el("option", { value: o, text: o }); if (o === valor) x.selected = true; s.appendChild(x); }); s.addEventListener("change", function () { aoMudar(s.value); lista(); }); return el("label", { "class": "field" }, [el("span", { text: rot }), s]); }
      var busca = el("input", { type: "search", "aria-label": "Buscar nos eventos", placeholder: "buscar…" }); busca.value = S.busca; busca.addEventListener("input", function () { S.busca = busca.value; lista(); });
      var tabela = el("div");
      out.appendChild(el("h3", { text: "Eventos" })); out.appendChild(el("div", { "class": "form" }, [selecao("Nó", S.node, ids, function (v) { S.node = v; }), selecao("Evento", S.ev, evs, function (v) { S.ev = v; }), el("label", { "class": "field" }, [el("span", { text: "Buscar" }), busca])]));
      out.appendChild(tabela);
      var bt = el("button", { type: "button", "class": "btn", id: "ras-baixa", text: "Baixar JSONL sem localização" });
      bt.addEventListener("click", function () { try { var u = URL.createObjectURL(new Blob([R.paraJsonl(l.recs)], { type: "application/x-ndjson" })), a = el("a", { href: u, download: "rastro-limpo.jsonl" }); doc.body.appendChild(a); a.click(); doc.body.removeChild(a); setTimeout(function () { URL.revokeObjectURL(u); }, 2000); aviso.textContent = "Arquivo baixado."; } catch (e) { aviso.textContent = "Não foi possível baixar."; } });
      out.appendChild(el("div", { style: "margin-top:8px;display:flex;gap:8px;align-items:center" }, [bt, aviso]));
      function lista() {
        tabela.textContent = ""; var f = R.filtrar(l.recs, { node: S.node, ev: S.ev, busca: S.busca }, 300);
        var tt = el("table"), hh = el("thead", {}, [el("tr", {}, ["t (s)", "nó", "evento", "detalhes"].map(function (h) { return el("th", { text: h }); }))]), bb = el("tbody");
        f.forEach(function (r) { var d = {}; Object.keys(r).forEach(function (k) { if (["v", "t", "node", "ev"].indexOf(k) < 0) d[k] = r[k]; }); bb.appendChild(el("tr", {}, [nf(r.t, 2), String(r.node), r.ev, JSON.stringify(d)].map(function (v) { return el("td", { text: v }); }))); });
        tt.appendChild(hh); tt.appendChild(bb); tabela.appendChild(el("p", { "class": "sub", text: f.length >= 300 ? "Mostrando os primeiros 300 eventos do filtro." : f.length + " evento(s)." })); tabela.appendChild(el("div", { "class": "tbl-wrap", style: "overflow-x:auto" }, [tt]));
      }
      lista();
    }
    calcula();
  }
  root.LeguaRastrosUI = { painel: painel, estado: S };
})(typeof window !== "undefined" ? window : this);
