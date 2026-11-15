# AdaptLoRa: parecer multidisciplinar e plano de implementação

> Documento 03 do projeto. Avalia os documentos 01 (ideia, revisão 3) e 02 (estado da arte) sob três olhares (engenharia, regulação e experiência de uso) e registra o que fazer, como fazer e o que não fazer.
> Premissas dadas pelo autor: biblioteca de **uso geral** e de **código livre**.
> Destino: servir de insumo para a montagem da bancada com a skill `/aiclp-kit-bancada-vm`.
> Data: 9 de novembro de 2026.

**Sobre as fontes.** Foram lidos os dois documentos do projeto. As conversas anteriores não estão acessíveis nesta sessão; se nelas houve decisões que não chegaram aos documentos, elas não estão refletidas aqui. A skill `/aiclp-kit-bancada-vm` não foi aberta, então a seção 9 segue apenas a descrição dela (bancada em VM Linux com placas via USB) e pode precisar de ajuste de formato.

---

## 1. Veredito em uma página

A ideia é viável e vale ser implementada, com três mudanças de rumo.

1. **Reposicionar.** O diferencial não é "adaptar o SF" (o AURORA já fez). É tornar a adaptação **recuperável** (âncora + rollback) e **ciente da regulação**. Todo o plano deve proteger essas duas coisas primeiro.
2. **Reduzir o primeiro alvo.** A versão inicial deve ser um **par de nós** com negociação e rollback corretos. Grupos, subgrupos, multi-salto, CAD multimodo e GNSS entram depois, cada um atrás de uma chave de compilação.
3. **Separar os dois problemas mais difíceis.** Acordo com rollback e sincronismo de salto em frequência não devem ser desenvolvidos juntos. Primeiro se prova o acordo em canal fixo; depois se acrescenta o salto como camada.

Do ponto de vista regulatório, a frase "opera no limite que a lei permite" precisa mudar. Quem responde pela conformidade é o **produto homologado**, não a biblioteca. A biblioteca deve **impedir que se ultrapasse** um teto informado pelo integrador, e não buscar o máximo por conta própria.

Do ponto de vista de uso, o público é o desenvolvedor de firmware. O sucesso se mede por três coisas: primeiro enlace funcionando em poucos minutos, erros que explicam o que fazer e um estado da rede sempre consultável ("por que não estou transmitindo?").

---

## 2. Parecer de engenharia

### 2.1 O que manter como está

| Item | Requisitos | Por quê |
|---|---|---|
| Modo base robusto + modo de dados negociado | RF-05 a RF-08 | Mesmo padrão usado pelo AURORA e justificado pelo OppLoRa |
| Âncora em memória não volátil, janela de validação, rollback em degraus | RF-24 a RF-28 | É o núcleo da contribuição; nem BLE nem LoRaWAN têm o degrau intermediário |
| Sondagem antes de trocar | RF-32 | Respaldo em Bor & Roedig e no AURORA |
| Sem alocação dinâmica, recursos removíveis na compilação | RNF-03, RNF-04 | Necessário para uso geral em MCUs pequenos |
| Camada de porte mínima | RNF-02 | Condição para ser multiplataforma de fato |
| Sem chave embutida, modo aberto explícito | RF-50a, RF-53e | Segurança por padrão sem bloquear protótipos |
| Telemetria em JSON por linha, um registro por nó | RF-56 a RF-61 | Simples e suficiente; facilita a bancada |

### 2.2 O que mudar, e como

