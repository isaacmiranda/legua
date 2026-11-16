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
| Fase 2 (simulação e validação cruzada) | feito para o par; falta validar contra Meshtasticator e LoRaSim | — |
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

1. **Onde o `core/` mora.** Hoje fica aqui, como referência executável do formato e da máquina de estados, com
   teste cruzado contra o Python. O firmware vai precisar dele (como submódulo, cópia versionada ou pacote). Decidir
   qual repositório é a fonte da verdade antes de a Fase 2 em C crescer.
2. **Licença** (Apache-2.0 é a proposta do doc 03), a definir pelo autor.
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

**Não feito:** o **Meshtasticator** (simulador de malha do Meshtastic): precisa de ambiente próprio e só serviria para
as topologias T4–T6, cujos baselines já são modelos comportamentais nossos; fica como próximo passo.

## 10. Próximos passos de simulação

1. Fase 2 no núcleo C: PROPOSE/VOTE/COMMIT, validação e rollback, com teste de equivalência contra `endpoint.py`.
2. (feito em 15/11/2026) Escala `full` rodada e publicada no site; repetir quando o protocolo mudar.
3. Validação simulação × simulação contra Meshtasticator e LoRaSim (Fase 2 do plano).
4. Compactar o pacote de controle de 20 para 14 a 16 B e medir o efeito em B3 (`docs/07`, pendência 4).
5. Aplicar o resultado da sintonia (F7) como perfil nomeado, se fizer sentido para o produto.
