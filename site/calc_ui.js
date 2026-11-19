/* Aba "Calculadoras": painel com os parâmetros do rádio e os resultados de tempo no ar, sensibilidade, ciclo de trabalho,
 * bateria e canais (calculadoras.js). O estado fica na página e sobrevive à troca de aba; nada sai do navegador. */
(function (root) {
  "use strict";
  var doc = root.document, S = { sf: 10, bw: 125, cr: 1, pl: 24, pre: 8, crc: true, expl: true, p: 14, ant: 2.15, cabo: 0.5, ganhoRx: 2.15, nf: null,
    pph: 60, limite: 1, cap: 1000, sono: 20, rxs: 1, canais: 35 };

  function el(tag, attrs, kids) {
    var e = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(typeof c === "string" ? doc.createTextNode(c) : c); });
    return e;
  }
  function nf(x, d) { return isFinite(x) ? x.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }) : "–"; }

  function painel(panel, DATA) {
    var K = DATA.constantes, C = root.LeguaCalc;
    if (S.nf == null) S.nf = K.nf_db;
    panel.textContent = "";
    var saida = el("div");
    function campo(rot, chave, op) {
      var inp;
      if (op.opcoes) {
        inp = el("select"); op.opcoes.forEach(function (o) { var x = el("option", { value: o[0], text: o[1] }); if (String(o[0]) === String(S[chave])) x.selected = true; inp.appendChild(x); });
      } else if (op.bool) { inp = el("input", { type: "checkbox" }); inp.checked = !!S[chave]; }
      else { inp = el("input", { type: "number", step: String(op.passo || 1), min: String(op.min), max: String(op.max), inputmode: "decimal" }); inp.value = S[chave]; }
      inp.setAttribute("aria-label", rot);
      inp.addEventListener(op.opcoes || op.bool ? "change" : "input", function () {
        if (op.bool) S[chave] = inp.checked;
        else if (op.opcoes) S[chave] = parseFloat(inp.value);
        else { var v = parseFloat(String(inp.value).replace(",", ".")); if (isFinite(v)) S[chave] = Math.min(op.max, Math.max(op.min, v)); }
        calcula();
      });
      return el("label", { "class": "field" }, [el("span", { text: rot + (op.un ? " (" + op.un + ")" : "") }), inp]);
    }
    function cartao(titulo, nota, kids) { return el("section", { "class": "card" }, [el("h2", { text: titulo })].concat(nota ? [el("p", { "class": "note", text: nota })] : []).concat(kids)); }
    function linhas(itens) {
      return el("div", { "class": "stats" }, itens.map(function (i) { return el("div", { "class": "stat" }, [el("div", { "class": "v", text: i[0] }), el("div", { "class": "l", text: i[1] })]); }));
    }
    var sfs = [5, 6, 7, 8, 9, 10, 11, 12].map(function (x) { return [x, "SF" + x]; });
    var form = cartao("Parâmetros do rádio", "Valem para todas as calculadoras abaixo. Os resultados se atualizam na hora; nada sai do seu navegador.", [el("div", { "class": "form" }, [
      campo("Fator de espalhamento", "sf", { opcoes: sfs }), campo("Largura de banda", "bw", { opcoes: [[125, "125 kHz"], [250, "250 kHz"], [500, "500 kHz"]] }),
      campo("Taxa de código", "cr", { opcoes: [[1, "4/5"], [2, "4/6"], [3, "4/7"], [4, "4/8"]] }), campo("Carga útil", "pl", { min: 1, max: 255, un: "bytes" }),
      campo("Preâmbulo", "pre", { min: 6, max: 65, un: "símbolos" }), campo("CRC no pacote", "crc", { bool: true }), campo("Cabeçalho explícito", "expl", { bool: true }),
      campo("Potência de TX", "p", { min: -9, max: 28, un: "dBm" }), campo("Ganho da antena de TX", "ant", { min: -5, max: 15, passo: 0.05, un: "dBi" }),
      campo("Perda de cabo", "cabo", { min: 0, max: 10, passo: 0.1, un: "dB" }), campo("Ganho da antena de RX", "ganhoRx", { min: -5, max: 15, passo: 0.05, un: "dBi" }),
      campo("Figura de ruído do RX", "nf", { min: 0.5, max: 15, passo: 0.5, un: "dB" })])]);
    var ciclo = cartao("Ciclo de trabalho", "Fração do tempo no ar. O limite é um número seu: o perfil BR-2026 (fonte secundária, nao_verificado) regula o tempo de ocupação por canal, não um ciclo único; confirme a regra do seu caso.",
      [el("div", { "class": "form" }, [campo("Pacotes por hora", "pph", { min: 1, max: 36000 }), campo("Limite de ciclo de trabalho", "limite", { min: 0.01, max: 100, passo: 0.1, un: "%" })])]);
    var bat = cartao("Vida de bateria (estimativa)", "Corrente de TX da tabela do simulador (estimada; meça na sua placa), RX do SX1262 e um consumo em repouso que você informa. Não inclui o resto da placa nem o desvio de temperatura.",
      [el("div", { "class": "form" }, [campo("Capacidade da bateria", "cap", { min: 10, max: 100000, un: "mAh" }), campo("Consumo em repouso", "sono", { min: 0, max: 100000, un: "µA" }), campo("Escuta de RX por pacote", "rxs", { min: 0, max: 60, passo: 0.1, un: "s" })])]);
    var can = cartao("Canais e regra de salto (BR-2026, nao_verificado)", "Plano de canais calculado no mesmo critério do simulador (guarda de 0,6 × a largura de banda) sobre as faixas do perfil; as regras vêm de fonte secundária.",
      [el("div", { "class": "form" }, [campo("Canais usados no salto", "canais", { min: 1, max: 200 })])]);
    var res = { toa: el("div"), sens: el("div"), ciclo: el("div"), bat: el("div"), can: el("div") };
    var rt = cartao("Tempo no ar e taxa de bits", null, [res.toa]), rs = cartao("Sensibilidade e perda máxima de percurso", "Perda máxima: o quanto o caminho pode atenuar antes de o sinal cair abaixo da sensibilidade. É o ponto de partida do orçamento de enlace; terreno e margem de desvanecimento ficam por sua conta (testador de enlaces).", [res.sens]);
    ciclo.appendChild(res.ciclo); bat.appendChild(res.bat); can.appendChild(res.can);
    [form, rt, rs, ciclo, bat, can].forEach(function (c) { saida.appendChild(c); });
    panel.appendChild(saida);

    function calcula() {
      var toa = C.toaS(S.sf, S.bw, S.pl, S.cr, S.pre, S.crc, S.expl), toaD = C.toaS(S.sf, S.bw, K.data_bytes, S.cr, 8, true, true), toaA = C.toaS(S.sf, S.bw, K.ack_bytes, S.cr, 8, true, true);
      res.toa.textContent = ""; res.toa.appendChild(linhas([[nf(toa * 1000, 1) + " ms", "tempo no ar da carga de " + S.pl + " B"], [nf(C.taxaBps(S.sf, S.bw, S.cr), 0) + " bit/s", "taxa de bits do modo"],
        [nf(toaD * 1000, 1) + " ms", "DATA da Légua (" + K.data_bytes + " B)"], [nf(toaA * 1000, 1) + " ms", "ACK da Légua (" + K.ack_bytes + " B)"],
        [toa > K.dwell_max_s ? "acima" : "dentro", "do tempo de ocupação por canal de " + nf(K.dwell_max_s, 1) + " s (perfil BR-2026, nao_verificado)"]]));
      var sens = C.sensibilidadeDbm(Object.assign({}, K, { nf_db: S.nf }), S.sf, S.bw, S.cr), eirp = S.p + S.ant - S.cabo, mapl = eirp + S.ganhoRx - sens;
      var dFs = Math.pow(10, (mapl - 20 * Math.log10(4 * Math.PI * 1e3 * 915e6 / 299792458)) / 20);
      res.sens.textContent = ""; res.sens.appendChild(linhas([[nf(sens, 1) + " dBm", "sensibilidade estimada (centro da curva de erro: +" + nf(K.per_offset_db, 1) + " dB)"], [nf(C.ruidoDbm(S.bw, S.nf), 1) + " dBm", "piso de ruído"],
        [nf(eirp, 1) + " dBm", "EIRP"], [nf(mapl, 1) + " dB", "perda máxima de percurso"], [nf(dFs, 1) + " km", "alcance no espaço livre (limite superior; sem terreno nem margem)"]]));
      var cu = C.cicloUtil(toa, S.pph), mini = C.intervaloMinimoS(toa, S.limite / 100);
      res.ciclo.textContent = ""; res.ciclo.appendChild(linhas([[nf(cu * 100, 3) + " %", "ciclo de trabalho com " + S.pph + " pacotes/h"], [cu * 100 <= S.limite ? "dentro" : "acima", "do limite de " + nf(S.limite, 2) + " %"],
        [nf(mini, 1) + " s", "intervalo mínimo entre pacotes para respeitar o limite"], [nf(Math.floor(3600 / mini), 0), "pacotes por hora no máximo"]]));
      var b = C.bateria(K, { capMah: S.cap, pDbm: S.p, toaS: toa, pph: S.pph, rxPorPacoteS: S.rxs, sonoUa: S.sono });
      res.bat.textContent = ""; res.bat.appendChild(linhas([[nf(b.dias, 1) + " dias", "autonomia estimada (" + nf(b.horas, 0) + " h)"], [nf(b.mediaMa, 3) + " mA", "corrente média"], [nf(b.iTxMa, 0) + " mA", "corrente de TX a " + S.p + " dBm (tabela estimada)"],
        [nf(b.energiaPacoteMj, 1) + " mJ", "energia de TX por pacote"]]));
      var plano = C.planoCanais(K.regulatorio.faixas_hz, S.bw), regra = C.regraSalto(K.regulatorio, S.bw, S.canais, S.ant);
      res.can.textContent = ""; res.can.appendChild(linhas([[String(plano.length), "canais de " + S.bw + " kHz nas faixas do perfil"],
        [regra.classe ? (regra.ok ? "atende" : "não atende") : "sem classe", regra.classe ? "mínimo de " + regra.canaisMin + " canais para esta largura de banda" : regra.motivo],
        [regra.classe ? nf(regra.tetoDbm, 1) + " dBm" : "–", "teto de potência com " + S.canais + " canais e antena de " + nf(S.ant, 2) + " dBi (EIRP máximo do perfil)"]]));
      res.can.appendChild(el("p", { "class": "note", text: "Perfil BR-2026: fonte secundária, nao_verificado. A conformidade é do produto; esta calculadora não afirma conformidade nem homologação." }));
    }
    calcula();
  }
  root.LeguaCalcUI = { painel: painel, estado: S };
})(typeof window !== "undefined" ? window : this);
