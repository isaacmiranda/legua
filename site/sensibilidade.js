/* Sensibilidade e incerteza do estimador (sem DOM): tornado (o que mais move a margem ou a entrega) e propagação de
 * incertezas por Monte Carlo com semente fixa. Usa o estimador analítico (estimator.js) sobre cópias das constantes; as
 * variações são as faixas que o pesquisador informa, não verdades. Estimativa, não previsão. */
(function (root) {
  "use strict";
  var EST = { make: function (K) { return (root.LeguaEstimator || (typeof require !== "undefined" ? require("./estimator.js") : null)).make(K); } };   // resolvido na hora do uso

  function copia(o) { return JSON.parse(JSON.stringify(o)); }
  function lcg(seed) { var x = seed >>> 0; return function () { x = (Math.imul(x, 1664525) + 1013904223) >>> 0; return x / 4294967296; }; }
  function normal(rnd) { var u = Math.max(rnd(), 1e-12), v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

  /* parâmetros perturbáveis: cada um aplica `s` (-1 ou +1 vezes a variação) a uma cópia das constantes e da entrada */
  var PARAMS = [
    { id: "p_dbm", rot: "Potência de TX", un: "dB", d: 3, ap: function (K, o, s, d) { o.p_dbm += s * d; } },
    { id: "d_km", rot: "Distância", un: "%", d: 25, ap: function (K, o, s, d) { o.d_km *= 1 + s * d / 100; } },
    { id: "offset_db", rot: "Terreno e obstrução (offset)", un: "dB", d: 6, ap: function (K, o, s, d) { o.offset_db = (o.offset_db || 0) + s * d; } },
    { id: "pl1km", rot: "Perda a 1 km (pl1km)", un: "dB", d: 4, ap: function (K, o, s, d) { K.envs[o.env].pl1km += s * d; } },
    { id: "n", rot: "Expoente de perda (n)", un: "", d: 0.4, ap: function (K, o, s, d) { K.envs[o.env].n += s * d; } },
    { id: "sigma_static", rot: "Variação entre locais (σ)", un: "dB", d: 2, ap: function (K, o, s, d) { var e = K.envs[o.env]; e.sigma_static = Math.max(0, e.sigma_static + s * d); } },
    { id: "snr_thr", rot: "Limiar de SNR do SF", un: "dB", d: 1.5, ap: function (K, o, s, d) { Object.keys(K.snr_thr).forEach(function (k) { K.snr_thr[k] += s * d; }); } },
    { id: "per_offset_db", rot: "Margem prática do limiar", un: "dB", d: 1, ap: function (K, o, s, d) { K.per_offset_db += s * d; } },
    { id: "nf_db", rot: "Figura de ruído do RX", un: "dB", d: 1.5, ap: function (K, o, s, d) { K.nf_db += s * d; } },
    { id: "noise_rise", rot: "Ruído do ambiente", un: "dB", d: 3, ap: function (K, o, s, d) { var e = K.envs[o.env]; e.noise_rise = Math.max(0, (e.noise_rise || 0) + s * d); } },
    { id: "load", rot: "Tráfego de terceiros", un: "×", d: 1, ap: function (K, o, s, d) { o.load = Math.max(0, (o.load == null ? 1 : o.load) * (s > 0 ? 1 + d : 1 / (1 + d))); } }
  ];

  function metrica(est, o, qual) { var r = est.estimate(o); return qual === "confirmado" ? r.cenarios[1].confirmado : r.margem_db; }
  /* base: entrada do estimador (env, d_km, sf, bw, cr, p_dbm, fhss, retries, interval_s, load, offset_db). Devolve linhas por amplitude. */
  function tornado(K, base, qual, variacoes) {
    var v0 = metrica(EST.make(K), copia(base), qual), linhas = [];
    PARAMS.forEach(function (p) {
      var d = variacoes && variacoes[p.id] != null ? variacoes[p.id] : p.d, vs = [-1, 1].map(function (s) { var K2 = copia(K), o2 = copia(base); p.ap(K2, o2, s, d); return metrica(EST.make(K2), o2, qual); });
      linhas.push({ id: p.id, rot: p.rot, un: p.un, variacao: d, baixo: Math.min(vs[0], vs[1]), alto: Math.max(vs[0], vs[1]), amplitude: Math.abs(vs[1] - vs[0]) });
    });
    linhas.sort(function (a, b) { return b.amplitude - a.amplitude; });
    return { base: v0, linhas: linhas, qual: qual };
  }

  /* Monte Carlo: sorteia cada parâmetro com desvio `inc[id]` (normal) e devolve percentis da margem e da entrega, e P(entrega >= alvo). */
  function monteCarlo(K, base, inc, n, alvo, semente) {
    var rnd = lcg(semente == null ? 20261119 : semente), mar = [], ent = [], i, acima = 0;
    n = n || 300;
    for (i = 0; i < n; i++) {
      var K2 = copia(K), o2 = copia(base);
      PARAMS.forEach(function (p) { var sd = inc[p.id]; if (sd > 0) p.ap(K2, o2, 1, sd * normal(rnd)); });
      var r = EST.make(K2).estimate(o2); mar.push(r.margem_db); ent.push(r.cenarios[1].confirmado); if (r.cenarios[1].confirmado >= alvo) acima++;
    }
    function pc(v, q) { var s = v.slice().sort(function (a, b) { return a - b; }); return s[Math.min(s.length - 1, Math.max(0, Math.round(q * (s.length - 1))))]; }
    return { n: n, margem: { p5: pc(mar, 0.05), p50: pc(mar, 0.5), p95: pc(mar, 0.95) }, entrega: { p5: pc(ent, 0.05), p50: pc(ent, 0.5), p95: pc(ent, 0.95) }, probAtingeAlvo: acima / n, alvo: alvo };
  }

  var api = { PARAMS: PARAMS, tornado: tornado, monteCarlo: monteCarlo };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaSensibilidade = api;
})(typeof window !== "undefined" ? window : this);
