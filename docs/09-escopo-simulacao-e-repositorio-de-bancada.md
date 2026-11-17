# 09 — Escopo deste repositório e o repositório de bancada

Decisão de 15/11/2026: os **experimentos práticos com as placas Heltec** e o **firmware** (driver SX1262, porte
ESP32-S3, exemplos, bancada) saem deste repositório. Eles ficam em um **repositório separado**, que será criado
depois com a skill `/anthropic-skills:aiclp-kit-bancada-vm`. Este repositório continua sendo o lugar da pesquisa por
simulação, do protocolo e da especificação.

## 1. O que fica aqui

| Área | Conteúdo |
|---|---|
| Protocolo | máquina de estados de referência (`simsuite/protocol/`), verificação formal (`simsuite/formal/`) |
| Especificação | formato do pacote (`docs/07`), contratos de rádio e de porte (`docs/08`), codec de referência `wire.py` |
| Simulação | suíte `simsuite/` (cenários B, F, M, T), sintonia de parâmetros (F7), relatório e site de resultados |
| Núcleo C99 | `core/`: codec, tempo no ar e DATA/ACK, com teste cruzado contra o Python (ver §5 sobre onde ele mora) |
| Regulação | perfil BR-2026 (`nao_verificado`), verificador de conformidade (B11) |
| Análise | analisador de telemetria JSONL (`simsuite/analysis/`), usado também nos logs reais |

## 2. O que vai para o repositório de bancada

Drivers e portes, exemplos Arduino/ESP-IDF, scripts de bancada (gravação, coleta serial, controle do atenuador,
injeção de falhas), medições e a campanha de campo. O material de preparo da bancada continua em
`docs/03`, seção 9 (insumos de RF, camadas de teste T0–T3, regras de segurança), e passa a valer lá.

## 3. Mapa do plano de testes (docs/05) por repositório

| Item | Aqui (simulação) | Bancada (placas) |
|---|---|---|
| Fase 0 (regulação, OCD, UTE, LGPD) | `regulatory.py` codifica a leitura atual | decisão jurídica; confirma homologação da Heltec V4 |
| Fase 1 (formal) | feito: P1 e P3 valem; contraexemplo sem descida por silêncio | — |
| Fase 2 (simulação e validação cruzada) | feito para o par; camada física validada contra os originais do Meshtasticator e do LoRaSim (§9.1); roteamento por inundação fora do escopo por decisão | — |
| B1 calibração RSSI/potência | usa 25,6 dBm da Heltec como referência | **medir por unidade** |
| B2 PDR × atenuação | curvas do modelo indicam onde medir | **curva real**, passos de 1 dB |
| B3 custo do plano de controle | feito (tempo no ar, energia estimada) | energia real depende de B8 |
| B4 injeção de falhas | feito (perda, reboot, relógio, âncora) | **reinício forçado no meio da troca** |
| B5 rendezvous | feito | tempos reais com salto sincronizado |
| B6 reprodução de traços | feito (traço simulado) | traço real no atenuador programável |
| B7 segurança | feito (replay, forjado, jammer reativo) | jammer real em bancada conduzida |
| B8 energia por estado | tabela do modelo | **curva de corrente** (PPK2/shunt) |
| B9 deriva térmica e LDRO | tolerâncias exatas; deriva estimada | **medir FEI**; confirmar TCXO |
| B10 CAD multi-SF | só tempos | **detecção e falso alarme** |
| B11 conformidade | verificador pronto | roda sobre os logs reais |
| F1–F6 campo fixo | canal estimado; F7 sintonia | **campanha de campo** (T3) |
| M1–M7 mobilidade | trajetórias, Doppler, perfis | campo com GNSS |
| T1 P2P contra presets | feito | campo |
| T2/T3 estrela, membro fraco | modelo nível 2 | 3 e 4 placas |
| T4–T6 malha e baselines | modelos comportamentais | só com protocolo congelado |
| Fase 7 pipeline de dados | esquema JSONL e analisador prontos | gera os logs reais |

## 4. Contrato entre os repositórios

