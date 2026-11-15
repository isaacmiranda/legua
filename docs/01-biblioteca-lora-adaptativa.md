# Ideia 01: Biblioteca de comunicação adaptativa sobre LoRa

> Nome: **AdaptLoRa** (provisório, aceito; ver §9.1)
> Tipo: software (biblioteca embarcada multiplataforma para rádios Semtech SX12xx)
> Status: rascunho para especificação (SDD), revisão 3

---

## 1. Visão geral

Hoje, cada projeto que usa LoRa fixa na mão os parâmetros de rádio: spreading factor (SF), largura de banda (BW), coding rate (CR), potência e frequência. Essa escolha fixa quase nunca é a melhor para todas as situações. Um nó perto do outro gasta bateria à toa com SF12 e muito tempo no ar. Um nó distante perde pacotes se usar SF7 com banda larga.

A **AdaptLoRa** é uma biblioteca que pode ser reaproveitada em qualquer projeto, em qualquer plataforma embarcada e com qualquer antena. Ela:

1. **Separa o conteúdo da configuração.** Todo pacote tem duas partes: um *payload genérico*, com os dados da aplicação, que a biblioteca não interpreta, e um *bloco de configuração*, com os metadados de enlace.
2. **Torna cada nó autônomo** para descobrir vizinhos e negociar o melhor modo de enlace com eles, seja a rede ponto a ponto, ponto-multiponto ou multiponto-multiponto.
3. **Parte sempre de um modo inicial comum**, conhecido por todos, e só depois negocia modos melhores.
4. **Decide por acordo entre todos os participantes do enlace.** Nenhum nó tem a palavra final sozinho.
5. **Adapta-se continuamente** às condições do enlace e ao perfil de energia de cada nó. A meta é a **maior taxa de entrega** e a **menor perda de pacotes**, trocando vazão por alcance, ou alcance por vazão, conforme o momento.
6. **Sempre tem um caminho de volta:** toda mudança é combinada antes e, se der errado, os nós fazem rollback para o último estado que garantia o enlace.
7. **Opera no limite que a lei permite** em cada região, escolhendo automaticamente o enquadramento regulatório que libera mais potência para os parâmetros em uso.
8. **É segura por padrão:** mensagens de negociação são sempre autenticadas.
9. **Não depende da antena.** A antena é só um parâmetro de configuração (ganho e perdas), usado no cálculo da potência legal e registrado na telemetria.
10. **Multi-salto selecionável:** cada nó pode ligar ou desligar o encaminhamento de pacotes durante o uso.
11. **Exporta telemetria** de forma simples, para ferramentas de diagnóstico e visualização.

**Objetivo principal:** garantir a comunicação e escolher, a cada momento, a forma de transmissão mais adequada, de modo adaptativo.

---

## 2. Público e contexto

- **Quem usa:** desenvolvedores de firmware que precisam de comunicação LoRa **estritamente P2P**, sem LoRaWAN, em qualquer microcontrolador ligado a um rádio SX12xx.
- **Plataformas-alvo:** Arduino (vários cores), ESP32 (Arduino e ESP-IDF), Nordic nRF52 e outras, por meio de uma camada de porte mínima.
- **Rádios-alvo:** família Semtech SX12xx: SX126x (SX1261/62/68), SX127x (SX1276/77/78) e compatíveis (ex.: LLCC68).
- **Antenas:** qualquer uma. Nada na biblioteca depende do tipo de antena.
- **Cenários típicos:**
  - Sensores a bateria que acordam, transmitem e voltam a dormir.
  - Equipamentos de bancada ou ligados na tomada, que podem priorizar vazão e latência.
  - Enlaces de dezenas de metros a vários quilômetros, com obstáculos variáveis.
  - Aplicações rurais, industriais e de monitoramento ambiental.
- **Região:** funciona em qualquer região, com **foco no Brasil**.

### 2.1 Plataforma de hardware de referência (ensaios)

- **Placas:** várias **Heltec WiFi LoRa 32 (V4)**, com ESP32-S3 e rádio Semtech **SX1262** (até 28 dBm).
- **GNSS:** módulo **Quectel L76K** ligado ao conector GNSS dedicado da V4. Todos os nós dos ensaios usam o mesmo conjunto, sem misturar modelos.
- **Faixa:** **915 MHz** (dentro das faixas brasileiras 902–907,5 MHz e 915–928 MHz).
- **Antena inicial:** **dipolo de meia onda** sintonizado para 915 MHz (cerca de 16 cm de comprimento total, ganho típico de ~2,15 dBi). A comparação entre antenas será feita pelo autor como atividade separada, usando a telemetria da biblioteca.
- A plataforma de referência é só para ensaios. A biblioteca não pode depender dela.

---

## 3. Conceitos centrais

