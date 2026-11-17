/* Orquestra o testador de enlaces: perfil de terreno + orçamento de enlace + estimador da Légua. Sem DOM, sem rede.
 * Contabilidade de dB (para não contar duas vezes): o estimador já soma 2 x (ganho de antena - perda de cabo) padrão e
 * usa antenas a ~3 m; aqui a perda média vem do terreno (espaço livre + difração + perda extra do usuário) e o que o
 * estimador recebe é só a DIFERENÇA, em offset_db. O ambiente escolhido contribui apenas com a variabilidade (σ,
 * desvanecimento, ruído, tráfego); sua perda de percurso é trocada pelo espaço livre. Estimativa, não previsão. */
(function (root) {
  "use strict";
  var P = root.LeguaPropagacao || (typeof require !== "undefined" ? require("./propagacao.js") : null);
  var EST = root.LeguaEstimator || (typeof require !== "undefined" ? require("./estimator.js") : null);
  var F_MHZ = 915.0;

  function make(K) {
    /* ambiente "enlace": variabilidade do ambiente escolhido; perda média = espaço livre (n = 2) e sem componente diurna */
    function envEnlace(base) {
      var e = {}; Object.keys(base).forEach(function (k) { e[k] = base[k]; });
      e.pl1km = P.fspl(1.0, F_MHZ); e.n = 2.0; e.diurnal_db = 0.0; e.label = "Enlace (espaço livre + terreno) com variabilidade de " + base.label;
      return e;
    }
    var K2 = {}; Object.keys(K).forEach(function (k) { K2[k] = K[k]; });
    K2.envs = {}; Object.keys(K.envs).forEach(function (k) { K2.envs[k] = envEnlace(K.envs[k]); });
    var est = EST.make(K2);
    var base = 2 * (K.ant_gain_dbi - K.cable_loss_db);          // o que o estimador já soma

    /* inp: perfil, hTx, hRx (m), k, p_dbm, gTx, gRx (dBi), lTx, lRx (dB), extra_db, env, sf, bw, cr, fhss, retries,
     * interval_s, load, alvo, sig */
    function analisar(inp) {
      var pf = P.analisarPerfil(inp.perfil, inp.hTx, inp.hRx, inp.k, F_MHZ), D = pf.D_km;
      var ex = inp.extra_db || 0, lfs = P.fspl(D, F_MHZ), ld = pf.perda_difracao_db;
      var ganhos = inp.gTx - inp.lTx + inp.gRx - inp.lRx;
      var perda = lfs + ld + ex, rx = inp.p_dbm + ganhos - perda;
      var offset = ganhos - base - ld - ex;                      // diferença para o que o estimador já soma
      var o = { env: inp.env, d_km: D, sf: inp.sf, bw: inp.bw, cr: inp.cr, p_dbm: inp.p_dbm, fhss: !!inp.fhss, retries: inp.retries,
        interval_s: inp.interval_s, offset_db: offset, load: inp.load };
      var e = est.estimate(o), rk = est.rankModes(o, inp.alvo, inp.sig || 0);
      var modos = rk.rows.map(function (r) {
        var oo = {}; Object.keys(o).forEach(function (k) { oo[k] = o[k]; });
        oo.sf = r.sf; oo.bw = r.bw; oo.cr = r.cr; oo.fhss = r.fhss;
        var ee = est.estimate(oo);
        return { sf: r.sf, bw: r.bw, cr: r.cr, fhss: r.fhss, margem_db: ee.margem_db, sens_dbm: ee.sens_dbm, confirmado: r.confirmado,
          energia_mj_entregue: r.energia_mj_entregue, latencia_s: r.latencia_s, atinge: r.ok, toa_dados_ms: ee.toa_dados_ms };
      });
      return { perfil: pf, perda: { espaco_livre_db: lfs, difracao_db: ld, extra_db: ex, total_db: perda }, eirp_dbm: inp.p_dbm + inp.gTx - inp.lTx,
        rx_dbm: rx, offset_db: offset, rx_estimador_dbm: e.rx_tipico_dbm, estimativa: e, modos: modos,
        melhor: rk.good.length ? rk.good[0] : null };
    }
    return { analisar: analisar, estimador: est, base_db: base };
  }

  var api = { make: make, F_MHZ: F_MHZ };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaEnlace = api;
})(typeof window !== "undefined" ? window : this);