**O que a bancada recebe daqui** (fonte da verdade, versionada):

1. **Formato do pacote:** `docs/07`, `simsuite/protocol/wire.py` e os vetores `core/tests/vectors/frames.txt`. O
   firmware precisa decodificar e gerar exatamente esses bytes (o codec C já passa nos 36 vetores).
2. **Contratos:** `core/include/legua/{legua,port,radio}.h` (`docs/08`).
3. **Esquema de telemetria JSONL** (`simsuite/analysis/telemetry.py`): os coletores da bancada emitem os mesmos campos
   (`v`, `t`, `node`, `ev`, e por evento `tx`, `rx`, `modo`...) mais `lat`, `lon`, `alt`, `vel`, `temp`, `fw` no
   hardware. Assim o analisador e o verificador B11 rodam sem mudança.
4. **Previsões a conferir:** as curvas de B2, o orçamento de enlace dos modos (`docs/06`), a tabela de energia de
   B8 e as tolerâncias de B9, todos em `simsuite/results/` e no site.
5. **Critérios de aceite:** P1 e P3 valem; nenhum desacordo permanente em B4; nenhum pacote fora do envelope em B11.

**O que a bancada devolve** (calibração; cada item é uma constante do modelo que hoje é estimada):

| Medida | Constante no simulador |
|---|---|
| limiar de demodulação e centro/inclinação da curva de PER | `SNR_THR`, `PER_OFFSET_DB`, `PER_SLOPE_DB` em `core/radio.py` |
| ganho do CR 4/8 | `CR_GAIN_DB` |
| corrente de TX por potência (B8) | `_I_TX_TABLE` |
| figura de ruído | `NF_DB` |
| potência real do PA (B1) | teto de 28 dBm e o valor medido de 25,6 dBm |
| deriva térmica e TCXO | taxas em `scenarios/bench.py` (B9) |
| detecção e falso alarme do CAD | hoje só o tempo de CAD (B10) |
| expoente de perda, sombreamento, AR(1) do campo | `core/channel_static.py` |

Procedimento: a bancada publica um arquivo `calibracao.json` com esses valores e a incerteza; este repositório os
incorpora, reroda a suíte e atualiza o site, marcando a escala e a versão da calibração. Enquanto não houver
medição, **todo resultado daqui vale só para comparar e dimensionar**.

## 5. Decisões em aberto

1. **Onde o `core/` mora: decidido em 17/11/2026.** Enquanto o protocolo mudar, o `core/` **fica aqui**, junto do
   `endpoint.py`, e toda mudança no C passa pelo teste de equivalência. O repositório de bancada o consome como
   **submódulo git fixado numa tag** deste repositório (`core-vX.Y.Z`), nunca como cópia editável. Correção que a
   bancada precisar no núcleo vem para cá, passa pela equivalência e sai numa tag nova. Quando o protocolo congelar e
   a biblioteca for publicada (Arduino, componente ESP-IDF), o `core/` vai para um repositório próprio (`legua-core`),
   que este e o de bancada passam a usar. Alternativas descartadas: levar o `core/` para o repositório de firmware
   (perde a equivalência com o Python) e criar o repositório próprio já agora (três repositórios para coordenar
   enquanto o formato ainda muda).
   **Tag `core-v0.1.0` (17/11/2026).** Primeira tag do núcleo; versão em `core/VERSION`. Cobre: codec do pacote v0 com
   os tipos 1 a 8 (docs/07), negociação PROPOSE/VOTE/COMMIT, validação, âncora e rollback, escada e silêncio,
   controle de potência, perfil móvel e `fade_k`, MIC AES-128-CMAC com limite de falhas, rotação de chave, registro de
   NVM, teto de TX do par e ressincronização autenticada do contador (RESYNC). Verificada por: testes do núcleo,
   fuzz com ASan e UBSan, equivalência Py/C nos quatro pares (200 sementes) e vetores do codec e do MIC. **Não cobre:**
   driver SX1262, porte ESP32-S3, CAD/LBT, guarda das chaves, fragmentação; o BR-2026 segue `nao_verificado` e os
   parâmetros vêm de simulação, não de medição. Regra de versão: mudança do formato de fio sobe o minor (0.2.0);
   correção sem mudar o fio sobe o patch; 1.0.0 só depois da calibração e do congelamento do protocolo.