| Conceito | Definição |
|---|---|
| **Payload genérico** | Os bytes da aplicação. A biblioteca não interpreta o conteúdo; ela só transporta, fragmenta e remonta. |
| **Bloco de configuração** | Cabeçalho próprio da biblioteca: versão do protocolo, origem e destino, tipo de pacote, número de sequência, fragmentação, saltos e parâmetros de rádio propostos ou aceitos. |
| **Parâmetros de rádio** | SF (7 a 12, conforme o chip), BW (ex.: 125/250/500 kHz), CR (4/5 a 4/8), potência de TX, frequência/canal, preâmbulo, palavra de sincronismo. |
| **Perfil de nó** | Capacidades e restrições de um nó: energia, chip de rádio, parâmetros suportados, perfil de antena, tamanho máximo de payload e prioridade (energia × vazão × alcance). |
| **Perfil de antena** | Descrição da antena instalada: identificador, tipo, ganho (dBi), perda de cabo e conectores (dB) e observações. Usado no cálculo de potência e na telemetria. |
| **Modo base (inicial)** | Configuração robusta, conhecida por todos e definida pelo perfil regional. Todo nó começa nele, e ele é usado para descoberta, controle e recuperação. |
| **Grupo de enlace** | Conjunto de nós que compartilham um mesmo modo de dados: 2 nós em ponto a ponto, ou vários em ponto-multiponto e multiponto-multiponto. |
| **Modo de dados** | O modo de rádio otimizado e negociado para um grupo de enlace. |
| **Agenda de escuta** | Divisão do tempo de um nó entre o modo base e os modos de dados dos grupos de que ele participa. |
| **Negociação por acordo** | Processo em que *todos os participantes de um grupo de enlace* propõem, avaliam e confirmam um modo de dados. Um modo só vale depois que todos confirmam. |
| **Estado confiável (âncora)** | O último modo de dados que funcionou comprovadamente no grupo. É o destino do rollback. |
| **Métricas de enlace** | RSSI, SNR, taxa de entrega (ACKs recebidos / enviados), latência, retransmissões e perdas consecutivas. |
| **Margem de enlace** | Diferença entre o SNR medido e o SNR mínimo exigido pelo SF atual. É o principal sinal para decidir se dá para acelerar ou se é preciso ganhar robustez. |
| **Tempo no ar (ToA)** | Duração de um pacote no ar. Cresce com o SF, com o tamanho do pacote e com a redução da BW. |
| **Perfil regional** | Faixas de frequência, potências máximas e regras de cada enquadramento regulatório de um país. |
| **Enquadramento regulatório** | A regra legal sob a qual uma transmissão se encaixa (ex.: modulação digital de banda larga, salto em frequência, sistema híbrido, baixa potência). Cada um tem limites próprios de potência e ocupação. |
| **Relay (encaminhador)** | Nó com o multi-salto ligado, que repassa pacotes destinados a outros nós. |
| **Telemetria** | Eventos estruturados que a biblioteca gera para diagnóstico e visualização. |
| **Pacote estático / dinâmico** | Estático: formato e tamanho fixos, conhecidos de antemão. Dinâmico: tamanho variável, que pode precisar de fragmentação. |

---

## 4. Escopo

### Dentro do escopo
- Biblioteca **portável** e **leve**: drivers próprios para SX126x e SX127x e uma camada de porte mínima (SPI, GPIO, interrupção, relógio, armazenamento não volátil).
- Comunicação **estritamente P2P** (sem LoRaWAN).
- **Ponto a ponto, ponto-multiponto e multiponto-multiponto**, com cada nó negociando de forma independente.
- **Modo base** sempre disponível como ponto de partida.
- **Multi-salto selecionável** em tempo de execução.
- Formato de pacote versionado: payload + bloco de configuração.
- Descoberta, negociação por acordo, confirmação e **rollback**.
- Adaptação de SF, BW, CR, potência e canal em tempo de execução.
- Fragmentação e remontagem.
- **Perfis regionais** que operam no máximo permitido por lei, com o Brasil como padrão.
- **Segurança por padrão:** autenticação obrigatória das mensagens de controle e criptografia dos dados ligada por padrão.
- **Independência de antena** e suporte a ensaios comparativos de antenas.
- Perfis de energia: bateria, bancada, máximo alcance e equilibrado.
- **Telemetria** simples para diagnóstico e visualização.
- Módulo opcional de georreferenciamento para ensaios de campo.

### Fora do escopo
- Compatibilidade com LoRaWAN, nem agora nem como objetivo futuro.
- Interpretação ou serialização do conteúdo do payload (fica a cargo da aplicação).
- Outros rádios (Wi-Fi, BLE, FSK puro) e chips fora da família SX12xx, na versão inicial.
- As ferramentas de diagnóstico e visualização em si (podem virar outra ideia do conjunto).

---

## 5. Requisitos

### 5.1 Formato de pacote
- **RF-01** Todo pacote deve ter um bloco de configuração seguido do payload genérico.
- **RF-02** O bloco de configuração deve ter um campo de versão, para o protocolo evoluir sem quebrar nós antigos.
- **RF-03** Tipos de pacote mínimos: `DATA`, `ACK`, `BEACON`, `HELLO`, `PROPOSE`, `VOTE`, `COMMIT`, `ROLLBACK`, `PROBE`, `HEARTBEAT`.
- **RF-04** O cabeçalho deve ser o menor possível, já que cada byte aumenta o tempo no ar. Campos opcionais (posição, saltos, autenticação) só entram quando usados, indicados por flags.

### 5.2 Modo base e agenda de escuta

Com um único rádio, um nó só recebe um modo por vez. A solução adotada combina um **modo base comum** com **modos de dados por grupo de enlace** e uma **agenda de escuta** combinada entre os nós. Ela funciona da mesma forma nos três cenários:

| Cenário | Como funciona |
|---|---|
| **Ponto a ponto** | O par sai do modo base, negocia um modo de dados exclusivo e passa a maior parte do tempo nele. Volta ao modo base só nas janelas de encontro. |
| **Ponto-multiponto** | O nó central e os nós periféricos formam um grupo. Se todos alcançam o mesmo modo, usa-se um modo de dados único, limitado pelo membro com pior enlace. Se a diferença entre os membros for grande, o grupo se divide em subgrupos (ex.: nós próximos em SF7 e distantes em SF11), e o nó central alterna entre eles pela agenda. |
| **Multiponto-multiponto** | Cada nó pode participar de vários grupos. A agenda de escuta divide o tempo entre os grupos e o modo base, com janelas combinadas na negociação. |

