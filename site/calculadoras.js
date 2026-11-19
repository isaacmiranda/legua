/* Calculadoras avulsas de LoRa (funções puras, sem DOM): tempo no ar, sensibilidade, ciclo de trabalho, bateria e plano de
 * canais. Referência Python e teste de paridade: simsuite/core/radio.py e regulatory.py. Valores de consumo e de
 * sensibilidade são estimativas (docs/09 §4); o perfil BR-2026 vem de fonte secundária e está nao_verificado. */
(function (root) {
  "use strict";

  /* Tempo no ar (s). AN1200.13 da Semtech; SF5 e SF6 conforme o datasheet do SX126x. */
  function toaS(sf, bwKhz, payloadB, cr, preamble, crc, explicit) {
    cr = cr || 1; preamble = preamble == null ? 8 : preamble; crc = crc !== false; explicit = explicit !== false;
    var tsym = Math.pow(2, sf) / (bwKhz * 1e3), de = tsym > 0.016 ? 1 : 0, ih = explicit ? 0 : 1, num, nsym;
    if (sf >= 7) {
      num = 8 * payloadB - 4 * sf + 28 + (crc ? 16 : 0) - 20 * ih;
      nsym = 8 + Math.max(Math.ceil(num / (4 * (sf - 2 * de))) * (cr + 4), 0);
      return (preamble + 4.25) * tsym + nsym * tsym;
    }
    num = 8 * payloadB + (crc ? 16 : 0) - 4 * sf + 20 * (1 - ih);
    nsym = 8 + Math.max(Math.ceil(num / (4 * sf)) * (cr + 4), 0);
    return (preamble + 6.25) * tsym + nsym * tsym;
  }
  function ruidoDbm(bwKhz, nfDb, subidaDb) { return -174.0 + 10 * Math.log10(bwKhz * 1e3) + nfDb + (subidaDb || 0); }
  /* Sensibilidade (dBm) = ruído + limiar de SNR do SF - ganho do CR. K: constantes do site (snr_thr, cr_gain_db, nf_db). */
  function sensibilidadeDbm(K, sf, bwKhz, cr) { return ruidoDbm(bwKhz, K.nf_db) + K.snr_thr[sf] - (K.cr_gain_db[cr] || 0); }
  /* Taxa de bits útil (bit/s), sem a carga de preâmbulo: SF * BW/2^SF * 4/(4+CR) */
  function taxaBps(sf, bwKhz, cr) { return sf * (bwKhz * 1e3 / Math.pow(2, sf)) * 4 / (4 + cr); }

  /* Ciclo de trabalho: fração do tempo no ar para `pph` pacotes por hora; e o intervalo mínimo para respeitar `limite` (fração). */
  function cicloUtil(toa, pph) { return toa * pph / 3600; }
  function intervaloMinimoS(toa, limite) { return limite > 0 ? toa / limite : Infinity; }

  function iTxMa(K, p) {
    var t = K.i_tx_table;
    if (p <= t[0][0]) return t[0][1];
    for (var j = 0; j < t.length - 1; j++) if (p <= t[j + 1][0]) return t[j][1] + (t[j + 1][1] - t[j][1]) * (p - t[j][0]) / (t[j + 1][0] - t[j][0]);
    return t[t.length - 1][1];
  }
  /* Bateria. e: { capMah, pDbm, toaS, pph, rxPorPacoteS, sonoUa, iRxMa } -> corrente média (mA), horas e dias. Estimativa. */
  function bateria(K, e) {
    var itx = iTxMa(K, e.pDbm), irx = e.iRxMa == null ? K.i_rx_ma : e.iRxMa;
    var ativoTx = e.toaS * e.pph / 3600, ativoRx = e.rxPorPacoteS * e.pph / 3600, ativo = Math.min(1, ativoTx + ativoRx);
    var media = itx * ativoTx + irx * ativoRx + (e.sonoUa / 1000) * (1 - ativo);
    var horas = media > 0 ? e.capMah / media : Infinity;
    return { iTxMa: itx, mediaMa: media, horas: horas, dias: horas / 24, ativoTx: ativoTx, ativoRx: ativoRx, energiaPacoteMj: itx * K.vcc * e.toaS };
  }

  /* Plano de canais: frequências centrais (Hz) que cabem nas faixas, com guarda (padrão 0,6 x BW, como no simulador). */
  function planoCanais(faixasHz, bwKhz, guardaKhz) {
    var passo = (bwKhz + (guardaKhz == null ? 0.6 * bwKhz : guardaKhz)) * 1e3, meio = bwKhz * 1e3 / 2, out = [];
    faixasHz.forEach(function (fx) { for (var f = fx[0] + meio; f + meio <= fx[1] + 1e-6; f += passo) out.push(f); });
    return out;
  }
  /* Regras de salto do perfil BR-2026 (nao_verificado): classe do BW, canais mínimos e teto de potência (dBm) para n canais. */
  function regraSalto(reg, bwKhz, nCanais, antDbi) {
    var cls = null;
    reg.salto.forEach(function (h) { if (!cls && h.bw_min_khz <= bwKhz && bwKhz < h.bw_max_khz) cls = h; });
    if (!cls) return { classe: null, ok: false, motivo: "largura de banda sem classe de salto no perfil" };
    var ok = nCanais >= cls.canais_min, p = (ok ? reg.p_max_dbm : reg.p_reduzida_dbm) - Math.max(0, (antDbi || 0) - reg.antena_max_dbi);
    return { classe: cls, ok: ok, tetoDbm: p, canaisMin: cls.canais_min, dwellS: cls.dwell_s, janelaS: cls.janela_s };
  }

  var api = { toaS: toaS, ruidoDbm: ruidoDbm, sensibilidadeDbm: sensibilidadeDbm, taxaBps: taxaBps, cicloUtil: cicloUtil, intervaloMinimoS: intervaloMinimoS,
    iTxMa: iTxMa, bateria: bateria, planoCanais: planoCanais, regraSalto: regraSalto };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaCalc = api;
})(typeof window !== "undefined" ? window : this);