2. **Licença:** decidida em 16/11/2026, o código é livre sob **Apache-2.0** (arquivo `LICENSE`, README). Contribuições com DCO.
3. **Como a bancada consome o analisador** (`simsuite/analysis/`): pacote Python instalável ou cópia.

## 6. Escala longa (full): orçamento de tempo

Máquina de referência: 4 CPUs, 3,4 GB de RAM, disco mecânico. A escala longa roda com **um processo por vez**
(`--procs 1`, sem disputar RAM e disco) e leva **cerca de 1 h 06 min** (66 min medidos). A escala rápida leva
9,5 min com um processo (4 min com quatro, mas aí os tempos por cenário ficam inflados pela contenção).

O orçamento é calculado por `python3 -m simsuite.analysis.orcamento` como `tempo(rápida) × fator de trabalho ×
contenção`. O fator vem do código (tempo simulado × sementes × amostras de cada cenário); a contenção é a mediana de
medido/extrapolado nos cenários da escala longa já rodados. **Previsão congelada antes da rodada** (1 h 08 min) contra o
medido:

| Cenário | Rápida (s) | Previsto (s) | Medido (s) | Medido/previsto | O que muda (rápida → longa) |
|---|---|---|---|---|---|
| F7 sintonia | 121 | 2112 | 2036 | 0,96 | 1 → 7 dias; 2 → 5 sementes |
| M mobilidade | 155 | 776 | 718 | 0,93 | T 1 h → 3 h (gado 6 → 24 h); 2 → 3 sementes |
| F campo fixo | 68 | 510 | 514 | 1,01 | T 2 → 6 h; 2 → 5 sementes |
| T456 malha | 75 | 225 | 229 | 1,01 | T 2 → 6 h |
| F6 longa duração | 29 | 204 | 200 | 0,98 | 1 → 7 dias; 3 sementes |
| B4 injeção de falhas | 9 | 88 | 87 | 0,98 | 300 → 3000 negociações |
| formal | 75 | 75 | 75 | 1,00 | independe da escala |
| B3 | 6 | 37 | 30 | 0,79 | 150 → 1000 negociações |
| B7 | 4 | 22 | 21 | 0,98 | T 4 → 24 h |
| B2 | 7 | 22 | 19 | 0,87 | 100 → 300 pacotes por ponto |
| demais (B5, B6, B11, T23, amostras, fase7, tabelas) | | 28 | 28 | 0,99 | |
| **Total** | **569** | **4100** | **3956** | **0,96** | relógio de parede: 3965 s |

**Rodada de 2026-11-16 (após o núcleo C, o P4 e a validação cruzada)**, medida, sem previsão congelada: total 4578 s
(1 h 16 min), 19 cenários e o relatório, todos ok. F7 2050 s, M 724 s, F 585 s, T456 224 s, F6 202 s, B4 149 s,
formal 171 s (o P4 e o histórico fantasma dobraram o espaço de estados: 179.393 estados), equiv 170 s (150 sementes,
525.412 eventos comparados, 0 divergências), xsim 124 s. O custo do formal e dos dois cenários novos soma ~8 min; o
limite de 8 h segue folgado.

**Limite de 8 horas.** Combinado com o autor: se a estimativa de uma rodada da escala longa passar de 8 h, ela fica
para depois. O `run_suite` aplica isso sozinho: na escala `full` ele calcula o orçamento dos cenários pedidos antes de
começar e recusa (código de saída 2) se passar de `--limite-horas` (padrão 8). `--so` roda um subconjunto e `--forcar`
ignora o limite. A rodada completa de 15/11/2026 (66 min) ficou muito abaixo.