- **RF-05** Todo nó **começa no modo base**, definido pelo perfil regional e igual para todos os nós da rede.
- **RF-05a** O modo base pode ser configurado em **qualquer modo LoRa suportado pelo chip SX12xx** e em qualquer enquadramento regulatório do perfil regional: canal fixo com baixa potência, salto em frequência, sistema híbrido ou banda larga (BW 500 kHz). O perfil regional define o padrão, e a aplicação pode trocá-lo.
- **RF-05b** Quando o modo base usa **salto em frequência**, um nó novo entra na rede escutando um único canal da sequência até receber um beacon. Como a rede passa por todos os canais num ciclo completo (no Brasil, ≥ 50 canais × 0,4 s ≈ 20 s), o tempo de entrada fica limitado a cerca de um ciclo. O beacon informa a posição atual na sequência, e o nó passa a saltar junto.
- **RF-05d** **Modo base padrão do perfil Brasil**, escolhido para o pior caso (grande distância e muitos obstáculos): **salto em frequência, BW 125 kHz, SF10, CR 4/5, potência máxima legal**. Justificativa:
  - No pior caso, o que mais pesa é o **orçamento de enlace**. O canal fixo com baixa potência perde cerca de **30 dB** de potência em relação ao enquadramento de 1 W, o que nenhum SF compensa (cada passo de SF vale ~2,5 dB).
  - Com salto em frequência, cada pacote precisa caber em **0,4 s** por canal. Na BW 125 kHz, o maior SF que cabe é o **SF10**: um pacote de 24 bytes leva ~0,37 s. O SF11 já passa do limite (~0,82 s), mesmo com pacotes curtos.
  - Por isso, os pacotes do modo base (`BEACON`, `HELLO`, controle) devem ter **no máximo ~24 bytes**, incluindo a autenticação.
  - O custo é o tempo de entrada de um nó novo: até um ciclo de saltos (~20 s), aceitável para um modo de recuperação.

  Tempo no ar de referência (CR 4/5, preâmbulo de 8 símbolos, cabeçalho explícito, CRC ligado):

| BW | SF | 16 bytes | 24 bytes | 32 bytes | Cabe em 0,4 s? |
|---|---|---|---|---|---|
| 125 kHz | 10 | 330 ms | 371 ms | 453 ms | Sim, até ~24 bytes |
| 125 kHz | 11 | 659 ms | 823 ms | 987 ms | Não |
| 250 kHz | 11 | 289 ms | 371 ms | 412 ms | Sim, até ~24 bytes |
| 500 kHz | 12 | 289 ms | 330 ms | 412 ms | Sim, até ~24 bytes |

- **RF-05e** **Decisão conservadora:** o padrão permanece **salto em frequência com SF10/BW 125 kHz**. Ele não depende de medições de laboratório, se enquadra em regras de salto em frequência adotadas em várias regiões e funciona com todos os chips SX12xx. O SF12 com BW 500 kHz, que dispensaria o salto, **não será usado como padrão**: ele depende de confirmar a largura de banda de 6 dB com analisador de espectro. Continua disponível como configuração manual, sob responsabilidade de quem a escolher.
- **RF-05c** Todos os nós de uma mesma rede devem usar a mesma configuração de modo base. Um nó com modo base diferente simplesmente não encontra a rede (e isso gera um evento de telemetria quando detectado).
- **RF-06** O modo base é usado para: descoberta (`BEACON`, `HELLO`), mensagens de controle (`PROPOSE`, `VOTE`, `COMMIT`, `ROLLBACK`) e recuperação.
- **RF-07** Todo nó deve visitar o modo base periodicamente, em **janelas de encontro** de duração e período configuráveis, para que nós novos ou perdidos sempre consigam se reconectar.
- **RF-08** O nó mantém uma **agenda de escuta** que reparte o tempo entre o modo base e os modos de dados de cada grupo do qual participa. As janelas de cada grupo são combinadas na negociação.
- **RF-09** O modo de dados de um grupo com vários nós é escolhido pelo **membro com pior enlace**, a menos que o grupo decida se dividir.
- **RF-10** Opcional: nos chips que suportam detecção de atividade no canal (CAD), o nó pode **varrer rapidamente** vários modos para detectar preâmbulos, reduzindo a necessidade de janelas fixas.
- **RF-11** A sincronização das janelas usa o relógio local corrigido pelos beacons. Quando houver GNSS, o pulso PPS pode ser usado para uma sincronização mais precisa.

### 5.3 Topologia e multi-salto
- **RF-12** Cada nó deve funcionar de forma independente: descobrir vizinhos, manter as métricas de cada vizinho e negociar modos de enlace sem coordenador central.
- **RF-13** A topologia é consequência dos grupos de enlace que os nós formam, não uma configuração fixa.
- **RF-14** O **multi-salto é selecionável durante o uso**, nó a nó: cada nó pode ser só ponto final ou também relay, e isso pode mudar em tempo de execução, sem reiniciar.
- **RF-15** A aplicação também pode definir, por mensagem, o **limite de saltos** (0 = só vizinhos diretos).
- **RF-16** Primeira versão do encaminhamento: inundação controlada (limite de saltos + descarte de duplicatas). Versão posterior: roteamento por vetor de distância, usando as métricas de enlace como custo.
- **RF-17** Um relay só encaminha pacotes autenticados (ver §5.10).

