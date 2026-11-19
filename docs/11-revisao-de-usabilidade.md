# 11. Revisão de usabilidade do site (heurísticas de Nielsen)

Data: 18/11/2026. Escopo: `site/index.html` (15 abas em 6 seções), `site/enlace.html` (testador de enlaces, com mapa e
elevação) e `site/consolidado.html`.

**Método e limites.** Avaliação heurística feita por leitura do código e por uma auditoria automática em jsdom (cada aba
e as duas outras páginas: botões sem nome, campos sem rótulo, SVG sem texto alternativo, parágrafos longos, siglas). Não
houve teste com usuários, nem inspeção visual em navegador real (contraste, quebra de linha, toque em celular), nem
leitor de tela. O que depende disso está marcado como **não verificado**. Gravidade na escala de Nielsen: 0 = não é
problema, 1 = cosmético, 2 = menor, 3 = importante, 4 = catastrófico.

**Relato do usuário que motivou a revisão.** (a) Não era possível dar zoom no mapa. Causa encontrada no código: o zoom, o
arrastar e o teclado só funcionavam depois de marcar o consentimento do mapa-base; antes disso não havia nenhum controle
visível. (b) Os avisos de consentimento eram grandes demais (parágrafos de 5 a 7 linhas, sempre abertos).

## Auditoria automática (jsdom)

| Página | Cartões | Caracteres | Botões sem nome | Campos sem rótulo | SVG sem alternativa |
|---|---|---|---|---|---|
| 16 abas de `index.html` | 3 a 10 | 3,2 mil a 12,8 mil | 0 | 0 | 0 |
| `enlace.html` | 6 | 5,3 mil | 0 | 0 | 0 |
| `consolidado.html` | 15 | 33 mil (com índice) | 0 | 0 | 0 |

Os pontos básicos de acessibilidade estão em dia. A aba mais densa é "Mecanismos (V, S)" (12,8 mil caracteres, 10
cartões, 9 tabelas). A sigla PDR aparece em 15 das 18 páginas e estava definida só no glossário da aba "Comece aqui".

## Achados por heurística

| # | Heurística | Achado | Grav. | Situação |
|---|---|---|---|---|
| 1 | Visibilidade do status | O botão de tema não mostrava o estado atual | 1 | **Corrigido**: "Tema: claro/escuro" |
| 1 | | Tiles do mapa que falham ao carregar não davam sinal | 3 | **Corrigido**: aviso no mapa ("Falha em N tile(s)…") |
| 1 | | A elevação mostrava "Baixando…" e o resultado; o mapa de relevo e a rota já tinham status | 0 | ok |
| 2 | Mundo real | Mensagens como "falta tile Terrarium 12/…", "sem CORS" | 3 | **Corrigido**: texto em português simples, com causa provável e saída |
| 2 | | Siglas (PDR, SF, ToA, EIRP, MIC, BW, CR) sem explicação fora do glossário | 3 | **Corrigido em parte**: primeira ocorrência por cartão vira `<abbr>` com a definição do glossário. **Não verificado em celular**: dica por `title` não aparece ao toque; o glossário continua na aba "Comece aqui" |
| 3 | Controle e liberdade | Pontos do mapa: remover um a um, sem desfazer; "Limpar" sem volta | 3 | **Corrigido**: "Desfazer" (30 passos), vale para clique, arraste, inverter, remover e limpar |
| 3 | | Mapa-base e elevação: sem como desligar | 2 | **Corrigido**: botão ⏻ desliga o mapa-base; a elevação só baixa ao clicar |
| 3 | | Testador e Estimativas sem como voltar ao estado inicial | 2 | **Corrigido**: "Restaurar padrões" nos dois |
| 4 | Consistência | Navegação diferente em cada página; tema só no `index` | 3 | **Corrigido** na reorganização (`nav.js`) |
| 4 | | Dois jeitos de consentir (caixa no mapa, caixa na elevação) com textos diferentes | 2 | **Corrigido**: um botão com o efeito escrito ("Ativar mapa-base", "Buscar elevação") e "O que é enviado?" recolhido |
| 5 | Prevenção de erros | Latitude/longitude aceitas sem checagem até o cálculo falhar | 3 | **Corrigido**: campo marcado como inválido na hora, com aviso (inclui "parece trocada") |
| 5 | | Consentimento por caixa que o usuário não lia | 2 | **Corrigido**: a ação (clique) é o consentimento, com o texto na própria ação |
| 5 | | Latitude e longitude trocadas **dentro** do intervalo (ex.: −43 e −22) não são detectáveis | 2 | **Corrigido em parte (19/11/2026)**: se o ponto cai fora do Brasil e, com os valores trocados, cairia dentro, aparece um aviso. Para pontos fora do Brasil de propósito, ou trocados dentro do Brasil, continua só o mapa mostrando o erro |
| 6 | Reconhecimento | A aba e a subseção são lembradas; o modo escolhido aparece no cartão | 0 | ok |
| 7 | Flexibilidade | Mapa com teclado (setas, + −, Enter), roda, duplo clique e botões; links com estado | 0 | ok (jsdom) |
| 7 | | Sem exemplo pronto no modo "Mapa" | 1 | **Corrigido (19/11/2026)**: botão "Usar exemplo" com dois pontos ilustrativos em Fortaleza (marcos públicos, sem dado de campo) |
| 8 | Minimalismo | Avisos de 4 a 7 linhas no topo de `index` e `enlace`, sempre abertos | 3 | **Corrigido**: uma linha e "O que isso significa" recolhido (a ressalva regulatória continua à mão) |
| 8 | | "Mecanismos (V, S)" com 10 cartões e 12,8 mil caracteres; consolidado com 33 mil | 2 | **Aberto**: dividir ou recolher seções; no consolidado, "voltar ao índice" por seção |
| 9 | Recuperação de erros | Falha de rede na elevação só dizia o que deu errado | 3 | **Corrigido**: causas comuns e saídas (tentar de novo, CSV, `.hgt`); o botão vira "Tentar de novo" |
| 10 | Ajuda e documentação | Sem passo a passo no testador | 2 | **Corrigido**: "Como usar em 3 passos" |
| 10 | | Ajuda do mapa (como zoom, arrastar, pôr ponto) só no `aria-label` | 3 | **Corrigido**: linha de instrução sob o mapa e botões +/− com rótulo |

## Pendências e riscos

- **Verificar em navegador real** (e em celular): zoom por roda e por botões, arraste, toque, carregamento dos tiles do OSM
  e da AWS (CORS), contraste, tamanho dos alvos de toque (em telas de toque, botões, abas e controles do mapa passaram a ter 44 px por CSS `pointer: coarse`, em 19/11/2026; só verificado por leitura do CSS).
- **Especificação no celular:** corrigido em 19/11/2026 (captura do usuário): índice e texto empilham abaixo de 760 px e os blocos de código rolam na horizontal.
- **Dica de sigla ao toque:** feito em 19/11/2026: a sigla vira botão (toque ou Enter) e abre a definição logo abaixo; o `title` continua para o mouse. Não verificado em celular real.
- **Densidade:** feito em 19/11/2026: a aba "Mecanismos (V, S)" foi dividida ("Estresses (X)" tem aba própria) e cada seção do consolidado ganhou "recolher" e "↑ Índice". Falta ver se a leitura melhorou (teste com pessoas).
- **Teste com usuários:** cinco pessoas com a tarefa "descobrir se o enlace entre dois pontos fecha" revelariam mais do que
  esta revisão; nenhuma foi feita.