Duas ressalvas. (1) O tempo depende da trajetória simulada, não só da duração: antes do conserto do laço em
`_descend` (`docs/06`, item 10) um caso de 2 dias levou 33 s contra 5 s depois. Orçamentos futuros assumem que não
há outro laço desse tipo; se o tempo medido de um cenário passar de 1,5× o previsto, investigue. (2) O orçamento vale
para esta máquina; em outra, rode a escala rápida com `--procs 1` e use a razão medida.

## 7. Estimativas e comparação de escalas no site

A aba **Estimativas** calcula, no navegador, o que esperar de um setup (cenário, distância, modo, potência,
retransmissões, intervalo, ganho extra, tráfego de terceiros) com um estimador analítico: o mesmo canal e a mesma curva
de demodulação da simulação, integrados por quadratura em vez de sorteados. Referência em
`simsuite/analysis/estimator.py`, porte em `site/estimator.js`, com teste de paridade (tolerância 1e-9). Não modela
colisão entre os dois nós, CAD/LBT, salto sincronizado nem a negociação de modo.

**Validação contra o simulador de eventos** (`tools/validar_estimador.py`, 15/11/2026): com o sombreamento estático
do enlace fixado em 0 e em +1σ (a simulação normal sorteia esse valor por semente, o que confunde a comparação),
3 modos fixos, urbano denso e rural aberto, 3 sementes de 6 h por ponto, 42 pontos: erro absoluto médio de **1,1 pontos
percentuais** na entrega do receptor, máximo de 4,9, viés de −0,7 (o estimador é levemente pessimista). Só a entrega foi
validada; energia e latência seguem a mesma conta, mas não foram comparadas ponto a ponto. O seletor **Rápida / Longa** troca a
escala de todas as abas; seções sem resultado na escala escolhida mostram o que falta e o tempo para gerar. A aba
**Escalas e orçamento** compara as duas escalas célula a célula. Cada aba termina com uma **Discussão dos resultados**
(características principais, vantagens, desvantagens, aplicações práticas, críticas e limitações); os números citados
vêm dos dados da escala escolhida e as críticas apontam o que o modelo não cobre (por exemplo, que os baselines de
terceiros são modelos nossos e que o BR-2026 está nao_verificado).

### 7.1 Ferramentas de uso dos resultados (17/11/2026)

- **Estado e exportação na aba Estimativas:** o setup vai no fragmento da URL (`#estimativas?d=2&sf=9...`), com
  resumo copiável, CSV, JSON e impressão. Tudo local, sem rede; o fragmento não vai ao servidor.
- **Testador de enlaces** (`site/enlace.html`, 17/11/2026): dois pontos, perfil de terreno digitado (plano, morro
  sintético ou CSV colado), curvatura da Terra (k), primeira zona de Fresnel, difração de gume único por Bullington
  (`site/propagacao.js`, J(v) da ITU-R P.526 em forma aproximada; o texto da Recomendação não foi lido), orçamento
  de enlace e margem por modo, ligados ao estimador pelo campo `offset_db`. O ambiente escolhido contribui só com a
  variabilidade; a perda média é o espaço livre mais a difração mais a perda extra do usuário, e o estimador recebe a
  diferença de ganho de antena (sem contar duas vezes). Referência em `simsuite/analysis/enlace.py` e teste de
  paridade com o JavaScript (`test_enlace.py`). **Elevação real:** arquivos `.hgt` (SRTM1 ou SRTM3) carregados do
  disco (`terreno.js`, interpolação bilinear, vazios tratados), com as coordenadas dos dois pontos digitadas; ficam só na
  memória da página (nem na URL, nem no resumo). **Fora do escopo desta versão:** busca automática de elevação, mapa, vegetação
  e prédios (use a perda extra), reflexão no solo e mais de um obstáculo além do equivalente de Bullington.
  **Privacidade:** o perfil colado fica só na página e não vai ao endereço compartilhável; não há `fetch`.
  **Validação da difração (17/11/2026):** com um pico agudo, o Bullington do testador é exatamente o gume único J(v) da
  geometria (teste analítico, tolerância 1e-9), e a perda cresce com a altura do obstáculo e cai com o mastro. **O que
  isso não prova:** o J(v) é a forma aproximada da P.526 (texto não lido) e não há comparação com o ITM da NTIA nem com
  medição. Limitações conhecidas do modelo, sem números próprios: obstáculo arredondado perde mais do que o gume agudo
  (o testador é otimista em morros suaves) e, com vários obstáculos, o método de Bullington tende a subestimar a perda.
  Uma comparação por Deygout sobre perfis suaves foi tentada e descartada: ela soma arestas espúrias da mesma colina e
  não serve de referência. A validação de verdade espera os vetores do ITM (NTIA) ou medições da bancada.
  Fonte de elevação e mapa (fases 3 e 4 do relatório de pesquisa) só entram com consentimento explícito e depois de
  testar o CORS num navegador real. É ferramenta de análise: não toca em rádio nem em bancada.