| # | Mudança | Como fazer | Requisitos afetados |
|---|---|---|---|
| E1 | **Núcleo como máquina de estados pura** | O protocolo não chama rádio nem relógio diretamente: recebe eventos (pacote, tempo, comando) e devolve ações (transmitir, sintonizar, armar temporizador, gravar). Isso permite rodar N nós virtuais no PC, com perda e SNR injetados, antes de tocar em hardware | RNF-02, RNF-08 |
| E2 | **Linguagem: C99 no núcleo**, com casca C++ fina para Arduino | Um único núcleo serve Arduino, ESP-IDF, nRF e o simulador | RNF-05 |
| E3 | **Unanimidade só em pares e grupos pequenos** | Par na primeira versão. Depois, grupo de até 4 nós com um proponente por rodada. Acima disso, dividir em subgrupos. Desacordo é tratado como estado normal, não como erro | RF-21, RF-09 |
| E4 | **Subgrupos separados por canal, não só por SF** | Um subgrupo SF7 próximo pode derrubar um SF11 distante no mesmo canal (Croce et al.). Subgrupo novo implica canal ou sequência de salto própria, e controle de potência | §5.2, RF-33, RF-34 |
| E5 | **Histerese assimétrica e SNR filtrado** | Degradar rápido (poucas perdas seguidas), acelerar devagar (janela estável longa). SNR por média móvel exponencial. Margem de 5 dB sobre o limite teórico. Um passo por vez e limite de trocas por período | RF-30, RF-31, RF-35 |
| E6 | **Adaptar em ordem: SF e potência, depois BW e CR, depois canal** | O espaço de 5 parâmetros atrasa a convergência. Ponto de partida por tabela SNR→SF, corrigida pela taxa de entrega medida. Sem aprendizado por reforço na primeira versão | RF-29 a RF-34 |
| E7 | **BW candidatas dependem do hardware** | O perfil de nó declara se há TCXO e quais BW são seguras. Sem isso, BW estreita fica fora da lista | RF-18, RF-30 |
| E8 | **Orçar os 24 bytes do modo base já na especificação** | Proposta a validar: tipo/versão 1, flags 1, origem 2, destino 2, contador 2, grupo 1, MIC 4 = 13 bytes; sobram 11 para o corpo. Endereços curtos de 16 bits derivados do identificador, com detecção de colisão | RF-04, RF-05d, RF-55 |
| E9 | **Vincular respostas às perguntas** | ACK, VOTE e COMMIT autenticam o contador da mensagem a que respondem. Os parâmetros do modo entram como dados associados da cifra. Nonce = identificador + contador + época de boot | RF-50 a RF-52 |
| E10 | **Contador sem desgastar a flash** | Gravar o contador em blocos (por exemplo, a cada 64 envios) e, ao reiniciar, saltar para o início do bloco seguinte | RF-52 |
| E11 | **Rollback como possível sinal de ataque** | Contar rollbacks por período; acima de um limiar, parar de negociar por um tempo, ficar na âncora e emitir evento. Descartar SNR implausível ou que mude de forma abrupta | RF-25, RF-54 |
| E12 | **Jitter em beacons e anúncios** | Atraso aleatório em tudo que é periódico, e retransmissão com contenção por SNR no flooding (quem está mais longe repete primeiro) | RF-06, RF-16 |
| E13 | **Perfil bateria sem PROBE dedicado** | Métricas embutidas nos dados e nos ACKs; negociação rara. Escuta por CAD com preâmbulo longo | RF-41 |
| E14 | **Uma tag de fragmentação por origem** | Necessária quando um relay recebe de várias origens ao mesmo tempo | RF-38 |
| E15 | **GNSS e PPS fora do núcleo** | A sincronia por beacon basta na maioria dos casos (deriva de ±12 ms em 10 min a 20 ppm). PPS é módulo opcional para janelas espaçadas por horas | RF-11, RF-72 |
| E16 | **Modelo de energia medido no SX1262** | A literatura mede SX1272. A curva de corrente por potência e o custo de acordar o ESP32-S3 precisam ser medidos na bancada | RF-33, RF-41 |

### 2.3 Drivers: decisão com ressalva

A decisão 13 (drivers próprios) é mantida, com uma ordem: **uma interface de rádio primeiro, um driver por vez**. O SX1262 vem primeiro, por ser a referência. O SX127x só entra depois que o protocolo estiver estável. A interface deve ser estreita o bastante para que o adaptador RadioLib (RNF-07) seja um arquivo pequeno; isso dá um plano B barato se a manutenção dos drivers pesar.

### 2.4 Ordem de desenvolvimento do modo base

A decisão 18 (padrão Brasil: salto em frequência, BW 125 kHz, SF10) e a decisão 22 (SF12/BW 500 não é padrão) continuam valendo **para a versão publicada**. A recomendação é só de ordem de trabalho:

- **Fases 1 a 3:** modo base em **canal fixo com BW 500 kHz**, em bancada com sinal conduzido. Serve para provar pacote, cripto, negociação, rollback e adaptação sem o sincronismo de salto no caminho.
- **Fase 4:** o salto em frequência entra como camada própria, com métrica de tempo de entrada e de perda de sincronismo.