### 5.4 Negociação por acordo
- **RF-18** Ao encontrar vizinhos no modo base, cada nó envia seu **perfil de nó** (`HELLO`).
- **RF-19** Qualquer participante pode **propor** um novo modo de dados (`PROPOSE`), com base nas métricas e nos perfis de todos.
- **RF-20** Cada participante **avalia e vota** (`VOTE`), considerando as próprias restrições (energia, suporte do chip, perfil regional).
- **RF-21** O modo só é adotado com a **confirmação de todos os participantes do grupo** (`COMMIT`). Se alguém recusar ou não responder no prazo, a proposta é descartada e o modo atual continua valendo.
- **RF-22** A troca acontece **num momento combinado** no `COMMIT`, para que todos mudem juntos.
- **RF-23** Propostas simultâneas são desempatadas por uma regra determinística (ex.: menor identificador de nó).

### 5.5 Rollback e recuperação
- **RF-24** Cada nó guarda o **estado confiável (âncora)** de cada grupo em memória não volátil, para que ele sobreviva a reinícios e ao deep sleep.
- **RF-25** Depois de uma troca, existe uma **janela de validação**. Se a comunicação não for confirmada dentro dela, todos voltam automaticamente à âncora, sem nova negociação.
- **RF-26** Se a âncora também falhar, os nós voltam ao **modo base** e reiniciam a descoberta.
- **RF-27** Um nó que acorda e não encontra o grupo no modo de dados tenta, nesta ordem: a âncora e depois o modo base. Assim, nós dormindo nunca ficam perdidos.
- **RF-28** Uma mudança só vira a nova âncora depois de passar pela janela de validação com sucesso.

### 5.6 Adaptação
- **RF-29** A biblioteca mede continuamente as métricas de enlace de cada vizinho.
- **RF-30** **Acelerar** (SF menor e/ou BW maior) quando a margem estiver alta e estável.
- **RF-31** **Ganhar robustez** (SF maior, BW menor ou CR mais forte) quando houver perdas ou margem baixa.
- **RF-32** Antes de trocar, usar **sondagem** (`PROBE`) para estimar a taxa de entrega no modo candidato.
- **RF-33** Ajustar a **potência de transmissão** para o mínimo que mantenha a taxa de entrega desejada, sem passar do limite legal (ver §5.9).
- **RF-34** Trocar de **canal/frequência** quando um canal tiver perdas persistentes, sempre por negociação.
- **RF-35** Aplicar histerese, para o modo não ficar oscilando.
- **RF-36** Toda escolha de parâmetros deve respeitar o enquadramento regulatório (ex.: em modo de salto em frequência, nenhum pacote pode ultrapassar o tempo máximo de ocupação por canal).

### 5.7 Pacotes estáticos e dinâmicos
- **RF-37** Pacotes estáticos têm caminho rápido: sem fragmentação e com cabeçalho mínimo.
- **RF-38** Pacotes dinâmicos são fragmentados automaticamente quando passam do tamanho máximo negociado, com remontagem e descarte por tempo limite.
- **RF-39** O tamanho do fragmento é adaptativo: menor em enlaces ruins, com SF alto ou quando o tempo no ar de um pacote inteiro ultrapassaria o limite regulatório; maior em enlaces bons.
- **RF-40** A biblioteca calcula o tempo no ar antes de cada envio e adia ou fragmenta o envio quando necessário.

### 5.8 Energia e janelas de encontro

Os nós podem ou não ser alimentados por bateria, e a rede pode misturar os dois tipos. O perfil de energia de cada nó decide quanto tempo ele passa no modo base e quais papéis assume.

- **RF-41** Perfil *bateria*: minimizar o tempo com o rádio ligado, agrupar envios, usar ACK enxuto, janelas de encontro curtas e espaçadas e deep sleep, com o estado de enlace salvo entre os ciclos.
- **RF-42** Perfil *bancada/rede*: priorizar vazão e latência, com o receptor sempre escutando, heartbeats frequentes e disponibilidade para atuar como relay.
- **RF-42a** Valores iniciais das janelas de encontro (a calibrar nos ensaios):

| Perfil | Escuta no modo base | Beacons próprios | Papéis assumidos |
|---|---|---|---|
| **Bancada/rede** | Todo o tempo em que não estiver num modo de dados | Frequentes (referência de sincronia para a rede) | Âncora de sincronia, relay, guarda mensagens para nós dormindo |
| **Equilibrado** | Janela curta a cada ciclo de poucos segundos | Moderados | Relay opcional |
| **Bateria** | Janela curta só ao acordar, ou em intervalos longos | Raros, ou nenhum | Só ponto final |
| **Máximo alcance** | Igual ao perfil de energia de base do nó | Igual ao perfil de base | Igual ao perfil de base, com prioridade a modos robustos |

- **RF-42b** **Divisão de tarefas por energia:** nós ligados na rede assumem o trabalho mais caro (escutar o modo base o tempo todo, emitir beacons, encaminhar pacotes, guardar mensagens para nós dormindo). Nós a bateria se apoiam neles e podem dormir mais.
- **RF-42c** **Ajuste pela energia disponível, sem depender de hardware:** a biblioteca não lê bateria nem detecta USB/solar. Ela oferece uma chamada para a **aplicação informar** a fonte e o nível de energia (ex.: `set_power_state(BATERIA, 35%)`), e uma para trocar o perfil de energia. A aplicação decide se e quando informar. Exemplo de uso: ao ser ligado no USB, o nó passa a se comportar como bancada; com bateria baixa, reduz as janelas e deixa de ser relay.
- **RF-42d** O perfil de energia é anunciado aos vizinhos no `HELLO` e pesa na negociação: um grupo com um nó a bateria tende a modos com menos tempo no ar, mesmo que isso custe algum alcance.
- **RF-42e** Em redes só com nós a bateria (sem nenhum nó de bancada), os nós combinam na negociação um ciclo comum de acordar e dormir, para que as janelas de encontro coincidam.