## 8. Núcleo C: Fase 2 e equivalência com o simulador

**O que o núcleo C faz agora** (`core/src/endpoint.c`, 15/11/2026): descoberta (HELLO), negociação
PROPOSE/VOTE/COMMIT com instante de troca relativo, janela de validação, âncora gravada só depois da validação,
rollback, escada de degradação, descida por silêncio, controle de potência, alarme de rollbacks repetidos (possível
jamming), perfil móvel, margem proporcional ao desvio do SNR (`fade_k`) e registro de NVM com o piso do contador do
par. Continua C99 puro, sem alocação, sem E/S e sem biblioteca de terceiros; a tabela de modos entra pelo integrador
(`docs/08` §2).

**Teste de equivalência** (`simsuite/tests/equiv_harness.py`, `test_equivalencia.py`; cenário `equiv` da suíte). Um
DES mínimo de dois nós, com canal determinístico, dirige cada ponta por um adaptador:
o `Endpoint` do Python **atrás do formato de fio real** (os quadros viram bytes de `wire.py` e voltam) ou o núcleo
C carregado como biblioteca (`core/tests/pyshim.c`, via ctypes). O mesmo cenário roda nos quatro pares Py-Py, C-C,
Py-C e C-Py e os rastros têm de ser **idênticos**: cada quadro transmitido (bytes, modo, potência), cada troca de
modo, cada gravação em NVM e as estatísticas. Py-C e C-Py provam também a interoperabilidade do formato de fio.
Cenários dirigidos (enlace bom, degradação e silêncio, reinício, replay e MIC forjado, jammer, rollbacks repetidos que
disparam o alarme) mais cenários aleatórios reprodutíveis (variantes: normal, âncora no COMMIT, sem validação, só
recuperação, móvel, sem silêncio, passo curto, `fade_k`; apagões, reinícios, replays, velocidades, ruído e teto de
potência diferentes). Em 15/11/2026: **280 cenários aleatórios sem divergência** (sementes 0 a 149 e 200 a 329) e
mais os dirigidos; o teste confirma a própria sensibilidade (um parâmetro diferente faz os rastros divergirem).

**Robustez** (`make -C core fuzz`, ASan e UBSan): bytes aleatórios, quadros truncados e adulterados e quadros com MIC
**válido** e campos absurdos (modo inexistente, voto 255, atraso enorme, potência 54 dBm) em todos os estados, com
invariantes conferidas depois de cada chamada (índices na tabela, potência no intervalo, fila no limite, ações sem
estouro, contador de TX crescente). 192 mil chamadas sem violação.

**O que a equivalência NÃO cobre:** o modelo de rádio. O canal do teste usa a mesma curva de PER do simulador e não
tem salto, colisão de terceiros nem escuta antes de transmitir; ela prova que o C **faz o mesmo que o Python**, não que
o Python descreve a realidade. `float` (C) contra `double` (Python) pode, em tese, divergir num empate de limiar; nenhum
apareceu.

**Mudanças no simulador para chegar à equivalência** (todas deixam o comportamento mais fiel ao fio; os resultados
foram regenerados):

