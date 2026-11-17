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

  var api = { lerCsv: lerCsv, validar: validar, plano: plano, morro: morro, reamostrar: reamostrar, MAX_PONTOS: MAX_PONTOS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaTerreno = api;
})(typeof window !== "undefined" ? window : this);
