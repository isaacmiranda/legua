/* Explicações em linguagem simples para cada gráfico e cada tabela do site, com diagramas, um guia interativo e glossário.
 * Só texto e desenhos estáticos: nenhum número daqui vem de resultados (os números ficam nos cartões). Carregado antes de app.js. */
(function () {
  "use strict";
  var NSX = "http://www.w3.org/2000/svg";
  var T = "fill:var(--text-2);font:11px system-ui,sans-serif", TB = "fill:var(--text);font:600 11px system-ui,sans-serif";
  var AX = "stroke:var(--text-3);stroke-width:1.2;fill:none", GR = "stroke:var(--grid);stroke-width:1;fill:none";

  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function tx(x, y, s, o) { o = o || {}; return '<text x="' + x + '" y="' + y + '" text-anchor="' + (o.a || "start") + '" style="' + (o.b ? TB : T) + (o.c ? ";fill:" + o.c : "") + '">' + esc(s) + "</text>"; }
  function ln(x1, y1, x2, y2, c, w, dash) { return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" style="stroke:' + (c || "var(--text-3)") + ";stroke-width:" + (w || 1.5) + (dash ? ";stroke-dasharray:4 3" : "") + '"/>'; }
  function arrow(x1, y1, x2, y2, c, dash) {
    var a = Math.atan2(y2 - y1, x2 - x1), h = 6, c0 = c || "var(--text-2)";
    return ln(x1, y1, x2, y2, c0, 1.6, dash) + '<path d="M' + x2 + " " + y2 + " L" + (x2 - h * Math.cos(a - 0.45)) + " " + (y2 - h * Math.sin(a - 0.45)) + " L" + (x2 - h * Math.cos(a + 0.45)) + " " + (y2 - h * Math.sin(a + 0.45)) + ' Z" style="fill:' + c0 + '"/>';
  }
  function rect(x, y, w, h, c, o) { o = o || {}; return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="' + (o.r == null ? 4 : o.r) + '" style="fill:' + (c || "none") + ";stroke:" + (o.s || "none") + ";stroke-width:1.2" + (o.op ? ";opacity:" + o.op : "") + '"/>'; }
  function circ(x, y, r, c, s) { return '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" style="fill:' + (c || "none") + ";stroke:" + (s || "none") + ';stroke-width:1.4"/>'; }
  function path(d, c, w, dash) { return '<path d="' + d + '" style="fill:none;stroke:' + c + ";stroke-width:" + (w || 2) + (dash ? ";stroke-dasharray:5 4" : "") + '"/>'; }
  function wrap(w, h, label, inner) {
    return '<svg xmlns="' + NSX + '" viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="' + esc(label) + '" class="dgm">' + inner + "</svg>";
  }
  function axes(xl, yl, extra) {
    return ln(44, 12, 44, 118, "var(--text-3)", 1.2) + ln(44, 118, 348, 118, "var(--text-3)", 1.2) + tx(196, 136, xl, { a: "middle" }) +
      '<text x="12" y="66" transform="rotate(-90 12 66)" text-anchor="middle" style="' + T + '">' + esc(yl) + "</text>" + (extra || "");
  }
  function legendDots(items, x, y) {
    return items.map(function (it, i) { return circ(x, y + i * 15, 4, it[0]) + tx(x + 9, y + 4 + i * 15, it[1]); }).join("");
  }
  var S1 = "var(--s1)", S2 = "var(--s2)", S3 = "var(--s3)", S4 = "var(--s4)", S5 = "var(--s5)", OK = "var(--ok)", BAD = "var(--bad)";

  // ------------------------------------------------------------------ diagramas
  // Gráfico de pontos como o dos resultados: uma linha por cenário, marcadores de formatos diferentes, linha fina ligando-os.
  function mk(shape, x, y, c) {
    if (shape === "d") return '<path d="M' + x + " " + (y - 5) + " L" + (x + 5) + " " + y + " L" + x + " " + (y + 5) + " L" + (x - 5) + " " + y + 'Z" style="fill:' + c + '"/>';
    if (shape === "s") return '<rect x="' + (x - 4) + '" y="' + (y - 4) + '" width="8" height="8" style="fill:' + c + '"/>';
    if (shape === "t") return '<path d="M' + x + " " + (y - 5) + " L" + (x + 5) + " " + (y + 4) + " L" + (x - 5) + " " + (y + 4) + 'Z" style="fill:' + c + '"/>';
    if (shape === "x") return ln(x - 4, y - 4, x + 4, y + 4, c, 2) + ln(x - 4, y + 4, x + 4, y - 4, c, 2);
    return circ(x, y, 4, c);
  }
  function dotRows(label, rows, leg, unit) {
    var L = 96, R = 340, inner = "", y0 = 22, dy = 26, k;
    rows.forEach(function (r, i) {
      var y = y0 + i * dy;
      if (i % 2 === 0) inner += '<rect x="8" y="' + (y - 13) + '" width="344" height="26" style="fill:var(--grid);opacity:.35"/>';
      inner += tx(L - 8, y + 4, r[0], { a: "end" });
      var xs = r[1].map(function (f) { return L + f * (R - L); });
      inner += ln(Math.min.apply(null, xs), y, Math.max.apply(null, xs), y, "var(--text-3)", 1);
      r[1].forEach(function (f, j) { inner += mk(leg[j][2], xs[j], y, leg[j][0]); });
    });
    var yb = y0 + rows.length * dy - 6;
    inner += ln(L, yb, R, yb, "var(--text-3)", 1.2) + tx(L, yb + 12, "menor", { a: "middle" }) + tx(R, yb + 12, "maior", { a: "middle" }) + tx((L + R) / 2, yb + 12, unit, { a: "middle" });
    var lx = 10, ly = yb + 30;
    leg.forEach(function (it, j) { inner += mk(it[2], lx + 4, ly - 4, it[0]) + tx(lx + 14, ly, it[1]); lx += 14 + it[1].length * 6 + 14; });
    return wrap(360, ly + 10, label, inner);
  }
  var DG = {
    "pontos-cenarios": function () {
      return dotRows("Gráfico de pontos: cada linha é um cenário e cada marcador, uma configuração; a posição horizontal é o valor medido",
        [["cenário A", [0.92, 0.98, 0.95]], ["cenário B", [0.55, 0.8, 0.7]], ["cenário C", [0.3, 0.5, 0.45]]],
        [[S1, "Légua", "o"], [S2, "modo fixo rápido", "t"], [S3, "modo fixo robusto", "s"]], "valor");
    },
    "pontos-escalas": function () {
      return dotRows("Gráfico de pontos: cada linha é uma configuração e os marcadores são a escala rápida e a escala longa, para comparar",
        [["configuração 1", [0.9, 0.86]], ["configuração 2", [0.6, 0.64]], ["configuração 3", [0.35, 0.33]]],
        [[S1, "escala rápida", "o"], [S2, "escala longa", "d"]], "valor");
    },
    "curva-perda": function () {
      return wrap(360, 146, "Curva: o eixo horizontal é a perda de quadros e o vertical, a medida do acordo; a curva sobe com a perda",
        axes("perda de quadros no ar →", "medida do acordo") + path("M44 112 C 120 108 180 96 240 70 C 280 52 320 34 344 26", S1, 2.4) +
        circ(44, 112, 3.5, S1) + circ(120, 108, 3.5, S1) + circ(190, 94, 3.5, S1) + circ(262, 62, 3.5, S1) + circ(344, 26, 3.5, S1) +
        tx(60, 28, "sobe devagar: bom", { c: OK }));
    },
    "tabela-linhas": function () {
      return wrap(360, 128, "Tabela: cada linha é um caso testado e as colunas são os resultados medidos para esse caso",
        rect(14, 8, 332, 22, "var(--grid)", { r: 2 }) + tx(24, 23, "caso", { b: 1 }) + tx(150, 23, "resultado", { b: 1 }) + tx(260, 23, "observação", { b: 1 }) +
        tx(24, 48, "caso 1") + tx(150, 48, "0,99") + tx(260, 48, "ok", { c: OK }) +
        tx(24, 70, "caso 2") + tx(150, 70, "0,93") + tx(260, 70, "ok", { c: OK }) +
        tx(24, 92, "caso 3") + tx(150, 92, "0,41") + tx(260, 92, "atenção", { c: BAD }) +
        tx(180, 118, "leia linha por linha: cada caso se compara com os outros", { a: "middle" }));
    },
    "curva-distancia": function () {
      return wrap(360, 170, "Curvas de taxa de entrega contra distância: modo rápido cai cedo, modo robusto cai tarde, a Légua acompanha o melhor",
        axes("distância entre os nós →", "taxa de entrega") + ln(44, 24, 348, 24, "var(--grid)", 1) + tx(50, 20, "100%") +
        path("M44 26 C 90 26 110 30 125 80 C 132 104 140 116 160 118", S2, 2) + path("M44 40 C 160 40 230 44 270 70 C 300 90 320 110 340 118", S3, 2) +
        path("M44 26 C 110 26 130 30 160 36 C 220 44 260 62 290 82 C 315 100 328 112 340 118", S1, 2.6) +
        circ(52, 158, 4, S2) + tx(60, 162, "modo rápido") + circ(142, 158, 4, S3) + tx(150, 162, "modo robusto") + circ(244, 158, 4, S1) + tx(252, 162, "Légua (troca de modo)"));
    },
    "rollback": function () {
      return wrap(360, 120, "Linha do tempo: modo antigo, tentativa do modo novo, validação falha e volta ao modo antigo",
        rect(20, 40, 90, 26, S3, { op: 0.3, s: S3 }) + tx(65, 57, "modo antigo", { a: "middle" }) +
        rect(110, 40, 90, 26, S2, { op: 0.3, s: S2 }) + tx(155, 57, "modo novo?", { a: "middle" }) +
        rect(200, 40, 140, 26, S3, { op: 0.3, s: S3 }) + tx(270, 57, "volta ao modo antigo", { a: "middle" }) +
        ln(110, 28, 110, 80, "var(--text-3)", 1, 1) + ln(200, 28, 200, 80, "var(--text-3)", 1, 1) +
        tx(110, 22, "troca", { a: "middle" }) + tx(200, 22, "validação falha", { a: "middle", c: BAD }) +
        arrow(200, 90, 110, 90, BAD) + tx(155, 106, "rollback", { a: "middle", c: BAD, b: 1 }));
    },
    "pontos-variantes": function () {
      return wrap(360, 134, "Gráfico de pontos: cada linha é uma variante do protocolo; cada ponto é um enlace; quanto mais à esquerda, menor o valor",
        ln(150, 14, 150, 108, "var(--grid)", 1) + ln(260, 14, 260, 108, "var(--grid)", 1) +
        tx(10, 34, "variante 1") + tx(10, 64, "variante 2") + tx(10, 94, "variante 3") +
        circ(210, 30, 5, S1) + circ(244, 30, 5, S2) + circ(170, 60, 5, S1) + circ(190, 60, 5, S2) + circ(300, 90, 5, S1) + circ(330, 90, 5, S2) +
        arrow(300, 114, 150, 114, OK) + tx(225, 127, "menos = melhor", { a: "middle", c: OK }) + legendDots([[S1, "enlace 1"], [S2, "enlace 2"]], 290, 22));
    },
    "tabela-celula": function () {
      return wrap(360, 130, "Anatomia de uma célula de tabela: PDR, ponto e energia por pacote",
        rect(20, 10, 150, 34, "var(--surface)", { s: "var(--text-3)" }) + tx(95, 32, "0,985 · 1.356 mJ", { a: "middle", b: 1 }) +
        rect(190, 10, 110, 34, "var(--surface)", { s: "var(--text-3)" }) + tx(245, 32, "sem enlace", { a: "middle", b: 1 }) +
        circ(24, 66, 4, S1) + tx(34, 70, "0,985 = PDR: fração dos pacotes que chegaram (1,000 = todos)") +
        circ(24, 86, 4, S2) + tx(34, 90, "1.356 mJ = energia de TX por pacote entregue (menor = melhor)") +
        circ(24, 106, 4, BAD) + tx(34, 110, "sem enlace = quase nada chegou (PDR < 2%): o enlace não fecha"));
    },
    "estrela-malha": function () {
      return wrap(360, 150, "Topologias: estrela com um centro e vários nós; malha com nós que repassam pacotes",
        circ(70, 70, 12, S1) + [[20, 24], [20, 116], [120, 24], [120, 116]].map(function (p) { return ln(70, 70, p[0], p[1], "var(--text-3)", 1.4) + circ(p[0], p[1], 7, "var(--surface)", "var(--text-2)"); }).join("") +
        tx(70, 146, "estrela", { a: "middle", b: 1 }) + tx(70, 48, "centro", { a: "middle" }) +
        [[230, 30], [310, 30], [270, 70], [230, 112], [310, 112]].map(function (p, i, a) { return (i < 4 ? ln(p[0], p[1], a[i + 1][0], a[i + 1][1], "var(--text-3)", 1.2) : "") + circ(p[0], p[1], 7, i == 2 ? S1 : "var(--surface)", i == 2 ? S1 : "var(--text-2)"); }).join("") +
        ln(230, 30, 230, 112, "var(--text-3)", 1.2) + ln(310, 30, 310, 112, "var(--text-3)", 1.2) + tx(270, 146, "malha (repasse)", { a: "middle", b: 1 }));
    },
    "estados-formal": function () {
      return wrap(360, 150, "Duas máquinas de estados, A e B, com mensagens que podem se perder; o verificador explora todas as possibilidades",
        rect(20, 20, 110, 70, "var(--surface)", { s: "var(--text-3)" }) + tx(75, 38, "Nó A", { a: "middle", b: 1 }) + tx(75, 58, "BASE · DATA", { a: "middle" }) + tx(75, 74, "NEG · VALID …", { a: "middle" }) +
        rect(230, 20, 110, 70, "var(--surface)", { s: "var(--text-3)" }) + tx(285, 38, "Nó B", { a: "middle", b: 1 }) + tx(285, 58, "BASE · DATA", { a: "middle" }) + tx(285, 74, "PEND · VALID …", { a: "middle" }) +
        arrow(132, 44, 228, 44, S1) + arrow(228, 66, 132, 66, S3, 1) + tx(180, 38, "pode perder", { a: "middle", c: BAD }) +
        tx(180, 112, "P1 nunca fica em desacordo para sempre", { a: "middle" }) + tx(180, 126, "P3 sempre dá para voltar a operar juntos", { a: "middle" }) + tx(180, 140, "P4 só grava como âncora o que o par aceitou", { a: "middle" }));
    },
    "aloha": function () {
      return wrap(360, 130, "Linha do tempo de pacotes: quando dois pacotes se sobrepõem no ar há colisão, e o mais forte pode sobreviver (captura)",
        ln(20, 100, 345, 100, "var(--text-3)", 1.2) + tx(184, 122, "tempo →", { a: "middle" }) +
        rect(30, 70, 70, 20, S1, { op: 0.35, s: S1 }) + tx(65, 84, "pacote 1", { a: "middle" }) +
        rect(150, 40, 80, 20, S2, { op: 0.35, s: S2 }) + tx(160, 54, "fraco", {}) + rect(190, 70, 80, 20, S3, { op: 0.45, s: S3 }) + tx(236, 84, "forte", {}) +
        rect(190, 36, 40, 58, "none", { s: BAD }) + tx(350, 14, "colisão: o pacote forte (≥ 6 dB acima)", { a: "end", c: BAD }) + tx(350, 28, "pode sobreviver; o fraco se perde", { a: "end", c: BAD }));
    },
    "teto-potencia": function () {
      return wrap(360, 130, "Dois nós com tetos de potência diferentes: o nó fraco limita os modos que o par consegue usar",
        rect(20, 58, 40, 40, S1, { op: 0.9 }) + rect(140, 86, 40, 12, S2, { op: 0.9 }) + tx(40, 116, "A: 28 dBm", { a: "middle" }) + tx(160, 116, "B: teto baixo", { a: "middle" }) +
        arrow(66, 68, 134, 88, S1) + arrow(134, 94, 66, 76, S2, 1) + tx(20, 40, "mesmo modo nos dois sentidos", {}) +
        tx(215, 56, "teto do nó fraco ↓", { b: 1 }) + tx(215, 74, "→ modos mais lentos", {}) + tx(215, 90, "→ mais tempo no ar", {}) + tx(215, 106, "→ mais energia por pacote", {}));
    },
    "seguranca": function () {
      return wrap(360, 120, "Quadros de um atacante são recusados: contador repetido (replay) e quadro sem assinatura válida (forjado)",
        rect(10, 36, 64, 28, "var(--surface)", { s: "var(--text-3)" }) + tx(42, 54, "atacante", { a: "middle" }) +
        arrow(76, 50, 130, 50, BAD) + rect(132, 24, 110, 52, "var(--surface)", { s: OK }) + tx(187, 44, "receptor", { a: "middle", b: 1 }) + tx(187, 62, "contador + MIC", { a: "middle" }) +
        arrow(244, 50, 270, 50, OK) + tx(274, 46, "recusado,", { c: OK, b: 1 }) + tx(274, 60, "sem efeito", { c: OK, b: 1 }) +
        tx(10, 98, "replay = quadro antigo reenviado", {}) + tx(10, 112, "forjado = quadro inventado, sem assinatura válida", {}));
    },
    "orcamento-tempo": function () {
      return wrap(360, 110, "Duas escalas: a rápida roda em minutos, a longa em mais de uma hora, com mais sementes e mais tempo simulado",
        rect(30, 24, 36, 24, S3) + tx(74, 40, "rápida: poucos minutos, 2 sementes") + rect(30, 60, 300, 24, S1) + tx(36, 76, "longa: ~1 h, 5 sementes, dias simulados", { c: "#fff", b: 1 }) +
        tx(30, 104, "a mesma conta, mais amostras: o resultado fica mais estável", {}));
    },
    "estimativa": function () {
      return wrap(360, 100, "Fluxo: parâmetros do setup alimentam um modelo analítico que estima a entrega por modo",
        rect(8, 30, 82, 40, "var(--surface)", { s: "var(--text-3)" }) + tx(49, 54, "seu setup", { a: "middle", b: 1 }) + arrow(92, 50, 110, 50) +
        rect(112, 30, 112, 40, "var(--surface)", { s: S1 }) + tx(168, 54, "modelo do canal", { a: "middle" }) + arrow(226, 50, 244, 50) +
        rect(246, 30, 106, 40, "var(--surface)", { s: S3 }) + tx(299, 54, "entrega × modo", { a: "middle", b: 1 }) +
        tx(180, 92, "distância, antena, potência, ambiente", { a: "middle" }));
    },
    "modos": function () {
      return wrap(360, 120, "Troca entre velocidade e alcance: espalhamento alto alcança mais longe e é mais lento",
        rect(30, 54, 300, 14, "var(--grid)") + arrow(40, 40, 320, 40, "var(--text-2)") + tx(36, 30, "mais rápido, curto", {}) + tx(324, 30, "mais lento, longo", { a: "end" }) +
        circ(60, 61, 7, S2) + tx(60, 88, "SF7", { a: "middle" }) + circ(130, 61, 7, S2) + tx(130, 88, "SF9", { a: "middle" }) + circ(210, 61, 7, S3) + tx(210, 88, "SF10", { a: "middle" }) + circ(290, 61, 7, S3) + tx(290, 88, "SF12", { a: "middle" }) +
        tx(180, 112, "SF = fator de espalhamento; BW = largura de banda", { a: "middle" }));
    },
    "equivalencia": function () {
      return wrap(360, 110, "A mesma sequência de eventos entra em duas implementações (Python e C) e as saídas são comparadas byte a byte",
        rect(14, 36, 80, 38, "var(--surface)", { s: "var(--text-3)" }) + tx(54, 59, "eventos", { a: "middle" }) + arrow(96, 48, 140, 30) + arrow(96, 62, 140, 84) +
        rect(142, 12, 90, 30, "var(--surface)", { s: S1 }) + tx(187, 31, "Python", { a: "middle" }) + rect(142, 70, 90, 30, "var(--surface)", { s: S2 }) + tx(187, 89, "C99", { a: "middle" }) +
        arrow(234, 28, 256, 46) + arrow(234, 86, 256, 64) + rect(258, 34, 96, 42, "var(--surface)", { s: OK }) + tx(306, 52, "iguais?", { a: "middle", b: 1 }) + tx(306, 67, "0 divergências", { a: "middle", c: OK }));
    }
  };

  // ------------------------------------------------------------------ explicações por cartão (casadas pelo título)
  // oque: o que está sendo mostrado; ler: como ler; atencao: o que não concluir
  var EX = [
    { re: /^Taxa de entrega × distância/, d: "curva-distancia", oque: "Para cada distância entre os dois rádios, quanta porcentagem dos pacotes chegou ao destino. Cada linha é uma configuração: um modo fixo ou a Légua, que escolhe o modo sozinha.",
      ler: "Procure onde cada linha começa a cair: quanto mais à direita, mais longe o enlace funciona. A Légua parte do modo seguro e acelera quando sobra folga, por isso fica perto da melhor linha em cada trecho.", atencao: "Cada ponto é a média de poucas sementes de canal; use as faixas de incerteza como alerta, não como garantia." },
    { re: /^Taxa de entrega por cenário de mobilidade/, d: "pontos-cenarios", oque: "O mesmo enlace com um dos nós em movimento (a pé, de carro, em rebanho). Cada linha é um cenário; cada marcador, uma configuração (a legenda está logo acima do gráfico).",
      ler: "Marcadores mais à direita são melhores. Compare os marcadores dentro de uma linha: a linha toda se desloca porque cada cenário tem velocidade e ambiente diferentes; a linha fina liga o pior ao melhor.", atencao: "Cenário rápido não é pior por si só: o que importa é a diferença entre os marcadores dentro da mesma linha." },
    { re: /^Energia por pacote entregue/, d: "pontos-cenarios", oque: "Quanta energia de transmissão foi gasta para cada pacote que realmente chegou. Pacotes perdidos contam como gasto sem retorno.",
      ler: "Marcadores mais à esquerda (menor energia) são melhores. Um modo rápido gasta pouco quando funciona e muito quando falha e retransmite.", atencao: "A corrente do amplificador é estimada, não medida; vale para comparar configurações, não para prever a bateria." },
    { re: /^SF\d+\/\d+/, d: "curva-distancia", oque: "Para um modo de rádio específico, a chance de um pacote chegar conforme a atenuação do enlace (a perda de sinal entre os dois nós).",
      ler: "A curva tem formato de degrau suave: do lado esquerdo o sinal sobra e quase tudo chega; do lado direito o sinal some e nada chega. O ponto onde a curva cai é o limite de alcance desse modo.", atencao: "Modos com espalhamento maior (SF mais alto) têm o degrau mais à direita, mas gastam mais tempo no ar." },
    { re: /^B9/, d: "modos", oque: "Quando a temperatura muda, o relógio do rádio deriva. Esta tabela diz de quanto pode ser a deriva antes de o pacote não ser mais recebido em cada modo.",
      ler: "Cada linha é um modo; a coluna de tolerância é o desvio máximo aceito. Tolerância pequena = modo sensível a temperatura.", atencao: "As taxas de deriva dos cristais são estimativas; a bancada deve medi-las." },
    { re: /^B10/, d: "modos", oque: "Tempo que o rádio gasta ‘ouvindo’ o canal para detectar se há transmissão (CAD) em cada espalhamento.",
      ler: "Tempos maiores significam varreduras mais lentas e mais energia ao procurar o parceiro.", atencao: "Só os tempos são calculados; a taxa de detecção e de falso alarme exige hardware." },
    { re: /^B3 · rollbacks/, d: "curva-perda", oque: "Quando a troca de modo é validada e falha, os nós voltam ao modo anterior (rollback). Aqui, quantos rollbacks acontecem a cada 100 trocas conforme a perda de quadros aumenta.",
      ler: "Eixo horizontal: perda de quadros no ar. Eixo vertical: rollbacks por 100 trocas. Subir devagar é bom: o protocolo desiste só quando o canal piora de verdade.", atencao: "Um rollback não é erro: é o mecanismo de segurança funcionando." },
    { re: /^B3 · tempo até validar/, d: "curva-perda", oque: "Quanto tempo leva, do início da proposta até o modo novo estar validado, quando há perda de quadros.",
      ler: "Mais perda significa mais retransmissões e mais espera. Linhas altas indicam acordos demorados.", atencao: "O tempo é de relógio simulado dos rádios, incluindo as janelas de espera do protocolo." },
    { re: /^B4/, d: "tabela-linhas", oque: "Injeção de falhas: reinícios no meio da troca, quadros duplicados, perdas de rajada. Cada linha é um tipo de falha e mostra se os dois nós voltaram a concordar.",
      ler: "Procure ‘desacordo’ e ‘rollbacks’: o ideal é o par sempre acabar no mesmo modo, mesmo que isso custe um rollback.", atencao: "Não mostra falhas que o simulador não modela." },
    { re: /^B5/, d: "tabela-linhas", oque: "Um nó novo (ou que reiniciou) precisa encontrar o parceiro. Aqui, quanto tempo leva até os dois estarem conversando, em função do intervalo entre os avisos (beacons).",
      ler: "Avisos mais frequentes encontram o parceiro mais rápido, mas gastam mais energia.", atencao: "Um rádio escutando o tempo todo seria mais rápido e muito mais caro." },
    { re: /^F6/, d: "tabela-linhas", oque: "Uma simulação de vários dias com variação diurna do canal e eventos aleatórios, para ver se a Légua fica estável: quantas trocas de modo e rollbacks por hora.",
      ler: "Poucas trocas e poucos rollbacks por hora indicam um protocolo calmo; muitos indicam oscilação.", atencao: "Trocas demais cansam a rede mesmo que o PDR esteja bom." },
    { re: /^B6/, d: "tabela-linhas", oque: "O mesmo traço de variação do canal é reproduzido em duas situações (‘campo’ e ‘bancada’) para ver se o resultado da bancada prevê o do campo.",
      ler: "Os dois resultados devem ser parecidos; se não forem, a bancada está escondendo algum efeito.", atencao: "A bancada reproduz só o ganho lento do canal, sem o desvanecimento rápido." },
    { re: /^(Quedas ao modo base|Desacordo entre os nós)/, d: "pontos-variantes", oque: "Comparação de variantes do critério para acelerar em dois enlaces difíceis. Cada ponto é um enlace; cada linha, uma variante.",
      ler: "Menos é melhor nos dois gráficos: menos quedas ao modo seguro e menos tempo em desacordo. Uma variante boa precisa ganhar nos dois e não gastar mais energia.", atencao: "Enlaces diferentes preferem variantes diferentes; olhe os dois pontos de cada linha." },
    { re: /^Todas as métricas/, d: "tabela-celula", oque: "As mesmas variantes do F7 com todos os números lado a lado.",
      ler: "Cada linha é uma variante; as colunas são entrega, energia, trocas e rollbacks por hora, quedas e desacordo.", atencao: "Nenhuma variante é melhor em tudo; escolha pelo que importa ao produto." },
    { re: /^Janela de validação: ACKs/, d: "tabela-celula", oque: "Depois de trocar de modo, o par precisa receber k confirmações (ACKs) para o modo novo valer; se falharem f vezes, volta ao modo anterior. Cada linha é um k e cada coluna um f.",
      ler: "Procure as colunas com f = 1: o PDR é parecido, mas os rollbacks por hora sobem, porque um único fracasso desfaz um modo bom. Com f de 3 ou mais os rollbacks caem.", atencao: "Rollback falso é o que o par faz quando o modo era bom, mas ACKs se perderam. Escala rápida é ruidosa demais para este ajuste." },
    { re: /^Janela de validação: duração/, d: "tabela-celula", oque: "Compara janelas de validação de 15, 45 e 90 segundos com k = 3 e f = 3.",
      ler: "Janela de 15 s gera mais rollbacks e PDR menor; 45 s e 90 s dão o mesmo resultado.", atencao: "Dois enlaces e um ambiente." },
    { re: /^Descida por silêncio/, d: "tabela-celula", oque: "Quanto tempo um nó espera sem ouvir o par antes de descer um degrau (linhas), para aplicações que mandam pacotes a cada poucos segundos ou a cada minutos (colunas).",
      ler: "Silêncio curto com aplicação esparsa produz muitas quedas ao modo base sem motivo e o PDR cai. A partir de 90 s as quedas somem.", atencao: "A 3 km o efeito some sob o ruído do enlace marginal." },
    { re: /^Estresse: erro de relógio/, d: "tabela-celula", oque: "Os dois relógios andam separados por até 100 ppm (cada um para um lado) e o cristal pode ser o comum, em vez do compensado. A tabela mostra se a troca de modo combinada no tempo ainda funciona.",
      ler: "Com cristal compensado, de 0 a 100 ppm o resultado é o mesmo: a troca só depende de alguns segundos e os relógios se realinham a cada quadro ouvido. O cristal comum a 28 dBm não entrega nada no modelo, porque o pacote longo esquenta o transmissor e a frequência corre; a 14 dBm funciona.", atencao: "A deriva térmica do cristal comum é estimada, não medida." },
    { re: /^Estresse: perda assimétrica/, d: "tabela-celula", oque: "Acrescenta perda só no sentido B para A, deixando A para B intacto, como acontece com antenas ou potências diferentes.",
      ler: "Quanto maior a perda de um sentido, menos o par acelera (menos trocas por hora), porque a margem vale o pior sentido. O PDR segue alto e a energia por pacote sobe, pois o par fica em modos mais lentos.", atencao: "Dois sentidos com perdas diferentes é só um deslocamento fixo; desvanecimento independente por sentido não foi modelado." },
    { re: /^Estresse: teto de TX × fade_k/, d: "tabela-celula", oque: "Combina o teto de potência com a margem extra proporcional à variabilidade do SNR (fade_k).",
      ler: "Com teto alto, fade_k maior reduz trocas e rollbacks e melhora a entrega, ao custo de mais energia por pacote. Com teto baixo o enlace não acelera de qualquer jeito e fade_k não muda nada.", atencao: "Um ambiente, uma distância e poucas sementes na escala rápida." },
    { re: /^Teto de TX simétrico/, d: "tabela-celula", oque: "Cada linha é uma distância e cada coluna um teto de potência (o máximo que o integrador permite). A célula mostra a entrega e a energia gasta por pacote.",
      ler: "Ande pela linha da esquerda para a direita: o teto sobe, a entrega sobe e a energia pode cair ou subir. ‘Sem enlace’ significa que o teto era baixo demais para essa distância.", atencao: "A posição do mínimo de energia depende da corrente do amplificador, que é estimada." },
    { re: /^Teto assimétrico/, d: "teto-potencia", oque: "Um nó tem sempre 28 dBm e o outro tem o teto da coluna. Mostra o que acontece quando os dois rádios têm potências diferentes.",
      ler: "Compare com a tabela anterior: a entrega se mantém mais, mas a energia por pacote costuma subir bastante, porque o nó mais fraco empurra o par para modos mais lentos.", atencao: "Os dados só vão de A para B, com B respondendo ACK; com tráfego nos dois sentidos o efeito na entrega seria maior." },
    { re: /^Controle de potência/, d: "teto-potencia", oque: "O protocolo pode reduzir a potência quando sobra margem de sinal. A tabela compara ligar e desligar esse controle.",
      ler: "Se as duas colunas são parecidas, o controle de potência rende pouco com este modelo de corrente.", atencao: "Com outra curva de corrente do amplificador o resultado pode mudar." },
    { re: /^Resumo: PDR médio/, d: "tabela-celula", oque: "Resumo da varredura: cada cenário foi repetido com o teto de potência limitado em vários valores. Cada célula é a média do PDR e a mediana da energia das células do cenário.",
      ler: "Se a média cai muito do 28 dBm para o teto menor, o cenário depende de potência sobrando; se quase não cai, o cenário funciona com menos.", atencao: "A média mistura enlaces mortos e saudáveis; a tabela de detalhe abaixo mostra cada célula." },
    { re: /^Detalhe por célula/, d: "tabela-celula", oque: "Cada linha é uma célula do cenário escolhido (por exemplo, uma distância e uma configuração) e as colunas são os tetos de potência.",
      ler: "Troque o cenário no seletor. ‘Sem enlace’ = quase nenhum pacote chegou.", atencao: "Os cenários de bancada já têm tetos fixos baixos e variam pouco." },
    { re: /^Verificação de estados/, d: "estados-formal", oque: "Um verificador testa todas as combinações de estados e de perdas de mensagem do protocolo, num modelo simplificado, para provar propriedades. Cada linha remove ou altera um mecanismo.",
      ler: "‘vale’ é bom, ‘viola’ aponta o mecanismo que protege aquela propriedade. P1: nunca fica em desacordo para sempre. P3: sempre dá para voltar a operar. P4: só vira âncora um modo que o par aceitou.", atencao: "Prova para o modelo, não para o código; a equivalência com o código C é testada à parte." },
    { re: /^Rodada de aceleração/, d: "curva-perda", oque: "Se cada quadro tem uma chance de se perder, qual a probabilidade de a troca de modo dar certo de primeira, passar por um desacordo curto ou desistir.",
      ler: "Quanto maior a perda, maior a fatia de ‘degrada’ e de desacordo transitório.", atencao: "Cálculo de cadeia de Markov com perdas independentes; perdas em rajada são piores." },
    { re: /^Núcleo C × simulador/, d: "equivalencia", oque: "Os dois programas (Python, referência, e C99, o código do produto) recebem os mesmos eventos e geram os mesmos quadros? Um teste compara byte a byte.",
      ler: "Zero divergências em muitos cenários aleatórios e dirigidos indica que o C faz o que o Python especifica.", atencao: "Prova que o C copia o Python, não que o Python descreve a realidade." },
    { re: /^Colisão em estrela/, d: "aloha", oque: "Muitos nós transmitem sem combinar com um receptor central (ALOHA). Quanto mais nós, mais colisões. A curva compara a fórmula teórica com dois simuladores.",
      ler: "As três curvas devem andar juntas: se o simulador concorda com a fórmula e com o de terceiros, a conta de colisão está certa.", atencao: "Pequenas diferenças vêm de regras de colisão específicas de cada simulador." },
    { re: /^Captura/, d: "aloha", oque: "Metade dos nós transmite 10 dB mais forte. Em colisão, o mais forte tende a ser recebido (captura) e o mais fraco se perde.",
      ler: "O PDR dos fortes deve ser maior que o dos fracos nos dois simuladores.", atencao: "Só se testa a regra de 6 dB entre pacotes no mesmo modo." },
    { re: /^Tempo no ar e sensibilidade/, d: "modos", oque: "Confere se os simuladores concordam em duas contas básicas: quanto tempo um pacote fica no ar e qual o sinal mínimo que o rádio consegue demodular.",
      ler: "Diferença zero no tempo no ar é o esperado (a conta é padrão). A sensibilidade difere porque cada fonte usa um chip e uma medição diferentes.", atencao: "A diferença de sensibilidade move os limites de alcance; a bancada deve calibrar." },
    { re: /^(LoRaSim original|Meshtasticator)/, d: "aloha", oque: "O código original de um simulador de terceiros foi executado e comparado com o simulador daqui na mesma situação.",
      ler: "Colunas parecidas significam que as conclusões não dependem do simulador escolhido.", atencao: "Só a camada de rádio foi comparada; o roteamento do Meshtastic não foi." },
    { re: /^B7/, d: "seguranca", oque: "Ataques simulados: reenvio de quadros antigos (replay), quadros inventados (forjados) e interferência dirigida (jammer reativo).",
      ler: "‘Rejeitados’ é bom: quadros do atacante foram descartados sem efeito. O jammer é o caso caro: gasta energia e provoca rollbacks.", atencao: "O MIC usado é de teste; não é segurança de produto." },
    { re: /^B11/, d: "modos", oque: "Um verificador lê o registro de tudo que foi transmitido e confere contra o perfil regulatório (ocupação por canal, canais, potência).",
      ler: "‘Sem violações’ quer dizer que o modelo respeitou o perfil; não é prova de conformidade legal.", atencao: "O perfil BR-2026 vem de fonte secundária e está não verificado." },
    { re: /^Tabela de modos/, d: "modos", oque: "Todos os modos de rádio da biblioteca, do mais rápido ao mais robusto, com o limite de potência de cada um.",
      ler: "O ‘orçamento’ é quanto de atenuação do caminho o modo aguenta (teto de potência menos a sensibilidade). Orçamento maior = alcança mais longe.", atencao: "Valores de sensibilidade vêm de um modelo; a bancada confirma." },
    { re: /^T2\/T3/, d: "estrela-malha", oque: "Um nó central fala com vários nós; um deles tem enlace mais fraco. Compara três políticas: todos concordam (unanimidade), dividir em subgrupos, ou um relay ajuda o mais fraco.",
      ler: "Veja como cada política equilibra entrega do grupo e do membro fraco.", atencao: "Modelo de nível 2, mais simples que o par." },
    { re: /^T4–T6/, d: "estrela-malha", oque: "Malha com vários saltos: a Légua é comparada com modelos de comportamento de outros sistemas de malha.",
      ler: "Compare entrega, energia e atraso em cada topologia.", atencao: "São modelos do comportamento desses sistemas, não os produtos reais." },
    { re: /^Orçamento de tempo/, d: "orcamento-tempo", oque: "Quanto tempo cada cenário leva na escala longa, estimado a partir da escala rápida e comparado com o tempo medido.",
      ler: "Medido/previsto perto de 1 significa que a previsão foi boa.", atencao: "O tempo depende da máquina em que a suíte roda." },
    { re: /^Rápida × longa/, d: "pontos-escalas", oque: "Os mesmos números nas duas escalas lado a lado: a longa tem mais sementes e mais tempo simulado.",
      ler: "Se um ponto muda muito entre as escalas, a escala rápida estava imprecisa naquele caso.", atencao: "A escala rápida é para desenvolvimento; use a longa para conclusões." },
    { re: /^Parâmetros do setup/, d: "estimativa", oque: "Os dados do seu cenário (distância, antena, ambiente, potência) para calcular uma estimativa sem rodar o simulador.",
      ler: "Mude um parâmetro por vez e veja como as tabelas abaixo respondem.", atencao: "É uma conta analítica, mais simples e rápida que a simulação." },
    { re: /^Entrega do receptor × distância/, d: "curva-distancia", oque: "A chance de o receptor entender o pacote conforme a distância, para os modos selecionados.",
      ler: "A distância em que a curva cruza o nível desejado é o alcance daquele modo.", atencao: "Só considera o enlace do rádio, não colisões nem trânsito." },
    { re: /^(Estimativa para o setup|Modos que atingem)/, d: "estimativa", oque: "Resultado da conta analítica para o seu setup: entrega, margem e quais modos atingem a meta de entrega.",
      ler: "A coluna de margem diz quanto sobra de sinal; margem negativa quer dizer que o modo não fecha.", atencao: "Valida contra o simulador de eventos com erro médio de ~1 ponto percentual." },
    { re: /^Estimativa × simulação/, d: "equivalencia", oque: "Compara a conta analítica do site com o simulador completo nos mesmos pontos.",
      ler: "Diferenças pequenas validam o estimador; só a entrega foi validada, não energia nem latência.", atencao: "O estimador não captura trocas de modo nem rollbacks." }
  ];

  // ------------------------------------------------------------------ glossário
  var GLOS = [
    ["PDR", "Taxa de entrega de pacotes: fração dos pacotes enviados que chegaram ao destino. 1,000 = todos."],
    ["SF", "Fator de espalhamento do LoRa (7 a 12). Mais alto alcança mais longe e é mais lento."],
    ["BW", "Largura de banda do canal em kHz (125, 250 ou 500). Mais larga é mais rápida e menos sensível."],
    ["CR", "Taxa de código de correção de erros (4/5 a 4/8): mais redundância, menos velocidade."],
    ["dBm", "Unidade de potência de rádio. 28 dBm é cerca de 0,6 W; a cada 3 dB a potência dobra."],
    ["dB", "Diferença entre duas potências, em escala logarítmica. 10 dB é dez vezes."],
    ["ToA", "Tempo no ar de um pacote (time on air): quanto ele ocupa o canal."],
    ["Modo", "Combinação de SF, BW, CR e salto de frequência usada para transmitir."],
    ["Modo base", "O modo mais robusto, onde os dois nós sempre conseguem se achar. É o ponto de segurança."],
    ["PROPOSE/VOTE/COMMIT", "Os três passos do acordo para trocar de modo: proposta, voto e confirmação."],
    ["Janela de validação", "Período depois da troca em que o par precisa confirmar que o modo novo funciona."],
    ["Âncora", "O último modo confirmado, gravado em memória não volátil para sobreviver a reinícios."],
    ["Rollback", "Voltar ao modo anterior quando o modo novo falha na validação."],
    ["Desacordo", "Tempo em que os dois nós estão em modos diferentes e, portanto, não conseguem conversar."],
    ["Semente", "Número que fixa o sorteio de ruído e sombreamento de uma simulação. Várias sementes dão uma média."],
    ["Escala rápida/longa", "A rápida roda em minutos; a longa tem mais sementes e mais dias simulados."],
    ["mJ/pacote", "Energia de transmissão gasta por pacote entregue, em milijoules."],
    ["Teto de TX", "Potência máxima que o integrador permite. O protocolo nunca passa dele."],
    ["MIC", "Código de autenticação que prova que o quadro veio de um nó com a chave."],
    ["Replay", "Ataque que reenvia um quadro antigo. O contador do quadro impede."],
    ["P1 / P3 / P4", "Propriedades verificadas: sem desacordo permanente, recuperação sempre possível, âncora só de modo confirmado pelo par."],
    ["Captura", "Em colisão, o pacote muito mais forte pode ser recebido mesmo assim."],
    ["ALOHA", "Transmitir sem combinar horário. Simples, mas colide quando há muitos nós."]
  ];
  var TERMS = {};
  GLOS.forEach(function (g) { TERMS[g[0]] = g[1]; });

  // ------------------------------------------------------------------ guia interativo (negociação passo a passo)
  var STEPS = [
    { t: "Os dois nós operam no modo atual", d: "A e B trocam dados e confirmações (ACK) no modo que já funciona. O protocolo mede a margem de sinal o tempo todo.", a: [] },
    { t: "A vê folga e propõe um modo mais rápido", d: "Quando a margem permite e um tempo de espera passou, A envia PROPOSE com o modo candidato.", a: [["A", "B", "PROPOSE (modo X)", S1]] },
    { t: "B vota", d: "B confere se também aguenta o modo X (potência, margem, regras). Responde VOTE sim ou não.", a: [["B", "A", "VOTE: sim", S3]] },
    { t: "A confirma com COMMIT", d: "Se B disse sim, A manda COMMIT com o instante da troca. Se o COMMIT se perder, B não troca e A, sem resposta, desiste: ninguém fica preso.", a: [["A", "B", "COMMIT (troca em t)", S1]], perda: true },
    { t: "Troca no instante combinado e janela de validação", d: "Os dois mudam juntos para o modo X. Nada é gravado ainda: o modo anterior continua como âncora.", a: [["A", "B", "DATA no modo X", S4], ["B", "A", "ACK no modo X", S4]] },
    { t: "Validação", d: "Se os pacotes e confirmações passam num número mínimo de tentativas, o modo X vira âncora (gravado em memória). Se o enlace piorar, é rollback.", a: [], final: true }
  ];

  function seqDiagram(step, perda, falha) {
    var s = STEPS[step], inner = rect(30, 6, 60, 20, "var(--surface)", { s: "var(--text-3)" }) + tx(60, 20, "Nó A", { a: "middle", b: 1 }) +
      rect(270, 6, 60, 20, "var(--surface)", { s: "var(--text-3)" }) + tx(300, 20, "Nó B", { a: "middle", b: 1 }) +
      ln(60, 26, 60, 150, "var(--grid)", 1.5, 1) + ln(300, 26, 300, 150, "var(--grid)", 1.5, 1);
    var upto = STEPS.slice(0, step + 1), y = 44;
    upto.forEach(function (st, i) {
      st.a.forEach(function (ar) {
        var lost = perda && st.perda && ar[2].indexOf("COMMIT") === 0 && i === step;
        var from = ar[0] === "A" ? 62 : 298, to = ar[0] === "A" ? (lost ? 190 : 296) : 66;
        inner += arrow(from, y, to, y + 8, lost ? BAD : ar[3], lost) + tx(180, y - 4, ar[2] + (lost ? "  ✕ perdido" : ""), { a: "middle", c: lost ? BAD : undefined });
        y += 24;
      });
    });
    var H = 168, yb = Math.max(y, 148) + 6;           // faixa de resultado abaixo da última seta, sem cobrir os rótulos
    if (step === STEPS.length - 1) {
      inner += falha ? rect(40, yb, 280, 26, BAD, { op: 0.15, s: BAD }) + tx(180, yb + 17, "enlace piorou: rollback ao modo anterior", { a: "middle", c: BAD, b: 1 }) :
        rect(40, yb, 280, 26, OK, { op: 0.15, s: OK }) + tx(180, yb + 17, "modo X validado: vira âncora", { a: "middle", c: OK, b: 1 });
      H = yb + 34;
    }
    if (perda && step >= 3) {
      var yn = step === STEPS.length - 1 ? H + 6 : 160;
      inner += tx(180, yn, "COMMIT perdido: B continua no modo antigo", { a: "middle", c: BAD }) + tx(180, yn + 14, "e A desiste depois de um tempo", { a: "middle", c: BAD });
      H = yn + 24;
    }
    return wrap(360, H, "Passo " + (step + 1) + " de " + STEPS.length + ": " + s.t, inner);
  }

  var LINKS = [
    ["campo", "O alcance muda com a distância?", "Veja a entrega de cada modo contra a distância e onde a Légua ganha."],
    ["mob", "E se um dos nós se mover?", "A pé, de carro, em rebanho: o que acontece com a entrega e a energia."],
    ["acordo", "A negociação é confiável?", "Rollbacks, perdas de quadro, reinícios e achar o parceiro."],
    ["mecanismos", "Os tempos e contagens do protocolo estão bem escolhidos?", "Varreduras da janela de validação (k, f, duração) e do tempo de silêncio."],
    ["potencia", "E se o rádio tiver menos potência?", "A varredura do teto de TX e o efeito de potências diferentes entre os nós."],
    ["tetos", "O teto de potência afeta todos os cenários?", "A varredura repetida em cada cenário, com resumo e detalhe."],
    ["formal", "Dá para provar que não trava?", "O verificador testa todas as combinações de perdas e reinícios."],
    ["seg", "E se alguém atacar?", "Replay, quadro forjado, jammer e o perfil regulatório."],
    ["validacao", "O simulador é confiável?", "Comparação com o LoRaSim, o Meshtasticator e o código C."],
    ["estimativas", "Quero estimar o meu caso", "Digite a distância e o ambiente e veja os modos que fecham."]
  ];

  function h(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") n.textContent = attrs[k]; else if (k === "class") n.className = attrs[k]; else n.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }
  function svgNode(str) { var w = document.createElement("div"); w.className = "dgm-wrap"; w.innerHTML = str; return w; }

  function guia() {
    var st = { step: 0, perda: false, falha: false };
    var nodes = [];
    nodes.push(h("section", { class: "card guide" }, [
      h("h2", { text: "Comece aqui: o que é a Légua e como ler este site" }),
      h("p", { text: "Dois rádios LoRa conversam sem rede por trás (ponto a ponto). O mesmo par pode usar vários modos: alguns são rápidos e curtos, outros lentos e longos. A Légua faz os dois rádios combinarem entre si, no meio do caminho, qual modo usar, e volta ao modo seguro se a troca der errado." }),
      h("p", { class: "note", text: "Tudo aqui vem de simulação com parâmetros estimados. Serve para comparar opções e dimensionar, não para prever o campo. Ainda não há medição com as placas." }),
      svgNode(DG["modos"]())
    ]));
    // negociação interativa
    var host = h("div", { class: "guide-demo" }), title = h("h3"), desc = h("p"), pic = h("div"), ctr = h("div", { class: "controls" });
    function redraw() {
      var s = STEPS[st.step];
      title.textContent = "Passo " + (st.step + 1) + " de " + STEPS.length + " · " + s.t;
      desc.textContent = s.d + (s.final ? (st.falha ? " Aqui o enlace piorou na janela: rollback, e o modo antigo continua como âncora." : " Aqui deu certo: o modo novo vira âncora.") : "");
      pic.textContent = ""; pic.appendChild(svgNode(seqDiagram(st.step, st.perda, st.falha)));
      prev.disabled = st.step === 0; next.disabled = st.step === STEPS.length - 1;
      cbP.parentNode.style.display = "inline-flex"; cbF.parentNode.style.display = st.step === STEPS.length - 1 ? "inline-flex" : "none";
    }
    var prev = h("button", { class: "btn", type: "button", text: "← Voltar" }), next = h("button", { class: "btn", type: "button", text: "Próximo passo →" }), rst = h("button", { class: "btn", type: "button", text: "Reiniciar" });
    var cbP = h("input", { type: "checkbox" }), cbF = h("input", { type: "checkbox" });
    prev.addEventListener("click", function () { st.step = Math.max(0, st.step - 1); redraw(); });
    next.addEventListener("click", function () { st.step = Math.min(STEPS.length - 1, st.step + 1); redraw(); });
    rst.addEventListener("click", function () { st.step = 0; redraw(); });
    cbP.addEventListener("change", function () { st.perda = cbP.checked; redraw(); });
    cbF.addEventListener("change", function () { st.falha = cbF.checked; redraw(); });
    [prev, next, rst, h("label", { class: "chk" }, [cbP, document.createTextNode(" perder o COMMIT")]), h("label", { class: "chk" }, [cbF, document.createTextNode(" enlace piora na validação")])].forEach(function (n) { ctr.appendChild(n); });
    [title, desc, pic, ctr].forEach(function (n) { host.appendChild(n); });
    nodes.push(h("section", { class: "card guide" }, [h("h2", { text: "Como dois rádios trocam de modo, passo a passo" }), h("p", { class: "note", text: "Use os botões para avançar. Marque as opções para ver o que acontece quando um quadro se perde ou o enlace piora." }), host]));
    redraw();
    // perguntas
    var grid = h("div", { class: "qgrid" });
    LINKS.forEach(function (l) {
      var b = h("button", { class: "qcard", type: "button" }, [h("b", { text: l[1] }), h("span", { text: l[2] })]);
      b.addEventListener("click", function () { document.dispatchEvent(new CustomEvent("legua:ir", { detail: l[0] })); });
      grid.appendChild(b);
    });
    nodes.push(h("section", { class: "card guide" }, [h("h2", { text: "Perguntas que o site responde" }), grid]));
    // glossário
    var gl = h("section", { class: "card guide" }, [h("h2", { text: "Glossário" })]), box = h("input", { type: "search", placeholder: "Filtrar termos…", "aria-label": "Filtrar termos do glossário", class: "gfilter" });
    var dl = h("dl", { class: "gloss" });
    function fill(q) {
      dl.textContent = ""; q = (q || "").toLowerCase();
      GLOS.filter(function (g) { return !q || (g[0] + " " + g[1]).toLowerCase().indexOf(q) >= 0; }).forEach(function (g) { dl.appendChild(h("dt", { text: g[0] })); dl.appendChild(h("dd", { text: g[1] })); });
    }
    box.addEventListener("input", function () { fill(box.value); });
    gl.appendChild(box); gl.appendChild(dl); fill("");
    nodes.push(gl);
    return nodes;
  }

  // ------------------------------------------------------------------ anotação dos cartões
  function anotar(panel) {
    panel.querySelectorAll(".card").forEach(function (c) {
      if (c.classList.contains("disc") || c.classList.contains("guide") || c.querySelector(".expl")) return;
      var hh = c.querySelector("h2"); if (!hh) return;
      var title = hh.textContent, e = null;
      for (var i = 0; i < EX.length; i++) if (EX[i].re.test(title)) { e = EX[i]; break; }
      if (!e) return;
      var tipo = c.querySelector("svg") ? "gráfico" : "tabela";
      var det = h("details", { class: "expl" });
      det.open = true;
      det.appendChild(h("summary", { text: "Entenda este " + tipo }));
      var body = h("div", { class: "expl-body" });
      body.appendChild(h("p", {}, [h("b", { text: "O que é: " }), document.createTextNode(e.oque)]));
      body.appendChild(h("p", {}, [h("b", { text: "Como ler: " }), document.createTextNode(e.ler)]));
      if (e.atencao) body.appendChild(h("p", { class: "att" }, [h("b", { text: "Cuidado: " }), document.createTextNode(e.atencao)]));
      if (DG[e.d]) body.appendChild(svgNode(DG[e.d]()));
      det.appendChild(body);
      var after = c.querySelector(".card-head") || c.querySelector(".note") || hh;      // sempre como filho direto do cartão
      while (after.parentNode !== c) after = after.parentNode;
      c.insertBefore(det, after.nextSibling);
    });
    // dicas nos cabeçalhos de tabela e rótulos
    panel.querySelectorAll("th").forEach(function (t) {
      var k = t.textContent.trim();
      Object.keys(TERMS).forEach(function (term) { if (!t.title && (k === term || k.indexOf(term + " ") === 0 || k.indexOf(term + "/") === 0)) t.title = TERMS[term]; });
    });
  }

  window.LeguaExplica = { guia: guia, anotar: anotar, diagramas: DG, explicacoes: EX, glossario: GLOS };
})();