| Mudança | Efeito |
|---|---|
| instante de troca relativo ao fim do COMMIT (antes absoluto) | a troca ocorre ~0,35 s depois |
| prazos com o tempo no ar arredondado ao ms | < 1 ms |
| fila cheia descarta o mais antigo que não está em voo (antes descartava o primeiro, mesmo em voo) | só sob saturação |
| duplicata por janela de 32 sequências, em 8 bits (antes um conjunto sem limite) | contagem estável após 256 pacotes |
| o ACK não carrega a velocidade | `peer_speed` não zera no ACK |
| ganho do ACK em passos de 0,5 dB; potência de TX no DATA em passos de 1 dB; velocidade em 0,5 m/s | quantização do fio |
| DATA enviado antes de uma troca de modo não arma prazo de ACK | evita prazo errado |
| tolerância de 1 ns nos prazos (`_due`, `_over`) | só estabilidade numérica |
| registro de NVM com piso do contador do par; gravação por bloco de 64 nos dois contadores | acrescenta gravações raras (~a cada 64 quadros) com 80 ms de parada |
| contador de retransmissão passa pelo mesmo bloco de NVM | corrige uma gravação omitida |

### 8.1 Cobertura, RAM e pilha do núcleo (16/11/2026, x86-64; recalibrar no alvo)

- **Cobertura de linhas** (gcov, `-O0`): `endpoint.c` 98,2% (637 de 649 linhas) somando os testes C (`test_sim`,
  `test_fuzz`, `test_codec`: 89,5%) e a suíte de equivalência com 60 sementes pela ponte ctypes (96,9%); `frame.c` 81,2%
  e `toa.c` 84,6%. Linhas sem cobertura: o transbordo do vetor de ações (que os testes exigem que nunca ocorra), ramos
  de entrada inválida em `legua_mode_pack`/`legua_frame_decode`, o caso SF 5–6 do tempo no ar e ramos `default:` de
  `switch`. Cobertura de ramos de `endpoint.c`: 72,8% só pelos testes C.
- **RAM:** `sizeof(legua_endpoint)` = 816 B, `legua_actions` = 388 B (na pilha do chamador), `legua_params` = 92 B,
  entrada da tabela de modos = 12 B (18 modos = 216 B, em flash). Em 32 bits os ponteiros encolhem; medir de novo no
  Xtensa.
- **Pilha** (`-fstack-usage`, `-Os`): pior quadro `legua_on_rx` 144 B; a cadeia mais funda observada
  (`on_rx` → `propose` → `emit` → `ctrl_frame` → `legua_frame_encode`) soma ~430 B, mais o vetor de ações do chamador.
  Recursão: nenhuma. **Código:** ~10 KB de `.text` em x86-64 com `-Os`.

## 9. Validação simulação × simulação (LoRaSim)

`simsuite/analysis/lorasim.py` (cenário `xsim`) compara o simulador de eventos desta suíte com as regras do **LoRaSim**
(Bor, Roedig, Voigt, Alonso, MSWiM 2016; `github.com/mcbor/lorasim`, commit `1eddb96`). O LoRaSim é **Python 2 e não
foi executado**: as funções `airtime`, `checkcollision`, `powerCollision`, `timingCollision` e `transmit` foram
**portadas à mão** para um laço próprio, então um erro de porte é possível. Para não depender só do porte, cada
comparação inclui também a expressão analítica do ALOHA puro. Resultados (escala rápida, 3 sementes de 1 h):

- **Tempo no ar:** idêntico em 4320 combinações (SF7 a SF12, BW 125/250/500, CR 1 a 4, 1 a 60 B), exceto **SF12/250**: o
  LoRaSim só liga a otimização de baixa taxa (LDRO) em 125 kHz com SF11/12, e aqui vale a regra da Semtech (símbolo
  acima de 16 ms), que inclui SF12/250. A diferença é do LoRaSim (simplificação), não daqui.
- **Colisão em estrela, potências iguais:** o simulador desta suíte acompanha a expressão analítica do ALOHA (por
  exemplo 0,827 contra 0,828 com 100 nós); o porte do LoRaSim fica ~1,3 ponto acima (0,841), por causa da exceção do
  preâmbulo: o pacote que chega nos últimos símbolos do preâmbulo do outro sobrevive.
