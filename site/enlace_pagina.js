/* Página do testador de enlaces (enlace.html): formulário, gráfico do perfil, tabela por modo e exportação.
 * Tudo local; o fragmento da URL guarda só os parâmetros (nunca o perfil colado). */
(function () {
  "use strict";
  var DATA = window.LEGUA_DATA, NS = "http://www.w3.org/2000/svg";
  var LE = window.LeguaEnlace.make(DATA.constantes), PR = window.LeguaPropagacao, TE = window.LeguaTerreno, TR = window.LeguaTerrarium;
  var app = document.getElementById("app");

  var st = { terreno: "plano", d: 5.0, base: 100, morro_h: 60, morro_pos: 50, morro_w: 0.8, csv: "", hTx: 10, hRx: 10, k: "1.3333", p: 20, gTx: 2.15, gRx: 2.15, lTx: 0.5, lRx: 0.5,
    extra: 0, latA: "", lonA: "", latB: "", lonB: "", grades: [], tiles: null, tilesMsg: "", consente: false, buscando: false, env: "rural_aberto", modelo: "p526", pontos: [], salto: 0, consenteMapa: false, sf: 10, bw: 125, cr: 1, alvo: 0.95, retries: 3, interval: 60, load: 1 };
  var PADRAO = JSON.parse(JSON.stringify(st));                 // estado inicial, para “Restaurar padrões”
  var CHAVES = ["terreno", "d", "base", "morro_h", "morro_pos", "morro_w", "hTx", "hRx", "k", "p", "gTx", "gRx", "lTx", "lRx", "extra", "env", "modelo", "sf", "bw", "cr", "alvo", "retries", "interval", "load"];
  var NUM = { d: [0.05, 40], base: [-400, 8000], morro_h: [0, 1500], morro_pos: [0, 100], morro_w: [0.05, 20], hTx: [0.5, 100], hRx: [0.5, 100], p: [-9, 28], gTx: [-5, 15], gRx: [-5, 15],
    lTx: [0, 10], lRx: [0, 10], extra: [0, 60], alvo: [0.5, 0.999], retries: [0, 6], interval: [1, 600], load: [0, 3] };

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { if (k === "text") n.textContent = attrs[k]; else if (k === "class") n.className = attrs[k]; else n.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function sv(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") n.textContent = attrs[k]; else n.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(n);
    return n;
  }
  function nf(v, dg) { return v == null || !isFinite(v) ? "–" : v.toLocaleString("pt-BR", { minimumFractionDigits: dg || 0, maximumFractionDigits: dg == null ? 0 : dg }); }
  function pct(v) { return v == null ? "–" : nf(100 * v, 1) + "%"; }
  function mj(v) { return v == null ? "–" : nf(v, v < 10 ? 2 : v < 100 ? 1 : 0) + " mJ"; }
  function pill(kind, text) { return el("span", { class: "pill " + kind }, [el("span", { "aria-hidden": "true", text: kind === "ok" ? "✓" : kind === "bad" ? "✕" : "!" }), el("span", { text: text })]); }
  function nomeModo(r) { return "SF" + r.sf + "/" + r.bw + (r.cr > 1 ? "/CR4" + (r.cr + 4) : "") + (r.fhss ? "/FH" : ""); }

  // ---- URL (só parâmetros)
  function consulta() { return CHAVES.map(function (k) { return k + "=" + encodeURIComponent(String(st[k])); }).join("&"); }
  function deConsulta(q) {
    var m = {};
    String(q || "").split("&").forEach(function (kv) { var i = kv.indexOf("="); if (i > 0) { try { m[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1)); } catch (e) { /* ignora */ } } });
    Object.keys(NUM).forEach(function (k) { var v = parseFloat(m[k]); if (isFinite(v) && v >= NUM[k][0] && v <= NUM[k][1]) st[k] = v; });
    function um(k, ok) { if (m[k] !== undefined && ok.indexOf(m[k]) >= 0) st[k] = m[k]; }
    function umN(k, ok) { var v = parseFloat(m[k]); if (ok.indexOf(v) >= 0) st[k] = v; }
    um("terreno", ["plano", "morro", "csv", "hgt", "terrarium", "mapa"]); um("env", Object.keys(DATA.constantes.envs)); um("modelo", ["p526", "j"]); um("k", ["1.3333", "1", "0.6667"]);
    umN("sf", [7, 8, 9, 10, 11, 12]); umN("bw", [125, 250, 500]); umN("cr", [1, 2, 3, 4]);
    if (st.terreno === "csv" || st.terreno === "hgt" || st.terreno === "terrarium" || st.terreno === "mapa") st.terreno = "plano";   // CSV e coordenadas nunca vêm pela URL
  }
  function sincroniza() { try { history.replaceState(null, "", "#" + consulta()); } catch (e) { /* ignore */ } }

  // ---- exportação
  function baixar(nome, tipo, texto) {
    try {
      var url = URL.createObjectURL(new Blob([texto], { type: tipo })), a = el("a", { href: url, download: nome });
      document.body.appendChild(a); a.click(); document.body.removeChild(a); setTimeout(function () { URL.revokeObjectURL(url); }, 2000); return true;
    } catch (e) { return false; }
  }
  function copiar(texto, aviso) {
    function fim(ok) { aviso.textContent = ok ? "Copiado." : "Não foi possível copiar."; }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texto).then(function () { fim(true); }, function () { fim(false); });
    else { var t = el("textarea", { readonly: "readonly" }); t.value = texto; document.body.appendChild(t); t.select(); var ok = false; try { ok = document.execCommand("copy"); } catch (e) { /* ignore */ } document.body.removeChild(t); fim(ok); }
  }
  function csvCell(v) { var t = v == null ? "" : String(v); return /[;"\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t; }

  // ---- perfil
  function pontoOk(p) { return p && isFinite(p.lat) && isFinite(p.lon); }
  /* perfil do salto i (do ponto i ao i+1): com elevação baixada, o terreno real; sem ela (ou fora dos tiles), plano na
   * altitude base, marcado com `plano: true` para a interface avisar. */
  function perfilSalto(i) {
    var A = st.pontos[i], B = st.pontos[i + 1];
    if (!pontoOk(A) || !pontoOk(B)) return { erro: "ponha ao menos dois pontos válidos no mapa ou na tabela" };
    if (st.tiles) {
      var r = TE.perfilEntre(st.tiles.fonte, A, B, 30);
      if (!r.erro) return { perfil: r.perfil, D_km: r.D_km, vazios: r.vazios };
      if (!/saíram da área de elevação/.test(r.erro)) return { erro: r.erro };
    }
    var D = TE.haversineKm(A.lat, A.lon, B.lat, B.lon);
    if (!(D >= 0.02 && D <= 100)) return { erro: "a distância entre os pontos precisa ficar entre 0,02 e 100 km (agora " + D.toFixed(2) + " km)" };
    return { perfil: TE.plano(D, st.base), D_km: D, plano: true };
  }
  function perfilAtual() {
    if (st.terreno === "csv") {
      var r = TE.lerCsv(st.csv, st.d);
      return r.erro ? { erro: r.erro } : { perfil: r.perfil };
    }
    if (st.terreno === "hgt") {
      if (!st.grades.length) return { erro: "carregue o(s) arquivo(s) .hgt que cobrem o enlace (SRTM1 ou SRTM3)" };
      var rh = TE.perfilEntre(st.grades, { lat: parseFloat(String(st.latA).replace(",", ".")), lon: parseFloat(String(st.lonA).replace(",", ".")) },
        { lat: parseFloat(String(st.latB).replace(",", ".")), lon: parseFloat(String(st.lonB).replace(",", ".")) }, 30);
      if (rh.erro) return { erro: rh.erro };
      st.d = Math.round(rh.D_km * 100) / 100;
      return { perfil: rh.perfil, vazios: rh.vazios };
    }
    if (st.terreno === "mapa") {
      var rs = perfilSalto(st.salto);
      if (rs.erro) return { erro: rs.erro };
      st.d = Math.round(rs.D_km * 100) / 100;
      return { perfil: rs.perfil, vazios: rs.vazios, plano: rs.plano };
    }
    if (st.terreno === "terrarium") {
      if (!st.tiles) return { erro: "marque o consentimento e clique em “Buscar elevação” para baixar os tiles do caminho" };
      var rt = TE.perfilEntre(st.tiles.fonte, { lat: parseFloat(String(st.latA).replace(",", ".")), lon: parseFloat(String(st.lonA).replace(",", ".")) },
        { lat: parseFloat(String(st.latB).replace(",", ".")), lon: parseFloat(String(st.lonB).replace(",", ".")) }, 30);
      if (rt.erro) return { erro: rt.erro };
      st.d = Math.round(rt.D_km * 100) / 100;
      return { perfil: rt.perfil, vazios: rt.vazios };
    }
    var D = st.d;
    return { perfil: st.terreno === "plano" ? TE.plano(D, st.base) : TE.morro(D, st.base, st.morro_h, st.morro_pos / 100, st.morro_w) };
  }

  function desenhaPerfil(host, A) {
    var pf = A.perfil, perfil = A._perfil, n = perfil.d.length, D = pf.D_km, W = 800, H = 300, ml = 58, mr = 14, mt = 12, mb = 36, i;
    var lo = Infinity, hi = -Infinity;
    for (i = 0; i < n; i++) { lo = Math.min(lo, perfil.h[i]); hi = Math.max(hi, pf.terreno_ef[i], pf.los[i] + 1.0 * pf.fresnel1[i]); }
    hi = Math.max(hi, pf.ht_m, pf.hr_m); lo = Math.min(lo, pf.ht_m, pf.hr_m, pf.los[0] - pf.fresnel1[Math.floor(n / 2)]);
    var pad = Math.max(5, 0.06 * (hi - lo)); lo -= pad; hi += pad;
    function X(x) { return ml + (W - ml - mr) * x / D; }
    function Y(y) { return mt + (H - mt - mb) * (1 - (y - lo) / (hi - lo)); }
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "class": "perfil",
      "aria-label": "Perfil de terreno de " + nf(D, 2) + " km: altitude de " + nf(Math.min.apply(null, perfil.h), 0) + " a " + nf(Math.max.apply(null, perfil.h), 0) + " m, folga da primeira zona de Fresnel " + (pf.folga_min_razao == null ? "não calculada" : nf(100 * pf.folga_min_razao, 0) + "%") + "." });
    sv("rect", { x: 0, y: 0, width: W, height: H, fill: "none" }, svg);
    // grade e eixos
    var t, ny = 4, nx = Math.min(8, Math.max(2, Math.round(D)));
    for (t = 0; t <= ny; t++) { var yv = lo + (hi - lo) * t / ny; sv("line", { x1: ml, x2: W - mr, y1: Y(yv), y2: Y(yv), stroke: "var(--grid)" }, svg); sv("text", { x: ml - 6, y: Y(yv) + 4, "text-anchor": "end", "font-size": 11, fill: "var(--text-2)", text: nf(yv, 0) }, svg); }
    for (t = 0; t <= nx; t++) { var xv = D * t / nx; sv("text", { x: X(xv), y: H - 18, "text-anchor": "middle", "font-size": 11, fill: "var(--text-2)", text: nf(xv, D < 3 ? 2 : 1) }, svg); }
    sv("text", { x: (ml + W - mr) / 2, y: H - 4, "text-anchor": "middle", "font-size": 11, fill: "var(--text-2)", text: "distância (km)" }, svg);
    sv("text", { x: 12, y: (mt + H - mb) / 2, "text-anchor": "middle", "font-size": 11, fill: "var(--text-2)", transform: "rotate(-90 12 " + (mt + H - mb) / 2 + ")", text: "altitude (m)" }, svg);
    // zona de Fresnel (100% e 60%)
    var up = [], dn = [], up6 = [], dn6 = [];
    for (i = 0; i < n; i++) { var x = X(perfil.d[i]); up.push(x + "," + Y(pf.los[i] + pf.fresnel1[i])); dn.unshift(x + "," + Y(pf.los[i] - pf.fresnel1[i])); up6.push(x + "," + Y(pf.los[i] + 0.6 * pf.fresnel1[i])); dn6.unshift(x + "," + Y(pf.los[i] - 0.6 * pf.fresnel1[i])); }
    sv("polygon", { points: up.concat(dn).join(" "), fill: "var(--accent)", "fill-opacity": 0.08, stroke: "var(--accent)", "stroke-opacity": 0.35, "stroke-dasharray": "3 3" }, svg);
    sv("polygon", { points: up6.concat(dn6).join(" "), fill: "var(--accent)", "fill-opacity": 0.14, stroke: "none" }, svg);
    // terreno (com abaulamento da Terra) e linha de visada
    var tp = [];
    for (i = 0; i < n; i++) tp.push(X(perfil.d[i]) + "," + Y(pf.terreno_ef[i]));
    sv("polygon", { points: X(0) + "," + Y(lo) + " " + tp.join(" ") + " " + X(D) + "," + Y(lo), fill: "var(--text-3)", "fill-opacity": 0.35, stroke: "var(--text-2)", "stroke-width": 1.5 }, svg);
    sv("line", { x1: X(0), y1: Y(pf.ht_m), x2: X(D), y2: Y(pf.hr_m), stroke: "var(--s2)", "stroke-width": 2 }, svg);
    [[0, pf.ht_m, perfil.h[0]], [D, pf.hr_m, perfil.h[n - 1]]].forEach(function (m) {
      sv("line", { x1: X(m[0]), x2: X(m[0]), y1: Y(m[2]), y2: Y(m[1]), stroke: "var(--text)", "stroke-width": 3 }, svg);
      sv("circle", { cx: X(m[0]), cy: Y(m[1]), r: 4, fill: "var(--s2)" }, svg);
    });
    if (pf.d_obst_km != null && pf.perda_difracao_db > 0.5) {
      sv("line", { x1: X(pf.d_obst_km), x2: X(pf.d_obst_km), y1: Y(pf.ht_m + (pf.hr_m - pf.ht_m) * pf.d_obst_km / D), y2: Y(pf.ht_m + (pf.hr_m - pf.ht_m) * pf.d_obst_km / D + pf.h_obst_m), stroke: "var(--bad)", "stroke-width": 3 }, svg);
      sv("text", { x: X(pf.d_obst_km) + 6, y: Y(pf.ht_m + (pf.hr_m - pf.ht_m) * pf.d_obst_km / D) - 6, "font-size": 11, fill: "var(--bad)", text: "obstáculo equivalente: " + nf(pf.h_obst_m, 1) + " m acima da linha de visada" }, svg);
    }
    host.appendChild(svg);
    host.appendChild(el("p", { class: "note", text: "Terreno desenhado com o abaulamento da Terra (k = " + nf(parseFloat(st.k), 2) + "). Laranja: linha de visada. Faixa azul: primeira zona de Fresnel (escura: 60%). Vermelho: obstáculo equivalente de Bullington." }));
  }

  // ---- formulário
  var host = el("div"), campos = el("div", { class: "form" });
  function fld(rot, ctl, val) { return el("label", { class: "field" }, [el("span", {}, [rot + ": ", val || null]), ctl]); }
  function rng(chave, rot, passo, fmt) {
    var lim = NUM[chave], inp = el("input", { type: "range", min: lim[0], max: lim[1], step: passo, value: st[chave] }), out = el("span", { class: "val", text: fmt(st[chave]) });
    inp.addEventListener("input", function () { st[chave] = parseFloat(inp.value); out.textContent = fmt(st[chave]); agenda(); });
    return fld(rot, inp, out);
  }
  function sel(chave, rot, opts, aoMudar) {
    var s = el("select");
    opts.forEach(function (o) { var op = el("option", { value: o[0], text: o[1] }); if (String(o[0]) === String(st[chave])) op.selected = true; s.appendChild(op); });
    s.addEventListener("change", function () { st[chave] = typeof st[chave] === "number" ? parseFloat(s.value) : s.value; if (aoMudar) aoMudar(); else agenda(); });
    return fld(rot, s);
  }
  var tm; function agenda() { clearTimeout(tm); tm = setTimeout(desenha, 40); }
  function monta() {
    campos.textContent = "";
    var u = function (v) { return function (x) { return nf(x, v[0]) + " " + v[1]; }; };
    var csvBox = null;
    /* mapa de pontos (nova opção): vários pontos = saltos em cadeia (relés); cada par seguido é um salto */
    var mapaObj = null;
    function blocoMapa() {
      var caixa = el("div", { class: "field", style: "grid-column:1/-1" }), tabela = el("div", { style: "grid-column:1/-1" }), seletorSalto = el("div", { style: "display:contents" });
      mapaObj = window.LeguaMapa.criar(caixa, {});
      mapaObj.definir(st.pontos); mapaObj.consentir(st.consenteMapa);
      if (st.pontos.some(pontoOk)) mapaObj.enquadrar();
      var hist = [];
      function snap() { hist.push(st.pontos.map(function (p) { return { lat: p.lat, lon: p.lon }; })); if (hist.length > 30) hist.shift(); }
      mapaObj.aoMudar(function (pts) { snap(); st.pontos = pts; listaPontos(); agenda(); });
      mapaObj.aoConsentir(function (v) { st.consenteMapa = v; });
      function sinc() { mapaObj.definir(st.pontos); }
      function listaPontos() {
        tabela.textContent = "";
        var t = el("table"), th = el("thead"), hr = el("tr");
        ["Ponto", "Latitude", "Longitude", ""].forEach(function (h) { hr.appendChild(el("th", { text: h })); }); th.appendChild(hr); t.appendChild(th);
        var tb = el("tbody");
        st.pontos.forEach(function (p, i) {
          var tr = el("tr"), la = el("input", { type: "text", inputmode: "decimal", autocomplete: "off", "aria-label": "Latitude do ponto " + window.LeguaMapa.rotulo(i), style: "width:9em" }), lo = el("input", { type: "text", inputmode: "decimal", autocomplete: "off", "aria-label": "Longitude do ponto " + window.LeguaMapa.rotulo(i), style: "width:9em" });
          la.value = isFinite(p.lat) ? p.lat.toFixed(5) : ""; lo.value = isFinite(p.lon) ? p.lon.toFixed(5) : "";
          var dica = el("span", { class: "sub", role: "alert", style: "color:var(--bad)" });
          function valida() {
            var a = Pf(la.value), b = Pf(lo.value), m = "";
            if (la.value.trim() && !(Math.abs(a) <= 90)) m = "A latitude vai de −90 a 90" + (Math.abs(a) <= 180 && Math.abs(b) <= 90 ? "; parece que latitude e longitude estão trocadas." : ".");
            else if (lo.value.trim() && !(Math.abs(b) <= 180)) m = "A longitude vai de −180 a 180.";
            la.setAttribute("aria-invalid", String(!!m && /latitude/i.test(m))); lo.setAttribute("aria-invalid", String(!!m && /longitude/i.test(m)));
            la.style.borderColor = la.getAttribute("aria-invalid") === "true" ? "var(--bad)" : ""; lo.style.borderColor = lo.getAttribute("aria-invalid") === "true" ? "var(--bad)" : "";
            dica.textContent = m;
          }
          function mudou() { st.pontos[i] = { lat: Pf(la.value), lon: Pf(lo.value) }; valida(); sinc(); agenda(); }
          la.addEventListener("input", mudou); lo.addEventListener("input", mudou);
          var rm = el("button", { type: "button", class: "btn", text: "Remover", "aria-label": "Remover o ponto " + window.LeguaMapa.rotulo(i) });
          rm.addEventListener("click", function () { snap(); st.pontos.splice(i, 1); st.salto = Math.max(0, Math.min(st.salto, st.pontos.length - 2)); sinc(); listaPontos(); monta(); });
          [el("td", { text: window.LeguaMapa.rotulo(i) }), el("td", {}, [la]), el("td", {}, [lo]), el("td", {}, [rm, document.createTextNode(" "), dica])].forEach(function (c) { tr.appendChild(c); }); valida();
          tb.appendChild(tr);
        });
        t.appendChild(tb);
        var ops = el("div", { class: "controls sem-impressao", style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:8px" });
        function ob(txt, fn, id) { var b = el("button", { type: "button", class: "btn", text: txt }); if (id) b.id = id; b.addEventListener("click", fn); ops.appendChild(b); }
        ob("Adicionar ponto digitando", function () { if (st.pontos.length < window.LeguaMapa.MAX_PONTOS) { snap(); st.pontos.push({ lat: NaN, lon: NaN }); listaPontos(); } }, "add-ponto");
        ob("Inverter a ordem", function () { snap(); st.pontos.reverse(); sinc(); listaPontos(); agenda(); });
        ob("Enquadrar no mapa", function () { mapaObj.enquadrar(); });
        ob("Desfazer", function () { if (!hist.length) return; st.pontos = hist.pop(); sinc(); listaPontos(); monta(); }, "desfaz-ponto");
        ops.lastChild.disabled = !hist.length; ops.lastChild.title = hist.length ? "Volta o último ajuste dos pontos" : "Nada para desfazer";
        ob("Limpar pontos", function () { snap(); st.pontos = []; st.salto = 0; st.tiles = null; st.tilesMsg = ""; sinc(); listaPontos(); monta(); });
        tabela.appendChild(el("p", { class: "sub", text: st.pontos.length < 2 ? "Clique no mapa (ou digite) para pôr os pontos: com dois, um enlace; com três ou mais, uma cadeia de saltos com relés. Até " + window.LeguaMapa.MAX_PONTOS + " pontos." : (st.pontos.length - 1) + " salto(s) em cadeia: " + st.pontos.map(function (_, i) { return window.LeguaMapa.rotulo(i); }).join(" → ") + "." }));
        tabela.appendChild(el("div", { class: "tbl-wrap", style: "overflow-x:auto" }, [t])); tabela.appendChild(ops);
        seletorSalto.textContent = "";                                      // o seletor de salto acompanha o número de pontos
        if (st.pontos.length > 1) {
          var opt = []; for (var q = 0; q < st.pontos.length - 1; q++) opt.push([q, "Salto " + (q + 1) + ": " + window.LeguaMapa.rotulo(q) + " → " + window.LeguaMapa.rotulo(q + 1)]);
          st.salto = Math.max(0, Math.min(st.salto, st.pontos.length - 2));
          seletorSalto.appendChild(sel("salto", "Salto em detalhe (perfil e modos)", opt));
        }
      }
      campos.appendChild(caixa);
      campos.appendChild(el("p", { class: "sub", style: "grid-column:1/-1;margin:-4px 0 0", text: "Arraste para mover, use + e − (ou a roda) para o zoom e clique para pôr um ponto. Os pontos ficam só nesta página." }));
      campos.appendChild(tabela);
      campos.appendChild(seletorSalto);
      listaPontos();
      blocoElevacao(function () { var h = []; for (var q = 0; q < st.pontos.length - 1; q++) h.push([st.pontos[q], st.pontos[q + 1]]); return h; });
    }
    function coordenadas() {
      [["latA", "Latitude do ponto A (graus decimais)"], ["lonA", "Longitude do ponto A"], ["latB", "Latitude do ponto B"], ["lonB", "Longitude do ponto B"]].forEach(function (c) {
        var inp = el("input", { type: "text", inputmode: "decimal", autocomplete: "off", "aria-label": c[1] }); inp.value = st[c[0]];
        inp.addEventListener("input", function () { st[c[0]] = inp.value; agenda(); });
        campos.appendChild(fld(c[1], inp));
      });
    }
    campos.appendChild(sel("terreno", "Terreno", [["plano", "Plano"], ["morro", "Morro entre as antenas"], ["csv", "Perfil colado (CSV)"], ["hgt", "Arquivo de elevação local (.hgt) + coordenadas"], ["terrarium", "Elevação pela internet (tiles Terrarium) + coordenadas"], ["mapa", "Mapa: escolher pontos (um enlace ou vários saltos)"]], monta));
    campos.appendChild(sel("env", "Variabilidade do canal (ambiente)", Object.keys(DATA.constantes.envs).map(function (k) { return [k, DATA.constantes.envs[k].label]; })));
    if (st.terreno !== "hgt" && st.terreno !== "terrarium" && st.terreno !== "mapa") campos.appendChild(rng("d", "Distância" + (st.terreno === "csv" ? " (só p/ CSV de uma coluna)" : ""), 0.05, u([2, "km"])));
    if (st.terreno !== "csv" && st.terreno !== "hgt" && st.terreno !== "terrarium") campos.appendChild(rng("base", "Altitude da base", 5, u([0, "m"])));
    if (st.terreno === "morro") {
      campos.appendChild(rng("morro_h", "Altura do morro", 1, u([0, "m"])));
      campos.appendChild(rng("morro_pos", "Posição do morro", 1, u([0, "% do enlace"])));
      campos.appendChild(rng("morro_w", "Meia-largura do morro", 0.05, u([2, "km"])));
    }
    if (st.terreno === "csv") {
      var ta = el("textarea", { rows: "7", "aria-label": "Perfil de terreno em CSV", placeholder: "distancia_km;altitude_m\n0;100\n0,5;112\n1;130\n...\n(ou uma coluna só de altitudes, igualmente espaçadas, usando a distância acima)", style: "width:100%;font:12px monospace;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:6px" });
      ta.value = st.csv;
      ta.addEventListener("input", function () { st.csv = ta.value; agenda(); });
      csvBox = el("div", { class: "field", style: "grid-column:1/-1" }, [el("span", { text: "Perfil colado (fica só nesta página; não vai para o endereço compartilhável)" }), ta]);
      campos.appendChild(csvBox);
    }
    if (st.terreno === "hgt") {
      var fi = el("input", { type: "file", accept: ".hgt", multiple: "multiple", "aria-label": "Arquivos de elevação .hgt" }), lista = el("span", { class: "sub", text: st.grades.length ? st.grades.map(function (g) { return g.nome; }).join(", ") : "nenhum arquivo carregado" });
      fi.addEventListener("change", function () {
        var arqs = Array.prototype.slice.call(fi.files || []), pend = arqs.length, novos = [], erros = [];
        if (!pend) return;
        arqs.forEach(function (f) {
          var rd = new FileReader();
          rd.onload = function () { var r = TE.lerHgt(rd.result, f.name); if (r.erro) erros.push(f.name + ": " + r.erro); else novos.push(r.grade); fim(); };
          rd.onerror = function () { erros.push(f.name + ": não foi possível ler"); fim(); };
          rd.readAsArrayBuffer(f);
        });
        function fim() { if (--pend) return; st.grades = novos; lista.textContent = (novos.length ? novos.map(function (g) { return g.nome; }).join(", ") : "nenhum arquivo válido") + (erros.length ? " · " + erros.join(" · ") : ""); agenda(); }
      });
      campos.appendChild(el("div", { class: "field", style: "grid-column:1/-1" }, [el("span", { text: "Arquivos .hgt (SRTM1/SRTM3; o nome diz a grade, ex.: S23W046.hgt). São lidos aqui, no navegador; nada é enviado." }), fi, lista]));
      coordenadas();
      campos.appendChild(el("p", { class: "note", style: "grid-column:1/-1", text: "As coordenadas ficam só na memória desta página: não vão para o endereço compartilhável, nem para o resumo, nem para o JSON. O SRTM é um modelo de superfície (copas e telhados contam como terreno)." }));
    }
    /* elevação por tiles Terrarium (consentimento próprio); `saltosFn()` devolve [[A, B], ...] */
    function blocoElevacao(saltosFn) {
      var bt = el("button", { type: "button", class: "btn", id: "busca-tiles", text: st.buscando ? "Baixando…" : (st.tiles ? "Atualizar elevação" : "Buscar elevação") });
      var stt = el("span", { class: "sub", role: "status", "aria-live": "polite", id: "status-tiles", text: st.tilesMsg });
      bt.disabled = st.buscando;
      bt.addEventListener("click", function () {
        if (st.buscando) return;
        st.buscando = true; st.tilesMsg = "Baixando os tiles de elevação…"; stt.textContent = st.tilesMsg; bt.disabled = true; bt.textContent = "Baixando…";
        var buscar = window.LeguaTerrariumBuscar || TR.buscarNoNavegador;               // o teste troca o buscador; nada vai à rede
        TR.carregarSaltos(saltosFn(), TR.Z_PADRAO, buscar).then(function (r) {
          st.buscando = false; bt.disabled = false;
          if (r.erro) { st.tiles = null; st.tilesMsg = r.erro; bt.textContent = "Tentar de novo"; } else { st.tiles = r; st.tilesMsg = "Elevação pronta (" + r.n_tiles + " tiles). Se mover os pontos para fora da área, busque de novo."; bt.textContent = "Atualizar elevação"; }
          stt.textContent = st.tilesMsg; agenda();
        });
      });
      var det = el("details", { class: "sub", style: "margin-top:4px" }, [el("summary", { style: "cursor:pointer", text: "O que é enviado?" }),
        el("p", { class: "note", text: "Ao clicar, o navegador baixa da AWS (s3.amazonaws.com) os tiles de elevação que cobrem o caminho. O servidor vê os números desses tiles (uma região de uns 10 km) e o seu IP; as coordenadas exatas dos pontos não são enviadas nem ficam em URL, resumo ou JSON. Dados: Terrain Tiles da AWS Open Data (SRTM, Copernicus e outros), com precisão de cerca de 30 m; copas e telhados contam como terreno." })]);
      campos.appendChild(el("div", { class: "field", style: "grid-column:1/-1" }, [el("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, [bt, stt]), det]));
    }
    function Pf(t) { return parseFloat(String(t).replace(",", ".")); }
    if (st.terreno === "terrarium") {
      coordenadas();
      blocoElevacao(function () { return [[{ lat: Pf(st.latA), lon: Pf(st.lonA) }, { lat: Pf(st.latB), lon: Pf(st.lonB) }]]; });
    }
    if (st.terreno === "mapa") blocoMapa();
    campos.appendChild(rng("hTx", "Altura da antena A", 0.5, u([1, "m"]))); campos.appendChild(rng("hRx", "Altura da antena B", 0.5, u([1, "m"])));
    campos.appendChild(sel("modelo", "Modelo de difração", [["p526", "ITU-R P.526-16, Bullington com correção (padrão)"], ["j", "Gume único (otimista; só para comparar)"]]));
    campos.appendChild(sel("k", "Fator k do raio da Terra", [["1.3333", "4/3 (padrão)"], ["1", "1 (sem refração)"], ["0.6667", "2/3 (pior caso)"]]));
    campos.appendChild(rng("p", "Potência de TX", 1, u([0, "dBm"])));
    campos.appendChild(rng("gTx", "Ganho da antena A", 0.05, u([2, "dBi"]))); campos.appendChild(rng("gRx", "Ganho da antena B", 0.05, u([2, "dBi"])));
    campos.appendChild(rng("lTx", "Perda de cabo A", 0.1, u([1, "dB"]))); campos.appendChild(rng("lRx", "Perda de cabo B", 0.1, u([1, "dB"])));
    campos.appendChild(rng("extra", "Perda extra (vegetação, paredes)", 0.5, u([1, "dB"])));
    campos.appendChild(sel("sf", "SF do modo escolhido", [7, 8, 9, 10, 11, 12].map(function (x) { return [x, "SF" + x]; })));
    campos.appendChild(sel("bw", "Largura de banda", [125, 250, 500].map(function (x) { return [x, x + " kHz" + (x < 500 ? " (salto)" : " (digital)")]; })));
    campos.appendChild(sel("cr", "Taxa de código", [1, 2, 3, 4].map(function (x) { return [x, "4/" + (x + 4)]; })));
    campos.appendChild(rng("alvo", "Entrega confirmada alvo", 0.005, function (x) { return pct(x); }));
    campos.appendChild(rng("retries", "Retransmissões", 1, u([0, ""]))); campos.appendChild(rng("interval", "Intervalo entre pacotes", 1, u([0, "s"])));
    campos.appendChild(rng("load", "Tráfego de terceiros (× do ambiente)", 0.1, u([1, "×"])));
    desenha();
  }

  function cartao(titulo, kids, cls) { return el("section", { class: "card" + (cls ? " " + cls : "") }, [el("h2", { text: titulo })].concat(kids)); }
  /* mapa de relevo com os tiles já baixados; nenhuma requisição a mais (sem mapa-base de terceiros) */
  function cartaoMapa() {
    var P = function (t) { return parseFloat(String(t).replace(",", ".")); };
    var A = st.terreno === "mapa" ? st.pontos[st.salto] : { lat: P(st.latA), lon: P(st.lonA) }, B = st.terreno === "mapa" ? st.pontos[st.salto + 1] : { lat: P(st.latB), lon: P(st.lonB) };
    var r = TR.relevo(st.tiles.fonte, A, B, 320);
    if (r.erro) return cartao("Mapa de relevo", [el("p", { class: "note", text: r.erro })]);
    var cv = el("canvas", { width: String(r.w), height: String(r.h), role: "img", class: "mapa-relevo", style: "max-width:100%;height:auto;border:1px solid var(--line,#8884)",
      "aria-label": "Relevo em volta dos dois pontos, de " + Math.round(r.min) + " a " + Math.round(r.max) + " m, com a linha do enlace entre A e B" });
    var g = cv.getContext && cv.getContext("2d");
    if (g) {
      g.putImageData(new ImageData(r.rgba, r.w, r.h), 0, 0);
      g.strokeStyle = "#fff"; g.lineWidth = 3; g.beginPath(); g.moveTo(r.A.x, r.A.y); g.lineTo(r.B.x, r.B.y); g.stroke();
      g.strokeStyle = "#c0392b"; g.lineWidth = 1.5; g.stroke();
      [[r.A, "A"], [r.B, "B"]].forEach(function (q) { g.fillStyle = "#c0392b"; g.beginPath(); g.arc(q[0].x, q[0].y, 4, 0, 7); g.fill(); g.fillStyle = "#fff"; g.font = "bold 12px sans-serif"; g.fillText(q[1], q[0].x + 6, q[0].y - 6); });
    }
    return cartao("Mapa de relevo", [cv, el("p", { class: "note", text: "Altitude de " + nf(r.min, 0) + " (verde) a " + nf(r.max, 0) + " m (branco), com sombreado; cada ponto da imagem tem cerca de " + nf(r.km_por_px * 1000, 0) + " m. Feito só com os tiles já baixados: nenhuma outra requisição, sem mapa-base de terceiros. Dados: Terrain Tiles da AWS Open Data." })]);
  }
  /* cadeia de saltos: um enlace por par de pontos seguidos, com o mesmo rádio e o mesmo modo; mostra o salto mais fraco e
   * os modos que atendem o alvo em todos os saltos. Sem coordenadas na saída (só distâncias e dB). */
  function cartaoRota(inpBase) {
    var n = st.pontos.length - 1, rows = [], comuns = null, pior = null, plano = 0, erros = 0, i;
    for (i = 0; i < n; i++) {
      var rot = window.LeguaMapa.rotulo(i) + " → " + window.LeguaMapa.rotulo(i + 1) + (i === st.salto ? " (em detalhe)" : "");
      var ps = perfilSalto(i);
      if (ps.erro) { rows.push([rot, "–", "–", "–", "–", "–", "–", { pill: "bad", text: "erro" }]); erros++; comuns = []; continue; }
      var inp = {}; Object.keys(inpBase).forEach(function (k) { inp[k] = inpBase[k]; }); inp.perfil = ps.perfil;
      var Ai = LE.analisar(inp), esc = Ai.modos.filter(function (m) { return m.sf === st.sf && m.bw === st.bw && m.cr === st.cr; })[0], marg = Ai.estimativa.margem_db, fr = Ai.perfil.folga_min_razao;
      if (ps.plano) plano++;
      var ok = Ai.modos.filter(function (m) { return m.atinge; }).map(nomeModo);
      comuns = comuns === null ? ok : comuns.filter(function (x) { return ok.indexOf(x) >= 0; });
      if (!pior || marg < pior.marg) pior = { rot: rot.replace(" (em detalhe)", ""), marg: marg };
      rows.push([rot, nf(Ai.perfil.D_km, 2) + " km", ps.plano ? "plano (sem elevação)" : "elevação real", nf(Ai.perda.total_db, 1) + " dB", nf(Ai.rx_dbm, 1) + " dBm", nf(marg, 1) + " dB", fr == null ? "–" : nf(100 * Math.min(Math.max(fr, 0), 9.99), 0) + "%", { pill: esc && esc.atinge ? "ok" : "bad", text: esc && esc.atinge ? "atinge" : "não atinge" }]);
    }
    var kids = [el("p", { class: "note", text: "Cada par seguido de pontos é um enlace, com o mesmo rádio, antenas e modo. A rota só fecha se todos os saltos fecharem; o salto mais fraco manda." })];
    if (pior) kids.push(el("p", {}, ["Salto mais fraco: " + pior.rot + ", margem de " + nf(pior.marg, 1) + " dB no modo escolhido. " +
      (comuns && comuns.length ? "Modos que atingem " + pct(st.alvo) + " de entrega em todos os saltos: " + comuns.join(", ") + "." : "Nenhum modo da tabela atinge " + pct(st.alvo) + " em todos os saltos.")]));
    if (plano) kids.push(el("p", { class: "note", text: plano + " salto(s) sem elevação real (terreno plano na altitude base): baixe a elevação com o consentimento acima para valer o terreno." }));
    if (erros) kids.push(el("p", { class: "note", text: erros + " salto(s) com ponto inválido ou distância fora de 0,02 a 100 km." }));
    kids.push(tabela(["Salto", "Distância", "Terreno", "Perda total", "Recebido", "Margem", "Fresnel livre", "Modo escolhido"], rows, [0, 1, 0, 1, 1, 1, 1, 0]));
    return cartao("Rota com " + n + " saltos", kids);
  }
  function stat(v, l) { return el("div", { class: "stat" }, [el("div", { class: "v", text: v }), el("div", { class: "l", text: l })]); }
  function tabela(head, rows, num) {
    var t = el("table"), th = el("thead"), hr = el("tr");
    head.forEach(function (h, i) { hr.appendChild(el("th", { text: h, class: num[i] ? "n" : "" })); }); th.appendChild(hr); t.appendChild(th);
    var tb = el("tbody");
    rows.forEach(function (r) { var tr = el("tr"); r.forEach(function (c, i) { var td = el("td", { class: num[i] ? "n" : "" }); if (c && c.pill) td.appendChild(pill(c.pill, c.text)); else td.textContent = c == null ? "–" : String(c); tr.appendChild(td); }); tb.appendChild(tr); });
    t.appendChild(tb); return el("div", { class: "tbl-wrap", style: "overflow-x:auto" }, [t]);
  }

  var ultimo = null;
  function desenha() {
    host.textContent = "";
    var pr = perfilAtual();
    if (pr.erro) { host.appendChild(cartao("Perfil inválido", [el("p", { class: "note", text: pr.erro })], "warn-card")); ultimo = null; sincroniza(); return; }
    var inp = { perfil: pr.perfil, hTx: st.hTx, hRx: st.hRx, k: parseFloat(st.k), p_dbm: st.p, gTx: st.gTx, gRx: st.gRx, lTx: st.lTx, lRx: st.lRx, extra_db: st.extra, env: st.env,
      sf: st.sf, bw: st.bw, cr: st.cr, fhss: st.bw < 500, retries: st.retries, interval_s: st.interval, load: st.load, alvo: st.alvo, sig: 0, modelo_difracao: st.modelo };
    var A = LE.analisar(inp); A._perfil = pr.perfil; ultimo = { A: A, inp: inp };
    var pf = A.perfil, e = A.estimativa, tip = e.cenarios[1], D = pf.D_km, fr = pf.folga_min_razao;
    var escolhido = A.modos.filter(function (m) { return m.sf === st.sf && m.bw === st.bw && m.cr === st.cr; })[0];
    var modoTxt = "SF" + st.sf + "/" + st.bw + (st.cr > 1 ? "/CR4" + (st.cr + 4) : "") + (st.bw < 500 ? "/FH" : "");
    var frase = "Em " + nf(D, 2) + " km com " + nf(st.p, 0) + " dBm, o sinal chega a " + nf(A.rx_dbm, 1) + " dBm. No modo " + modoTxt + " a margem é de " + nf(e.margem_db, 1) + " dB e a entrega confirmada típica, " + pct(tip.confirmado) +
      (A.melhor ? ". O modo de menor energia que atinge " + pct(st.alvo) + " é " + nomeModo(A.melhor) + " (" + mj(A.melhor.energia_mj_entregue) + " por pacote entregue)." : ". Nenhum modo da tabela atinge " + pct(st.alvo) + " neste enlace: suba a potência, a altura das antenas ou reduza a distância.");
    var avisos = [];
    if (fr != null && fr < 0) avisos.push(pill("bad", "linha de visada obstruída (perda de difração de " + nf(pf.perda_difracao_db, 1) + " dB)"));
    else if (fr != null && fr < 0.6) avisos.push(pill("warn", "primeira zona de Fresnel com apenas " + nf(100 * Math.min(Math.max(fr, 0), 1), 0) + "% livre (o recomendado é 60% ou mais)"));
    else if (fr != null) avisos.push(pill("ok", "primeira zona de Fresnel livre (" + nf(100 * Math.min(fr, 9.99), 0) + "% de folga mínima)"));
    avisos.push(pill("warn", "EIRP de " + nf(A.eirp_dbm, 1) + " dBm: confira o limite do seu perfil regulatório (BR-2026 está nao_verificado)"));
    var resumo = ["Légua, testador de enlaces (estimativa; não é previsão de campo)", frase,
      "Perdas: espaço livre " + nf(A.perda.espaco_livre_db, 1) + " dB + difração " + nf(A.perda.difracao_db, 1) + " dB + extra " + nf(A.perda.extra_db, 1) + " dB = " + nf(A.perda.total_db, 1) + " dB.",
      "Parâmetros: terreno " + st.terreno + "; antenas " + st.hTx + " m e " + st.hRx + " m; k " + st.k + "; ganhos " + st.gTx + " e " + st.gRx + " dBi; cabos " + st.lTx + " e " + st.lRx + " dB; ambiente " + st.env + ".",
      st.terreno === "csv" || st.terreno === "hgt" || st.terreno === "terrarium" || st.terreno === "mapa" ? "(perfil local não incluído no link)" : location.href.split("#")[0] + "#" + consulta()].join("\n");
    var aviso = el("span", { class: "sub", role: "status", "aria-live": "polite" });
    function btn(t, fn) { var b = el("button", { type: "button", class: "btn", text: t }); b.addEventListener("click", fn); return b; }
    var resposta = cartao("Resposta para este enlace", [el("p", {}, [frase]), el("p", {}, avisos.reduce(function (a, p) { a.push(p, document.createTextNode("  ")); return a; }, [])),
      el("div", { class: "controls sem-impressao", style: "display:flex;gap:8px;flex-wrap:wrap;align-items:center" }, [
        btn("Copiar resumo e link", function () { copiar(resumo, aviso); }),
        btn("Baixar CSV (modos)", function () {
          var linhas = [["modo", "tempo_no_ar_ms", "margem_db", "entrega_confirmada", "energia_mj_por_entregue", "latencia_s", "atinge_alvo"]].concat(A.modos.map(function (m) { return [nomeModo(m), m.toa_dados_ms.toFixed(1), m.margem_db.toFixed(1), m.confirmado.toFixed(4), m.energia_mj_entregue == null ? "" : m.energia_mj_entregue.toFixed(2), m.latencia_s == null ? "" : m.latencia_s.toFixed(2), m.atinge ? "sim" : "nao"]; }));
          aviso.textContent = baixar("legua-enlace-modos.csv", "text/csv;charset=utf-8", "﻿" + linhas.map(function (r) { return r.map(csvCell).join(";"); }).join("\r\n") + "\r\n") ? "CSV baixado." : "Não foi possível baixar.";
        }),
        btn("Baixar JSON", function () {
          var js = JSON.stringify({ aviso: "Estimativa; não é previsão de campo nem prova de conformidade regulatória.", gerado_em: DATA.meta.gerado_em, commit: DATA.meta.commit || null, entrada: { terreno: st.terreno, parametros: CHAVES.reduce(function (o, k) { o[k] = st[k]; return o; }, {}) },
            perfil: { d_km: pr.perfil.d, altitude_m: pr.perfil.h }, resultado: { eirp_dbm: A.eirp_dbm, perdas_db: A.perda, rx_dbm: A.rx_dbm, offset_db_para_o_estimador: A.offset_db, folga_fresnel_min_razao: pf.folga_min_razao, difracao: { v: pf.v, d_obst_km: pf.d_obst_km, h_obst_m: pf.h_obst_m, perda_db: pf.perda_difracao_db }, modos: A.modos } }, null, 2);
          aviso.textContent = baixar("legua-enlace.json", "application/json", js) ? "JSON baixado." : "Não foi possível baixar.";
        }),
        btn("Imprimir", function () { window.print(); }), aviso])]);
    var stats = el("div", { class: "stats" }, [stat(nf(A.perda.espaco_livre_db, 1) + " dB", "perda no espaço livre (915 MHz)"), stat(nf(A.perda.difracao_db, 1) + " dB", "perda por difração (Bullington)"),
      stat(nf(A.perda.total_db, 1) + " dB", "perda total (com " + nf(A.perda.extra_db, 1) + " dB extras)"), stat(nf(A.rx_dbm, 1) + " dBm", "potência recebida"),
      stat(nf(e.margem_db, 1) + " dB", "margem no modo " + modoTxt), stat(fr == null ? "–" : nf(100 * fr, 0) + "%", "folga mínima da 1ª zona de Fresnel")]);
    var grafico = cartao("Perfil do enlace", []); desenhaPerfil(grafico, A);
    var linhasModos = A.modos.slice().sort(function (a, b) { return b.margem_db - a.margem_db; }).map(function (m) {
      return [nomeModo(m), nf(m.toa_dados_ms, 0) + " ms", nf(m.margem_db, 1) + " dB", pct(m.confirmado), mj(m.energia_mj_entregue), { pill: m.atinge ? "ok" : "bad", text: m.atinge ? "atinge" : "não atinge" }];
    });
    var tab = cartao("Margem e entrega por modo", [el("p", { class: "note", text: "Modos fixos da tabela BR-2026 (nao_verificado), enlace típico, ordenados pela margem. A Légua negocia entre eles em campo; a energia é de TX, com corrente do PA estimada. A sensibilidade é o centro da curva de erro de pacote usada na simulação, não o limiar do datasheet." }),
      tabela(["Modo", "Tempo no ar", "Margem", "Entrega confirmada", "Energia por entregue", "Alvo " + pct(st.alvo)], linhasModos, [false, true, true, true, true, false])]);
    var cont = el("section", { class: "card warn-card" }, [el("p", { class: "note", text: "Contabilidade de dB: a perda média vem do espaço livre mais a difração do perfil e a perda extra que você informa; o ambiente escolhido contribui só com a variabilidade (sombreamento, desvanecimento, ruído e tráfego), e o estimador recebe a diferença de ganho de antena, sem contar duas vezes. Ficam fora do modelo: reflexão no solo, vegetação e prédios no caminho (use a perda extra), difração em mais de um obstáculo além do equivalente de Bullington e a atmosfera real." })]);
    var mapa = (st.terreno === "terrarium" || st.terreno === "mapa") && st.tiles ? cartaoMapa() : null;
    var rota = st.terreno === "mapa" && st.pontos.length > 2 ? cartaoRota(inp) : null;
    [resposta, rota, stats, grafico, mapa, tab, cont].forEach(function (n) { if (n) host.appendChild(n); });
    sincroniza();
  }

  // o tema é tratado por nav.js, comum às três páginas
  deConsulta((location.hash || "").slice(1));
  app.appendChild(cartao("Parâmetros do enlace", [el("p", { class: "note", text: "Informe o terreno entre as duas antenas (plano, um morro, ou um perfil colado) e os parâmetros do rádio; o resultado se atualiza na hora." }), campos, (function () { var b = el("button", { type: "button", class: "btn sem-impressao", id: "restaura", text: "Restaurar padrões", title: "Volta todos os campos ao estado inicial (o mapa e a elevação baixada são descartados)" }); b.addEventListener("click", function () { Object.keys(PADRAO).forEach(function (k) { st[k] = JSON.parse(JSON.stringify(PADRAO[k])); }); monta(); agenda(); }); return b; })()], null));
  app.appendChild(host);
  app.appendChild(el("section", { class: "card" }, [el("h2", { text: "Entenda os números" }),
    el("dl", { class: "gloss" }, [
      el("dt", { text: "Perda no espaço livre" }), el("dd", { text: "O quanto o sinal enfraquece só por se espalhar no espaço: cresce 20 dB a cada dez vezes a distância. A 915 MHz, cerca de 91,7 dB a 1 km." }),
      el("dt", { text: "Zona de Fresnel" }), el("dd", { text: "O “tubo” em volta da linha reta entre as antenas por onde passa a maior parte do sinal. Com menos de 60% da primeira zona livre, o terreno já tira potência mesmo sem cortar a linha de visada. Antenas mais altas ou menos distância abrem a zona." }),
      el("dt", { text: "Fator k e abaulamento" }), el("dd", { text: "A Terra é curva e a atmosfera curva o sinal um pouco. Com k = 4/3 o abaulamento no meio de 10 km é de cerca de 1,5 m; k menor (pior caso) sobe o “chão” e reduz a folga." }),
      el("dt", { text: "Difração (Bullington, ITU-R P.526-16)" }), el("dd", { text: "Quando um morro entra no caminho, o sinal contorna o topo e chega mais fraco. O método troca os obstáculos por um só, equivalente, e soma a correção empírica da Recomendação; mesmo com visada, uma zona de Fresnel raspando o chão já custa alguns dB. Em comparação com o ITM da NTIA (44 perfis sintéticos, 915 MHz) o testador ainda é otimista, em média cerca de 11 dB, com até 35 dB em morros altos e isolados; trate o resultado em terreno obstruído como limite superior do que chega e use a perda extra para ser conservador." }),
      el("dt", { text: "Perda extra" }), el("dd", { text: "Onde você lança o que o modelo não vê: folhagem, paredes, caixa metálica. Comece com 0 e teste cenários piores." }),
      el("dt", { text: "Margem" }), el("dd", { text: "Quantos dB o sinal fica acima do mínimo que o modo decodifica. Perto de zero perde pacote; 10 a 20 dB aguentam o desvanecimento. Modos mais lentos (SF maior) têm margem maior." }),
      el("dt", { text: "Entrega confirmada" }), el("dd", { text: "A fração de pacotes cujo ACK volta ao emissor, com as retransmissões escolhidas. É o que a aplicação sente." })
    ])]));
  monta();
  window.addEventListener("resize", function () { /* o SVG é escalável: nada a refazer */ });
})();
