# Légua: simulação em ambientes urbanos e rurais

> Documento 04 do projeto. Comparação quantitativa entre a Légua (como especificada nos documentos 01 e 03) e métodos tradicionais, em ponto a ponto, estrela e malha.
> Data: 14 de novembro de 2026. Simulador: `adaptsim` (Python + numpy, semente fixa).
> Painel da campanha 1: https://claude.ai/artifact/2sqmzqzbR3rNukxvTt56FD
> Painel da campanha 2 (SF11/SF12, capacidade total, exceção da Anatel): https://claude.ai/artifact/3Rtc3iSNNkvkBYNmSMj86R

## 1. O que foi simulado

**Ambientes (915 MHz, antenas a ~3 m, dipolo 2,15 dBi):**

| Ambiente | PL a 1 km | Expoente | Sombra fixa | Variação | Rice K | Ruído extra | R7 (SF7, 22 dBm) |
|---|---|---|---|---|---|---|---|
| Urbano denso | 142 dB | 4,0 | 8 dB | 3 dB | 3 dB | +6 dB | ~0,96 km |
| Urbano residencial | 133 dB | 3,7 | 7 dB | 2 dB | 5 dB | +3 dB | ~2,0 km |
| Industrial / portuário | 138 dB | 3,8 | 10 dB | 3,5 dB | 2 dB | +8 dB | ~1,1 km |
| Rural aberto | 112 dB | 4,0 | 4 dB | 1 dB | 10 dB | 0 | ~7,6 km |
| Rural com vegetação | 128 dB | 4,2 | 6 dB | 2 dB + umidade/chuva | 6 dB | 0 | ~2,9 km |
| Rural serrano | 118 dB | 4,0 | 12 dB | 1,5 dB | 8 dB | 0 | ~5,4 km |

R7 é a distância em que a perda média esgota o orçamento do SF7/125 a 22 dBm. Eventos: obstruções (veículos, contêineres), chuva, ciclo diurno de umidade; interferência de terceiros por ALOHA com captura. Calibração grosseira: rural aberto reproduz ~8 km com SF7/20 dBm (Facina et al., SBrT 2021). Curva de erro 2,5 dB acima do limiar do datasheet (Hernandez Ortiz et al., 2026).

**Métodos:** fixo SF7/125, fixo SF12/125, fixo SF11/250 (LongFast), fixo SF12/500, ADR estilo LoRaWAN (servidor Semtech + ADR_ACK_LIMIT/DELAY, com receptor idealmente sincronizado), Légua (cabeçalho de dados de 10 B) e Légua com cabeçalho de 8 B. Na malha: inundação gerenciada estilo Meshtastic, roteamento SF7 fixo estilo LoRaMesher e Légua com modo por enlace e rota de menor custo.

**Légua modelada:** modo base SF10/125 com salto; PROPOSE/VOTE/COMMIT no modo base, com perda de COMMIT gerando dessincronia; janela de validação de 3 pacotes; âncora e rollback (para o modo base quando o modo que falhou era mais robusto que a âncora); histerese assimétrica (degrada após perda, acelera após 20 pacotes estáveis, 10 min entre trocas, máx. 6 trocas/h); sondagem de 2 pacotes; margem de 5 dB; potência mínima por energia; ocupação ≤ 0,4 s por canal (fragmenta se passar); recuo exponencial após falhas de negociação; congelamento após rollbacks repetidos (E11). Em estrela: subgrupos de até 4 nós por canal, unanimidade, divisão do grupo após 3 falhas.

**Dois regimes de potência:**
- *Mesma potência:* 22 dBm para todos (comparação técnica pura).
- *Regra brasileira (interpretação do projeto, a confirmar com OCD):* canal fixo < 500 kHz na classe de baixa potência (~−3 dBm conduzidos); SF12/500 fixo e Légua a 28 dBm.

## 2. Resultados principais

### Ponto a ponto, alcance com 90% de entrega (km)