- **Captura:** com metade dos nós 10 dB mais forte, os fortes e os fracos têm PDR parecido nos dois (diferença de
  menos de 1 ponto, de novo pela exceção do preâmbulo).
- **Sensibilidade (informativo):** a tabela do LoRaSim é medida num SX1272; a daqui vem do limiar de SNR e da figura de
  ruído do SX1262. A diferença média é de ~3,9 dB (máxima 6,5 dB). Isso desloca os limiares de alcance e é uma das
  razões para a bancada calibrar `SNR_THR` e `NF_DB`.

### 9.1 Os originais executados (16/11/2026)

Para não depender só do porte, o cenário `xsim` agora **executa o código original** dos dois:

- **LoRaSim original** (`simsuite/analysis/lorasim_original.py`): o `loraDir.py` do commit `1eddb96` é lido do clone
  (`LEGUA_LORASIM` ou `~/.cache/ext/lorasim`), com **só a sintaxe de `print` convertida** de Python 2 para 3 em memória;
  a lógica não é tocada. Precisa de `simpy==3.0.10`. Experimento 0 (SF12, BW125, CR 4/8, 20 B, uma frequência,
  colisão completa), nós em posições aleatórias do disco de alcance; o simulador daqui recebe **o RSSI que o original
  sorteou** para cada nó. Escala longa (3 sementes de 6 h): PDR do original / daqui / analítico, com 50 nós 0,802 /
  0,791 / 0,752; 200 nós 0,412 / 0,395 / 0,319; 800 nós 0,068 / 0,061 / 0,010. As duas curvas ficam dentro de ~2 pontos
  uma da outra; ambas ficam acima do ALOHA puro porque a posição aleatória cria captura, e o original ainda tem a
  exceção do preâmbulo.
- **Meshtasticator** (`simsuite/analysis/meshtasticator.py`): `lib.phy.airtime`, `lib.phy.check_collision` e a tabela
  de presets são importados do clone (`LEGUA_MESHTASTICATOR` ou `~/.cache/ext/Meshtasticator`) e executados. Só a
  camada física é comparada; o roteamento por inundação do Meshtastic não tem equivalente aqui. Resultados: tempo no
  ar idêntico nos 10 presets e 240 tamanhos, exceto `VERY_LONG_SLOW` (BW 62,5 kHz: LDRO só em 125 kHz no
  Meshtasticator); regra de captura de 6 dB igual nos 10 casos testados; sensibilidade dos presets difere em média
  2,07 dB (máx. 2,49) da calculadora que o Meshtastic usa (NF de 6 dB); PDR da estrela ALOHA com 20 a 300 nós fica a
  menos de 0,4 ponto do analítico no Meshtasticator e até 3,8 pontos acima no simulador daqui (que usa preâmbulo 8
  e portanto tempo no ar menor; o analítico de cada um usa o tempo do próprio).

Sem os clones, ou sem `simpy`, os dois blocos devolvem `disponivel: false` e os testes são pulados; a suíte segue.

**Limites:** o experimento 0 do LoRaSim é uma estrela de um canal e um SF; o Meshtasticator só foi usado na camada
física.

**Decisão sobre o roteamento por inundação (16/11/2026): não fazer agora.** O escopo do projeto é o par bem provado
(docs/05, "Escopo refinado"); a malha entra só como extensão, e os baselines T4–T6 já são modelos comportamentais da
inundação gerenciada do Meshtastic. Comparar com o roteamento original exigiria modelar mobilidade de pacotes, papéis
e a camada de aplicação do Meshtastic, sem que o resultado mudasse uma decisão do par. Reabrir se o projeto passar a
mirar malha.

## 10. Próximos passos de simulação

1. (feito em 15 e 16/11/2026) Fase 2 no núcleo C: PROPOSE/VOTE/COMMIT, validação e rollback, com teste de
   equivalência contra `endpoint.py` (§8).
