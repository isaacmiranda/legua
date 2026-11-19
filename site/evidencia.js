/* Nível de evidência de cada seção: o que sustenta os números. Sem medição em hardware, nenhuma seção chega ao nível 3.
 * Níveis: 0 simulação com parâmetros estimados; 1 conferido por teste ou verificação do próprio projeto; 2 conferido contra
 * outro simulador ou modelo independente; 3 medido em hardware (ainda não existe). */
(function (root) {
  "use strict";
  var NIVEIS = [
    "Simulação com parâmetros estimados (canal, corrente do PA, deriva).",
    "Conferido por testes ou verificação do próprio projeto.",
    "Conferido contra outro simulador ou modelo independente.",
    "Medido em hardware (ainda não existe nenhuma medição)."
  ];
  /* id da aba -> { nivel (o mais alto atingido, 0 a 2), itens: [texto curto], ref } */
  var POR_ABA = {
    campo: { nivel: 1, itens: ["Protocolo igual no núcleo C e no simulador (equivalência byte a byte)", "Canal e consumo estimados"], ref: "docs/09 §8" },
    mob: { nivel: 1, itens: ["Protocolo igual no núcleo C e no simulador", "Mobilidade e Doppler estimados"], ref: "docs/09 §8" },
    alcance: { nivel: 2, itens: ["Tempo no ar e sensibilidade conferidos contra LoRaSim e Meshtasticator", "Atenuação do canal estimada"], ref: "docs/09 §9.1" },
    potencia: { nivel: 0, itens: ["Varredura do simulador; corrente do PA estimada"], ref: "docs/09" },
    tetos: { nivel: 0, itens: ["Varredura do simulador; sem comparação externa"], ref: "docs/09" },
    malha: { nivel: 2, itens: ["Camada física conferida contra LoRaSim e Meshtasticator (originais executados)", "Roteamento por inundação não comparado (decisão de escopo)"], ref: "docs/09 §9.1" },
    acordo: { nivel: 1, itens: ["Propriedades P1, P3 e P4 verificadas por busca exaustiva de estados", "Falhas simuladas, não medidas"], ref: "docs/06" },
    mecanismos: { nivel: 0, itens: ["Varreduras do simulador; ajuste com parâmetros estimados"], ref: "docs/09" },
    sintonia: { nivel: 0, itens: ["Sintonia por simulação; os perfis valem até a bancada medir"], ref: "docs/09" },
    formal: { nivel: 1, itens: ["Verificação de estados do modelo do protocolo (não do código C)"], ref: "docs/06" },
    validacao: { nivel: 2, itens: ["Comparação com LoRaSim e Meshtasticator (originais executados)", "Equivalência Py×C em 4 pares"], ref: "docs/09 §9" },
    seg: { nivel: 1, itens: ["Vetores de teste do AES-CMAC e testes de replay e forjamento", "Regulação BR-2026: fonte secundária, nao_verificado"], ref: "docs/07 §6" },
    estimativas: { nivel: 1, itens: ["Estimador conferido contra o simulador (tools/validar_estimador.py)", "Parâmetros do canal estimados"], ref: "docs/09 §7" },
    calc: { nivel: 1, itens: ["Tempo no ar idêntico ao do simulador (teste de paridade com 960 combinações)", "Consumo, sensibilidade e perfil BR-2026 estimados ou de fonte secundária"], ref: "docs/09 §4" },
    modos: { nivel: 1, itens: ["Tabela de modos conferida pelos testes de tempo no ar", "Perfil BR-2026: nao_verificado"], ref: "docs/05" },
    enlace: { nivel: 2, itens: ["Difração pela ITU-R P.526-16, comparada com o ITM da NTIA em 44 perfis (testador ~11 dB otimista em média)", "Sem medição de campo"], ref: "docs/09 §7.1" }
  };
  var COR = ["warn", "ok", "ok", "ok"];

  function el(tag, attrs, kids) {
    var e = root.document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(c); });
    return e;
  }
  /* faixa de evidência da seção; null para seções sem entrada */
  function faixa(id) {
    var s = POR_ABA[id];
    if (!s) return null;
    var f = el("details", { "class": "evidencia sem-impressao", style: "margin:0 0 12px;font-size:13px" });
    var sum = el("summary", { style: "cursor:pointer" });
    sum.appendChild(el("b", { text: "Evidência: nível " + s.nivel + " de 3. " }));
    sum.appendChild(el("span", { "class": "sub", text: NIVEIS[s.nivel] + " Nenhuma medição em hardware." }));
    f.appendChild(sum);
    var ul = el("ul", { style: "margin:6px 0 0;padding-left:20px" });
    s.itens.forEach(function (t) { ul.appendChild(el("li", { text: t })); });
    f.appendChild(ul);
    var leg = el("ol", { start: "0", style: "margin:6px 0 0;padding-left:20px;color:var(--text-2)" });
    NIVEIS.forEach(function (t, i) { leg.appendChild(el("li", { text: t, style: i === s.nivel ? "font-weight:600;color:var(--text)" : "" })); });
    f.appendChild(leg);
    f.appendChild(el("p", { "class": "sub", style: "margin:6px 0 0", text: "Detalhes e limites: " + s.ref + ". Resultados de simulação servem para comparar e dimensionar, não para prever o campo." }));
    return f;
  }
  var api = { NIVEIS: NIVEIS, POR_ABA: POR_ABA, faixa: faixa };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LeguaEvidencia = api;
})(typeof window !== "undefined" ? window : this);