### 5.9 Perfis regionais: operar no máximo permitido por lei

- **RF-43** Os perfis regionais são **tabelas de dados**, separadas do código. Cada perfil lista as faixas de frequência e, para cada enquadramento regulatório, os limites de potência conduzida, potência irradiada (EIRP), largura de banda, número mínimo de canais e tempo de ocupação.
- **RF-44** Para cada modo de dados candidato, a biblioteca **identifica em qual enquadramento ele se encaixa** e aplica a **maior potência que a regra permite**, descontado o ganho da antena (ver §5.12).
- **RF-45** Se um modo não se encaixar em nenhum enquadramento de alta potência, ele só pode ser usado no enquadramento de baixa potência, ou é descartado.
- **RF-46** **Perfil Brasil** (padrão). Faixas: 902–907,5 MHz e 915–928 MHz. Enquadramentos previstos na regulamentação de radiação restrita (Ato nº 14.448/2017, atualizado pelo Ato nº 14.158/2025):

| Enquadramento | Condição principal | Potência máxima | Uso típico no LoRa |
|---|---|---|---|
| **Modulação digital (banda larga)** | Largura de banda mínima de 6 dB de 500 kHz | 1 W conduzido, EIRP máx. 6 dBW (4 W) | BW = 500 kHz, se a medição comprovar a largura mínima |
| **Salto em frequência** | Mín. 50 frequências de salto; largura de 20 dB ≤ 500 kHz; ocupação ≤ 0,4 s a cada 20 s por canal | 1 W conduzido | BW 125/250 kHz saltando entre ≥ 50 canais nas duas faixas brasileiras |
| **Sistema híbrido** | Salto + modulação digital; ocupação ≤ 0,4 s × número de canais; densidade ≤ 8 dBm em 3 kHz | Conforme a regra | Menos canais que o salto puro, com controle da densidade de potência |
| **Baixa potência (genérico)** | Sem exigência de espalhamento | Muito baixa (limite de intensidade de campo) | Último recurso; ensaios de curto alcance |

  > **Atenção:** desde 6 de outubro de 2026, o LoRa com BW menor que 500 kHz em canal fixo não se enquadra mais na isenção de largura de banda para **novas certificações**. Na prática, para potência alta com BW 125/250 kHz, a biblioteca precisa operar com **salto em frequência**. Os valores da tabela devem ser conferidos no texto vigente dos atos da Anatel antes de fechar o perfil.

- **RF-47** **Consequência do salto em frequência:** como cada canal pode ser ocupado por no máximo 0,4 s, combinações lentas (SF alto com BW 125 kHz) podem exceder esse tempo mesmo com pacotes curtos. Nesses casos, a biblioteca deve fragmentar, mudar para BW maior ou escolher outro enquadramento.
- **RF-48** O salto em frequência exige que os nós sigam a **mesma sequência de canais, sincronizados**. A sequência é derivada da chave da rede, e a sincronização usa os beacons do modo base (e o PPS do GNSS, quando houver).
- **RF-49** Perfis para outras regiões (ex.: US915, AU915, EU868) podem ser adicionados sem alterar o núcleo.

### 5.10 Segurança: a opção mais segura

#### Por que as chaves são necessárias

O rádio é um meio aberto: qualquer pessoa com uma placa LoRa de R$ 100 na mesma faixa consegue ouvir e transmitir. Sem chaves, a biblioteca não tem como saber se uma mensagem veio de um nó legítimo. E, como os nós obedecem às mensagens de negociação, isso abre ataques sérios:

- **Sabotagem da negociação:** um intruso envia `PROPOSE`/`COMMIT` falsos e força todos os nós para um modo ruim, ou envia `ROLLBACK` repetidamente e impede a rede de se estabilizar. É uma negação de serviço barata.
- **Mensagens falsas:** o intruso injeta dados como se fosse um sensor ou um atuador legítimo.
- **Repetição (replay):** ele grava um pacote válido (ex.: "abrir válvula") e o retransmite depois.
- **Espionagem:** sem criptografia, qualquer um lê o conteúdo dos dados.
- **Salto em frequência previsível:** se a sequência de canais for pública, fica fácil interferir nela.

As chaves resolvem isso: a **autenticação** prova quem enviou e que nada foi alterado; a **criptografia** impede a leitura; o **contador** impede a repetição.

#### O cuidado com chaves derivadas do MAC

O endereço MAC e outras características do chip são **identificadores, não segredos**. O MAC aparece em transmissões Wi-Fi e Bluetooth e segue padrões conhecidos por fabricante. Se a chave fosse calculada só a partir dele, qualquer pessoa que descobrisse o MAC conseguiria calcular a mesma chave. Por isso o MAC (ou o ID único do chip) serve só como **identificador do nó**.

#### Modelo adotado: chaves fornecidas por quem usa a biblioteca

As chaves são definidas pelo **desenvolvedor que integra a biblioteca**, durante a gravação do firmware ou depois, por meios que ele mesmo cria. A biblioteca **não faz pareamento** e não impõe nenhuma interface de configuração.

#### Modos de segurança

| Modo | Como funciona | Quando usar |
|---|---|---|
| **Chave de rede (padrão)** | Uma única chave para todos os nós. Controle sempre autenticado; dados criptografados. | Uso geral. É a opção mais simples entre as seguras. |
| **Aberto (sem senha)** | Nenhuma chave. Pacotes sem autenticação nem criptografia. A sequência de salto usa uma semente pública padrão. | Protótipos, ensaios e redes onde a segurança não importa. Precisa ser escolhido explicitamente. |