2. (feito em 15/11/2026) Escala `full` rodada e publicada no site; repetir quando o protocolo mudar.
3. (feito em 16/11/2026, camada física) Validação simulação × simulação contra Meshtasticator e LoRaSim, com os
   originais executados (§9.1). A comparação do roteamento por inundação ficou fora por decisão (§9.1).
4. (feito) Controle compactado para 16 B.
4b. (feito em 16/11/2026) Varredura da potência de TX (cenário `P`, docs/06): teto simétrico, teto assimétrico e
   controle de potência. O teto do vizinho passou a valer no cálculo da margem em 17/11/2026 (docs/07 §4). Medição antes e depois, 2 h, 3
   sementes, urbano residencial, A a 28 dBm e B a 14 dBm, 1 km: rollbacks 33 → 0, PDR 0,961 → 0,993, energia mediana
   1533 → 993 mJ por pacote; com B a 8 dBm, rollbacks 32 → 0, PDR 0,970 → 0,993, energia 2007 → 1677 mJ. A 2 km, onde o
   enlace no modo base já não fecha, nada muda. Cenário `P` inteiro (escala rápida, antes → depois): com teto simétrico,
   resultado idêntico (conferido também em B6, F, F6, V, S e M); no assimétrico os rollbacks por hora caem a 0 em todas as
   células que tinham (de até 6,5), o PDR sobe até 3 pontos e a energia por pacote cai em 11 das 13 células com
   enlace; as duas exceções (4 km com B a 14 e a 20 dBm) variam dentro do ruído do enlace marginal (PDR 0,929 → 0,923
   com B a 20 dBm; energia +2%). Falta medir a curva de corrente do PA na bancada, da qual depende o
   mínimo de energia.
5. (feito em 16/11/2026) Resultado da sintonia (F7) aplicado como perfis nomeados `padrao`, `estavel` e `cauteloso`
   (`simsuite/protocol/perfis.py` e `legua_params_profile` no núcleo C, conferidos pelo teste de equivalência).
6. (feito em 16/11/2026) Algoritmo do MIC: AES-128-CMAC truncado a 4 B, com referência em C e Python e vetores
   (docs/07 §6). Limite de falhas de MIC feito em 17/11/2026 (congela a negociação, mantém o modo).
   Ressincronização autenticada do contador do par (RESYNC/RESYNC_RSP, docs/07 §6.3) feita em 17/11/2026: muda o formato
   de fio (tipos 7 e 8; vetores regenerados).
   Provisionamento (uma chave por enlace) e rotação em ciclo pelo `key_id` feitos em 17/11/2026 (docs/07 §6.1 e
   §6.2). A guarda das chaves no ESP32-S3 fica para o repositório de bancada.
7. (decidido em 17/11/2026) O `core/` fica aqui até o protocolo congelar; a bancada o usa como submódulo numa tag
   (§5, item 1).

### Varreduras já feitas e o que falta (16/11/2026)

Feitas, isoladas: teto de TX global e cenário P; margem/`fade_k` (F7); janela de validação (V); `t_silence` × aplicação (S). Feitas em 17/11/2026 (cenário `X`): deriva do cristal e erro de relógio, perda assimétrica entre os sentidos e teto × `fade_k`. Não feita: **payload**, que depende do formato (cada tipo de quadro tem tamanho fixo; variar o payload exige fragmentação ou novos tamanhos, `docs/07` pendência 3) e foi retirada do escopo atual por decisão do autor em 17/11/2026. Também feito: desvanecimento lento independente por sentido (`SlowFade`, processo de Ornstein-Uhlenbeck, correlação de 10 min, um por sentido, grupo `lento` do `X`). Escala longa, 2 km: PDR 0,983 / 0,981 / 0,961 / 0,924 para desvios de 0 / 3 / 6 / 9 dB, rollbacks de 0,1 a 0,3 por hora; na rápida (2 sementes) a ordem entre 0 e 3 dB inverte por ruído. Parâmetros estimados; a correlação e o desvio reais vêm da bancada. Combinação completa é inviável (minutos por ponto na escala longa); payload e distância densos têm modelo analítico no estimador. Orçamento: V e S somam ~9 min na escala longa; a varredura de teto, ~4 h.
