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
  var Z_PADRAO = 12, Z_MIN = 8, Z_MAX = 14, MAX_TILES = 24, TAM = 256;

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
    if (Math.abs(a.lat) > 84 || Math.abs(b.lat) > 84 || Math.abs(a.lon) > 180 || Math.abs(b.lon) > 180) return { erro: "coordenada fora do intervalo válido" };
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
    if (tiles.length > MAX_TILES) return { erro: "o caminho precisaria de " + tiles.length + " tiles (máximo " + MAX_TILES + "); reduza a distância" };
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

  /* Busca os tiles do caminho com `buscar(url) -> Promise<Float32Array|null>` (injetado: no navegador, fetch + canvas).
   * Concorrência baixa (2) para não castigar o servidor nem a máquina. Resolve { fonte, n_tiles, z } ou { erro }. */
  function carregar(a, b, z, buscar) {
    var r = tilesDoCaminho(a, b, z);
    if (r.erro) return Promise.resolve({ erro: r.erro });
    var mapa = {}, fila = r.tiles.slice(), falhas = [], total = fila.length;
    function um() {
      var t = fila.shift();
      if (!t) return Promise.resolve();
      return Promise.resolve().then(function () { return buscar(urlTile(t.z, t.x, t.y)); }).then(function (d) {
        if (d) mapa[t.z + "/" + t.x + "/" + t.y] = d; else falhas.push(t.z + "/" + t.x + "/" + t.y);
      }, function (e) { falhas.push(t.z + "/" + t.x + "/" + t.y + " (" + (e && e.message ? e.message : "falha") + ")"); }).then(um);
    }
    return Promise.all([um(), um()]).then(function () {
      if (falhas.length) return { erro: "não consegui baixar " + falhas.length + " de " + total + " tiles (rede bloqueada, sem CORS ou fora do ar): " + falhas.slice(0, 2).join(", ") };
      return { fonte: fonte(mapa, r.tiles[0].z), n_tiles: total, z: r.tiles[0].z };
    });
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

  var api = { urlTile: urlTile, tileXY: tileXY, tilesDoCaminho: tilesDoCaminho, decodificar: decodificar, fonte: fonte, carregar: carregar,
    buscarNoNavegador: buscarNoNavegador, Z_PADRAO: Z_PADRAO, MAX_TILES: MAX_TILES, BASE: BASE };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaTerrarium = api;
})(typeof window !== "undefined" ? window : this);
