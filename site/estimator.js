/* Estimador analítico de enlace: porta fiel de simsuite/analysis/estimator.py.
 * Recebe as constantes do modelo (K = LEGUA_DATA.constantes), então não duplica parâmetros.
 * Teste de paridade: simsuite/tests/test_estimator.py (roda este arquivo no node). */
(function (root) {
  "use strict";
  function make(K) {
    var SQRT2 = Math.sqrt(2), SQRTPI = Math.sqrt(Math.PI);
    var nodes = [], i;
    for (i = K.gh8_x.length - 1; i >= 0; i--) nodes.push([-K.gh8_x[i], K.gh8_w[i]]);
    for (i = 0; i < K.gh8_x.length; i++) nodes.push([K.gh8_x[i], K.gh8_w[i]]);
    var NORM = nodes.map(function (n) { return [n[0] * SQRT2, n[1] / SQRTPI]; });

    function toaS(sf, bw, pl, cr) {
      var tsym = Math.pow(2, sf) / (bw * 1e3), de = tsym > 0.016 ? 1 : 0;
      var num = 8 * pl - 4 * sf + 28 + 16;
      var nsym = 8 + Math.max(Math.ceil(num / (4 * (sf - 2 * de))) * (cr + 4), 0);
      return (8 + 4.25) * tsym + nsym * tsym;
    }
    function iTxMa(p) {
      var t = K.i_tx_table;
      if (p <= t[0][0]) return t[0][1];
      for (var j = 0; j < t.length - 1; j++) {
        var p0 = t[j][0], i0 = t[j][1], p1 = t[j + 1][0], i1 = t[j + 1][1];
        if (p <= p1) return i0 + (i1 - i0) * (p - p0) / (p1 - p0);
      }
      return t[t.length - 1][1];
    }
    function noiseDbm(bw, rise) { return -174.0 + 10 * Math.log10(bw * 1e3) + K.nf_db + (rise || 0); }
    function pDemod(snr, sf) {
      var x = (snr - K.snr_thr[sf] - K.per_offset_db) / K.per_slope_db;
      if (x > 30) return 1.0;
      if (x < -30) return 0.0;
      return 1.0 / (1.0 + Math.exp(-x));
    }
    function pExtOk(env, toa, load, cr) {
      var g = env.G_ext * load, pHit = 1 - Math.exp(-g * (toa + K.ext_toa_s));
      return 1 - pHit * (1 - (K.capture_p + 0.08 * (cr - 1)));
    }
    function pathloss(env, d) { return env.pl1km + 10 * env.n * Math.log10(Math.max(d, 0.02)); }
    function fastFades(kDb) {
      var Kl = Math.pow(10, kDb / 10), los = Math.sqrt(Kl / (Kl + 1)), sc = Math.sqrt(1 / (2 * (Kl + 1))), out = [];
      NORM.forEach(function (a) { NORM.forEach(function (b) {
        var re = los + sc * a[0], im = sc * b[0];
        out.push([10 * Math.log10(Math.max(re * re + im * im, 1e-12)), a[1] * b[1]]);
      }); });
      return out;
    }
    function slowStates(env) {
      var states = [[0.0, 1.0]];
      [[env.obstr_rate_h, env.obstr_db, env.obstr_dur_s], [env.rain_rate_h, env.rain_db, env.rain_dur_s]].forEach(function (e) {
        var occ = Math.min(1.0, e[0] * e[2] / 3600.0);
        if (occ <= 0) return;
        var depth = 0.5 * (e[1][0] + e[1][1]);
        states = states.map(function (s) { return [s[0], s[1] * (1 - occ)]; })
          .concat(states.map(function (s) { return [s[0] + depth, s[1] * occ]; }));
      });
      return states;
    }
    function pPkt(env, mode, rx, nbytes, fades, load) {
      var noise = noiseDbm(mode.bw, env.noise_rise), toa = toaS(mode.sf, mode.bw, nbytes, mode.cr);
      var ext = pExtOk(env, toa, load, mode.cr), cg = K.cr_gain_db[mode.cr], s = 0;
      for (var j = 0; j < fades.length; j++) s += fades[j][1] * pDemod(rx + fades[j][0] - noise + cg, mode.sf);
      return ext * s;
    }
    function linkStats(env, mode, pDbm, rxStatic, retries, fades, states, load, dataB, ackB) {
      var toaD = toaS(mode.sf, mode.bw, dataB, mode.cr), toaA = toaS(mode.sf, mode.bw, ackB, mode.cr);
      var deadline = toaA + (mode.fhss ? 0.45 : 0.05) + 0.15, r = retries;
      var acc = { entregue: 0, confirmado: 0, tentativas: 0, acks: 0, lat: 0 };
      NORM.forEach(function (zt) { states.forEach(function (st) {
        var w = zt[1] * st[1], slow = rxStatic - env.sigma_t * zt[0] - st[0];
        var pd = pPkt(env, mode, slow, dataB, fades, load), pa = pPkt(env, mode, slow, ackB, fades, load), s = pd * pa;
        var entregue = 1 - Math.pow(1 - pd, r + 1), att = 0, k, ek = 0;
        for (k = 0; k <= r; k++) att += Math.pow(1 - s, k);
        if (entregue > 1e-12) {
          var sk = 0; for (k = 0; k <= r; k++) sk += k * Math.pow(1 - pd, k) * pd;
          ek = sk / entregue;
        }
        var lat = toaD + ek * (toaD + deadline + K.backoff_medio_s);
        acc.entregue += w * entregue; acc.confirmado += w * (1 - Math.pow(1 - s, r + 1));
        acc.tentativas += w * att; acc.acks += w * pd * att; acc.lat += w * entregue * lat;
      }); });
      var ePkt = K.vcc * iTxMa(pDbm) * (acc.tentativas * toaD + acc.acks * toaA);
      return { entregue: acc.entregue, confirmado: acc.confirmado, tentativas: acc.tentativas, energia_mj_pacote: ePkt,
        energia_mj_entregue: acc.entregue > 1e-9 ? ePkt / acc.entregue : null,
        latencia_s: acc.entregue > 1e-9 ? acc.lat / acc.entregue : null,
        airtime_s_pacote: acc.tentativas * toaD + acc.acks * toaA };
    }
    function rxMedio(env, d, p, off) {
      return p - pathloss(env, d) + 2 * (K.ant_gain_dbi - K.cable_loss_db) + off - 0.5 * env.diurnal_db;
    }
    function estimate(o) {
      var env = K.envs[o.env], mode = { sf: o.sf, bw: o.bw, cr: o.cr, fhss: !!o.fhss };
      var retries = o.retries == null ? 3 : o.retries, interval = o.interval_s == null ? 60 : o.interval_s;
      var off = o.offset_db || 0, load = o.load == null ? 1 : o.load, dataB = o.data_b || K.data_bytes, ackB = o.ack_b || K.ack_bytes;
      var fades = fastFades(env.K_db), states = slowStates(env);
      var rxMed = rxMedio(env, o.d_km, o.p_dbm, off);
      var noise = noiseDbm(o.bw, env.noise_rise), sens = noise + K.snr_thr[o.sf] + K.per_offset_db - K.cr_gain_db[o.cr];
      var toaD = toaS(o.sf, o.bw, dataB, o.cr), toaA = toaS(o.sf, o.bw, ackB, o.cr);
      var cenarios = [-1.0, 0.0, 1.0, 2.0].map(function (sig) {
        var st = linkStats(env, mode, o.p_dbm, rxMed - sig * env.sigma_static, retries, fades, states, load, dataB, ackB);
        st.sigmas = sig; return st;
      });
      var media = { entregue: 0, confirmado: 0, tentativas: 0, energia_mj_pacote: 0, airtime_s_pacote: 0 };
      NORM.forEach(function (zn) {
        var st = linkStats(env, mode, o.p_dbm, rxMed - zn[0] * env.sigma_static, retries, fades, states, load, dataB, ackB);
        Object.keys(media).forEach(function (k) { media[k] += zn[1] * st[k]; });
      });
      var pkts = interval > 0 ? 3600.0 / interval : 0.0, ref = cenarios[1];
      return { toa_dados_ms: 1000 * toaD, toa_ack_ms: 1000 * toaA, ruido_dbm: noise, sens_dbm: sens, rx_tipico_dbm: rxMed,
        margem_db: rxMed - sens, dwell_ok: (!o.fhss) || toaD <= K.dwell_max_s, cenarios: cenarios, media_enlaces: media,
        airtime_hora_s: pkts * ref.airtime_s_pacote, duty_pct: 100.0 * pkts * ref.airtime_s_pacote / 3600.0,
        energia_dia_j: 24 * pkts * ref.energia_mj_pacote / 1000.0 };
    }
    function estimateOne(o, sigmas) {
      var env = K.envs[o.env], mode = { sf: o.sf, bw: o.bw, cr: o.cr, fhss: !!o.fhss };
      var rx = rxMedio(env, o.d_km, o.p_dbm, o.offset_db || 0);
      return linkStats(env, mode, o.p_dbm, rx - (sigmas || 0) * env.sigma_static, o.retries == null ? 3 : o.retries,
        fastFades(env.K_db), slowStates(env), o.load == null ? 1 : o.load, o.data_b || K.data_bytes, o.ack_b || K.ack_bytes);
    }
    function withD(o, d) { var c = {}; Object.keys(o).forEach(function (k) { c[k] = o[k]; }); c.d_km = d; return c; }
    function rangeKm(o, target, sigmas) {
      var lo = 0.02, hi = 400.0;
      function ok(d) { return estimateOne(withD(o, d), sigmas).confirmado >= target; }
      if (!ok(lo)) return null;
      if (ok(hi)) return hi;
      for (var j = 0; j < 40; j++) { var mid = Math.sqrt(lo * hi); if (ok(mid)) lo = mid; else hi = mid; }
      return lo;
    }
    function modeList() {
      var out = [], sf, cr;
      [7, 8, 9, 10].forEach(function (s) { [1, 4].forEach(function (c) {
        if (toaS(s, 125, K.data_bytes, c) <= K.dwell_max_s) out.push({ sf: s, bw: 125, cr: c, fhss: true }); }); });
      [7, 8, 9, 10, 11].forEach(function (s) { if (toaS(s, 250, K.data_bytes, 1) <= K.dwell_max_s) out.push({ sf: s, bw: 250, cr: 1, fhss: true }); });
      for (sf = 7; sf <= 12; sf++) out.push({ sf: sf, bw: 500, cr: 1, fhss: false });
      return out;
    }
    function rankModes(o, target, sigmas) {
      var rows = modeList().map(function (m) {
        var c = {}; Object.keys(o).forEach(function (k) { c[k] = o[k]; });
        c.sf = m.sf; c.bw = m.bw; c.cr = m.cr; c.fhss = m.fhss;
        var st = estimateOne(c, sigmas);
        return { sf: m.sf, bw: m.bw, cr: m.cr, fhss: m.fhss, confirmado: st.confirmado, energia_mj_entregue: st.energia_mj_entregue,
          latencia_s: st.latencia_s, ok: st.confirmado >= target };
      });
      var good = rows.filter(function (r) { return r.ok && r.energia_mj_entregue != null; })
        .sort(function (a, b) { return a.energia_mj_entregue - b.energia_mj_entregue; });
      return { good: good, rows: rows };
    }
    return { estimate: estimate, estimateOne: estimateOne, rangeKm: rangeKm, modeList: modeList, rankModes: rankModes, toaS: toaS };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { make: make };
  else root.LeguaEstimator = { make: make };
})(typeof window !== "undefined" ? window : this);