- **RF-50** No modo **chave de rede**, a autenticação de todas as mensagens de controle (`BEACON`, `HELLO`, `PROPOSE`, `VOTE`, `COMMIT`, `ROLLBACK`, `PROBE`) é obrigatória e não pode ser desligada separadamente.
- **RF-50a** O modo **aberto** existe para quem quer criar enlaces sem senha. Ele precisa ser ativado de forma explícita (ex.: `init(..., MODO_ABERTO)`), gera um aviso na telemetria ao iniciar e deixa a rede vulnerável aos ataques descritos acima. Nós em modo aberto e nós com chave não se comunicam entre si.
- **RF-51** **Criptografia autenticada dos dados** (ex.: AES-128-CCM, que tem aceleração por hardware no ESP32 e no nRF52), ligada por padrão no modo chave de rede.
- **RF-52** **Proteção contra repetição** (replay): contador por remetente, guardado em memória não volátil.
- **RF-53** **Chave de rede fornecida pela aplicação:** uma chave de 128 bits, comum a todos os nós da rede, passada à biblioteca na inicialização (ex.: `init(..., chave_rede)`). Ela pode estar fixa no código (hardcoded) ou vir de qualquer menu de configuração que o desenvolvedor criar.
- **RF-53a** **Troca de chave em tempo de execução:** uma chamada (ex.: `set_network_key()`) permite trocar a chave sem reiniciar. Guardar a chave em memória não volátil fica a cargo da aplicação, usando a camada de porte.
- **RF-53b** **Ferramenta de geração:** a biblioteca inclui um utilitário (script) que gera uma chave aleatória forte para o desenvolvedor colar no firmware ou no menu de configuração. Isso evita chaves fracas, como senhas curtas ou derivadas do MAC.
- **RF-53c** **Chaves derivadas internamente:** a partir da chave de rede, a biblioteca deriva chaves separadas para autenticação, criptografia e sequência de salto (ex.: por HKDF). Assim, uma única chave fornecida pelo desenvolvedor alimenta tudo.
- **RF-53d** **Identificador do nó:** derivado do MAC/ID único do chip por padrão, ou definido pela aplicação.
- **RF-53e** **Sem chave embutida:** não existe chave padrão no código. Se a aplicação não fornecer uma chave nem escolher o modo aberto explicitamente, a biblioteca não transmite e gera um erro claro. Isso evita que alguém fique sem segurança por esquecimento.

#### Preparação para chaves por grupo (extensão futura)

A versão inicial usa **uma única chave para a rede inteira**. A arquitetura, porém, deve permitir que alguém acrescente depois **chaves diferentes para grupos de nós** dentro da mesma rede, sem quebrar a compatibilidade:

- **RF-53g** O bloco de configuração reserva um pequeno campo de **identificador de chave** (ex.: 4 bits). Na versão inicial, ele só assume dois valores: "sem chave" (modo aberto) e "chave de rede".
- **RF-53h** A biblioteca não acessa a chave diretamente: ela pede a chave a um **provedor de chaves**, uma interface interna que recebe o identificador de chave e o grupo de enlace e devolve a chave a usar. A implementação padrão sempre devolve a chave de rede. Uma extensão futura só precisa substituir o provedor.
- **RF-53i** Mensagens de controle e de dados já carregam o identificador do grupo de enlace, para que o provedor possa escolher a chave certa no futuro.
- **RF-53f** A documentação deve alertar para não publicar chaves em repositórios públicos e para trocar a chave de exemplo.
- **RF-54** Pacotes sem autenticação válida são descartados e geram um evento de telemetria.
- **RF-55** O custo de bytes da autenticação (tag de integridade) entra no cálculo do tempo no ar e do tamanho de fragmento.

### 5.11 Telemetria: simples e abstraída
- **RF-56** A biblioteca gera **eventos de telemetria** como estruturas internas fixas: pacote enviado, recebido, perdido, retransmitido; proposta, voto, commit e rollback; mudança de modo; falha de autenticação; métricas periódicas por vizinho.
- **RF-57** O desenvolvedor **não precisa lidar com o formato**. Ele só liga a telemetria e escolhe o destino com uma chamada (ex.: `telemetry_enable(SAIDA_SERIAL, NIVEL_RESUMO)`).
- **RF-58** Formato de saída padrão: **JSON por linha** (um evento por linha), por ser o mais simples de implementar e de ler com qualquer ferramenta. Cada linha traz a versão do formato.
- **RF-59** Destinos prontos: serial e arquivo (SD/flash). Para outros destinos, a aplicação registra um callback que recebe a linha pronta.
- **RF-60** Nível de detalhe configurável: desligado, resumo, completo.
- **RF-61** **Cada nó guarda o próprio registro.** As ferramentas juntam os registros de vários nós depois, pelo identificador do nó e pelo horário.

### 5.12 Independência de antena

A biblioteca se concentra na adaptação da comunicação LoRa. A comparação entre antenas é uma atividade separada, feita pelo autor com a telemetria. A biblioteca só precisa não atrapalhar e fornecer os dados.

- **RF-62** Nada na biblioteca depende do tipo de antena. A antena entra apenas como um **perfil de antena** configurável: identificador, ganho (dBi) e perdas de cabo e conectores (dB).
- **RF-63** O ganho e as perdas são usados para calcular a potência irradiada (EIRP) e limitar a potência de TX dentro da lei (§5.9). Uma antena de ganho maior faz a biblioteca reduzir a potência conduzida automaticamente quando necessário.
- **RF-64** O perfil de antena pode ser trocado em tempo de execução, sem reiniciar.
- **RF-65** Todo evento de telemetria inclui o **identificador da antena** em uso. Com isso, os dados servem para comparar antenas fora da biblioteca.
- **RF-66** A aplicação pode **travar os parâmetros de rádio** (desligar a adaptação temporariamente), o que é útil para qualquer ensaio externo que precise de condições fixas.

