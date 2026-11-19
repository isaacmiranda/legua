/* Citação, reprodução e exportação de dados para o site (funções puras, sem rede). Cada aba de resultados ganha uma
 * barra com: texto de citação e BibTeX, o comando que reproduz os números, os dados brutos da aba em JSON e as tabelas
 * visíveis em CSV. Os dados de simulação não têm coordenadas nem chaves; o JSON do testador de enlaces tem a sua
 * própria exportação e não passa por aqui. */
(function (root) {
  "use strict";
  var FALTA = "não informado";

  function escalaTxt(e) { return e === "full" ? "longa (full)" : "rápida (quick)"; }
  function comando(escala, cenarios) {
    return "PYTHONPATH=. ~/.venvs/legua/bin/python -m simsuite.run_suite --escala " + escala + " --procs 1" + (cenarios && cenarios.length ? " --so " + cenarios.join(" ") : "") +
      " && ~/.venvs/legua/bin/python tools/build_site.py";
  }
  /* inp: { aba, abaId, escala, cenarios[], meta{gerado_em, commit, versao_nucleo, repositorio}, sementes, url } */
  function bloco(inp) {
    var m = inp.meta || {}, ano = (m.gerado_em || "").slice(0, 4) || "s.d.", repo = m.repositorio || FALTA, url = inp.url || repo;
    var sem = inp.sementes == null ? "fixas no código da suíte (determinísticas)" : (Array.isArray(inp.sementes) ? inp.sementes.join(", ") : String(inp.sementes));
    var texto = "Légua, núcleo " + (m.versao_nucleo || FALTA) + ", «" + inp.aba + "», escala " + escalaTxt(inp.escala) + ", cenários " + ((inp.cenarios || []).join(", ") || "–") +
      ". Sementes: " + sem + ". Dados gerados em " + (m.gerado_em || FALTA) + ", commit " + (m.commit || FALTA) + ". Estimativa de simulação com parâmetros estimados; sem medição em hardware. " + url;
    var chave = "legua" + ano + (inp.abaId || "aba");
    var bib = "@misc{" + chave + ",\n  title = {Légua: " + inp.aba + " (escala " + (inp.escala === "full" ? "longa" : "rápida") + ")},\n  author = {Miranda, Isaac},\n  year = {" + ano + "},\n  note = {Núcleo " +
      (m.versao_nucleo || FALTA) + ", commit " + (m.commit || FALTA) + ". Estimativa de simulação; sem medição em hardware.},\n  howpublished = {\\url{" + url + "}}\n}";
    return { texto: texto, bibtex: bib, comando: comando(inp.escala, inp.cenarios) };
  }

  function celula(c) { var t = String(c == null ? "" : c).replace(/\s+/g, " ").trim(); return /[;"\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t; }
  /* tabelas visíveis de uma raiz DOM -> [{ titulo, csv }]; o CSV começa com linhas de comentário com a procedência */
  function tabelasCsv(raiz, procedencia) {
    var out = [];
    Array.prototype.forEach.call(raiz.querySelectorAll("table"), function (t, i) {
      var card = t.closest ? t.closest(".card") : null, h = card && card.querySelector("h2"), titulo = (h ? h.textContent : "tabela " + (i + 1)).trim();
      var linhas = Array.prototype.map.call(t.querySelectorAll("tr"), function (tr) {
        return Array.prototype.map.call(tr.children, function (c) { return celula(c.textContent); }).join(";");
      });
      if (linhas.length < 2) return;
      out.push({ titulo: titulo, csv: "﻿# " + procedencia + "\r\n# tabela: " + titulo.replace(/\s+/g, " ") + "\r\n" + linhas.join("\r\n") + "\r\n" });
    });
    return out;
  }
  function slug(t) { return String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48) || "dados"; }
  /* dados brutos da aba (só os cenários que ela usa) + procedência */
  function jsonDaAba(inp, dados) {
    var o = { procedencia: { projeto: "Légua", aba: inp.aba, escala: inp.escala, cenarios: inp.cenarios || [], gerado_em: (inp.meta || {}).gerado_em || null, commit: (inp.meta || {}).commit || null,
      versao_nucleo: (inp.meta || {}).versao_nucleo || null, aviso: "Estimativa de simulação com parâmetros estimados; sem medição em hardware. Não é previsão de campo." }, dados: {} };
    (inp.cenarios || []).forEach(function (c) { if (dados && dados[c] !== undefined) o.dados[c] = dados[c]; });
    return JSON.stringify(o, null, 1);
  }

  var api = { bloco: bloco, comando: comando, tabelasCsv: tabelasCsv, jsonDaAba: jsonDaAba, slug: slug, celula: celula };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaCitar = api;
})(typeof window !== "undefined" ? window : this);
