/* Elevação por tiles Terrarium (PNG com a altitude codificada em RGB), para o testador de enlaces.
 * Fonte: AWS Open Data "Terrain Tiles" (https://registry.opendata.aws/terrain-tiles/), derivada de SRTM, Copernicus e
 * outros DEMs; a atribuição exigida está na página. Codificação: altitude (m) = R*256 + G + B/256 - 32768.
 *
 * PRIVACIDADE: este é o único trecho do site que fala com a rede, e só depois de um clique com consentimento. O que
 * sai é a URL de cada tile (zoom, x, y), que revela a região (~10 km no zoom 12) e o endereço IP do navegador ao
 * servidor da AWS; as coordenadas exatas dos pontos NUNCA são enviadas. Sem cookies, sem referenciador. O módulo
 * não guarda nada em disco: a memória de tiles vive só na página. Sem DOM aqui (a decodificação do PNG é injetada),
 * para poder testar em Node. */
(function (root) {
  "use strict";
  var BASE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/";
  var Z_PADRAO = 12, Z_MIN = 8, Z_MAX = 14, MAX_TILES = 24, MAX_TILES_TOTAL = 64, TAM = 256;

  function urlTile(z, x, y) { return BASE + z + "/" + x + "/" + y + ".png"; }

  /* coordenadas contínuas de tile (Web Mercator) */
  function tileXY(lat, lon, z) {
    var n = Math.pow(2, z), r = lat * Math.PI / 180;
    return { x: (lon + 180) / 360 * n, y: (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n };
  }

  /* tiles que cobrem o segmento A-B (amostrado fino o bastante para não pular tile), com 1 pixel de folga para a
   * interpolação bilinear nas bordas. Devolve { tiles: [{z,x,y}] } ou { erro }. */
  function tilesDoCaminho(a, b, z) {
    z = z || Z_PADRAO;
    if (![a.lat, a.lon, b.lat, b.lon].every(isFinite)) return { erro: "informe as quatro coordenadas" };
    if (Math.abs(a.lat) > 84 || Math.abs(b.lat) > 84 || Math.abs(a.lon) > 180 || Math.abs(b.lon) > 180) return { erro: "Coordenada fora do intervalo válido: a latitude vai de −90 a 90 e a longitude de −180 a 180. Confira se não trocou latitude e longitude." };
    if (z < Z_MIN || z > Z_MAX) return { erro: "zoom fora de " + Z_MIN + " a " + Z_MAX };
    var n = Math.pow(2, z), vistos = {}, tiles = [], passos = 400, i, dx, dy;
    for (i = 0; i <= passos; i++) {
      var t = i / passos, p = tileXY(a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t, z);
      for (dx = -1; dx <= 1; dx += 2) for (dy = -1; dy <= 1; dy += 2) {
        var tx = Math.floor(p.x + dx / TAM), ty = Math.floor(p.y + dy / TAM);
        if (ty < 0 || ty >= n) continue;
        tx = ((tx % n) + n) % n;
        var k = tx + "/" + ty;
        if (!vistos[k]) { vistos[k] = 1; tiles.push({ z: z, x: tx, y: ty }); }
      }
    }
    if (tiles.length > MAX_TILES) return { erro: "O caminho é longo demais para baixar a elevação (" + tiles.length + " pedaços, máximo " + MAX_TILES + "). Reduza a distância" };
    return { tiles: tiles };
  }

  /* RGBA (Uint8ClampedArray de 256x256x4) -> Float32Array de altitudes em metros */
  function decodificar(rgba) {
    var out = new Float32Array(TAM * TAM), i;
    if (!rgba || rgba.length < TAM * TAM * 4) return null;
    for (i = 0; i < TAM * TAM; i++) out[i] = rgba[4 * i] * 256 + rgba[4 * i + 1] + rgba[4 * i + 2] / 256 - 32768;
    return out;
  }

  /* fonte de elevação síncrona sobre os tiles já carregados: f(lat, lon) -> { v, ok, falta }.
   * mapa: { "z/x/y": Float32Array(256*256) }. Interpolação bilinear entre centros de pixel. */
  function fonte(mapa, z) {
    var n = Math.pow(2, z);
    var W = n * TAM;
    function px(X, Y) {                                  // pixel global (X, Y): número, null (fora do mapa) ou a chave do tile que falta
      var ty = Math.floor(Y / TAM);
      if (ty < 0 || ty >= n) return null;
      var Xw = ((X % W) + W) % W, tx = Math.floor(Xw / TAM), k = z + "/" + tx + "/" + ty, d = mapa[k];
      return d ? d[(Y - ty * TAM) * TAM + (Xw - tx * TAM)] : k;
    }
    return function (lat, lon) {
      var p = tileXY(lat, lon, z), X = p.x * TAM - 0.5, Y = p.y * TAM - 0.5;
      var x0 = Math.floor(X), y0 = Math.floor(Y), fx = X - x0, fy = Y - y0;
      var v = [px(x0, y0), px(x0 + 1, y0), px(x0, y0 + 1), px(x0 + 1, y0 + 1)], w = [(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy], s = 0, d = 0, j;
      for (j = 0; j < 4; j++) {
        if (typeof v[j] === "string") return { v: NaN, ok: false, falta: "tile Terrarium " + v[j] };
        if (v[j] !== null && isFinite(v[j])) { s += w[j] * v[j]; d += w[j]; }
      }
      return d > 1e-9 ? { v: s / d, ok: true } : { v: NaN, ok: true };
    };
  }

  /* Busca os tiles de um ou mais saltos [[a, b], ...] com `buscar(url) -> Promise<Float32Array|null>` (injetado: no
   * navegador, fetch + canvas). Tiles repetidos entre saltos são baixados uma vez. Concorrência baixa (2) para não
   * castigar o servidor nem a máquina. Resolve { fonte, n_tiles, z } ou { erro }. */
  function carregarSaltos(saltos, z, buscar) {
    var vistos = {}, fila = [], k, r, i;
    if (!saltos.length) return Promise.resolve({ erro: "informe ao menos dois pontos" });
    for (k = 0; k < saltos.length; k++) {
      r = tilesDoCaminho(saltos[k][0], saltos[k][1], z);
      if (r.erro) return Promise.resolve({ erro: (saltos.length > 1 ? "salto " + (k + 1) + ": " : "") + r.erro });
      for (i = 0; i < r.tiles.length; i++) { var t = r.tiles[i], c = t.z + "/" + t.x + "/" + t.y; if (!vistos[c]) { vistos[c] = 1; fila.push(t); } }
    }
    if (fila.length > MAX_TILES_TOTAL) return Promise.resolve({ erro: "A rota é grande demais para baixar a elevação de uma vez (" + fila.length + " pedaços, máximo " + MAX_TILES_TOTAL + "). Reduza as distâncias ou o número de saltos" });
    var mapa = {}, falhas = [], total = fila.length, zz = fila[0].z;
    function um() {
      var t = fila.shift();
      if (!t) return Promise.resolve();
      return Promise.resolve().then(function () { return buscar(urlTile(t.z, t.x, t.y)); }).then(function (d) {
        if (d) mapa[t.z + "/" + t.x + "/" + t.y] = d; else falhas.push(t.z + "/" + t.x + "/" + t.y);
      }, function (e) { falhas.push(t.z + "/" + t.x + "/" + t.y + " (" + (e && e.message ? e.message : "falha") + ")"); }).then(um);
    }
    return Promise.all([um(), um()]).then(function () {
      if (falhas.length) return { erro: "Não consegui baixar a elevação (" + falhas.length + " de " + total + " pedaços). Causas comuns: sem internet, bloqueador de anúncios ou rede da empresa. Você pode tentar de novo, colar um perfil (CSV) ou carregar um arquivo .hgt. Detalhe técnico: " + falhas.slice(0, 2).join(", ") };
      return { fonte: fonte(mapa, zz), n_tiles: total, z: zz };
    });
  }
  function carregar(a, b, z, buscar) { return carregarSaltos([[a, b]], z, buscar); }

  /* Mapa de relevo sem rede extra: pinta, com os mesmos tiles já baixados, a altitude em rampa de cor com sombreado
   * (luz de noroeste) na caixa em volta dos pontos A e B. Devolve { w, h, rgba, lat0, lat1, lon0, lon1, min, max } ou
   * { erro }; áreas sem tile ficam transparentes. Projeção equiretangular com escala de longitude por cos(lat). */
  function relevo(f, a, b, larg) {
    larg = larg || 320;
    var cx = Math.cos((a.lat + b.lat) / 2 * Math.PI / 180), dlat = Math.abs(a.lat - b.lat), dlon = Math.abs(a.lon - b.lon) * cx;
    var lado = Math.max(dlat, dlon, 0.02), mlat = (lado - dlat) / 2 + 0.25 * lado, mlon = (lado - dlon) / 2 + 0.25 * lado;
    var lat0 = Math.min(a.lat, b.lat) - mlat, lat1 = Math.max(a.lat, b.lat) + mlat;
    var lon0 = Math.min(a.lon, b.lon) - mlon / cx, lon1 = Math.max(a.lon, b.lon) + mlon / cx;
    var w = larg, h = Math.max(40, Math.round(larg * (lat1 - lat0) / ((lon1 - lon0) * cx))), z = new Float32Array(w * h), i, j, lo = Infinity, hi = -Infinity;
    for (j = 0; j < h; j++) for (i = 0; i < w; i++) {
      var e = f(lat1 - (lat1 - lat0) * j / (h - 1), lon0 + (lon1 - lon0) * i / (w - 1)), v = e.ok && isFinite(e.v) ? e.v : NaN;
      z[j * w + i] = v; if (v === v) { if (v < lo) lo = v; if (v > hi) hi = v; }
    }
    if (!(hi >= lo)) return { erro: "sem altitudes nesta área" };
    var rgba = new Uint8ClampedArray(w * h * 4), esc = Math.max(hi - lo, 1), pxM = (lon1 - lon0) * cx * 111320 / (w - 1);
    var rampa = [[0, 60, 120, 70], [0.35, 150, 170, 90], [0.7, 150, 110, 70], [1, 245, 240, 235]];
    function cor(t) { var k = 0; while (k < rampa.length - 2 && t > rampa[k + 1][0]) k++; var u = (t - rampa[k][0]) / (rampa[k + 1][0] - rampa[k][0]); u = Math.min(Math.max(u, 0), 1); return [1, 2, 3].map(function (q) { return rampa[k][q] + (rampa[k + 1][q] - rampa[k][q]) * u; }); }
    for (j = 0; j < h; j++) for (i = 0; i < w; i++) {
      var o = (j * w + i) * 4, v = z[j * w + i];
      if (v !== v) continue;
      var vx = z[j * w + Math.min(i + 1, w - 1)], vy = z[Math.min(j + 1, h - 1) * w + i], ox = z[j * w + Math.max(i - 1, 0)], oy = z[Math.max(j - 1, 0) * w + i];
      var gx = ((vx === vx ? vx : v) - (ox === ox ? ox : v)) / (2 * pxM), gy = ((vy === vy ? vy : v) - (oy === oy ? oy : v)) / (2 * pxM);
      var sombra = Math.min(Math.max(0.85 + 1.6 * (gx - gy) / Math.SQRT2, 0.55), 1.25), c = cor((v - lo) / esc);
      rgba[o] = Math.min(255, c[0] * sombra); rgba[o + 1] = Math.min(255, c[1] * sombra); rgba[o + 2] = Math.min(255, c[2] * sombra); rgba[o + 3] = 255;
    }
    function xy(p) { return { x: (p.lon - lon0) / (lon1 - lon0) * (w - 1), y: (lat1 - p.lat) / (lat1 - lat0) * (h - 1) }; }
    return { w: w, h: h, rgba: rgba, lat0: lat0, lat1: lat1, lon0: lon0, lon1: lon1, min: lo, max: hi, A: xy(a), B: xy(b), km_por_px: pxM / 1000 };
  }

  /* No navegador: baixa um PNG e devolve as altitudes. Sem cookies nem referenciador. */
  function buscarNoNavegador(url) {
    if (typeof fetch !== "function" || typeof createImageBitmap !== "function") return Promise.reject(new Error("navegador sem fetch/createImageBitmap"));
    return fetch(url, { mode: "cors", credentials: "omit", referrerPolicy: "no-referrer", cache: "force-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.blob();
    }).then(function (blob) { return createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" }); }).then(function (bmp) {
      var c = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(TAM, TAM) : Object.assign(document.createElement("canvas"), { width: TAM, height: TAM });
      var g = c.getContext("2d", { willReadFrequently: true });
      g.drawImage(bmp, 0, 0);
      return decodificar(g.getImageData(0, 0, TAM, TAM).data);
    });
  }

  var api = { urlTile: urlTile, tileXY: tileXY, tilesDoCaminho: tilesDoCaminho, decodificar: decodificar, fonte: fonte, relevo: relevo, carregar: carregar, carregarSaltos: carregarSaltos,
    buscarNoNavegador: buscarNoNavegador, Z_PADRAO: Z_PADRAO, MAX_TILES: MAX_TILES, BASE: BASE };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaTerrarium = api;
})(typeof window !== "undefined" ? window : this);
