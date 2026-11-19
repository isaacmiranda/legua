/* Reprodutor de rastros de telemetria JSONL (sem DOM). Mesmo esquema de simsuite/analysis/telemetry.py: um evento por linha com
 * v, t (s), node, ev e os campos do evento. PRIVACIDADE: rastros de hardware trazem lat, lon, alt e GNSS; esses campos são
 * REMOVIDOS na leitura e nunca aparecem, são guardados ou exportados. Tudo local. */
(function (root) {
  "use strict";
  var LOCALIZACAO = /^(lat|lon|lng|alt|latitude|longitude|altitude|gnss|gps|coord|coordenadas)(_|$)/;

  /* texto JSONL -> { recs, removidos: {campo: n}, avisos[], erro } */
  function ler(texto) {
    var linhas = String(texto || "").split(/\r?\n/), recs = [], ruins = 0, removidos = {}, i;
    for (i = 0; i < linhas.length; i++) {
      var l = linhas[i].trim(); if (!l) continue;
      var r; try { r = JSON.parse(l); } catch (e) { ruins++; continue; }
      if (!r || typeof r !== "object" || typeof r.t !== "number" || typeof r.ev !== "string") { ruins++; continue; }
      Object.keys(r).forEach(function (k) { if (LOCALIZACAO.test(k)) { removidos[k] = (removidos[k] || 0) + 1; delete r[k]; } });
      recs.push(r);
    }
    if (!recs.length) return { erro: "nenhum evento válido: cada linha deve ser um JSON com t (número) e ev (texto)" };
    recs.sort(function (a, b) { return a.t - b.t; });
    var avisos = [];
    if (ruins) avisos.push(ruins + " linha(s) ignorada(s) (JSON inválido ou sem t e ev)");
    var nrem = Object.keys(removidos).reduce(function (a, k) { return a + removidos[k]; }, 0);
    if (nrem) avisos.push("campos de localização removidos por privacidade: " + Object.keys(removidos).join(", ") + " (" + nrem + " valores)");
    return { recs: recs, removidos: removidos, avisos: avisos };
  }

  /* resumo: nós, duração, contagem por evento, intervalos de modo por nó, marcas (rollback, reboot, resync, alarmes) */
  function resumo(recs) {
    var nos = {}, cont = {}, t0 = recs[0].t, t1 = recs[recs.length - 1].t, marcas = [];
    recs.forEach(function (r) {
      var n = r.node == null ? "?" : String(r.node), no = nos[n] || (nos[n] = { id: n, eventos: 0, modos: [], atual: null, tx: 0, rx: 0, rollbacks: 0, rejeitados: 0, reboots: 0, resync: 0 });
      no.eventos++; cont[r.ev] = (cont[r.ev] || 0) + 1;
      if (r.ev === "tx") no.tx++; else if (r.ev === "rx") no.rx++;
      else if (r.ev === "rejeitado") no.rejeitados++;
      else if (r.ev === "reboot") { no.reboots++; marcas.push({ t: r.t, node: n, tipo: "reboot" }); }
      else if (r.ev === "alarme_rollback") { no.rollbacks++; marcas.push({ t: r.t, node: n, tipo: "rollback" }); }
      else if (r.ev === "resync") { no.resync++; marcas.push({ t: r.t, node: n, tipo: "resync" }); }
      else if (r.ev === "alarme_mic") marcas.push({ t: r.t, node: n, tipo: "alarme de MIC" });
      if (r.ev === "modo" && r.modo != null) {
        if (no.atual) { no.atual.t1 = r.t; }
        no.atual = { t0: r.t, t1: t1, modo: String(r.modo), estado: r.estado == null ? "" : String(r.estado), motivo: r.motivo == null ? "" : String(r.motivo) }; no.modos.push(no.atual);
      }
    });
    return { nos: nos, contagem: cont, t0: t0, t1: t1, duracao: t1 - t0, total: recs.length, marcas: marcas };
  }

  /* eventos filtrados por nó e tipo, limitados a `max` */
  function filtrar(recs, f, max) {
    var out = [], i; max = max || 500; f = f || {};
    for (i = 0; i < recs.length && out.length < max; i++) {
      var r = recs[i];
      if (f.node && String(r.node) !== String(f.node)) continue;
      if (f.ev && r.ev !== f.ev) continue;
      if (f.busca && JSON.stringify(r).toLowerCase().indexOf(String(f.busca).toLowerCase()) < 0) continue;
      out.push(r);
    }
    return out;
  }
  function paraJsonl(recs) { return recs.map(function (r) { return JSON.stringify(r); }).join("\n") + "\n"; }

  var api = { ler: ler, resumo: resumo, filtrar: filtrar, paraJsonl: paraJsonl, LOCALIZACAO: LOCALIZACAO };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaRastros = api;
})(typeof window !== "undefined" ? window : this);
