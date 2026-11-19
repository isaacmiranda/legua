/* Cobertura em área a partir de um ponto (sem DOM): margem de enlace em cada célula de uma grade em volta do transmissor, com a
 * perda de espaço livre e a difração pela ITU-R P.526-16 sobre o perfil de elevação (propagacao.js). Estimativa sobre um modelo
 * de superfície: copas e prédios contam como terreno, e o modelo é otimista frente ao ITM (docs/09 §7.1). Não é previsão de campo. */
(function (root) {
  "use strict";
  var P = root.LeguaPropagacao || (typeof require !== "undefined" ? require("./propagacao.js") : null);
  var R_KM = 6371.0088, F_MHZ = 915.0;

  function destino(lat, lon, rumoGraus, dKm) {
    var r = Math.PI / 180, d = dKm / R_KM, b = rumoGraus * r, la1 = lat * r, lo1 = lon * r;
    var la2 = Math.asin(Math.sin(la1) * Math.cos(d) + Math.cos(la1) * Math.sin(d) * Math.cos(b));
    var lo2 = lo1 + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(la1), Math.cos(d) - Math.sin(la1) * Math.sin(la2));
    return { lat: la2 / r, lon: ((lo2 / r + 540) % 360) - 180 };
  }
  function haversineKm(a, b) {
    var r = Math.PI / 180, x = Math.sin((b.lat - a.lat) * r / 2), y = Math.sin((b.lon - a.lon) * r / 2), h = x * x + Math.cos(a.lat * r) * Math.cos(b.lat * r) * y * y;
    return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  /* perfil entre a e b com n amostras (interpolação linear em lat/lon); null se faltar elevação em algum ponto */
  function perfil(fonte, a, b, n) {
    var D = haversineKm(a, b), d = [], h = [], i;
    for (i = 0; i < n; i++) {
      var t = i / (n - 1), e = fonte(a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t);
      if (!e.ok) return { falta: true };
      if (!isFinite(e.v)) return { vazio: true };
      d.push(D * t); h.push(e.v);
    }
    return { d: d, h: h, D: D };
  }

  /* p: { centro{lat,lon}, raioKm, n (células por lado, ímpar), hTx, hRx, k, pDbm, ganhos (dB, soma de antenas menos cabos), extraDb, sensDbm }
   * Devolve { n, margem: Float32Array(n*n) (NaN = sem dado), lat0, lat1, lon0, lon1, semTile (bool) }. */
  function grade(fonte, p) {
    var n = p.n || 41, marg = new Float32Array(n * n), la0 = destino(p.centro.lat, p.centro.lon, 180, p.raioKm).lat, la1 = destino(p.centro.lat, p.centro.lon, 0, p.raioKm).lat;
    var cx = Math.cos(p.centro.lat * Math.PI / 180), dlon = p.raioKm / (111.195 * cx), lo0 = p.centro.lon - dlon, lo1 = p.centro.lon + dlon, i, j, semTile = false;
    for (j = 0; j < n; j++) for (i = 0; i < n; i++) {
      var lat = la1 - (la1 - la0) * j / (n - 1), lon = lo0 + (lo1 - lo0) * i / (n - 1), idx = j * n + i, B = { lat: lat, lon: lon }, D = haversineKm(p.centro, B);
      if (D < 0.02) { marg[idx] = NaN; continue; }
      var np = Math.max(8, Math.min(100, Math.ceil(D * 1000 / 90)) + 1), pf = perfil(fonte, p.centro, B, np);
      if (pf.falta) { semTile = true; marg[idx] = NaN; continue; }
      if (pf.vazio) { marg[idx] = NaN; continue; }
      var a = P.analisarPerfil({ d: pf.d, h: pf.h }, p.hTx, p.hRx, p.k, F_MHZ), perda = P.fspl(pf.D, F_MHZ) + a.perda_difracao_db + (p.extraDb || 0);
      marg[idx] = p.pDbm + p.ganhos - perda - p.sensDbm;
    }
    return { n: n, margem: marg, lat0: la0, lat1: la1, lon0: lo0, lon1: lo1, semTile: semTile };
  }

  /* resumo: área (km²) com margem >= limiar e alcance por rumo (distância até a última célula com margem >= 0 em 16 rumos) */
  function resumo(g, p, limiares) {
    var n = g.n, cx = Math.cos(p.centro.lat * Math.PI / 180), alturaKm = (g.lat1 - g.lat0) * 111.195, larguraKm = (g.lon1 - g.lon0) * 111.195 * cx, celula = (alturaKm / (n - 1)) * (larguraKm / (n - 1)), out = { area: {}, rumos: [] };
    (limiares || [0, 10, 20]).forEach(function (L) { var c = 0, k; for (k = 0; k < g.margem.length; k++) if (g.margem[k] >= L) c++; out.area[L] = c * celula; });
    var r, s;
    for (r = 0; r < 16; r++) {
      var rumo = r * 22.5, ult = 0;
      for (s = 1; s <= 60; s++) {
        var d = p.raioKm * s / 60, q = destino(p.centro.lat, p.centro.lon, rumo, d);
        var i = Math.round((q.lon - g.lon0) / (g.lon1 - g.lon0) * (n - 1)), j = Math.round((g.lat1 - q.lat) / (g.lat1 - g.lat0) * (n - 1));
        if (i < 0 || i >= n || j < 0 || j >= n) break;
        var v = g.margem[j * n + i]; if (v >= 0) ult = d;
      }
      out.rumos.push({ rumo: rumo, alcanceKm: ult });
    }
    return out;
  }

  /* cor RGBA por margem (dB): vermelho < 0, laranja 0-10, amarelo 10-20, verde >= 20 */
  function cor(m) {
    if (!isFinite(m)) return [0, 0, 0, 0];
    if (m < 0) return [200, 60, 50, 150]; if (m < 10) return [235, 140, 50, 190]; if (m < 20) return [235, 210, 70, 190]; return [60, 170, 100, 200];
  }

  var api = { destino: destino, haversineKm: haversineKm, perfil: perfil, grade: grade, resumo: resumo, cor: cor };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaCobertura = api;
})(typeof window !== "undefined" ? window : this);
