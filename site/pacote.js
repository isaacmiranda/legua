/* Decodificador e gerador de pacotes da Légua v0 (docs/07), sem DOM. Referência: simsuite/protocol/wire.py e
 * core/src/frame.c; teste de paridade em simsuite/tests/test_ferramentas_site.py. O MIC conferido aqui é o MIC de TESTE
 * (FNV-1a de 32 bits com a chave de teste 00..0f): não é segurança. O MIC real (AES-128-CMAC) exige a chave do enlace, e a
 * chave nunca deve ser digitada numa página: confira com `core/src/mic_cmac.c` ou `simsuite/protocol/mic.py`. */
(function (root) {
  "use strict";
  var T = { 1: "HELLO", 2: "DATA", 3: "ACK", 4: "PROPOSE", 5: "VOTE", 6: "COMMIT", 7: "RESYNC", 8: "RESYNC_RSP" };
  var BODY = { 1: 4, 2: 12, 3: 2, 4: 4, 5: 4, 6: 4, 7: 4, 8: 4 }, HDR = 8, MIC = 4, BROADCAST = 0xFFFF;
  var TEST_KEY = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
  var BW = { 0: 125, 1: 250, 2: 500 };

  function hexParaBytes(txt) {
    var t = String(txt || "").replace(/0x/gi, "").replace(/[^0-9a-fA-F]/g, "");
    if (!t.length) return { erro: "cole o quadro em hexadecimal (por exemplo 22 00 00 01 …)" };
    if (t.length % 2) return { erro: "número ímpar de dígitos hexadecimais (" + t.length + ")" };
    var b = [], i; for (i = 0; i < t.length; i += 2) b.push(parseInt(t.substr(i, 2), 16));
    return { bytes: b };
  }
  function bytesParaHex(b) { return b.map(function (x) { return ("0" + (x & 255).toString(16)).slice(-2); }).join(""); }
  function u16(b, i) { return (b[i] << 8) | b[i + 1]; }
  function u32(b, i) { return ((b[i] << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3]) >>> 0; }
  function be(n, k) { var o = [], i; for (i = k - 1; i >= 0; i--) o.push(Math.floor(n / Math.pow(256, i)) & 255); return o; }

  /* MIC de teste: FNV-1a 32 bits sobre chave || src(2) || ctr32(4) || dados */
  function testMic(key, src, ctr32, dados) {
    var h = 0x811C9DC5 >>> 0, seq = key.concat(be(src, 2), be(ctr32, 4), dados), i;
    for (i = 0; i < seq.length; i++) { h = (h ^ seq[i]) >>> 0; h = Math.imul(h, 0x01000193) >>> 0; }
    return h >>> 0;
  }
  function modo(b) {
    var bw = (b >> 3) & 3; if (!(bw in BW)) return { id: b, texto: "código de largura de banda inválido" };
    var sf = ((b >> 5) & 7) + 5, cr = ((b >> 1) & 3) + 1, fh = !!(b & 1);
    return { id: b, sf: sf, bw: BW[bw], cr: cr, fhss: fh, texto: "SF" + sf + "/" + BW[bw] + (cr > 1 ? "/CR4" + (cr + 4) : "") + (fh ? "/FH" : "") };
  }
  function capDbm(c) { return { codigo: c, dbm: c - 9 }; }

  function corpo(tipo, b) {
    var c = [];
    function add(nome, valor, nota) { c.push({ campo: nome, valor: valor, nota: nota || "" }); }
    if (tipo === 2) {
      var dfl = b[1];
      add("seq", b[0]); add("dflags", "0x" + ("0" + dfl.toString(16)).slice(-2), "VAL=" + (dfl & 1) + ", HB=" + ((dfl >> 1) & 1) + ", potência " + (((dfl >> 2) & 63) - 9) + " dBm (código " + ((dfl >> 2) & 63) + ")");
      add("speed", b[2], (b[2] * 0.5) + " m/s"); add("payload (9 B)", bytesParaHex(b.slice(3)));
    } else if (tipo === 3) {
      add("seq", b[0]); add("gain", b[1], b[1] === 255 ? "desconhecido" : "ganho " + (-60 - b[1] * 0.5) + " dB");
    } else if (tipo === 1) {
      add("flags", b[0], "REPLY=" + (b[0] & 1)); add("speed", b[1], (b[1] * 0.5) + " m/s"); add("cap", b[2], capDbm(b[2]).dbm + " dBm"); add("reservado", b[3], b[3] ? "deveria ser 0" : "");
    } else if (tipo === 4) {
      add("cand", b[0], modo(b[0]).texto); add("speed", b[1], (b[1] * 0.5) + " m/s"); add("cap", b[2], capDbm(b[2]).dbm + " dBm"); add("reservado", b[3], b[3] ? "deveria ser 0" : "");
    } else if (tipo === 5) {
      add("cand", b[0], modo(b[0]).texto); add("yes", b[1], b[1] ? "sim" : "não"); add("speed", b[2], (b[2] * 0.5) + " m/s"); add("cap", b[3], capDbm(b[3]).dbm + " dBm");
    } else if (tipo === 6) {
      add("cand", b[0], modo(b[0]).texto); add("delay_ms", u16(b, 1), "relativo ao fim da transmissão do COMMIT"); add("speed", b[3], (b[3] * 0.5) + " m/s");
    } else if (tipo === 7) {
      add("nonce", "0x" + ("00000000" + u32(b, 0).toString(16)).slice(-8), "aleatório, do pedinte");
    } else if (tipo === 8) {
      add("ctr32", u32(b, 0), "contador completo de TX do respondente; o nonce do pedido entra só no MIC");
    }
    return c;
  }

  /* Decodifica o quadro. op: { ctr32 (contador completo, se souber; padrão = ctr16), extraHex (nonce do RESYNC_RSP) }.
   * Devolve { erro } ou { tipo, nome, cabecalho{...}, corpo[...], mic{...}, avisos[] }. */
  function decodificar(hex, op) {
    op = op || {};
    var h = hexParaBytes(hex); if (h.erro) return { erro: h.erro };
    var b = h.bytes, avisos = [];
    if (b.length < HDR + MIC) return { erro: "quadro curto demais: " + b.length + " bytes (o mínimo é " + (HDR + MIC) + ")" };
    var ver = b[0] >> 5, tipo = b[0] & 31;
    if (ver !== 0) return { erro: "versão " + ver + " não suportada (esta é a v0)" };
    if (!(tipo in T)) return { erro: "tipo " + tipo + " desconhecido (os tipos vão de 1 a 8)" };
    var esperado = HDR + BODY[tipo] + MIC;
    if (b.length !== esperado) return { erro: T[tipo] + " tem " + esperado + " bytes, mas o quadro tem " + b.length };
    if (b[1] & 0xF0) avisos.push("bits reservados das flags diferentes de zero (0x" + (b[1] & 0xF0).toString(16) + "): o núcleo recusa este quadro");
    var src = u16(b, 2), dst = u16(b, 4), c16 = u16(b, 6), ctr = op.ctr32 != null && isFinite(op.ctr32) ? (op.ctr32 >>> 0) : c16;
    var b8 = b.slice(HDR, b.length - MIC), micLido = u32(b, b.length - MIC), extra = [], micOk = null;
    if (tipo === 8) { ctr = u32(b8, 0); if ((ctr & 0xFFFF) !== c16) avisos.push("os 16 bits baixos do ctr32 do corpo (" + (ctr & 0xFFFF) + ") não batem com o contador do cabeçalho (" + c16 + ")"); }
    else if (op.ctr32 != null && isFinite(op.ctr32) && ((op.ctr32 & 0xFFFF) !== c16)) avisos.push("o ctr32 informado não bate com os 16 bits do cabeçalho (" + c16 + ")");
    if (op.extraHex) { var e = hexParaBytes(op.extraHex); if (e.erro) return { erro: "dado extra do MIC: " + e.erro }; extra = e.bytes; }
    if (tipo === 8 && !extra.length) avisos.push("RESYNC_RSP: o MIC inclui o nonce do pedido, que não vai no ar; informe-o para conferir o MIC");
    var micCalc = testMic(TEST_KEY, src, ctr, b.slice(0, b.length - MIC).concat(extra));
    micOk = micCalc === micLido;
    return { tipo: tipo, nome: T[tipo], tamanho: b.length, avisos: avisos,
      cabecalho: [{ campo: "versão", valor: ver }, { campo: "tipo", valor: tipo, nota: T[tipo] },
        { campo: "flags", valor: "0x" + ("0" + b[1].toString(16)).slice(-2), nota: "ACKREQ=" + (b[1] & 1) + ", FRAG=" + ((b[1] >> 1) & 1) + ", key_id=" + ((b[1] >> 2) & 3) },
        { campo: "src", valor: src }, { campo: "dst", valor: dst, nota: dst === BROADCAST ? "broadcast" : "" }, { campo: "ctr16", valor: c16 }],
      corpo: corpo(tipo, b8),
      mic: { lido: "0x" + ("00000000" + micLido.toString(16)).slice(-8), calculado_teste: "0x" + ("00000000" + micCalc.toString(16)).slice(-8), confere_com_mic_de_teste: micOk,
        nota: "MIC de teste (FNV-1a, chave 00..0f), usado nos vetores e na simulação. Não é segurança; com AES-CMAC real este valor não vai bater." } };
  }

  /* Monta um quadro de teste. c: { tipo, src, dst, ctr32, flags, corpo: [bytes] , extraHex } -> { hex, bytes } | { erro } */
  function montar(c) {
    var t = c.tipo | 0;
    if (!(t in T)) return { erro: "tipo inválido" };
    var cb = c.corpo || [];
    if (cb.length !== BODY[t]) return { erro: T[t] + " leva " + BODY[t] + " bytes de corpo (recebeu " + cb.length + ")" };
    if ((c.flags | 0) & 0xF0) return { erro: "os bits 4 a 7 das flags são reservados" };
    var ctr = (c.ctr32 || 0) >>> 0, extra = c.extraHex ? hexParaBytes(c.extraHex) : { bytes: [] };
    if (extra.erro) return { erro: extra.erro };
    var cab = [t & 31, (c.flags | 0) & 255].concat(be(c.src | 0, 2), be(c.dst | 0, 2), be(ctr & 0xFFFF, 2)), dados = cab.concat(cb.map(function (x) { return x & 255; }));
    var mic = testMic(TEST_KEY, c.src | 0, ctr, dados.concat(extra.bytes)), fr = dados.concat(be(mic, 4));
    return { bytes: fr, hex: bytesParaHex(fr) };
  }

  var api = { decodificar: decodificar, montar: montar, hexParaBytes: hexParaBytes, bytesParaHex: bytesParaHex, testMic: testMic, modo: modo, TIPOS: T, TAMANHO_CORPO: BODY };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaPacote = api;
})(typeof window !== "undefined" ? window : this);
