/* Aba "Pacotes": decodificador e gerador de quadros da Légua v0 (pacote.js). Tudo local; o MIC conferido é o de teste. */
(function (root) {
  "use strict";
  var doc = root.document, S = { hex: "", ctr: "", extra: "", tipo: 2, src: 1, dst: 2, ctr32: 70000, ackreq: true, frag: false, key: 0, corpo: "" };

  function el(tag, attrs, kids) {
    var e = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(typeof c === "string" ? doc.createTextNode(c) : c); });
    return e;
  }
  var DICAS = { 1: "flags, speed, cap, reservado (4 B)", 2: "seq, dflags, speed, payload de 9 B (12 B)", 3: "seq, gain (2 B)", 4: "cand, speed, cap, reservado (4 B)", 5: "cand, yes, speed, cap (4 B)", 6: "cand, delay_ms (2 B), speed (4 B)", 7: "nonce (4 B)", 8: "ctr32 do respondente (4 B)" };

  function tabela(linhas) {
    var t = el("table"), th = el("thead", {}, [el("tr", {}, ["Campo", "Valor", "Significado"].map(function (h) { return el("th", { text: h }); }))]), tb = el("tbody");
    linhas.forEach(function (l) { tb.appendChild(el("tr", {}, [el("td", { text: l.campo }), el("td", { "class": "n", text: String(l.valor) }), el("td", { text: l.nota || "" })])); });
    t.appendChild(th); t.appendChild(tb); return el("div", { "class": "tbl-wrap", style: "overflow-x:auto" }, [t]);
  }
  function pill(tipo, txt) { return el("span", { "class": "pill " + tipo, text: txt }); }

  function painel(panel, DATA) {
    var P = root.LeguaPacote; panel.textContent = "";
    var out1 = el("div"), out2 = el("div");
    function campo(rot, chave, tipo, extra) {
      var inp = tipo === "area" ? el("textarea", { rows: "3", style: "width:100%;font:13px monospace", spellcheck: "false" }) : el("input", { type: tipo || "text", autocomplete: "off", spellcheck: "false" });
      if (tipo === "checkbox") inp.checked = !!S[chave]; else inp.value = S[chave];
      inp.setAttribute("aria-label", rot);
      inp.addEventListener(tipo === "checkbox" || tipo === "select" ? "change" : "input", function () { S[chave] = tipo === "checkbox" ? inp.checked : inp.value; (extra || decodifica)(); });
      return el("label", { "class": "field", style: tipo === "area" ? "grid-column:1/-1" : "" }, [el("span", { text: rot }), inp]);
    }
    function num(v) { var n = parseInt(String(v).trim(), String(v).trim().toLowerCase().indexOf("0x") === 0 ? 16 : 10); return isFinite(n) ? n : null; }
    function decodifica() {
      out1.textContent = "";
      if (!S.hex.trim()) { out1.appendChild(el("p", { "class": "note", text: "Cole um quadro em hexadecimal (com ou sem espaços) ou use um exemplo." })); return; }
      var r = P.decodificar(S.hex, { ctr32: num(S.ctr), extraHex: S.extra });
      if (r.erro) { out1.appendChild(el("p", {}, [pill("bad", "não decodificou"), " " + r.erro])); return; }
      out1.appendChild(el("p", {}, [pill("ok", r.nome), " " + r.tamanho + " bytes. ", r.mic.confere_com_mic_de_teste ? pill("ok", "MIC de teste confere") : pill("warn", "MIC de teste não confere")]));
      r.avisos.forEach(function (a) { out1.appendChild(el("p", { "class": "note", text: "Atenção: " + a })); });
      out1.appendChild(tabela(r.cabecalho.concat(r.corpo)));
      out1.appendChild(el("p", { "class": "note", text: "MIC lido " + r.mic.lido + "; calculado com a chave de teste " + r.mic.calculado_teste + ". " + r.mic.nota }));
    }
    function gera() {
      out2.textContent = "";
      var t = S.tipo | 0, n = P.TAMANHO_CORPO[t], b = P.hexParaBytes(S.corpo || new Array(n + 1).join("00"));
      if (b.erro) { out2.appendChild(el("p", {}, [pill("bad", "corpo inválido"), " " + b.erro])); return; }
      var g = P.montar({ tipo: t, src: num(S.src) || 0, dst: num(S.dst) || 0, ctr32: num(S.ctr32) || 0, flags: (S.ackreq ? 1 : 0) | (S.frag ? 2 : 0) | ((num(S.key) & 3) << 2), corpo: b.bytes, extraHex: t === 8 ? S.extra : "" });
      if (g.erro) { out2.appendChild(el("p", {}, [pill("bad", "não montou"), " " + g.erro])); return; }
      var ta = el("textarea", { readonly: "readonly", rows: "2", style: "width:100%;font:13px monospace", "aria-label": "Quadro gerado em hexadecimal" }); ta.value = g.hex;
      var bt = el("button", { type: "button", "class": "btn", text: "Decodificar este quadro" }); bt.addEventListener("click", function () { S.hex = g.hex; S.ctr = String(num(S.ctr32) || 0); painel(panel, DATA); });
      out2.appendChild(el("p", { "class": "note", text: "Quadro de " + g.bytes.length + " bytes, com o MIC de teste (não é segurança)." })); out2.appendChild(ta); out2.appendChild(bt);
    }
    var ex = el("div", { style: "display:flex;gap:8px;flex-wrap:wrap" });
    [["Exemplo: DATA", { tipo: 2, src: 1, dst: 2, ctr32: 70000, flags: 1, corpo: [5, 0x24, 4, 1, 2, 3, 4, 5, 6, 7, 8, 9] }], ["Exemplo: COMMIT", { tipo: 6, src: 2, dst: 1, ctr32: 300, flags: 0, corpo: [0x4C, 0x07, 0xD0, 0] }],
      ["Exemplo: HELLO", { tipo: 1, src: 1, dst: 65535, ctr32: 1, flags: 0, corpo: [0, 0, 37, 0] }]].forEach(function (e) {
      var b = el("button", { type: "button", "class": "btn", text: e[0] }); b.addEventListener("click", function () { var g = P.montar(e[1]); S.hex = g.hex; S.ctr = String(e[1].ctr32); S.extra = ""; painel(panel, DATA); }); ex.appendChild(b);
    });
    var c1 = el("section", { "class": "card" }, [el("h2", { text: "Decodificar um quadro" }), el("p", { "class": "note", text: "Cole os bytes do quadro (o que o rádio recebeu). O cabeçalho e o corpo são explicados campo a campo, conforme o docs/07. O contador completo (ctr32) é opcional: sem ele vale o de 16 bits do cabeçalho." }),
      el("div", { "class": "form" }, [campo("Quadro em hexadecimal", "hex", "area"), campo("ctr32 (opcional)", "ctr", "text"), campo("Dado extra do MIC (nonce do RESYNC_RSP, hex)", "extra", "text")]), ex, out1]);
    var tipos = Object.keys(P.TIPOS).map(function (k) { return el("option", { value: k, text: k + " " + P.TIPOS[k] }); });
    var sel = el("select", { "aria-label": "Tipo do quadro" }); tipos.forEach(function (o) { if (+o.value === +S.tipo) o.selected = true; sel.appendChild(o); });
    var dica = el("p", { "class": "sub" });
    function dicaTxt() { dica.textContent = "Corpo de " + P.TAMANHO_CORPO[S.tipo | 0] + " B: " + DICAS[S.tipo | 0] + ". Em branco = zeros."; }
    sel.addEventListener("change", function () { S.tipo = +sel.value; S.corpo = ""; dicaTxt(); gera(); });
    dicaTxt();
    var c2 = el("section", { "class": "card" }, [el("h2", { text: "Gerar um quadro de teste" }), el("p", { "class": "note", text: "Monta um quadro v0 com o MIC de teste, igual ao que os vetores e a simulação usam. Serve para testar um decodificador ou uma porta do protocolo; não use em produto." }),
      el("div", { "class": "form" }, [el("label", { "class": "field" }, [el("span", { text: "Tipo" }), sel]), campo("src (número ou 0x…)", "src", "text", gera), campo("dst (65535 = broadcast)", "dst", "text", gera), campo("ctr32", "ctr32", "text", gera),
        campo("ACKREQ", "ackreq", "checkbox", gera), campo("FRAG", "frag", "checkbox", gera), campo("key_id (0 a 3)", "key", "text", gera), campo("Corpo em hexadecimal", "corpo", "text", gera), campo("Dado extra do MIC (RESYNC_RSP)", "extra", "text", gera)]), dica, out2]);
    var c3 = el("section", { "class": "card" }, [el("h2", { text: "Vetores de teste para quem porta o protocolo" }),
      el("p", { "class": "note", text: "O núcleo C e o simulador geram e conferem os mesmos vetores byte a byte. Quem implementa a Légua em outra linguagem deve reproduzi-los. Formato: uma linha por quadro, `<ctr32> <hex> [<dado extra do MIC>]`; chave de teste 00..0f." }),
      el("p", {}, [el("a", { "class": "btn", href: "vetores/frames.txt", download: "frames.txt", text: "Baixar frames.txt (48 quadros)" }), " ", el("a", { "class": "btn", href: "vetores/mic.txt", download: "mic.txt", text: "Baixar mic.txt (AES-CMAC)" })]),
      el("p", { "class": "note", text: "Nunca digite a chave real de um enlace em uma página da web. Para conferir um MIC de produção use `core/src/mic_cmac.c` ou `simsuite/protocol/mic.py` na sua máquina." })]);
    [c1, c2, c3].forEach(function (c) { panel.appendChild(c); });
    decodifica(); gera();
  }
  root.LeguaPacoteUI = { painel: painel, estado: S };
})(typeof window !== "undefined" ? window : this);
