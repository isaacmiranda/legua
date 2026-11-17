/* Propagação para o testador de enlaces: funções puras (dB, m, km), sem DOM. Referência Python e teste de paridade:
 * simsuite/analysis/enlace.py e simsuite/tests/test_enlace.py.
 * Modelo: espaço livre + curvatura da Terra (raio efetivo k) + difração de gume de faca pelo método de Bullington
 * (J(v) da ITU-R P.526, forma aproximada). O texto da Recomendação não foi lido; o limite v > -0,78 é o que dá J = 0 sem
 * salto. Estimativa de enlace, não previsão de campo. */
(function (root) {
  "use strict";
  var C = 299792458.0, R_TERRA_KM = 6371.0;

  function lambdaM(fMHz) { return C / (fMHz * 1e6); }
  /* perda no espaço livre (dB); d em km, f em MHz */
  function fspl(dKm, fMHz) { return 20 * Math.log10(4 * Math.PI * dKm * 1000 * fMHz * 1e6 / C); }
  /* raio da n-ésima zona de Fresnel (m) num ponto a d1 e d2 km das antenas */
  function fresnelR(d1Km, d2Km, fMHz, n) {
    return Math.sqrt((n || 1) * lambdaM(fMHz) * d1Km * 1000 * d2Km * 1000 / ((d1Km + d2Km) * 1000));
  }
  /* abaulamento da Terra (m) a d1 e d2 km das pontas, com fator k do raio efetivo */
  function bulge(d1Km, d2Km, k) { return d1Km * d2Km / (2 * k * R_TERRA_KM / 1000.0); }
  /* perda de difração de gume único (dB) para o parâmetro v */
  function J(v) { return v > -0.78 ? 6.9 + 20 * Math.log10(Math.sqrt((v - 0.1) * (v - 0.1) + 1) + v - 0.1) : 0.0; }
  /* parâmetro de Fresnel-Kirchhoff: h (m) acima da linha entre as antenas, d1 e d2 em km */
  function vParam(h, d1Km, d2Km, fMHz) {
    var d1 = d1Km * 1000, d2 = d2Km * 1000;
    return h * Math.sqrt(2 * (d1 + d2) / (lambdaM(fMHz) * d1 * d2));
  }

  /* Analisa o perfil. perfil = { d: [km crescente, d[0] = 0], h: [m acima do mar] }; alturas das antenas em m acima do
   * solo local. Devolve folga de Fresnel, obstrução e perda de difração (Bullington). */
  function analisarPerfil(perfil, hTx, hRx, k, fMHz) {
    var d = perfil.d, e = perfil.h, n = d.length, D = d[n - 1], i;
    var ht = e[0] + hTx, hr = e[n - 1] + hRx;
    var out = { D_km: D, ht_m: ht, hr_m: hr, los: [], terreno_ef: [], fresnel1: [], folga_min_razao: Infinity, folga_min_i: -1,
      obstruido: false, v: null, h_obst_m: null, d_obst_km: null, perda_difracao_db: 0 };
    var st = -Infinity, sr = -Infinity;
    for (i = 0; i < n; i++) {
      var d1 = d[i], d2 = D - d[i], los = ht + (hr - ht) * d1 / D, ef = e[i] + (i > 0 && i < n - 1 ? bulge(d1, d2, k) : 0);
      out.los.push(los); out.terreno_ef.push(ef);
      if (i > 0 && i < n - 1) {
        var r1 = fresnelR(d1, d2, fMHz, 1), raz = (los - ef) / r1;
        out.fresnel1.push(r1);
        if (raz < out.folga_min_razao) { out.folga_min_razao = raz; out.folga_min_i = i; }
        st = Math.max(st, (ef - ht) / d1); sr = Math.max(sr, (ef - hr) / d2);
      } else out.fresnel1.push(0);
    }
    if (n < 3) { out.folga_min_razao = null; return out; }
    out.obstruido = out.folga_min_razao < 0;
    var den = st + sr;
    if (den > 0) {
      var db = (hr - ht + sr * D) / den, hb = ht + st * db, linha = ht + (hr - ht) * db / D, h = hb - linha;
      if (db > 0 && db < D) {
        out.d_obst_km = db; out.h_obst_m = h; out.v = vParam(h, db, D - db, fMHz); out.perda_difracao_db = J(out.v);
      }
    }
    return out;
  }

  var api = { C: C, lambdaM: lambdaM, fspl: fspl, fresnelR: fresnelR, bulge: bulge, J: J, vParam: vParam, analisarPerfil: analisarPerfil };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaPropagacao = api;
})(typeof window !== "undefined" ? window : this);