Isso não muda o padrão final; evita depurar dois problemas inéditos ao mesmo tempo.

---

## 3. Parecer de regulação

Este parecer não substitui consulta a um organismo de certificação designado (OCD) nem aconselhamento jurídico.

### 3.1 O que foi confirmado em fonte oficial nesta revisão

O documento 02 dependia de fonte secundária porque o portal da Anatel estava fora do ar. Agora foi possível confirmar no portal de legislação da Anatel:

- O Ato nº 14.158/2025 revoga o item 10.3.4.4 do Anexo I do Ato nº 14.448/2017 (Art. 11, III) e é de aplicação obrigatória desde 6/4/2026 ([Ato 14.158](https://informacoes.anatel.gov.br/legislacao/component/content/article/169-atos-de-certificacao-de-produtos/2025/2070-ato-14158)).
- O Ato nº 4.746/2026 tornou esse inciso obrigatório só a partir de 6/10/2026 e preservou os produtos já homologados na manutenção da certificação ([Ato 4.746](https://informacoes.anatel.gov.br/legislacao/atos-de-certificacao-de-produtos/2026/2132-ato-4746)).
- Pelo novo item 10.6, as emissões fora de faixa devem ficar 20 dB abaixo do nível em faixa, ou 30 dB para equipamento avaliado pelo método alternativo do item 10.3.4.

Como hoje é 9/11/2026, a regra já vale para **novas certificações**. A leitura de que isso atinge LoRa de 125/250 kHz em canal fixo continua sendo interpretação do projeto, coerente com a de um laboratório ([GMA Labs](https://www.gmalabs.com/post/brazil-anatel-restricted-radiation-equipment-500-khz-rule)), e deve ser confirmada com um OCD.

**Ainda não conferido no texto oficial:** os números da seção 10 do Anexo I (50 canais, 0,4 s em 20 s, 1 W, densidade de 8 dBm/3 kHz, regra de ganho de antena). A página do Ato nº 14.448 não abriu nesta sessão. A tabela RF-46 segue marcada como "não verificada".

### 3.2 Pontos que mudam o desenho

| # | Ponto regulatório | Consequência para a biblioteca |
|---|---|---|
| R1 | A Resolução nº 680/2017 exige certificação dos equipamentos de radiação restrita (Art. 4º). **Quem é homologado é o produto**, não a biblioteca ([Res. 680](https://informacoes.anatel.gov.br/legislacao/index.php/component/content/article?id=936)) | A biblioteca nunca se declara "conforme" ou "homologada". A documentação diz que a conformidade é do integrador |
| R2 | O equipamento deve ser projetado para usar apenas a antena comercializada com ele (Art. 6º da mesma resolução) | A troca de antena em tempo de execução (RF-64) vira recurso de **ensaio**. Em compilação de produto, o perfil de antena é fixo e travado |
| R3 | O teto de potência de um produto vem do **certificado dele**, não da regra geral | Substituir "maior potência que a regra permite" por: potência = mínimo entre (regra do perfil, **teto informado pelo integrador**, pedido da adaptação). O teto é obrigatório na inicialização |
| R4 | Radiação restrita não tem proteção contra interferência e deve cessar a emissão se causar interferência prejudicial | Oferecer uma chamada de silêncio imediato do transmissor e documentá-la. Escuta antes de transmitir como boa prática opcional |
| R5 | Em salto em frequência, o receptor deve acompanhar o transmissor | RF-48 é obrigatório. A entrada de nó novo escutando um canal fixo (RF-05b) fica registrada como dúvida a levar ao OCD |
| R6 | A classe de 250 kHz pode ter regra de ocupação diferente (na FCC tem); a densidade espectral pode limitar 1 W em BW 500 | Os dois itens ficam como campos da tabela regional, sem valor até verificação |
| R7 | A faixa 907,5–915 MHz não é permitida no Brasil | Tabela de canais própria (902–907,5 e 915–928 MHz). Não reaproveitar o plano US915 |
| R8 | Certificados da Anatel registram declaração do requerente sobre requisitos de segurança cibernética | A ausência de chave padrão (RF-53e) ajuda o integrador. Conferir o ato aplicável na hora de certificar |
| R9 | Posição GNSS em pacotes e registros pode ser dado pessoal quando ligada a uma pessoa | Posição desligada por padrão; quando ligada, vai cifrada. Orientação de LGPD na documentação dos ensaios |

### 3.3 Como tratar perfis regionais numa biblioteca de uso geral

- Cada perfil é uma tabela de dados com três campos de procedência: **fonte, data da conferência e estado** (`verificado` ou `nao_verificado`).
- Perfil não verificado funciona, mas gera aviso na compilação e na telemetria.
- A primeira versão publica **só o perfil Brasil**. US915, AU915 e EU868 entram quando alguém conferir a norma e assinar a tabela. O EU868 exige ciclo de trabalho, que o núcleo deve prever como campo desde já.
- Há três travas de compilação para produto: região fixa, antena fixa e teto de potência fixo.

### 3.4 Pendências regulatórias, por ordem

1. Ler a seção 10 do Anexo I do Ato nº 14.448 consolidado e preencher a tabela RF-46 com item e número.
2. Consultar um OCD sobre: LoRa 125 kHz em canal fixo após 6/10/2026; entrada de nó novo em rede com salto; classe de 250 kHz; densidade em BW 500.
3. Verificar a situação de homologação da Heltec V4 e o que vale para uso em desenvolvimento e ensaio de campo. Existe um caminho de declaração de conformidade para uso próprio; confirmar se ele se aplica a este caso.
4. Ler as duas patentes USPTO apontadas no documento 02 antes de qualquer alegação de novidade.

---

## 4. Parecer de experiência de uso

O usuário é quem escreve firmware. A "interface" é a API, as mensagens de erro, os exemplos, a telemetria e a documentação.

### 4.1 Perfis de usuário

| Perfil | O que quer | O que o faz desistir |
|---|---|---|
| Integrador Arduino | Dois nós conversando em minutos | Configurar pinos, região e chave sem exemplo pronto |
| Desenvolvedor de produto (ESP-IDF, nRF) | Controle, previsibilidade, consumo documentado | Comportamento "mágico" que não dá para travar ou auditar |
| Pesquisador de campo | Dados comparáveis e parâmetros fixos | Adaptação mudando o ensaio no meio |
| Quem porta para outra placa | Lista curta e clara do que implementar | Camada de porte grande ou mal documentada |

### 4.2 O que fazer

| # | Diretriz | Como |
|---|---|---|
| U1 | **Primeiro enlace em cerca de 10 linhas** | `init(placa, região, chave, teto de potência)`, `send()`, callback de recepção, `process()` no laço. Pinos por arquivo de placa, fora do núcleo |
| U2 | **API em três níveis** | Básico (enviar e receber), intermediário (perfis de energia, antena, relay), avançado (travar parâmetros, política de adaptação, provedor de chaves) |
| U3 | **Estado sempre consultável** | `status()` devolve estado (procurando, no modo base, negociando, em dados, degradado, silenciado) e o motivo. Eventos de mudança de estado por callback |
| U4 | **Recusas explicadas** | Códigos específicos: sem chave, tempo no ar excede a ocupação, potência limitada pelo teto, modo fora do perfil regional. Cada código com uma linha de "o que fazer" |
| U5 | **Expectativa de tempo explícita** | Entrar numa rede com salto pode levar cerca de um ciclo (~20 s). O exemplo mostra o progresso em vez de parecer travado |
| U6 | **Chave difícil de errar** | Gerador de chave incluído. A chave dos exemplos é reconhecida pela biblioteca, que avisa na telemetria e se recusa a usá-la em compilação de produto |
| U7 | **Modo de ensaio de primeira classe** | Um exemplo "ensaio de campo" que trava parâmetros, registra por pacote e identifica a antena |
| U8 | **Telemetria legível por humano e por ferramenta** | Nível resumo com uma linha curta por evento importante; nível completo em JSON por linha. Versão do formato em cada linha |
| U9 | **Nunca bloquear** | Nenhuma chamada espera o rádio. Tudo é por evento, com tarefa RTOS opcional |
| U10 | **Documentação bilíngue** | API e código em inglês; guia rápido, glossário e solução de problemas em português e inglês. Diagrama da máquina de estados e do rollback |
| U11 | **Consumo e tamanho publicados** | Tabela de RAM e flash por combinação de recursos, gerada pela integração contínua |
| U12 | **Versões separadas** | Versão da API (semântica) e versão do protocolo no ar, com regra de compatibilidade escrita |

### 4.3 O que evitar na experiência

- Adaptação que não pode ser desligada ou observada.
- Falha silenciosa: nó que não transmite e não diz por quê.
- Exemplos que só funcionam na placa de referência.
- Nomes de API misturando português e inglês.
- Interface de pareamento, telas ou menus dentro da biblioteca (ficam com a aplicação).

---

## 5. Decisões consolidadas

### 5.1 Fazer na primeira versão

- Enlace **par a par** com DATA/ACK, fragmentação, cripto autenticada e contador contra repetição.
- Negociação PROPOSE/VOTE/COMMIT com troca em instante combinado, janela de validação, âncora persistida e rollback em degraus.
- Adaptação de SF e potência, com histerese assimétrica; BW e CR em seguida.
- Perfil Brasil com salto em frequência como padrão, teto de potência do integrador e tabela de canais própria.
- Driver SX1262, camada de porte, simulador no PC, telemetria JSON.
- Pacotes Arduino, PlatformIO e componente ESP-IDF.

### 5.2 Fazer depois, atrás de chave de compilação

| Recurso | Condição para entrar |
|---|---|
| Grupos de até 4 nós e subgrupos por canal | Par estável em campo |
| Multi-salto por inundação controlada | Grupos funcionando; contenção por SNR implementada |
| Next-hop aprendido e vetor de distância | Dados de campo do flooding |
| Driver SX127x e porte nRF52 | Protocolo congelado na versão 1 |
| Varredura CAD multimodo (RF-10) | Medição de falso despertar no SX1262 |
| GNSS, PPS e registros de ensaio georreferenciados | Módulo separado; não bloqueia o núcleo |
| Perfis de outras regiões | Tabela conferida e assinada por alguém |
| Chaves por grupo | Já previsto pelo provedor de chaves (RF-53h) |
| Adaptação por distância (RF-74) | Só se os dados mostrarem ganho; a literatura indica que distância sozinha não determina o SNR |

### 5.3 Não fazer

| Não fazer | Motivo |
|---|---|
| Compatibilidade com LoRaWAN | Decisão 5; mudaria todo o desenho |
| Chave padrão, chave derivada do MAC, pareamento embutido | Segurança e escopo |
| Unanimidade em grupos grandes | Sucesso cai para ~39% com 4 nós e 10% de perda |
| Subgrupos de SFs diferentes no mesmo canal | SFs não são independentes |
| Buscar "o máximo legal" por conta própria | A conformidade é do produto; usar teto do integrador |
| Afirmar que a biblioteca é legal, certificada ou homologada | Só o produto pode ser |
| Publicar perfil regional sem fonte conferida como se fosse confiável | Risco para quem usa |
| Trocar região, antena ou teto em tempo de execução num produto | Res. 680, Art. 6º, e teto do certificado |
| Aprendizado por reforço sobre os 5 parâmetros na primeira versão | Convergência lenta e custo não medido em MCU |
| Escrever os dois drivers ao mesmo tempo | Dobra o custo antes de o protocolo estabilizar |
| Depender de GNSS ou PPS no núcleo | Desnecessário na maioria dos casos |
| Usar o SNR máximo ou instantâneo para decidir | Abre a porta para manipulação e oscilação |
| PROBE dedicado no perfil bateria | Custa centenas de mJ em SF alto |
| Transmitir em bancada sem antena, sem carga ou em potência alta irradiada | Risco ao hardware e de interferência |
| Posição GNSS ligada por padrão ou em claro | Privacidade |
| Dizer "primeira a adaptar parâmetros por par" | O AURORA veio antes; a alegação correta é a combinação com rollback |
| Alocação dinâmica, dependência de um RTOS ou de biblioteca de terceiros no núcleo | RNF-01, RNF-03 |

---

## 6. Código livre: licença, nome e governança

| Tema | Recomendação | Alternativa e custo |
|---|---|---|
| Licença do código | **Apache-2.0**: permissiva, aceita uso em produto fechado e traz concessão explícita de patentes, útil dado que há patentes próximas ainda não lidas | MIT é mais curta, mas sem cláusula de patentes. GPL/LGPL dificulta o uso em firmware comercial e contraria o "uso geral" |
| Especificação, documentação e tabelas regionais | CC BY 4.0 | — |
| Dados de ensaio | CC BY 4.0, com posições revisadas antes de publicar | — |
| Nome | Manter "AdaptLoRa" como provisório. Existe um esquema acadêmico "AdapLoRa"; conferir conflito e registros (GitHub, PlatformIO, Arduino, ESP Component Registry) antes da primeira publicação | Trocar o nome antes da versão 0.1 custa pouco; depois custa muito |
| Marca LoRa | "LoRa" é marca da Semtech. Conferir as regras de uso de marca antes de fixar o nome | — |
| Contribuições | DCO (assinatura no commit), guia de contribuição, código de conduta, política de divulgação de falhas de segurança | CLA é mais pesado e afasta contribuidores |
| Dependências | Núcleo sem terceiros. AES próprio pequeno ou de licença compatível, com aceleração por hardware via camada de porte | — |

A escolha de licença é decisão do autor; vale uma conferência jurídica se houver intenção comercial.

---

## 7. Arquitetura proposta

```
aplicação
   │  API pública (C) + casca C++ Arduino
┌──┴───────────────────────────────────────────┐
│ núcleo (C99, sem E/S, testável no PC)        │
│  enlace: DATA/ACK, fragmentação, métricas    │
│  acordo: PROPOSE/VOTE/COMMIT, âncora, rollback│
│  adaptação: política, histerese, sondagem    │
│  agenda: modo base, janelas, salto           │
│  regulação: perfil regional, ToA, teto       │
│  segurança: AEAD, contador, provedor de chave│
│  telemetria: eventos → JSON                  │
└──┬───────────────────────┬───────────────────┘
   │ interface de rádio    │ camada de porte
   │ (SX126x, SX127x,      │ (SPI, GPIO, IRQ, relógio,
   │  simulado, RadioLib)  │  NVM, aleatório, AES opc.)
```

Estrutura de repositório sugerida:

```
/spec        formato de pacote, máquinas de estado, perfis (fonte da verdade)
/core        núcleo C99
/radio       sx126x/, sx127x/, sim/, radiolib_adapter/
/port        arduino/, espidf/, nrf/, posix/
/boards      heltec_v4/ ...
/regions     br.yaml (com fonte e estado), gerador de tabela C
/tools       gerador de chave, calculadora de ToA, juntador de registros
/sim         simulador multi-nó com canal configurável
/tests       unit/, sim/, hil/
/examples    ola_mundo, sensor_bateria, ensaio_de_campo, relay
/docs        guia rápido (pt/en), glossário, solução de problemas
```

---

## 8. Roteiro por fases

> **Atualização de 15/11/2026 (escopo dos repositórios).** Os experimentos práticos com as placas Heltec e o firmware
> (driver SX1262, porte ESP32-S3, exemplos, bancada) passam para um **repositório separado**, criado depois com
> `/anthropic-skills:aiclp-kit-bancada-vm`. Este repositório fica com protocolo, especificação, simulação e a
> referência do núcleo C99. A coluna "Onde" abaixo marca cada fase; detalhes e o contrato entre os repositórios em
> `docs/09`. As seções 8 (partes de hardware) e 9 deste documento valem agora para o repositório de bancada.

Cada fase só fecha quando o critério de saída é medido.

| Fase | Onde | Entrega | Critério de saída |
|---|---|---|---|
| **0. Fundação** | aqui (feita, falta só a licença) | Especificação do pacote (v0), interface de rádio e de porte, repositório com licença e integração contínua, simulador mínimo | Dois nós virtuais trocam DATA/ACK no PC; orçamento dos 24 bytes fechado |
| **1. Enlace fixo** | bancada (repo novo); codec e contador de referência aqui | Driver SX1262, porte ESP32, cripto, contador, fragmentação, telemetria, calculadora de ToA | Par de Heltec V4 por cabo e atenuadores; taxa de entrega e ToA medidos batem com o cálculo |
| **2. Acordo e rollback** | simulador e núcleo C aqui; bancada para o reinício forçado | PROPOSE/VOTE/COMMIT, instante combinado, validação, âncora em NVM, retorno ao modo base | No simulador, com perda de 0 a 50% em cada mensagem, **nenhum cenário termina com os nós em modos diferentes sem recuperação**. Na bancada, o mesmo com atenuador variável e reinício forçado no meio da troca |
| **3. Adaptação** | simulação aqui (F7 sintonia); confirmação na bancada | Tabela SNR→SF, média móvel, histerese assimétrica, sondagem, potência; depois BW e CR | Com atenuação variando em degraus, o par converge sem oscilar e degrada em poucos pacotes; limite de trocas respeitado |
| **4. Salto e perfil Brasil** | tabela, sequência e verificador aqui; SDR e tempos reais na bancada | Tabela de canais BR, sequência derivada da chave, sincronismo por beacon, entrada de nó novo, teto de potência | Tempo de entrada e taxa de perda de sincronismo medidos; nenhum pacote excede a ocupação por canal; sequência conferida com receptor SDR |
| **5. Energia e agenda** | modelo aqui; medição de consumo na bancada | Perfis de energia, janelas de encontro, sono profundo, CAD com preâmbulo longo | Consumo por ciclo medido no SX1262 e no ESP32-S3; nó que dorme reencontra o par pela ordem dados → âncora → base |
| **6. Grupos e multi-salto** | modelos T2–T6 aqui; 3 e 4 placas na bancada | Grupo de até 4, subgrupos por canal, inundação controlada com jitter e contenção | Três e quatro nós em bancada; taxa de sucesso do acordo medida contra a prevista; relay ligado e desligado em uso |
| **7. Versão 1.0** | repositório de firmware (portes, pacotes, exemplos); protocolo congelado aqui | SX127x, porte nRF52, pacotes, documentação bilíngue, tabela de RAM/flash | Exemplo "olá mundo" funcionando em três plataformas; protocolo congelado |

Trilhas paralelas, do início ao fim: pendências regulatórias (seção 3.4), campanha de campo em 915 MHz (resultado científico mais original, segundo o documento 02) e correções nos documentos 01 e 02 (seção 10).

---

## 9. Insumos para a bancada (`/aiclp-kit-bancada-vm`)

### 9.1 Dados do projeto para o kit

| Campo | Valor |
|---|---|
| Projeto | AdaptLoRa, biblioteca C99 de comunicação LoRa P2P adaptativa |
| Placas | Heltec WiFi LoRa 32 V4 (ESP32-S3 + SX1262, até 28 dBm), via USB |
| Quantidade | Mínimo 2 (fases 1 a 5); 4 para grupos e relay (fase 6) |
| Periféricos | GNSS Quectel L76K (só para o módulo opcional) |
| Faixa | 915 MHz (902–907,5 e 915–928 MHz) |
| Ferramentas | PlatformIO e ESP-IDF; compilador nativo para testes no PC; Python para ferramentas |
| Saída das placas | Telemetria JSON por linha na serial |
| Licença | Apache-2.0 (proposta) |

### 9.2 Material de RF para ensaio conduzido

- Atenuadores fixos SMA que suportem a potência da placa (28 dBm ≈ 0,63 W; usar atenuadores de 2 W ou mais no primeiro estágio).
- Atenuador variável (por passos ou programável) para simular o enlace piorando e melhorando.
- Divisor/combinador para ligar 3 ou 4 nós por cabo.
- Cargas de 50 Ω para portas sem uso.
- Receptor SDR simples, só para conferir canais e sequência de salto. **Não substitui laboratório** para largura de 6 dB, densidade espectral ou espúrios.
- Medidor de consumo para a fase 5.

### 9.3 Camadas de teste

| Camada | Onde roda | O que prova |
|---|---|---|
| T0 Unidade | VM, sem placa | ToA, cabeçalhos, cripto, contador, tabela regional |
| T1 Simulação multi-nó | VM, sem placa | Acordo, rollback, histerese, grupos, com perda e SNR injetados e semente fixa |
| T2 Placa na bancada, sinal por cabo | VM + placas USB + atenuadores | Driver, tempos reais, NVM, reinício no meio da troca, consumo |
| T3 Campo | Fora da bancada | Alcance, salto em frequência a potência plena, obstáculos |

### 9.4 Necessidades da VM

- Repasse USB estável e nomes fixos por número de série de cada placa (regra udev), para saber qual nó é qual.
- Gravação e reinício de cada placa por comando, sem intervenção manual.
- Coletor que lê as seriais em paralelo, carimba o horário e junta os registros por identificador de nó.
- Controle do atenuador variável por script, se for programável.
- Injeção de falhas: reiniciar uma placa em instante definido; cortar alimentação USB de uma porta, se o hub permitir.

### 9.5 Regras de segurança da bancada

1. Nunca transmitir com a porta de antena aberta: sempre antena, carga ou atenuador.
2. Ensaio de bancada é por cabo, com a menor potência que sirva ao teste.
3. Firmware de bancada com teto de potência baixo fixado na compilação; potência plena só em compilação de campo.
4. Chaves de teste nunca vão para o repositório.
5. Qualquer transmissão irradiada segue o perfil Brasil e a tabela de canais BR.

### 9.6 Do requisito ao teste (amostra)

| Requisito | Camada | Teste |
|---|---|---|
| RF-21, RF-22 | T1, T2 | Perder cada mensagem do acordo, uma por vez, e verificar o estado final dos dois nós |
| RF-24 a RF-28 | T1, T2 | Reiniciar um nó antes, durante e depois do instante de troca |
| RF-35 | T1, T2 | Atenuação em serra e em degrau; contar trocas |
| RF-40, RF-47 | T0 | ToA calculado contra medido; recusa quando excede a ocupação |
| RF-52 | T0, T2 | Repetir pacote gravado; reiniciar e verificar que o contador não regride |
| RF-53e | T0 | Sem chave e sem modo aberto, nenhuma transmissão |
| RF-05b, RF-48 | T2, T3 | Tempo de entrada de nó novo; perda de sincronismo após N minutos sem beacon |

---

## 10. Correções a aplicar nos documentos anteriores

| Documento | Onde | Ajuste |
|---|---|---|
| 01 | §1, item 7; RF-44; decisão 15 | Trocar "opera no limite que a lei permite" por "nunca excede o teto informado pelo integrador nem o perfil regional" |
| 01 | RF-21, RF-09 | Limitar unanimidade a pares e grupos de até 4; subgrupos por canal |
| 01 | RF-35 | Histerese assimétrica, SNR filtrado, um passo por vez, limite de trocas |
| 01 | RF-64 | Troca de antena em execução só em compilação de ensaio |
| 01 | §5.9, nota de atenção | Citar Art. 11, III do Ato 14.158 e o Ato 4.746, agora confirmados no portal; manter a leitura sobre LoRa como interpretação |
| 01 | §9.1, §9.3 | Correções de atribuição já listadas no documento 02; registrar o "AdapLoRa" |
| 01 | §10 | Reabrir questões: licença, nome, orçamento de bytes, pendências regulatórias |
| 02 | Seção regulatória | Atualizar: os Atos 14.158 e 4.746 foram conferidos na fonte oficial; a seção 10 do Ato 14.448 ainda não |

---

## 11. Questões para o autor decidir

1. Licença: Apache-2.0, como proposto?
2. Nome: manter AdaptLoRa apesar do "AdapLoRa" acadêmico?
3. Aceita a ordem de trabalho com canal fixo BW 500 nas fases 1 a 3, mantendo o salto como padrão da versão publicada?
4. MIC de 4 bytes no modo base é aceitável, dado o limite de 24 bytes?
5. Quantas placas e qual material de RF já estão disponíveis para a bancada?
6. Haverá consulta formal a um OCD antes da fase 4?

---

## Fontes desta revisão

- [Ato nº 14.158/2025, Anatel](https://informacoes.anatel.gov.br/legislacao/component/content/article/169-atos-de-certificacao-de-produtos/2025/2070-ato-14158)
- [Ato nº 4.746/2026, Anatel](https://informacoes.anatel.gov.br/legislacao/atos-de-certificacao-de-produtos/2026/2132-ato-4746)
- [Resolução nº 680/2017, Anatel](https://informacoes.anatel.gov.br/legislacao/index.php/component/content/article?id=936)
- [GMA Labs: regra de 500 kHz](https://www.gmalabs.com/post/brazil-anatel-restricted-radiation-equipment-500-khz-rule)
- Documentos 01 e 02 do projeto, com as fontes neles citadas
