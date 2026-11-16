# Rascunho de artigo técnico (v0, 16/11/2026)

> **Estado:** rascunho de estrutura e de argumento, não um manuscrito. Os números de simulação **não são copiados
> aqui** para não divergirem: a fonte é a página consolidada
> (<https://isaacmiranda.github.io/legua/consolidado.html>, gerada por `tools/build_consolidado.py` a partir de
> `simsuite/results_full/`). Cada afirmação abaixo marca de onde vem. Referências bibliográficas: as de `docs/02` e
> `docs/05`; **nenhuma foi relida para este rascunho**, confira cada uma antes de submeter. Resultados são de
> simulação com parâmetros estimados; não são previsão de campo (CLAUDE.md).

## Título provisório

**Acordo, validação, âncora e rollback na adaptação de modo de enlaces LoRa ponto a ponto: especificação, verificação
formal e avaliação por simulação**

## Resumo (esboço)

Enlaces LoRa ponto a ponto sem LoRaWAN precisam trocar SF, largura de banda, CR e potência quando o canal muda, e a
troca é um problema de acordo entre dois nós sobre um canal com perdas assimétricas. Apresentamos a Légua, um
protocolo de adaptação de modo com negociação explícita (PROPOSE/VOTE/COMMIT), troca em instante combinado, janela
de validação, âncora em memória não volátil só depois da validação e rollback. O protocolo é especificado em
um quadro de controle de 16 B, implementado em Python (referência) e em C99 sem alocação dinâmica, e verificado: um
verificador de estados explícitos cobre as propriedades de ausência de desacordo permanente (P1), recuperação (P3)
e âncora confirmada pelo par (P4), com ablações que mostram qual mecanismo sustenta qual propriedade; o núcleo C é
equivalente ao simulador em rastros byte a byte nos quatro pares Python/C. A avaliação por simulação cobre
bancada, campo urbano e rural, mobilidade e malha, e o simulador é comparado com o LoRaSim e o Meshtasticator
(código original executado). **Não há medição em hardware:** a calibração depende de um trabalho de bancada
separado.

## 1. Introdução

- Problema: adaptar modo em P2P LoRa. ADR do LoRaWAN depende de servidor e é lento (docs/02, seção sobre ADR).
- Lacuna: a literatura adapta o SF sem acordo, ou agenda o encontro mas fixa o modo (docs/02, tabela de trabalhos
  próximos). **Cuidado:** não alegar novidade que a literatura já cobre; a contribuição defensável é o conjunto
  acordo + validação + âncora + rollback com verificação formal, dentro de um envelope regulatório executável
  (docs/05). Há patentes de título próximo (docs/02); a análise de anterioridade é de busca, não jurídica.
- Contribuições: (1) protocolo e quadro de 16 B (docs/07); (2) verificação formal com ablações (docs/06, aba
  Verificação formal); (3) núcleo C equivalente ao simulador, com testes diferenciais (docs/09 §8); (4) avaliação por
  simulação com escala rápida e longa, e validação cruzada com dois simuladores de terceiros (docs/09 §9).

## 2. Protocolo

- Máquina de estados: BASE, DATA, NEG, PEND, VALID, RECOV (docs/03, docs/07). Modo base como canal de controle comum.
- Negociação em três mensagens; COMMIT leva um atraso relativo ao fim da transmissão.
- Validação: o modo novo só vira âncora depois de *k* ACKs numa janela; falha provoca rollback ao modo anterior.
- Descida por silêncio, escada de degradação, controle de potência, alarme de rollbacks repetidos, congelamento em
  mobilidade (docs/06 itens 1–10).
- Segurança: MIC de 4 B por quadro, contador anti-replay em NVM por blocos (piso do par por bloco de 64). Insumos da
  escolha do algoritmo em docs/07 §6.

## 3. Verificação formal

- Modelo abstrato, perdas adversárias e assimétricas, reinício não determinístico, voto "não" arbitrário.
- Propriedades: P1, P2 (limite do desacordo transitório), P3, P4 (com variável fantasma de histórico de modos).
- **Resultado central (fonte: aba Verificação formal, escala longa):** a referência satisfaz P1, P3 e P4. Sem a descida
  por silêncio, P1 e P3 falham (contraexemplo: A em DATA, B em BASE). Sem validação ou com âncora gravada no COMMIT,
  P1 e P3 continuam valendo e **P4 falha**: ou seja, a validação e a âncora tardia não se justificam por P1/P3, e sim
  por P4. Essa distinção é o que torna a ablação informativa.
- Limite: o modelo é abstrato (4 modos, ticks); a equivalência com o código é por testes diferenciais, não por prova.
  Teto de potência assimétrico: o caso extremo (B nunca aceita) preserva P1, P2 = 0 e P4 e não acelera.

## 4. Implementação e equivalência

- Núcleo C99: sem alocação dinâmica, sem E/S, ações devolvidas por um vetor de tamanho fixo (docs/08).
- Teste diferencial: cenários aleatórios e dirigidos nos pares Py-Py, C-C, Py-C e C-Py comparados quadro a quadro,
  trocas de modo e gravações em NVM (docs/09 §8). Fuzz com ASan e UBSan. Cobertura medida no núcleo (docs/09 §8).
- Ausência longa: ressincronização em minutos mesmo com reinício de um nó (docs/07 §8, item 2).
- Custo: RAM e pilha do endpoint (docs/09 §8); número de x86-64, recalibrar no alvo.

## 5. Avaliação por simulação

Seções, cada uma com a tabela e a discussão que já estão na página consolidada:

1. Bancada (B2–B11): alcance, acordo (B3/B4), segurança (B7), regulação (B11, perfil `nao_verificado`).
2. Campo fixo (F, F6) e sintonia (F7): perfis nomeados padrão, estável e cauteloso.
3. Mobilidade (M).
4. Malha (T2–T6) com baselines comportamentais próprios (não são implementações dos sistemas originais).
5. Validação cruzada (xsim): LoRaSim original executado e porte; Meshtasticator original executado; equivalência.

**Ameaças à validade (escrever com cuidado):** parâmetros de canal, corrente do PA e deriva estimados; sensibilidade
do modelo difere da tabela medida do SX1272 em média ~3,9 dB e da calculadora do Meshtastic em ~2 dB; o perfil BR-2026
vem de fonte secundária e está `nao_verificado`; heterogeneidade de teto de TX não é modelada no orçamento de enlace;
baselines de malha são modelos comportamentais.

## 6. Discussão e limitações

- O que a simulação mostra e o que não mostra; por que o resultado vale para comparar e dimensionar, não para prever
  campo.
- Críticas e alternativas: ver a seção "Críticas" da página consolidada.

## 7. Trabalhos futuros

Ver a seção correspondente da página consolidada. Em resumo: calibração em bancada (repositório separado),
algoritmo de MIC e rotação de chave, procedimento de ressincronização para contador fora da janela, fragmentação,
CAD/LBT, comparação com outros simuladores de malha e verificação com um *model checker* sobre o código C.

## Checklist antes de submeter

- [ ] Reler e citar cada referência de `docs/02` e `docs/05` na fonte original.
- [ ] Copiar as tabelas da página consolidada para a escala longa mais recente, rotulando escala e semente.
- [ ] Rever a alegação de contribuição frente às patentes citadas em `docs/02`.
- [ ] Decidir licença e onde o `core/` mora (decisões do autor).
- [ ] Substituir o perfil BR-2026 por fonte primária ou manter `nao_verificado` em todo o texto.
- [ ] Depois da bancada, acrescentar uma seção com a calibração real; sem ela, declarar "somente simulação".