| Ambiente | SF7 | SF12/125 | LongFast | SF12/500 | ADR | Légua | Légua 8 B |
|---|---|---|---|---|---|---|---|
| *Mesma potência* | | | | | | | |
| Urbano denso | 0,48 | **1,01** | 0,73 | 0,67 | 0,21 | 0,63 | 0,67 |
| Urbano residencial | 1,02 | **2,45** | 1,77 | 1,73 | 0,64 | 1,70 | 1,78 |
| Industrial | 0,29 | **0,82** | 0,45 | 0,43 | 0,00 | 0,41 | 0,44 |
| Rural aberto | 5,7 | **11,0** | 8,4 | 8,3 | 10,6 | 8,3 | 8,6 |
| Rural vegetação | 1,8 | **3,8** | 2,3 | 2,2 | 2,4 | 2,2 | 2,3 |
| Rural serrano | 2,2 | **4,7** | 4,1 | 3,9 | 4,4 | 4,0 | 4,3 |
| *Regra brasileira* | | | | | | | |
| Urbano denso | 0 | 0,29 | 0,17 | 1,03 | 0 | 1,01 | **1,03** |
| Urbano residencial | 0 | 0,50 | 0,36 | 2,46 | 0,35 | 2,45 | **2,49** |
| Industrial | 0 | 0,17 | 0 | **0,82** | 0 | 0,81 | **0,82** |
| Rural aberto | 1,3 | 2,5 | 1,6 | 11,0 | 2,4 | 11,2 | **12,0** |
| Rural vegetação | 0,5 | 0,7 | 0,5 | 3,7 | 0,6 | 3,6 | **3,8** |
| Rural serrano | 0 | 1,2 | 1,0 | 4,7 | 1,2 | 4,7 | **4,8** |

### Energia por pacote entregue a 0,5×R7 (mJ, mediana; soma de TX dos dois nós)

| Ambiente | LongFast | SF12/500 | ADR | Légua |
|---|---|---|---|---|
| Rural aberto, mesma potência | 214 | 214 | 38 | **32** |
| Rural aberto, regra BR | sem enlace | 751 | sem enlace | **45** |
| Urbano residencial, mesma potência | 236 | 237 | 56 (alcance 0,6 km) | **126** |
| Urbano residencial, regra BR | sem enlace | 808 | sem enlace | **210** |
| Urbano denso, mesma potência | 261 | 263 | 55 (alcance 0,2 km) | **221** |

### Estrela e malha (resumo)

- **Estrela:** a Légua empata em entrega com o SF12/500 e o LongFast, mas com cabeçalho de 10 B gasta cerca de 2× mais energia: nós fracos não conseguem unanimidade, ficam no modo base e cada pacote de 26 B vira 2 fragmentos em SF10/125. Com cabeçalho de 8 B o custo cai para o nível dos fixos robustos (ex.: urbano denso 1296 → 656 mJ) e a entrega sobe 3 a 5 pontos.
- **Malha, mesma potência:** Légua entrega 97–100% (inundação 95–98%, SF7 roteado 82–99%) com 3 a 10× menos tempo no ar que a inundação, mas latência de 3–5 s contra 1–1,5 s.
- **Malha, regra BR:** só a Légua funciona (97–100%); inundação e SF7 roteado em canal fixo caem para 0–20%.

## 3. Conclusões para o projeto

1. **O ganho da Légua é de energia e de conformidade, não de alcance bruto.** Com potência igual, o SF12/125 fixo vai mais longe, porque a Légua abre mão de SF11/SF12 em 125 kHz para respeitar 0,4 s por canal. O teto de robustez dela (SF10/125 ≈ SF11/250 ≈ SF12/500) fica ~5 dB atrás.
2. **Sob a regra brasileira, a comparação muda de figura.** Os métodos de canal fixo estreito perdem quase todo o alcance; restam a Légua e o SF12/500 fixo. Contra este, a Légua tem o mesmo alcance e gasta de 2,5 a 17× menos energia a meia distância.
3. **O ADR estilo LoRaWAN é o tradicional mais eficiente em ambientes estáveis, mas falha nos voláteis** (alcance 90% de 0–0,6 km nos urbanos): reduz potência pelo SNR máximo e demora a reagir à piora. Confirma a literatura (Li et al.; Farhad et al.).
4. **Em ambiente urbano volátil a adaptação rende pouco** (221 contra 261 mJ no urbano denso). Rollbacks e renegociações consomem o que a aceleração economiza.
5. **O ponto fraco é a estrela com nós de borda.** A unanimidade trava com membros fracos e o modo base fica caro. A divisão de grupo após falhas repetidas foi necessária para funcionar.

