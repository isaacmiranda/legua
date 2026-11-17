/* Gera o trecho C que configura o núcleo (legua_config) com um perfil nomeado, o teto de TX e a elevação de ruído do
 * ambiente escolhido. O perfil é pedido por legua_params_profile (nenhum número de parâmetro é copiado para o site, então
 * não há como divergir do núcleo). Estimativa para comparar e dimensionar; BR-2026 nao_verificado. */
(function (root) {
  "use strict";
  var PERFIS = {
    padrao: { enum: "LEGUA_PROFILE_DEFAULT", resumo: "margem de aceleração fixa de 8 dB; gasta menos energia, oscila mais em enlaces urbanos" },
    estavel: { enum: "LEGUA_PROFILE_STABLE", resumo: "8 dB + 3 desvios do SNR medido: menos quedas ao modo base e menos desacordo, ao custo de energia" },
    cauteloso: { enum: "LEGUA_PROFILE_CAUTIOUS", resumo: "margem fixa de 14 dB: só acelera com folga grande; simples, sem estatística" }
  };
  function inteiro(v, lo, hi) { v = Math.round(Number(v)); return Math.min(hi, Math.max(lo, isFinite(v) ? v : lo)); }
  function gerar(o) {
    var p = PERFIS[o.perfil];
    if (!p) throw new Error("perfil desconhecido: " + o.perfil);
    var cap = inteiro(o.cap_dbm, -9, 28), ruido = Math.max(0, Math.min(30, Number(o.ruido_db) || 0));
    return [
      "/* Gerado pelo site da Légua. Estimativa para comparar e dimensionar; o perfil regulatório BR-2026 é nao_verificado",
      " * e a conformidade do produto é do integrador. Perfil \"" + o.perfil + "\": " + p.resumo + ". */",
      "#include <string.h>",
      "#include \"legua/legua.h\"",
      "#include \"profiles/br2026.h\"",
      "",
      "/* id e peer são os endereços curtos dos dois nós (docs/07); a chave e o registro de NVM ficam por conta do porte. */",
      "static int meu_enlace_config(legua_config *cfg, uint16_t id, uint16_t peer)",
      "{",
      "    memset(cfg, 0, sizeof *cfg);",
      "    cfg->id = id;",
      "    cfg->peer = peer;",
      "    cfg->modes = LEGUA_BR2026_MODES;",
      "    cfg->n_modes = LEGUA_BR2026_N_MODES;",
      "    cfg->base_mode_id = LEGUA_BR2026_BASE_MODE_ID;",
      "    cfg->rec_mode_id = LEGUA_BR2026_REC_MODE_ID;",
      "    cfg->cap_dbm = " + cap + ";            /* teto de TX permitido pelo integrador, em dBm */",
      "    cfg->noise_rise_db = " + ruido.toFixed(1) + "f;     /* elevação de ruído do ambiente, em dB */",
      "    return legua_params_profile(&cfg->params, " + p.enum + ");   /* 0 se o perfil existe */",
      "}",
      ""
    ].join("\n");
  }
  var api = { PERFIS: PERFIS, gerar: gerar };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaPerfilC = api;
})(typeof window !== "undefined" ? window : this);
