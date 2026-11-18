/* Perfis de terreno para o testador de enlaces: leitura de CSV colado, perfis sintéticos e reamostragem. Sem DOM,
 * sem rede: o perfil nunca sai do navegador. perfil = { d: [km, crescente, d[0] = 0], h: [m acima do mar] }. */
(function (root) {
  "use strict";
  var MAX_PONTOS = 5000, H_MIN = -500, H_MAX = 9000;

  function num(t) { var v = parseFloat(String(t).trim().replace(",", ".")); return isFinite(v) ? v : NaN; }

  /* Aceita "distancia_km;altitude_m" (separador ; tab ou espaço; vírgula decimal só com esses separadores, ou vírgula
   * como separador quando há ponto decimal) ou uma coluna só de altitudes, igualmente espaçadas ao longo de dTotalKm. */
  function lerCsv(texto, dTotalKm) {
    var linhas = String(texto || "").split(/\r?\n/).map(function (l) { return l.trim(); }).filter(function (l) { return l && l[0] !== "#"; });
    var pares = [], uma = [], i;
    for (i = 0; i < linhas.length; i++) {
      var l = linhas[i], partes;
      if (l.indexOf(";") >= 0) partes = l.split(";");
      else if (l.indexOf("\t") >= 0) partes = l.split("\t");
      else if (/\s/.test(l)) partes = l.split(/\s+/);
      else if (l.indexOf(",") >= 0 && l.indexOf(".") >= 0) partes = l.split(",");
      else partes = [l];
      var v = partes.map(num);
      if (v.some(function (x) { return !isFinite(x); })) { if (i === 0) continue; return { erro: "linha " + (i + 1) + " não é numérica: " + l.slice(0, 40) }; }
      if (v.length === 1) uma.push(v[0]); else if (v.length === 2) pares.push(v); else return { erro: "linha " + (i + 1) + ": use duas colunas (distância em km; altitude em m)" };
    }
    if (pares.length && uma.length) return { erro: "misturou linhas de uma e de duas colunas" };
    var d = [], h = [];
    if (pares.length) { pares.forEach(function (p) { d.push(p[0]); h.push(p[1]); }); }
    else {
      if (!(dTotalKm > 0)) return { erro: "com uma coluna só é preciso informar a distância total" };
      uma.forEach(function (x, j) { d.push(dTotalKm * j / Math.max(uma.length - 1, 1)); h.push(x); });
    }
    return validar({ d: d, h: h });
  }

  function validar(p) {
    var n = p.d.length, i;
    if (n < 2) return { erro: "são precisos pelo menos 2 pontos" };
    if (n > MAX_PONTOS) return { erro: "pontos demais (máximo " + MAX_PONTOS + ")" };
    var d0 = p.d[0], d = p.d.map(function (x) { return x - d0; });
    for (i = 1; i < n; i++) if (!(d[i] > d[i - 1])) return { erro: "a distância precisa crescer a cada linha (linha " + (i + 1) + ")" };
    for (i = 0; i < n; i++) if (!(p.h[i] >= H_MIN && p.h[i] <= H_MAX)) return { erro: "altitude fora de " + H_MIN + " a " + H_MAX + " m na linha " + (i + 1) };
    if (d[n - 1] < 0.02 || d[n - 1] > 100) return { erro: "a distância total precisa ficar entre 0,02 e 100 km" };
    return { perfil: { d: d, h: p.h.slice() } };
  }

  function amostrar(dKm, f, n) {
    var d = [], h = [], i;
    n = n || 101;
    for (i = 0; i < n; i++) { var x = dKm * i / (n - 1); d.push(x); h.push(f(x)); }
    return { d: d, h: h };
  }
  function plano(dKm, altitudeM) { return amostrar(dKm, function () { return altitudeM; }); }
  /* morro gaussiano: altura (m) acima da base, posição (fração do enlace) e meia-largura (km) */
  function morro(dKm, baseM, alturaM, posicao, larguraKm) {
    var c = posicao * dKm, w = Math.max(larguraKm, 0.01);
    return amostrar(dKm, function (x) { return baseM + alturaM * Math.exp(-((x - c) * (x - c)) / (2 * w * w)); }, 201);
  }
  /* interpolação linear em pontos igualmente espaçados */
  function reamostrar(p, n) {
    var D = p.d[p.d.length - 1], j = 0;
    return amostrar(D, function (x) {
      while (j < p.d.length - 2 && p.d[j + 1] < x) j++;
      var t = (x - p.d[j]) / (p.d[j + 1] - p.d[j]);
      return p.h[j] + (p.h[j + 1] - p.h[j]) * Math.min(Math.max(t, 0), 1);
    }, n);
  }


  /* ---- SRTM .hgt local (nada sai do navegador). Grade de n x n amostras em int16 big-endian, linhas do norte para o sul,
   * colunas do oeste para o leste; o nome do arquivo (ex.: S23W046.hgt) dá o canto sudoeste. -32768 = vazio. */
  var VAZIO = -32768, R_MEDIO_KM = 6371.0088;
  function lerHgt(buf, nome) {
    var m = /^([NS])(\d{2})([EW])(\d{3})/i.exec(String(nome || "").split(/[\\/]/).pop());
    if (!m) return { erro: "o nome do arquivo precisa ser do tipo S23W046.hgt (canto sudoeste da grade)" };
    var bytes = buf.byteLength, n = Math.round(Math.sqrt(bytes / 2));
    if (n * n * 2 !== bytes || (n !== 1201 && n !== 3601)) return { erro: "tamanho inesperado: use SRTM1 (3601x3601) ou SRTM3 (1201x1201) em .hgt" };
    var lat0 = (m[1].toUpperCase() === "S" ? -1 : 1) * parseInt(m[2], 10), lon0 = (m[3].toUpperCase() === "W" ? -1 : 1) * parseInt(m[4], 10);
    var dv = new DataView(buf), dados = new Int16Array(n * n), i;
    for (i = 0; i < dados.length; i++) dados[i] = dv.getInt16(2 * i, false);
    return { grade: { lat0: lat0, lon0: lon0, n: n, dados: dados, nome: String(nome) } };
  }
  /* elevação por interpolação bilinear; vazios nos cantos são ignorados (média dos válidos); NaN se todos vazios */
  function elevacaoNaGrade(g, lat, lon) {
    var r = (g.lat0 + 1 - lat) * (g.n - 1), c = (lon - g.lon0) * (g.n - 1);
    if (!(r >= 0 && r <= g.n - 1 && c >= 0 && c <= g.n - 1)) return NaN;
    var r0 = Math.min(Math.floor(r), g.n - 2), c0 = Math.min(Math.floor(c), g.n - 2), fr = r - r0, fc = c - c0;
    var v = [g.dados[r0 * g.n + c0], g.dados[r0 * g.n + c0 + 1], g.dados[(r0 + 1) * g.n + c0], g.dados[(r0 + 1) * g.n + c0 + 1]];
    var w = [(1 - fr) * (1 - fc), (1 - fr) * fc, fr * (1 - fc), fr * fc], num = 0, den = 0, j;
    for (j = 0; j < 4; j++) if (v[j] !== VAZIO) { num += w[j] * v[j]; den += w[j]; }
    if (den > 1e-9) return num / den;
    var q = 0, k2 = 0;                                   // o ponto cai exatamente sobre o vazio: média simples dos vizinhos válidos
    for (j = 0; j < 4; j++) if (v[j] !== VAZIO) { q += v[j]; k2++; }
    return k2 ? q / k2 : NaN;
  }
  function elevacao(grades, lat, lon) {
    var la = Math.floor(lat), lo = Math.floor(lon), j;
    for (j = 0; j < grades.length; j++) {
      var g = grades[j];
      if (lat >= g.lat0 && lat <= g.lat0 + 1 && lon >= g.lon0 && lon <= g.lon0 + 1) return { v: elevacaoNaGrade(g, lat, lon), ok: true };
    }
    return { v: NaN, ok: false, falta: (la < 0 ? "S" : "N") + ("0" + Math.abs(la)).slice(-2) + (lo < 0 ? "W" : "E") + ("00" + Math.abs(lo)).slice(-3) };
  }
  function haversineKm(la1, lo1, la2, lo2) {
    var r = Math.PI / 180, a = Math.sin((la2 - la1) * r / 2), b = Math.sin((lo2 - lo1) * r / 2);
    var h = a * a + Math.cos(la1 * r) * Math.cos(la2 * r) * b * b;
    return 2 * R_MEDIO_KM * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  /* perfil entre dois pontos (graus decimais), amostrado a cada ~passoM metros; interpolação linear em lat/lon */
  function perfilEntre(grades, a, b, passoM) {
    var elev = typeof grades === "function" ? grades : function (la, lo) { return elevacao(grades, la, lo); };   // grades .hgt ou fonte (Terrarium)
    if (![a.lat, a.lon, b.lat, b.lon].every(function (x) { return isFinite(x); })) return { erro: "informe as quatro coordenadas" };
    if (typeof grades !== "function" && (Math.abs(a.lat) > 60 || Math.abs(b.lat) > 60)) return { erro: "o SRTM cobre latitudes entre 60° S e 60° N" };
    var D = haversineKm(a.lat, a.lon, b.lat, b.lon);
    if (D < 0.02 || D > 100) return { erro: "a distância entre os pontos precisa ficar entre 0,02 e 100 km (agora " + D.toFixed(2) + " km)" };
    var n = Math.min(MAX_PONTOS, Math.max(3, Math.ceil(D * 1000 / (passoM || 30)) + 1)), d = [], h = [], i, vazios = 0;
    for (i = 0; i < n; i++) {
      var t = i / (n - 1), e = elev(a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t);
      if (!e.ok) return { erro: "falta " + (/^tile /.test(e.falta) ? e.falta : "a grade " + e.falta + ".hgt") + " para cobrir o caminho" };
      if (!isFinite(e.v)) { if (i === 0 || i === n - 1) return { erro: "a grade tem vazio exatamente no ponto " + (i === 0 ? "A" : "B") + "; mova o ponto alguns metros" }; vazios++; e.v = h[i - 1]; }
      d.push(D * t); h.push(e.v);
    }
    if (vazios > n * 0.2) return { erro: "grade com muitos vazios nesse caminho (" + vazios + " de " + n + " pontos)" };
    return { perfil: { d: d, h: h }, vazios: vazios, D_km: D };
  }

  var api = { lerHgt: lerHgt, elevacao: elevacao, perfilEntre: perfilEntre, haversineKm: haversineKm, lerCsv: lerCsv, validar: validar, plano: plano, morro: morro, reamostrar: reamostrar, MAX_PONTOS: MAX_PONTOS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaTerreno = api;
})(typeof window !== "undefined" ? window : this);