## 4. Recomendações para a especificação

| # | Recomendação | Requisitos |
|---|---|---|
| S1 | Orçar o cabeçalho de **dados** para que 16 B de aplicação caibam em um fragmento SF10/125 (≤ 24 B no ar, isto é, ≤ 8 B de cabeçalho). Hoje, com 10 B, todo pacote de recuperação fragmenta. | RF-04, RF-55, E8 |
| S2 | Admitir SF11/250 ou SF12/500 como **modo de dados de recuperação** pré-combinado, sem negociação, com a mesma robustez do modo base e um fragmento só. | RF-26, RF-27 |
| S3 | Formalizar a **divisão de grupo**: após N falhas de unanimidade, o membro fraco sai para um subgrupo próprio. | RF-09, RF-21, E3 |
| S4 | **Recuo exponencial** entre negociações falhas; sem ele, enlaces mortos gastam energia renegociando a cada pacote. | RF-19 a RF-21 |
| S5 | Em validação de um modo **mais robusto** que a âncora, falha leva ao modo base, não à âncora. | RF-25 a RF-27 |
| S6 | Dentro da janela de um subgrupo, usar **slots** em vez de ALOHA: a agenda concentra o tráfego e aumenta colisões. | RF-08, §5.2 |
| S7 | Controle no modo base a 1 W custa caro (a 28 dBm, ~0,5 J por mensagem, estimado): negociação rara e sem PROBE dedicado no perfil bateria, como já previsto. | RF-41, E13 |

## 5. Limitações

- Parâmetros de canal estimados, sem campanha de campo. Servem para comparar métodos, não para prever alcance absoluto.
- Corrente a 28 dBm (~420 mA) é estimativa; medir na Heltec V4 (E16).
- Regime "regra brasileira" é interpretação a confirmar com OCD; SF12/500 depende da medição de 6 dB.
- ADR com receptor ideal (favorece o ADR). Sem mobilidade, ataques, consumo do MCU, assimetria de enlace nem interferência inter-SF detalhada.
- Estrela e malha usam aproximações de duas passadas para colisões.

## 6. Próximos passos sugeridos

1. Aplicar S1 e S5 na especificação; S2–S4 entram como requisitos novos.
2. Usar o `adaptsim` como base da camada T1 (simulação multi-nó) da bancada, trocando os modelos por medições à medida que a fase 1 produzir dados.
3. Calibrar os ambientes com a campanha de campo em 915 MHz e refazer a comparação.

---

## 7. Campanha 2: SF11/SF12, capacidade total do SX1262 e exceção da Anatel

### 7.1 O que mudou

**Métodos (só os melhores da campanha 1):** fixo SF12/125 (maior alcance), fixo SF12/500 (conforme), ADR estilo LoRaWAN (mais eficiente) e, na malha, a inundação estilo Meshtastic. Contra eles, três versões da Légua:

| Versão | Modos | Outras mudanças |
|---|---|---|
| **Atual** | SF7–10/125, SF7–11/250, SF7–12/500, CR 4/5 | Cabeçalho 10 B, base SF10/125 com salto |
| **+ SF11/SF12** | Atual + SF11/SF12 em 125 e 250 kHz | Cabeçalho 8 B, base mais robusta permitida, controle no modo atual quando ele alcança mais que a base (in-band), modo de recuperação pré-combinado |
| **Completa** | SF5–SF12 × BW 31,25–500 kHz × CR 4/5–4/8, −9 a 28 dBm | Igual à anterior. BW < 31,25 kHz ficou fora (tolerância de frequência mesmo com TCXO) |

Em todas, a escolha de modo pondera energia pela interferência medida no canal: um pacote longo fica mais exposto e custa mais.

**Três regimes** (todos a até 28 dBm, PA da Heltec V4):

