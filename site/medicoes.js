/* Medições de campo -> calibração do modelo (sem DOM, sem rede). O pesquisador cola um CSV de medições; o módulo ajusta a perda
 * de percurso (pl1km e n, por mínimos quadrados, com erro-padrão e desvio) e o limiar de SNR por SF (curva logística sobre a
 * entrega, com bootstrap determinístico) e gera um calibracao.json versão 1 (docs/09 §4), que o importador do simulador
 * (`simsuite.analysis.calibracao`) valida e aplica. PRIVACIDADE: colunas de localização (lat, lon, gnss, gps, coordenadas) são
 * recusadas; só distância, potência e qualidade de sinal entram. Nada sai do navegador. Estimativa estatística, não prova. */
(function (root) {
  "use strict";
  var PROIBIDAS = /(^|_)(lat|lon|lng|latitude|longitude|gnss|gps|coord|coordenada|coordenadas|altitude|alt)(_|$)/;
  var ALIAS = { d: ["distancia_km", "dist_km", "d_km", "distancia"], rssi: ["rssi_dbm", "rssi"], snr: ["snr_db", "snr"], pdr: ["pdr", "entrega", "taxa_entrega"],
    sf: ["sf"], p: ["potencia_dbm", "p_dbm", "tx_dbm", "ptx_dbm"], bw: ["bw_khz", "bw"] };

  function norm(t) { return String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""); }
  function num(t) { var v = parseFloat(String(t).trim().replace(",", ".")); return isFinite(v) ? v : null; }

  /* CSV com cabeçalho; separador ; , tab ou espaço. Devolve { linhas: [{d, rssi, snr, pdr, sf, p, bw}], colunas, avisos } ou { erro }. */
  function lerCsv(texto) {
    var ls = String(texto || "").split(/\r?\n/).map(function (l) { return l.trim(); }).filter(function (l) { return l && l[0] !== "#"; });
    if (ls.length < 2) return { erro: "cole um CSV com cabeçalho e pelo menos uma linha de dados" };
    var sep = ls[0].indexOf(";") >= 0 ? ";" : ls[0].indexOf("\t") >= 0 ? "\t" : ls[0].indexOf(",") >= 0 && !/\d,\d/.test(ls[1]) ? "," : /\s/.test(ls[0]) ? /\s+/ : ";";
    var cab = ls[0].split(sep).map(norm), i, j;
    for (i = 0; i < cab.length; i++) if (PROIBIDAS.test(cab[i])) return { erro: "a coluna “" + cab[i] + "” parece dado de localização. Remova-a: a calibração não usa coordenadas e elas não devem circular (privacidade)." };
    var idx = {};
    Object.keys(ALIAS).forEach(function (k) { for (j = 0; j < cab.length; j++) if (ALIAS[k].indexOf(cab[j]) >= 0) { idx[k] = j; break; } });
    var temLimiar = idx.snr != null && idx.pdr != null && idx.sf != null;
    if (idx.d == null && !temLimiar) return { erro: "falta a coluna de distância (distancia_km) com rssi_dbm, para a perda de percurso; ou snr_db, pdr e sf, para o limiar" };
    if (!temLimiar && idx.rssi == null && idx.pdr == null) return { erro: "falta a coluna rssi_dbm (para a perda de percurso) ou snr_db, pdr e sf (para o limiar)" };
    var linhas = [], avisos = [], ruins = 0;
    for (i = 1; i < ls.length; i++) {
      var c = ls[i].split(sep), o = {};
      Object.keys(idx).forEach(function (k) { o[k] = num(c[idx[k]]); });
      var serveLimiar = o.snr != null && o.pdr != null && o.sf != null, servePercurso = o.d > 0 && (o.rssi != null || o.pdr != null);
      if (!serveLimiar && !servePercurso) { ruins++; continue; }
      if (o.pdr != null && (o.pdr < 0 || o.pdr > 1)) { if (o.pdr <= 100 && o.pdr > 1) o.pdr = o.pdr / 100; else { ruins++; continue; } }
      linhas.push(o);
    }
    if (ruins) avisos.push(ruins + " linha(s) ignorada(s) (distância não positiva, valor ausente ou pdr fora de 0 a 1)");
    if (!linhas.length) return { erro: "nenhuma linha válida" };
    return { linhas: linhas, colunas: Object.keys(idx), avisos: avisos };
  }

  /* Perda de percurso: PL_i = P_tx + ganhos - RSSI_i;  PL = pl1km + n * 10 log10(d). g = { p, ganhos } (dBm, dB) como padrão
   * quando a linha não traz a potência. Mínimos quadrados com erro-padrão. */
  function ajustePercurso(linhas, g) {
    var x = [], y = [];
    linhas.forEach(function (l) { if (l.rssi != null) { var p = l.p != null ? l.p : g.p; x.push(10 * Math.log10(l.d)); y.push(p + g.ganhos - l.rssi); } });
    var n = x.length;
    if (n < 3) return { erro: "são precisos ao menos 3 medições de RSSI (há " + n + ")" };
    var mx = x.reduce(function (a, b) { return a + b; }, 0) / n, my = y.reduce(function (a, b) { return a + b; }, 0) / n, sxx = 0, sxy = 0, i;
    for (i = 0; i < n; i++) { sxx += (x[i] - mx) * (x[i] - mx); sxy += (x[i] - mx) * (y[i] - my); }
    if (sxx < 1e-9) return { erro: "todas as medições estão na mesma distância; varie a distância (pelo menos 2 distâncias bem diferentes)" };
    var dmin = Math.min.apply(null, linhas.map(function (l) { return l.d; })), dmax = Math.max.apply(null, linhas.map(function (l) { return l.d; }));
    var nn = sxy / sxx, pl1 = my - nn * mx, rss = 0, tss = 0;
    for (i = 0; i < n; i++) { var r = y[i] - (pl1 + nn * x[i]); rss += r * r; tss += (y[i] - my) * (y[i] - my); }
    var gl = Math.max(n - 2, 1), s2 = rss / gl, sigma = Math.sqrt(s2), seN = Math.sqrt(s2 / sxx), sePl = Math.sqrt(s2 * (1 / n + mx * mx / sxx));
    var avisos = [];
    if (dmax / dmin < 3) avisos.push("a faixa de distâncias é curta (" + dmin + " a " + dmax + " km): n e pl1km ficam correlacionados e a incerteza real é maior que a mostrada");
    if (n < 8) avisos.push("poucas medições (" + n + "): prefira 20 ou mais, em várias distâncias");
    return { pl1km: pl1, n: nn, sigma: sigma, se_pl1km: sePl, se_n: seN, r2: tss > 0 ? 1 - rss / tss : 0, pontos: n, d_min: dmin, d_max: dmax, avisos: avisos, residuos: y.map(function (v, k) { return v - (pl1 + nn * x[k]); }) };
  }

  function logistica(snr, c, s) { return 1 / (1 + Math.exp(-(snr - c) / s)); }
  function sse(ds, c, s) { var e = 0, i; for (i = 0; i < ds.length; i++) { var r = ds[i][1] - logistica(ds[i][0], c, s); e += r * r; } return e; }
  function melhor(ds) {
    var bc = 0, bs = 1, be = Infinity, c, s, passo = [0.5, 0.1, 0.02], faixa = [[-35, 15, 0.2, 3, 0.1], null, null], k;
    var c0 = -35, c1 = 15, s0 = 0.1, s1 = 4;
    for (k = 0; k < 3; k++) {
      var dc = passo[k], ds_ = [0.2, 0.05, 0.01][k];
      for (c = c0; c <= c1 + 1e-9; c += dc) for (s = s0; s <= s1 + 1e-9; s += ds_) { var e = sse(ds, c, s); if (e < be) { be = e; bc = c; bs = s; } }
      c0 = bc - 2 * dc; c1 = bc + 2 * dc; s0 = Math.max(0.05, bs - 2 * ds_); s1 = bs + 2 * ds_;
    }
    return { c: bc, s: bs, sse: be };
  }
  function lcg(seed) { var x = seed >>> 0; return function () { x = (Math.imul(x, 1664525) + 1013904223) >>> 0; return x / 4294967296; }; }

  /* Limiar por SF: ajusta PDR = 1/(1+exp(-(snr - c)/s)); c é o centro da curva (SNR com 50% de entrega). Bootstrap de 200
   * reamostragens (semente fixa) para o erro-padrão. Devolve { porSf: { sf: { c, s, se_c, pontos, avisos } } }. */
  function ajusteLimiar(linhas) {
    var por = {}, out = {}, erros = [];
    linhas.forEach(function (l) { if (l.snr != null && l.pdr != null && l.sf != null) (por[l.sf] = por[l.sf] || []).push([l.snr, l.pdr]); });
    Object.keys(por).forEach(function (sf) {
      var ds = por[sf], av = [];
      var lo = ds.filter(function (d) { return d[1] < 0.2; }).length, hi = ds.filter(function (d) { return d[1] > 0.8; }).length, meio = ds.length - lo - hi;
      if (ds.length < 6 || !lo || !hi) { erros.push("SF" + sf + ": preciso de ao menos 6 pontos, com entrega baixa (<20%) e alta (>80%), para achar o limiar (há " + ds.length + ")"); return; }
      if (meio < 1) av.push("nenhum ponto na região de transição: o limiar é pouco determinado");
      var m = melhor(ds), rnd = lcg(12345 + (+sf)), cs = [], b, i;
      for (b = 0; b < 200; b++) { var amostra = []; for (i = 0; i < ds.length; i++) amostra.push(ds[Math.floor(rnd() * ds.length)]); cs.push(melhor(amostra).c); }
      var mc = cs.reduce(function (a, v) { return a + v; }, 0) / cs.length, se = Math.sqrt(cs.reduce(function (a, v) { return a + (v - mc) * (v - mc); }, 0) / (cs.length - 1));
      out[sf] = { c: m.c, s: m.s, se_c: se, pontos: ds.length, avisos: av };
    });
    return { porSf: out, erros: erros };
  }

  function arred(v, d) { var f = Math.pow(10, d); return Math.round(v * f) / f; }
  /* calibracao.json versão 1 só com o que foi ajustado. op: { id, data, hardware, firmware, ambiente, percurso, limiar, perOffsetDb }.
   * snr_thr[sf] = centro - per_offset_db (o simulador soma o offset de volta). */
  function gerarCalibracao(op) {
    var cs = {}, notas = [];
    if (op.percurso && !op.percurso.erro) {
      var v = {}; v[op.ambiente] = { pl1km: arred(op.percurso.pl1km, 1), n: arred(op.percurso.n, 2), sigma_static: arred(op.percurso.sigma, 1) };
      cs.canal = { valor: v, incerteza: arred(op.percurso.se_pl1km, 1) };
      notas.push("canal: " + op.percurso.pontos + " medições de " + arred(op.percurso.d_min, 2) + " a " + arred(op.percurso.d_max, 2) + " km; erro-padrão de n = " + arred(op.percurso.se_n, 2) + "; a incerteza do arquivo é a de pl1km (dB)");
    }
    if (op.limiar && op.limiar.porSf && Object.keys(op.limiar.porSf).length) {
      var t = {}, mx = 0;
      Object.keys(op.limiar.porSf).forEach(function (sf) { var r = op.limiar.porSf[sf]; t[sf] = arred(r.c - op.perOffsetDb, 2); mx = Math.max(mx, r.se_c); });
      cs.snr_thr = { valor: t, incerteza: arred(mx, 2) };
      notas.push("snr_thr: centro da curva de entrega menos per_offset_db (" + op.perOffsetDb + " dB); incerteza = maior erro-padrão (bootstrap) entre os SFs");
    }
    if (!Object.keys(cs).length) return { erro: "nada foi ajustado: carregue medições de RSSI e/ou de SNR com entrega" };
    return { obj: { versao: 1, id: op.id, data: op.data, hardware: op.hardware, firmware: op.firmware, notas: "Gerado no navegador a partir de medições de campo (sem coordenadas). " + notas.join("; ") + ". Estimativa estatística; revise antes de aplicar.", constantes: cs } };
  }

  var api = { lerCsv: lerCsv, ajustePercurso: ajustePercurso, ajusteLimiar: ajusteLimiar, gerarCalibracao: gerarCalibracao, logistica: logistica };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaMedicoes = api;
})(typeof window !== "undefined" ? window : this);