### 5.13 Georreferenciamento e ensaios de campo (módulo opcional)

Objetivo: em cada ensaio, saber **onde cada nó estava** quando transmitiu ou recebeu um pacote, associando as métricas de rádio à distância e à direção entre os nós.

- **RF-68** Ler a posição pelo GNSS (na referência, o L76K): latitude, longitude, altitude, horário UTC, número de satélites e precisão (HDOP).
- **RF-69** Opcionalmente, incluir a posição do remetente no bloco de configuração (campo compacto, enviado só quando a posição mudar ou em intervalos definidos).
- **RF-70** Calcular, para cada par de nós: **distância** (fórmula de Haversine, corrigida pela altitude), **azimute/rumo** (o sentido da comunicação), **diferença de altitude** e ângulo de elevação.
- **RF-71** Registrar cada pacote numa **linha de dados de ensaio**, no formato de telemetria de §5.11, com: horário, origem, destino, posições, distância, rumo, antenas, parâmetros de rádio, RSSI, SNR, entregue/perdido e retransmissões.
- **RF-72** Usar o pulso PPS do GNSS para sincronizar os relógios, as janelas de escuta e o salto em frequência.
- **RF-73** A partir dos registros, permitir calcular: perda de percurso × distância (comparada com modelos teóricos), alcance máximo por combinação de parâmetros e mapa de cobertura.
- **RF-74** Opcionalmente, a política de adaptação pode usar a distância para escolher o modo de partida.
- **RF-75** O GNSS pode ficar desligado no perfil *bateria*, ou ser ligado só durante os ensaios.

### Requisitos não funcionais
- **RNF-01** **Leveza de execução como prioridade:** drivers próprios e enxutos para SX126x e SX127x, sem dependência de bibliotecas de terceiros no núcleo.
- **RNF-02** **A plataforma fica totalmente abstraída.** A camada de porte é mínima: SPI, GPIO, interrupção, relógio/temporizador, armazenamento não volátil, gerador aleatório e, opcionalmente, nível e fonte de energia. Portar para uma plataforma nova deve exigir só a implementação dessas funções. Não há plataforma prioritária na especificação; a plataforma de referência (§2.1) serve apenas para validar.
- **RNF-03** Sem alocação dinâmica de memória; buffers dimensionados em tempo de compilação.
- **RNF-04** Recursos opcionais (multi-salto, GNSS, telemetria completa, ensaios) devem ser removíveis na compilação, para que nós simples não paguem por eles.
- **RNF-05** Distribuída como biblioteca Arduino, componente ESP-IDF e pacote PlatformIO.
- **RNF-06** Consumo de RAM e flash documentado para cada combinação de recursos.
- **RNF-07** Opcional: um adaptador para usar a RadioLib como backend em chips que os drivers próprios ainda não suportam, sem que ela seja obrigatória.
- **RNF-08** Testes de campo e de bancada reproduzíveis, medindo entrega, latência, alcance, consumo e desempenho por antena.

---

## 6. Relações com outras ideias

*(A preencher conforme novas ideias forem listadas.)*
- **Ferramentas de diagnóstico e visualização:** consomem a telemetria (§5.11), os registros de ensaio (§5.13) e as comparações de antenas (§5.12). Candidata natural a ser uma ideia própria do conjunto.
- Projetos de sensores ou atuadores que usem esta biblioteca como transporte.
- Um livro ou guia técnico que explique o protocolo e as decisões de projeto.

---

## 7. Decisões já tomadas

| # | Tema | Decisão |
|---|---|---|
| 1 | Topologia | Livre. Cada nó é independente e negocia seus enlaces. |
| 2 | Quem decide | Decisão por acordo entre todos os participantes do grupo de enlace. |
| 3 | Hardware de referência | Heltec WiFi LoRa 32 V4 + GNSS L76K, em 915 MHz. A biblioteca deve rodar em Arduino, ESP e nRF com rádios SX12xx. |
| 4 | Troca de parâmetros | Negociada antes, com rollback para o estado mais confiável. |
| 5 | LoRaWAN | Não. Estritamente P2P. |
| 6 | Região | Todas as regiões, com foco no Brasil. |
| 7 | GNSS nos ensaios | Um único modelo de placa e módulo. |
| 8 | Registros | Cada nó mantém o próprio registro. |
| 9 | Nome | AdaptLoRa, sujeito à verificação de §9.1. |
| 10 | Antena | A biblioteca é independente de antena; a antena é um perfil configurável. A comparação de antenas é feita à parte. |
| 11 | Multi-salto | Selecionável durante o uso, nó a nó. |
| 12 | Escuta de vários modos | Modo base comum (sempre o inicial) + modos de dados por grupo de enlace + agenda de escuta. Vale para ponto a ponto, ponto-multiponto e multiponto-multiponto. |
| 13 | Camada de rádio | Drivers próprios e enxutos (mais leve em execução). RadioLib só como adaptador opcional. |
| 14 | Telemetria | Eventos internos + saída padrão em JSON por linha, ligada com uma chamada. O formato fica abstraído para o desenvolvedor. |
| 15 | Perfil Brasil | Operar no máximo que a lei permite, escolhendo automaticamente o enquadramento regulatório. |
| 16 | Segurança | Padrão: chave de rede, com autenticação obrigatória do controle e criptografia dos dados. Modo aberto (sem senha) disponível se escolhido explicitamente. |
| 17 | Chaves | Definidas pelo desenvolvedor na gravação do firmware ou por menus próprios. A biblioteca recebe a chave de rede, deriva as demais e não faz pareamento. O MAC serve só como identificador. |
| 18 | Modo base | Configurável em qualquer modo LoRa suportado pelo SX12xx. Padrão no Brasil, pensado para o pior caso: salto em frequência, BW 125 kHz, SF10, potência máxima legal. |
| 19 | Janelas de encontro | Dependem do perfil de energia; nós ligados na rede assumem os papéis mais caros. |
| 22 | Modo base sem salto (SF12/BW 500 kHz) | Não é padrão; só configuração manual. Sem medições de laboratório. |
| 23 | Chaves por grupo | Fora da versão inicial, mas com a arquitetura preparada (identificador de chave no cabeçalho e provedor de chaves substituível). |
| 21 | Energia | A biblioteca não detecta bateria nem fonte; a aplicação informa, se quiser. A troca automática de perfil é assunto da plataforma de testes, não da biblioteca. |
| 20 | Plataformas | Totalmente abstraídas; sem ordem de prioridade na especificação. |

