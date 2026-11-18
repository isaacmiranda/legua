/* Mapa para escolher os pontos do enlace, sem biblioteca: tiles de mapa-base do OpenStreetMap (Web Mercator, 256 px),
 * arrastar para mover, roda ou +/- para o zoom, clique (ou Enter no teclado) para pôr um ponto, arrastar o ponto para
 * ajustar. Os pontos são A, B, C... na ordem em que foram postos; cada par seguido é um salto do enlace.
 *
 * PRIVACIDADE (a regra do projeto é não mandar coordenadas de campo a serviços externos):
 *  - nada é pedido à rede antes do consentimento explícito (`consentir(true)`); sem ele só aparece o aviso;
 *  - o que sai são as URLs dos tiles que cobrem a janela que você está vendo (zoom, x, y) e o seu IP, para
 *    tile.openstreetmap.org; as coordenadas exatas dos pontos nunca viram parte de uma URL;
 *  - o referenciador enviado é só a origem do site (`referrerPolicy = "origin"`): a política de uso dos tiles do OSM pede
 *    um Referer válido, e a origem não leva o caminho nem o fragmento da página;
 *  - a vista inicial é o Brasil inteiro (zoom 4), que não revela nada. Os pontos ficam só na memória da página.
 * Atribuição obrigatória: © colaboradores do OpenStreetMap (ODbL), mostrada no mapa. Uso leve; não é para varredura. */