| Regime | Regra aplicada |
|---|---|
| Limite do hardware | Qualquer modo, 28 dBm, sem regra. Teto técnico, não é uso legal |
| **Exceção da Anatel** | Produto homologado na base antiga (item 10.3.4.4 do Anexo I do Ato 14.448, preservado pelo Ato 4.746/2026 na manutenção da certificação): canal fixo liberado em qualquer BW, mas a densidade de 8 dBm/3 kHz limita 125 kHz a ~24 dBm, 250 kHz a ~27 dBm e 31,25 kHz a ~18 dBm. Modos que cabem em 0,4 s podem saltar a 28 dBm |
| Regra nova | < 500 kHz só com salto e ≤ 0,4 s por canal (fragmentando se preciso); o que não cabe vai para baixa potência (~−3 dBm). 500 kHz em canal fixo a 28 dBm |

Interpretação do projeto, a confirmar com OCD (inclusive se a exceção cobre um produto novo que use firmware novo).

### 7.2 Alcance com 90% de entrega, ponto a ponto (km)

| Ambiente | SF12/125 | SF12/500 | ADR | Légua atual | + SF11/SF12 | Completa |
|---|---|---|---|---|---|---|
| *Limite do hardware* | | | | | | |
| Urbano denso | **1,34** | 1,21 | 0,21 | 1,16 | 1,28 | 1,28 |
| Urbano residencial | **3,34** | 2,45 | 1,12 | 2,39 | 3,25 | 3,24 |
| Industrial | **0,97** | 0,88 | 0,00 | 0,87 | 0,93 | 0,94 |
| Rural aberto | 16,0 | 11,4 | 14,8 | 13,6 | 16,1 | **16,3** |
| Rural vegetação | **5,08** | 3,03 | 3,70 | 3,05 | 5,03 | 4,77 |
| Rural serrano | 5,81 | 5,47 | 5,65 | 5,48 | 5,78 | **5,83** |
| *Exceção* | | | | | | |
| Urbano denso | **1,23** | 1,21 | 0,20 | 1,16 | **1,23** | **1,23** |
| Urbano residencial | **3,13** | 2,45 | 0,85 | 2,39 | 3,12 | 3,11 |
| Industrial | **0,91** | 0,88 | 0,00 | 0,87 | 0,90 | 0,90 |
| Rural aberto | **13,8** | 11,4 | 13,1 | 13,6 | 13,8 | 13,8 |
| Rural vegetação | **3,60** | 3,03 | 2,62 | 3,05 | 3,59 | 3,56 |
| Rural serrano | **5,55** | 5,47 | 5,24 | 5,48 | 5,54 | **5,55** |
| *Regra nova* | | | | | | |
| Urbano denso | 0,29 | 1,21 | 0,00 | 1,16 | **1,22** | 1,21 |
| Urbano residencial | 0,50 | 2,45 | 0,34 | 2,39 | **3,08** | 3,07 |
| Industrial | 0,17 | **0,88** | 0,00 | 0,87 | **0,88** | **0,88** |
| Rural aberto | 2,49 | 11,4 | 2,41 | 13,6 | **13,7** | 13,7 |
| Rural vegetação | 0,65 | 3,03 | 0,60 | 3,05 | **3,24** | 3,21 |
| Rural serrano | 1,21 | 5,47 | 1,15 | 5,48 | **5,51** | **5,51** |

### 7.3 Energia por pacote entregue a 0,5×R7 (mJ, mediana)

| Ambiente | SF12/125 | SF12/500 | ADR | Légua atual | + SF11/SF12 | Completa |
|---|---|---|---|---|---|---|
| *Limite do hardware* | | | | | | |
| Urbano denso | 4409 | 871 | 79 | 334 | 760 | 1048 |
| Urbano residencial | 3666 | 808 | 73 | 260 | 408 | 652 |
| Rural aberto | 3033 | 750 | 54 | 45 | 76 | 56 |
| Rural vegetação | 3034 | 752 | 58 | 96 | 223 | 210 |
| *Exceção* | | | | | | |
| Urbano denso | 2420 | 871 | 63 | 334 | 489 | 833 |
| Urbano residencial | 2005 | 808 | 63 | 260 | 298 | 410 |
| Rural aberto | 1657 | 750 | 44 | 45 | 59 | 47 |
| Rural vegetação | 1658 | 752 | 49 | 96 | 134 | 129 |
| *Regra nova* | | | | | | |
| Urbano denso | sem enlace | 871 | sem enlace | 334 | 329 | 278 |
| Urbano residencial | sem enlace | 808 | sem enlace | 260 | 165 | 202 |
| Rural aberto | sem enlace | 750 | sem enlace | 45 | 48 | 42 |