---

## 8. Riscos e cuidados

- **Salto em frequência é obrigatório para potência alta com BW < 500 kHz no Brasil.** Isso aumenta a complexidade: exige sincronização entre os nós e limita o tempo no ar de cada pacote a 0,4 s por canal.
- **A largura de banda de 6 dB de um sinal LoRa de 500 kHz** precisa ser medida para confirmar se atinge o mínimo de 500 kHz. Se não atingir, o enquadramento de modulação digital não se aplica.
- **A regulamentação acabou de mudar.** Os limites de §5.9 devem ser confirmados no texto vigente da Anatel antes de fechar o perfil Brasil.
- **Drivers próprios** são mais leves, mas exigem mais trabalho de manutenção e testes do que usar a RadioLib.
- **Agenda de escuta em multiponto-multiponto** pode reduzir a vazão útil quando um nó participa de muitos grupos.

---

## 9. Estudo prévio: bibliotecas e trabalhos similares

### 9.1 Verificação do nome

Uma busca por "AdaptLoRa" não encontrou nenhuma biblioteca publicada com esse nome. Antes de publicar, ainda vale conferir diretamente nos registros do GitHub, do PlatformIO, do Gerenciador de Bibliotecas do Arduino e do ESP Component Registry.

### 9.2 Projetos existentes

| Projeto | O que faz | Plataformas | Adaptação de enlace? | O que aproveitar | O que evitar / diferença |
|---|---|---|---|---|---|
| **RadioLib** | Driver universal para muitos rádios, incluindo SX126x, SX127x, SX128x e LR11x0; também tem LoRaWAN. | Arduino e ambientes não Arduino, via HAL interna; componente ESP-IDF. | Não. | Referência para os drivers próprios; adaptador opcional. | Mais pesada que o necessário, por suportar muitos rádios e protocolos. |
| **RadioHead** | Drivers + entrega confiável com ACK/retransmissão, roteamento e malha (RHMesh). | Vários microcontroladores. | Não. | Separação driver/manager; entrega confiável e malha. | Parâmetros fixos; sem negociação. |
| **LoRaMesher** | Malha multi-salto com vetor de distância, entrega confiável e fragmentação. | Só ESP32 (RadioLib + FreeRTOS). | Não. | Referência para fragmentação e para o roteamento futuro. | Preso ao ESP32 e ao FreeRTOS; parâmetros fixos. |
| **Meshtastic** | Firmware completo de malha (não é biblioteca), com presets de modem. | Várias placas, incluindo Heltec V4. | Não; todos os nós usam o mesmo preset. | Presets como referência de combinações SF/BW/CR testadas em campo. | Não é reutilizável como biblioteca; configuração fixa por rede. |
| **SX126x-Arduino** | Driver baseado no código da Semtech, com LoRaWAN e P2P. | ESP32, ESP8266, nRF52, RP2040. | Só o ADR do LoRaWAN. | Exemplo de nRF52 + SX1262. | Foco em LoRaWAN. |
| **SX12XX-LoRa** | Biblioteca com muitos exemplos de P2P. | Arduino. | Não. | Exemplos de testes de alcance. | Sem negociação. |

### 9.3 Pesquisa acadêmica relacionada

- **ASFS** (Kim, Lee e Jeon, 2020): seleção adaptativa de SF entre transmissor e receptor em redes multi-salto, com ganho de vazão de até 3×.
- **Adaptação auto-organizada de SF** (Fraunhofer, 2021): mapeamento de SNR para SF que garante uma taxa de entrega mínima entre dois nós; mostra que altitude e ambiente também afetam o SNR.
- **AURORA** (2026): seleção de SF por enlace em redes multi-salto, com sondagem e ajuste de modelo para prever a taxa de entrega de cada SF.

### 9.4 Conclusões do estudo

- **A lacuna existe.** Nenhuma biblioteca oferece negociação por acordo + adaptação de enlace + rollback em P2P, de forma portável. A adaptação de SF entre pares só aparece em trabalhos acadêmicos.
- **Features necessárias:** ACK e retransmissão, fragmentação, sondagem antes de trocar de modo, mapeamento SNR → SF.
- **Features desnecessárias:** pilha LoRaWAN, interface de usuário e aplicativos, dependência de um sistema operacional específico.

---

## 10. Questões em aberto

Nenhuma no momento. Todas as questões levantadas até a revisão 3 foram decididas (ver §7).