(function (root) {
  "use strict";
  var TILE = 256, URL_BASE = "https://tile.openstreetmap.org/", Z_MIN = 3, Z_MAX = 17, MAX_PONTOS = 8, LAT_MAX = 85.0511287798;
  var VISTA_INICIAL = { lat: -14.2, lon: -51.9, z: 4 };

  function clampLat(lat) { return Math.max(-LAT_MAX, Math.min(LAT_MAX, lat)); }
  /* coordenada global em pixels no zoom z */
  function proj(lat, lon, z) {
    var n = Math.pow(2, z) * TILE, r = clampLat(lat) * Math.PI / 180;
    return { x: (lon + 180) / 360 * n, y: (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n };
  }
  function inv(x, y, z) {
    var n = Math.pow(2, z) * TILE, t = Math.PI * (1 - 2 * y / n);
    return { lat: Math.atan(Math.sinh(t)) * 180 / Math.PI, lon: x / n * 360 - 180 };
  }
  function normLon(lon) { return ((lon + 180) % 360 + 360) % 360 - 180; }

  /* tiles visíveis numa janela w x h centrada em (lat, lon): [{z, x, y, px, py}] com px,py = canto do tile na janela */
  function tilesVisiveis(v, w, h) {
    var c = proj(v.lat, v.lon, v.z), x0 = c.x - w / 2, y0 = c.y - h / 2, n = Math.pow(2, v.z), out = [], tx, ty;
    for (ty = Math.floor(y0 / TILE); ty <= Math.floor((y0 + h) / TILE); ty++) {
      if (ty < 0 || ty >= n) continue;
      for (tx = Math.floor(x0 / TILE); tx <= Math.floor((x0 + w) / TILE); tx++) {
        out.push({ z: v.z, x: ((tx % n) + n) % n, y: ty, px: tx * TILE - x0, py: ty * TILE - y0 });
      }
    }
    return out;
  }
  function urlTile(t) { return URL_BASE + t.z + "/" + t.x + "/" + t.y + ".png"; }

  /* novo zoom mantendo fixo o ponto (px, py) da janela: devolve a nova vista */
  function zoomEm(v, w, h, px, py, dz) {
    var z = Math.max(Z_MIN, Math.min(Z_MAX, v.z + dz));
    if (z === v.z) return v;
    var c = proj(v.lat, v.lon, v.z), alvo = inv(c.x - w / 2 + px, c.y - h / 2 + py, v.z), a = proj(alvo.lat, alvo.lon, z);
    var novo = inv(a.x - px + w / 2, a.y - py + h / 2, z);
    return { lat: clampLat(novo.lat), lon: normLon(novo.lon), z: z };
  }
  /* vista que enquadra todos os pontos (com folga); um só ponto: zoom 13 */
  function enquadrar(pts, w, h) {
    if (!pts.length) return VISTA_INICIAL;
    var la = pts.map(function (p) { return p.lat; }), lo = pts.map(function (p) { return p.lon; });
    var cla = (Math.min.apply(null, la) + Math.max.apply(null, la)) / 2, clo = (Math.min.apply(null, lo) + Math.max.apply(null, lo)) / 2, z;
    for (z = Z_MAX; z >= Z_MIN; z--) {
      var a = proj(Math.max.apply(null, la), Math.min.apply(null, lo), z), b = proj(Math.min.apply(null, la), Math.max.apply(null, lo), z);
      if (b.x - a.x < w * 0.75 && b.y - a.y < h * 0.75) return { lat: cla, lon: clo, z: Math.min(z, pts.length === 1 ? 13 : Z_MAX) };
    }
    return { lat: cla, lon: clo, z: Z_MIN };
  }
  function rotulo(i) { return String.fromCharCode(65 + i); }

  /* ---------------------------------------------------------------- componente (DOM) */
  function criar(host, op) {
    op = op || {};
    var doc = host.ownerDocument, vista = { lat: VISTA_INICIAL.lat, lon: VISTA_INICIAL.lon, z: VISTA_INICIAL.z }, pontos = [], consentiu = false, ouvintes = [];
    var cx = doc.createElement("div"), camada = doc.createElement("div"), svg = doc.createElementNS("http://www.w3.org/2000/svg", "svg"), marc = doc.createElement("div");
    var aviso = doc.createElement("div"), atrib = doc.createElement("div"), mira = doc.createElement("div");
    cx.className = "mapa"; cx.tabIndex = 0; cx.setAttribute("role", "application");
    cx.setAttribute("aria-label", "Mapa para escolher os pontos do enlace. Setas movem, mais e menos mudam o zoom, Enter põe um ponto no centro.");
    cx.style.cssText = "position:relative;overflow:hidden;height:" + (op.altura || 380) + "px;border:1px solid var(--border);border-radius:8px;background:var(--surface);touch-action:none;cursor:grab";
    camada.style.cssText = "position:absolute;inset:0"; svg.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none"; marc.style.cssText = "position:absolute;inset:0;pointer-events:none";
    mira.style.cssText = "position:absolute;left:50%;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;border:1px solid #c0392b;border-radius:50%;opacity:.55;pointer-events:none";
    aviso.style.cssText = "position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:16px;font-size:13px;color:var(--text-2);background:var(--surface)";
    aviso.textContent = "O mapa-base ainda não foi pedido. Marque o consentimento abaixo para baixar os tiles do OpenStreetMap; os pontos também podem ser digitados na tabela.";
    atrib.style.cssText = "position:absolute;right:0;bottom:0;background:rgba(255,255,255,.8);color:#222;font-size:11px;padding:1px 6px";
    atrib.innerHTML = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer" style="color:#1a5fb4">colaboradores do OpenStreetMap</a>';
    [camada, svg, marc, mira, aviso, atrib].forEach(function (n) { cx.appendChild(n); });
    host.appendChild(cx);

    function tam() { var r = cx.getBoundingClientRect(); return { w: r.width || 640, h: r.height || (op.altura || 380) }; }
    function avisa() { ouvintes.forEach(function (f) { f(pontos.map(function (p) { return { lat: p.lat, lon: p.lon }; })); }); }
    function px(lat, lon) { var s = tam(), c = proj(vista.lat, vista.lon, vista.z), p = proj(lat, lon, vista.z); return { x: p.x - c.x + s.w / 2, y: p.y - c.y + s.h / 2 }; }
    function geo(x, y) { var s = tam(), c = proj(vista.lat, vista.lon, vista.z); var g = inv(c.x - s.w / 2 + x, c.y - s.h / 2 + y, vista.z); return { lat: g.lat, lon: normLon(g.lon) }; }

    function desenha() {
      var s = tam();
      aviso.style.display = consentiu ? "none" : "flex";
      camada.textContent = "";
      if (consentiu) tilesVisiveis(vista, s.w, s.h).forEach(function (t) {
        var im = doc.createElement("img");
        im.alt = ""; im.width = TILE; im.height = TILE; im.draggable = false; im.decoding = "async";
        im.referrerPolicy = "origin"; im.setAttribute("referrerpolicy", "origin");
        im.style.cssText = "position:absolute;left:" + Math.round(t.px) + "px;top:" + Math.round(t.py) + "px;width:" + TILE + "px;height:" + TILE + "px;user-select:none";
        im.src = urlTile(t);
        camada.appendChild(im);
      });
      svg.textContent = ""; marc.textContent = "";
      var validos = pontos.map(function (p, i) { return { i: i, p: p }; }).filter(function (q) { return isFinite(q.p.lat) && isFinite(q.p.lon); });
      var pts = validos.map(function (q) { return px(q.p.lat, q.p.lon); });
      if (pts.length > 1) {
        var pl = doc.createElementNS("http://www.w3.org/2000/svg", "polyline");
        pl.setAttribute("points", pts.map(function (p) { return p.x.toFixed(1) + "," + p.y.toFixed(1); }).join(" "));
        pl.setAttribute("fill", "none"); pl.setAttribute("stroke", "#c0392b"); pl.setAttribute("stroke-width", "3"); pl.setAttribute("stroke-dasharray", "6 4");
        svg.appendChild(pl);
      }
      pts.forEach(function (p, k) {
        var i = validos[k].i, m = doc.createElement("div");
        m.textContent = rotulo(i); m.dataset.i = String(i); m.title = "Ponto " + rotulo(i) + " (arraste para mover)";
        m.style.cssText = "position:absolute;left:" + (p.x - 11).toFixed(1) + "px;top:" + (p.y - 11).toFixed(1) + "px;width:22px;height:22px;border-radius:50%;background:#c0392b;color:#fff;font:700 12px/22px sans-serif;text-align:center;border:2px solid #fff;box-shadow:0 1px 3px #0006;pointer-events:auto;cursor:move";
        marc.appendChild(m);
      });
    }

    function pos(ev) { var r = cx.getBoundingClientRect(); return { x: ev.clientX - r.left, y: ev.clientY - r.top }; }
    var arrasto = null;
    cx.addEventListener("pointerdown", function (ev) {
      if (!consentiu || ev.button > 0) return;
      var p = pos(ev), alvo = ev.target && ev.target.dataset && ev.target.dataset.i;
      arrasto = { x: p.x, y: p.y, mover: alvo != null && alvo !== "" ? +alvo : -1, vista: { lat: vista.lat, lon: vista.lon, z: vista.z }, andou: false };
      try { cx.setPointerCapture(ev.pointerId); } catch (e) { /* jsdom */ }
      cx.style.cursor = "grabbing";
    });
    cx.addEventListener("pointermove", function (ev) {
      if (!arrasto) return;
      var p = pos(ev), dx = p.x - arrasto.x, dy = p.y - arrasto.y;
      if (!arrasto.andou && Math.abs(dx) + Math.abs(dy) < 4) return;
      arrasto.andou = true;
      if (arrasto.mover >= 0) { var g = geo(p.x, p.y); pontos[arrasto.mover].lat = g.lat; pontos[arrasto.mover].lon = g.lon; desenha(); }
      else { var s = tam(), c = proj(arrasto.vista.lat, arrasto.vista.lon, arrasto.vista.z), n = inv(c.x - dx, c.y - dy, arrasto.vista.z); vista = { lat: clampLat(n.lat), lon: normLon(n.lon), z: vista.z }; desenha(); }
    });
    function solta(ev) {
      if (!arrasto) return;
      var a = arrasto; arrasto = null; cx.style.cursor = "grab";
      if (a.mover >= 0 && a.andou) { avisa(); return; }
      if (!a.andou && a.mover < 0 && ev.type === "pointerup") { var p = pos(ev), g = geo(p.x, p.y); adicionar(g.lat, g.lon); }
    }
    cx.addEventListener("pointerup", solta); cx.addEventListener("pointercancel", function () { arrasto = null; cx.style.cursor = "grab"; });
    cx.addEventListener("wheel", function (ev) {
      if (!consentiu) return;
      ev.preventDefault(); var p = pos(ev), s = tam();
      vista = zoomEm(vista, s.w, s.h, p.x, p.y, ev.deltaY < 0 ? 1 : -1); desenha();
    }, { passive: false });
    cx.addEventListener("keydown", function (ev) {
      if (!consentiu) return;
      var s = tam(), c = proj(vista.lat, vista.lon, vista.z), passo = 80, d = null;
      if (ev.key === "ArrowLeft") d = [-passo, 0]; else if (ev.key === "ArrowRight") d = [passo, 0]; else if (ev.key === "ArrowUp") d = [0, -passo]; else if (ev.key === "ArrowDown") d = [0, passo];
      if (d) { var n = inv(c.x + d[0], c.y + d[1], vista.z); vista = { lat: clampLat(n.lat), lon: normLon(n.lon), z: vista.z }; desenha(); ev.preventDefault(); }
      else if (ev.key === "+" || ev.key === "=") { vista = zoomEm(vista, s.w, s.h, s.w / 2, s.h / 2, 1); desenha(); ev.preventDefault(); }
      else if (ev.key === "-") { vista = zoomEm(vista, s.w, s.h, s.w / 2, s.h / 2, -1); desenha(); ev.preventDefault(); }
      else if (ev.key === "Enter") { adicionar(vista.lat, vista.lon); ev.preventDefault(); }
    });

    function adicionar(lat, lon) {
      if (pontos.length >= MAX_PONTOS) return false;
      pontos.push({ lat: lat, lon: lon }); desenha(); avisa(); return true;
    }
    var api = {
      elemento: cx, adicionar: adicionar,
      pontos: function () { return pontos.map(function (p) { return { lat: p.lat, lon: p.lon }; }); },
      definir: function (arr) { pontos = (arr || []).slice(0, MAX_PONTOS).map(function (p) { return { lat: p.lat, lon: p.lon }; }); desenha(); },
      consentir: function (sim) { consentiu = !!sim; desenha(); },
      enquadrar: function () { var s = tam(); vista = enquadrar(pontos, s.w, s.h); desenha(); },
      ir: function (lat, lon, z) { vista = { lat: lat, lon: lon, z: z || vista.z }; desenha(); },
      vista: function () { return { lat: vista.lat, lon: vista.lon, z: vista.z }; },
      aoMudar: function (f) { ouvintes.push(f); },
      zoom: function (dz) { var s = tam(); vista = zoomEm(vista, s.w, s.h, s.w / 2, s.h / 2, dz); desenha(); },
      redesenhar: desenha
    };
    desenha();
    return api;
  }

  var api = { proj: proj, inv: inv, tilesVisiveis: tilesVisiveis, urlTile: urlTile, zoomEm: zoomEm, enquadrar: enquadrar, rotulo: rotulo, criar: criar,
    MAX_PONTOS: MAX_PONTOS, URL_BASE: URL_BASE, VISTA_INICIAL: VISTA_INICIAL };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaMapa = api;
})(typeof window !== "undefined" ? window : this);