O ADR gasta pouco a meia distância, mas seu alcance a 90% nos urbanos é de 0–1,1 km.

### 7.4 Estrela e malha

- **Estrela:** nos três regimes, a versão + SF11/SF12 tem a maior entrega média em quase todos os ambientes (ex.: urbano residencial, hardware: 92% contra 90% do SF12/125 fixo). Na exceção e no hardware ela gasta cerca de 2× a versão atual, pelo controle no modo base SF12 a 28 dBm. Na regra nova, ela gasta menos que a atual (1250–1665 contra 1753–2706 mJ), por causa do cabeçalho de 8 B.
- **Malha:** as três Légua entregam 99–100% em todos os regimes. Na regra nova, a inundação cai para 5–20%. No hardware e na exceção, a inundação entrega 98–100%, mas com 2,7 a 3,6 J por pacote, contra 0,3–0,6 J da Légua atual e 0,5–1,9 J das versões novas.

### 7.5 Conclusões

1. **Liberar SF11/SF12 só vale onde a regra deixa usá-los em alta potência.** No hardware e na exceção, a Légua alcança o SF12/125 fixo (ganho de 1% a 65% sobre a versão atual, maior em vegetação e urbano residencial) e gasta 3,6 a 40× menos energia que ele a meia distância. Na regra nova, SF11/SF12 em 125 kHz não cabem em 0,4 s e não ajudam.
2. **A capacidade total do chip rende pouco além do SF11/SF12.** BW estreita ganha até ~7 dB no papel, mas pacotes de vários segundos ficam expostos a interferência e desvanecimento. Na exceção, o limite de 8 dBm/3 kHz corta a potência na mesma proporção e anula o ganho. SF5/SF6 economizam um pouco em enlaces curtos. CR mais forte rende ~1 dB (estimado).
3. **Para negociar SF12 a distância, o modo base também precisa alcançar, e isso custa caro.** Sem base robusta e sem controle in-band, a versão com SF11/SF12 ficava presa no alcance do SF10 (teste exploratório). Com base SF12/125 a 28 dBm, cada mensagem de controle custa ~2 J (estimado) e a malha gasta 1,6 a 3× mais energia.
4. **O que a regra nova realmente pede é BW 500 kHz confirmada em laboratório**, não SF mais alto: a largura de 6 dB do SF12/500 decide o teto de robustez legal.

### 7.6 Recomendações adicionais

| # | Recomendação | Requisitos |
|---|---|---|
| S8 | **Controle in-band:** permitir PROPOSE/VOTE/COMMIT no modo de dados atual quando ele alcança mais que o modo base | RF-06, RF-19 a RF-22 |
| S9 | **Tabela de modos por enquadramento:** cada modo candidato traz o enquadramento e a potência máxima (salto, banda larga, canal fixo da base antiga, baixa potência). O regime "base antiga" deve ser selecionável e travado na compilação de produto | RF-43 a RF-46, R1–R3 |
| S10 | **Custo de modo com a interferência medida no canal** (CAD/RSSI): sem isso a política escolhe BW estreita longa demais | RF-29 a RF-34 |
| S11 | **Base robusta só onde a regra permite** (SF12/125 na base antiga); manter SF10/125 com salto na regra nova. Intervalo de beacon maior quando a base for cara | RF-05a, RF-05d, RF-07 |
| S12 | Não priorizar SF5/SF6 e BW < 125 kHz na v1: ganho pequeno e complexidade de cristal, ToA e tabela regulatória | §5.2, E6, E7 |

### 7.7 Limitações próprias da campanha 2

- Pacotes de vários segundos sem desvanecimento intra-pacote e sem limite de ciclo de trabalho (otimista para BW estreita).
- Ganho de CR e tolerância a colisões por CR são estimativas.
- A exceção pode não cobrir um produto novo, só a manutenção de um já homologado; isso decide se o regime "exceção" é aplicável ao projeto.
