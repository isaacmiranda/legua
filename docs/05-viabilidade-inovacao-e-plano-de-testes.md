# Regulação de 2026 redesenha a Légua viável

A Légua é viável, e o núcleo dela tem originalidade defensável. Esse núcleo é a negociação P2P PROPOSE/VOTE/COMMIT com troca em instante combinado, janela de validação, âncora em NVM e rollback, desde que a garantia seja formulada como **"nenhum desacordo permanente"** e que seja provada formalmente e medida em hardware SX1262. Não encontrei na literatura LoRa um protocolo equivalente. Os sistemas adaptativos publicados são centralizados (AdapLoRa, RALoRa, Toshiba) ou trocam de PHY quadro a quadro (Wi-SUN). Já a adaptação de SF/potência/canal em si **não é nova**, e a vantagem prática se estreita bastante sob a regra brasileira pós-06/10/2026. Pela leitura secundária do Ato 14.448, LoRa a 125 kHz em alta potência só é legal com salto em **≥35 canais e ≤0,4 s por canal a cada 14 s**. Pelo meu cálculo de tempo no ar, isso limita o modo base SF10/125 a **24 bytes de payload PHY com CR 4/5**, e elimina SF11/SF12 a 125 kHz e o "modo base robusto SF12/125 a 28 dBm" proposto no Doc 04. O alcance longo legal passa a vir de SF12/500 kHz como modulação digital. A simulação própria do projeto (Doc 04) já indicava que, com potência igual, o ganho da Légua está em **energia e conformidade**, e não em alcance. As evidências externas confirmam esse enquadramento. O escopo v1 deve se concentrar no par P2P com tabela de modos regulatória, degradação unilateral e aceleração negociada. Grupos em estrela, malha por vetor de distância, mobilidade veicular e drone ficam como cenários de avaliação, e não como funcionalidades completas. O plano de testes abaixo tem sete fases, das verificações regulatórias e formais até campanhas de campo urbano/rural a 915 MHz. Ele dimensiona amostras (**~865 pacotes por condição** para PDR≈0,9 ±2 pp; **≥3.000 negociações** para limitar desacordo permanente a <0,1%) e trata como baselines Meshtastic, MeshCore, Reticulum, LoRaMesher, presets fixos e um ADR do lado do nó. Vários pontos regulatórios, entre eles o texto consolidado do Ato 14.158, a homologação da Heltec V4 e o regime de uso experimental, **não foram verificados em fonte primária**, porque o portal da Anatel estava em manutenção durante a coleta.

> **Legenda de força da evidência** usada ao longo do texto: **[HW-PR]** hardware, revisado por pares; **[HW-PP]** hardware, preprint; **[SIM]** simulação ou analítico; **[DOC]** documentação de fabricante ou projeto; **[SEC]** fonte secundária (consultoria, fórum, blog); **[PAT]** patente; **[PRÓPRIO]** cálculo meu ou simulação adaptsim do projeto, sem calibração de campo; **[NV]** não verificado em fonte primária.

## A ideia central se sustenta; o alcance não é o argumento

### O que a literatura já resolveu e o que deixou aberto

A adaptação conjunta de parâmetros LoRa tem precedente forte. O AdapLoRa (ICNP 2020) adapta SF7–12, potência de 2 a 14 dBm, 8 canais e taxa de código Reed-Solomon acima da PHY, com BW fixa em 125 kHz. A decisão é centralizada no servidor e enviada por downlink. Em 4 gateways e 20 nós SX1276 o ganho foi de **+23,7% de vida útil** sobre o EF-LoRa **[HW-PR]** ([AdapLoRa, ICNP 2020](https://icnp20.cs.ucr.edu/proceedings/main/AdapLoRa.pdf)). O RALoRa (IEEE/ACM ToN 2024) faz o mesmo com código rateless. Ele obteve **+66,1% de vida útil** sobre LoRaWAN em testbed de 10 nós emulando 450, e mudou parâmetros em apenas 43,6% dos ciclos **[HW-PR]** ([RALoRa](https://par.nsf.gov/servlets/purl/10536073)). Os dois têm três características que deixam espaço para a Légua: são centralizados, usam SX1276 e mantêm BW e CR da PHY fixos. Não encontrei medição em SX126x que isole o ganho de BW ou de CR por enlace. O único trabalho com hardware que inclui BW (125 ou 250 kHz) como braço de bandit é um preprint de 2025/2026 com SF fixo em 7 **[HW-PP]** ([Ariyoshi et al., arXiv 2512.22089](https://www.arxiv.org/pdf/2512.22089)).

O sinal de alerta mais relevante vem de um preprint que **abandonou um protocolo dinâmico de SF por latência, limitações de hardware e overhead de pacotes de controle**, e passou a uma seleção estática por regras **[HW parcial + SIM, PP]** ([Wijesuriya, arXiv 2507.19938](https://arxiv.org/pdf/2507.19938)). Para a Légua, isso significa que o custo do PROPOSE/VOTE/COMMIT (airtime, energia, tempo até COMMIT, taxa de rollback) é a métrica que decide a viabilidade. Esse custo precisa ser medido e amortizado com histerese, e não apenas assumido.

No acordo propriamente dito, o análogo industrial mais próximo é o *mode switch* do Wi-SUN/802.15.4g. Os vizinhos anunciam PHYs suportados, a troca vale só para unicast, o broadcast fica no PHY base, e há **fallback automático ao PHY base quando as retentativas superam os sucessos em ~4×** **[DOC]** ([Silicon Labs Wi-SUN Mode Switch](https://docs.silabs.com/wisun/latest/wisun-mode-switch/)). No Wi-SUN o modo é sinalizado quadro a quadro no PHR. O LoRa não tem esse campo, de modo que o receptor precisa estar configurado antes, e é isso que torna necessário o instante de troca combinado da Légua. Os padrões maduros quase nunca fazem rollback silencioso depois do instante. No BLE, perder o *instant* derruba o enlace (HCI 0x28) **[SEC/HW]** ([TI E2E](https://e2e.ti.com/support/wireless-connectivity/bluetooth-group/bluetooth/f/bluetooth-forum/252581/ll_status_error-instant-passed)). No 802.11 com OCV, quando a confirmação pós-troca expira a conexão é *terminada*, e os autores rejeitaram de propósito voltar ao canal antigo ([Vanhoef et al., WiSec'18](https://papers.mathyvanhoef.com/wisec2018.pdf)). A Légua combina recusa prévia (VOTE=NO), confirmação pós-troca (janela de validação) e recuperação por estado conhecido (modo base). Ela acrescenta um nível intermediário, a âncora persistida, que não encontrei documentado como tal em nenhum padrão estudado.

### O que a física e o Two Generals permitem prometer

O protocolo não pode garantir ausência de desacordo transitório, pelo argumento clássico dos Dois Generais. Pode garantir que **todo desacordo é absorvido** em tempo limitado por T_valid + T_âncora + T_base, porque âncora e base são alcançáveis unilateralmente. Isso equivale a um "abort por timeout" local. Implementações de 2PC/3PC em rádio de baixa potência sobre transmissões síncronas chegam a 100% de confiabilidade com 1 jammer e caem para **~47–52% com 4 jammers** **[HW-PR]** ([XPC, EWSN 2020](https://www.ewsn.org/file-repository/ewsn2020/073_084_spina.pdf)). Logo, "acordo garantido" seria uma promessa falsa. A verificação formal mCRL2 da formação de cluster TSCH encontrou topologias em que a meta **nunca** é atingida em nenhuma execução ("narrow bridge", colisões de ACK a broadcast) **[FORMAL]** ([Talebi et al., arXiv 1703.06572](https://ar5iv.labs.arxiv.org/html/1703.06572)). A vivacidade da Légua, portanto, precisa ser verificada com perdas assimétricas e com o membro fraco, e não só com perda uniforme.

Um modelo mínimo **[PRÓPRIO]** explica o achado da simulação (Doc 04) de que a unanimidade sofre em estrelas com membros fracos. Com perda independente p_i por enlace, a rodada completa tem probabilidade Π(1−p_i)³, porque cada membro precisa receber PROPOSE e COMMIT e o coordenador precisa receber o VOTE. O pior membro domina. Com p=0,2 num único membro, ele sozinho reduz a rodada a 0,8³ ≈ 51%.

### O que o Doc 04 já indicava, e o que as fontes externas confirmam

A simulação adaptsim (Doc 04, **[PRÓPRIO]**, sem calibração) concluiu quatro coisas. Com potência igual, SF12/125 fixo tem o maior alcance. O ganho da Légua é energético (por exemplo, 32 mJ contra 214 mJ do LongFast em rural aberto a 0,5×R7). O ADR falha em ambientes urbanos voláteis. E o modo base robusto custa de 1,6 a 3× em energia na malha. As fontes externas são coerentes. Os esquemas ADR *mobility-aware* (EMA-ADR, G-ADR, M-ASFA, PF-ADR, LoRa-LQE) relatam ganhos de PDR de ~12% a 122% sobre o ADR padrão, mas **quase todos só em ns-3** **[SIM-PR]**. Os mais próximos da política da Légua, com EMA de SNR, penalidade por variância e *cooldown*, vêm da UFPI/IFMA, no Brasil ([LoRa-LQE, JISA 2026](https://journals-sol.sbc.org.br/index.php/jisa/article/download/7298/4207/43118); [Farhad et al., Sensors 2020](https://doaj.org/article/12b9a213027d4c71aa30ab13ee608e12)). Nenhum foi validado em hardware P2P com negociação bilateral. É uma lacuna real, e o projeto pode ocupá-la.

### Mobilidade: o Doppler não limita, o tempo de residência sim

A 915 MHz o Doppler estático é desprezível **[PRÓPRIO]**: ~85 Hz a 100 km/h e ~61 Hz num drone a 72 km/h, contra a tolerância de ±25% da BW, que dá ±31 kHz em 125 kHz **[SIM-PR]** ([Ullah et al., IEEE OJ-COMS 2024](https://cris.unibo.it/retrieve/57fd622b-1afb-46f5-af7a-fccc4658d75e/Understanding_the_Limits_of_LoRa_Direct-to-Satellite_The_Doppler_Perspectives.pdf)). O risco está na variação dentro do pacote. A tolerância dinâmica em SF12/125 é de apenas **10 Hz sem LDRO e 163 Hz com LDRO**, e a Semtech recomenda TCXO para TX de 1 s em alta potência por causa da deriva térmica **[DOC]** ([Semtech SX1262 AN](https://cdn.sparkfun.com/assets/f/f/b/4/2/SX1262_AN-Recommendations_for_Best_Performance.pdf)). Em hardware, o SF7 caiu de 99,46% de PDR a 4 km/h para 89,39% a 58 km/h, enquanto o SF12 ficou entre 96,6% e 100% **[HW-PP]** ([Karunathilake & Förster, arXiv 2311.18070](https://arxiv.org/pdf/2311.18070)).

O fator dominante, porém, é a visada. Na mesma rota, LoS+NLoS derrubou o SF7 para 56–90%. Numa fazenda em Santa Rita do Sapucaí, o RSSI não teve relação monotônica com a distância entre 3,24 e 3,76 km **[HW-PR]** ([Piedade et al., SBrT 2023](https://biblioteca.sbrt.org.br/articlefile/4516.pdf)). Daí duas consequências. A negociação faz sentido quando o **tempo de residência** do nó numa condição de canal supera o ciclo negociar+validar, o que vale para pedestre e gado. Para veículos em NLoS urbano, o modo base ou uma escada pré-acordada é mais seguro. Além disso, a adaptação por distância GNSS deve ser auxiliar, nunca substituta da SNR.

### Malha: nenhum benchmark controlado existe, e isso é oportunidade

A avaliação quantitativa de Meshtastic, MeshCore e Reticulum é rasa. O melhor estudo de 2026 mede presets Meshtastic num enlace único cabeado: os presets curtos falham em 110–120 dB e o LongSlow em ~180 dB, com falha abrupta a 2–4 dB do limite teórico **[HW-PP]** ([Hernandez Ortiz et al., arXiv 2605.17063](https://arxiv.org/abs/2605.17063)). Um sistema de campus com 4 nós reporta só SNR de um enlace **[HW-PP]** ([arXiv 2605.20379](https://arxiv.org/html/2605.20379v1)). Para MeshCore e Reticulum só encontrei comparações qualitativas em wikis ([Colorado Mesh](https://wiki.coloradomesh.org/index.php/Meshtastic_vs_MeshCore_vs_Reticulum)). No lado acadêmico, a métrica de roteamento por time-on-air multi-SF do grupo LoRaMesher equilibra o PDR e reduz a latência **[SIM-PR]** ([Pueyo Centelles et al., IEEE Access 2024](https://doaj.org/article/6a9af1db0ea4433bb41b1aa855d0211b)). Uma malha TDMA em ns-3 mostrou que relays perto do sumidouro gastam ~315% mais energia e que atribuições estáticas repetem as mesmas colisões a cada ciclo **[SIM-PR]** ([Durand & Booysen, Sensors 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11902654/)). Isso sustenta usar um custo de enlace ETX × ToA no vetor de distância. Note também que o vizinho mais próximo apontado no Doc 02, o AURORA (JCN 2026, SF por enlace em TSCH/RPL com hardware), já ocupa a ideia de "SF por enlace numa malha". A originalidade da Légua na malha está em operar sem TSCH, sob FHSS regulatório e com acordo validado, e não na adaptação por enlace em si.

## A regulação de 2026 reescreve a tabela de modos

### Os números de salto do projeto estavam errados

O Doc 01 usava números da FCC (≥50 canais, 0,4 s a cada 20 s). Uma cópia do texto original de 2017 do Ato 14.448, Seção 10.2.5, dá para 902–907,5 e 915–928 MHz: **1 W de pico com ≥35 canais de salto, ou 0,25 W com menos; largura de 20 dB abaixo de 250 kHz exige ≥35 saltos e ≤0,4 s em 14 s; largura de 250 kHz ou mais exige ≥17 saltos e 0,4 s em 7 s; largura máxima de 500 kHz** **[SEC: cópia no fórum TTN, resumida por ferramenta]** ([Ato 14.448, cópia TTN](https://www.thethingsnetwork.org/forum/uploads/default/original/2X/e/e75d7b1471333df4ddc7f8d4eff114e5a126b59c.pdf)). O mesmo texto confirma que **907,5–915 MHz não está na faixa**. Um perfil "US915" copiado, portanto, não é conforme no Brasil. O item 10.2.8.1 **proíbe coordenar conjuntos de salto entre múltiplos transmissores** para evitar as mesmas frequências. Já o item 10.2.8 permite que cada sistema adapte individualmente seu conjunto de saltos. Na modulação digital (10.3), a DEP é limitada a 8 dBm por 3 kHz. Pelo meu cálculo, com espectro plano isso dá ~24 dBm em 125 kHz, ~27 dBm em 250 kHz e ~30 dBm em 500 kHz. Ou seja, "1 W como modulação digital" só fecha em 500 kHz **[PRÓPRIO]**, o que é coerente com o exemplo da Semtech de SF7/125 a +21 dBm no modo híbrido **[DOC]** ([Semtech AN1200.62](https://www.mouser.lt/pdfDocs/AN120062_BestPracticesforFCC_Rev_1_0_FINAL.pdf)).

Sobre a mudança de 2025/2026, o Art. 11, III do Ato 14.158/2025 revoga o item 10.3.4.4, que isentava da largura mínima de 500 kHz os equipamentos avaliados pelo método alternativo. O Ato 4.746/2026 adiou essa revogação para **06/10/2026**. O Art. 19, alterado, mantém a base original para produtos já homologados, na manutenção da certificação **[SEC]** ([GMA Labs](https://www.gmalabs.com/post/brazil-anatel-restricted-radiation-equipment-500-khz-rule); [IB-Lenhardt](https://ib-lenhardt.com/news/anatel-6-db-bandwidth-exemption-to-end-on-october-6-2026)). A GMA recomenda consultar o OCD **antes de qualquer alteração de hardware ou firmware** que possa disparar reavaliação. Para uma biblioteca, isso significa que a "exceção de produtos homologados" do Doc 04 não serve de base de projeto. Uma atualização de firmware que habilite modos novos provavelmente cai na regra nova.

### O que cabe no envelope: tempo no ar como restrição dura

A tabela abaixo é **[PRÓPRIO]**, calculada com a fórmula padrão de tempo no ar LoRa, preâmbulo de 8 símbolos, cabeçalho explícito, CRC ligado e LDRO quando o símbolo é ≥16 ms. Os valores estão em ms.

| Modo | Payload PHY 16 B (CR 4/5 / 4/8) | 24 B (4/5 / 4/8) | 25 B (4/5) | 32 B (4/5) | Regime aplicável (BR-2026, a confirmar) |
|---|---|---|---|---|---|
| SF7/125 | 51 / 70 | 62 / 86 | 62 | 72 | FHSS ≥35 canais, ≤0,4 s/14 s |
| SF9/125 | 165 / 214 | 206 / 280 | 206 | 247 | FHSS ≥35 canais |
| **SF10/125** | 330 / **428** | **371** / 494 | **412** | 453 | FHSS: **só CR 4/5 e ≤24 B** |
| SF11/125 | 659 / 856 | 823 / 1118 | 823 | 987 | **Excede 0,4 s → proibido em FHSS** |
| SF12/125 | 1319 / 1712 | 1483 / 1974 | 1483 | 1810 | **Proibido em FHSS** |
| SF11/250 | 289 / 362 | 371 / 494 | 371 | 412 | FHSS ≥17 canais, 0,4 s/7 s (≈ sensibilidade de SF10/125) |
| SF12/250 | 659 / 856 | 741 / 987 | 741 | 905 | Proibido em FHSS |
| **SF12/500** | 289 / 362 | 330 / 428 | 371 | 412 | **Digital (≥500 kHz, DEP 8 dBm/3 kHz): sem limite de dwell, até ~1 W** |

Três consequências práticas saem daí. A primeira é que o modo base SF10/125 tem uma **parede dura de 24 bytes de payload PHY**: cabeçalho, MIC do AES-CCM e corpo precisam caber nesse total. Com cabeçalho de 8 B e MIC de 4 B sobram 12 B de corpo, e não 16 B como o Doc 04 assumiu. Com cabeçalho implícito ganham-se 2 B. A segunda é que **a adaptação de CR só tem efeito em SF≤9** dentro do FHSS de 125 kHz, porque SF10 com CR 4/8 já estoura 0,4 s com 16 B. A terceira é que o "modo base robusto SF12/125 a 28 dBm", estimado no Doc 04 em ~2 J por mensagem de controle (recomendação S10), **não existe legalmente** na leitura BR-2026. A alternativa de longo alcance legal é SF12/500 em modo digital. Ela é ~6 dB menos sensível que SF12/125, mas pode usar até ~30 dBm sem dwell, e é por isso que a simulação mostrou "só Légua e SF12/500 fixo mantêm alcance".

### Pontos regulatórios ainda não verificados

| Ponto | Status | Fonte | Ação |
|---|---|---|---|
| 10.2.5: ≥35 canais / 0,4 s em 14 s (<250 kHz); ≥17 / 0,4 s em 7 s (≥250 kHz); 1 W só com ≥35 | **[SEC]**, texto de 2017 resumido por ferramenta | cópia TTN | Ler o texto consolidado e confirmar se o Ato 14.158 alterou 10.2.5 ou 10.4 |
| Revogação do 10.3.4.4 em 06/10/2026; 30 dBc fora da faixa | **[SEC]** | GMA Labs, IB-Lenhardt | Confirmar no Ato 14.158/4.746 oficial |
| Alcance do Art. 19 (base antiga na manutenção) para firmware novo | **[SEC]**, interpretação | GMA Labs | Consulta formal ao OCD |
| Rota de baixa potência em "outra seção do Ato 14.448" | **[NV]** | menção da GMA | Identificar a seção e os limites de campo |
| Exigência de antena fornecida com o produto (Res. 680) | **[NV]**, não está na Seção 10 | — | Ler a Res. 680/2017 |
| Redução de potência quando a antena passa de 6 dBi (10.5) | **[SEC]** | cópia TTN | Incluir no teto de potência do integrador |
| Escuta "stay" num canal não está sujeita ao dwell | **[PRÓPRIO]**, o limite é de ocupação em TX | inferência | Confirmar com o OCD |
| Homologação Anatel da Heltec WiFi LoRa 32 V4 (915 MHz) | **[NV]** | — | Consultar SCH/Mosaico |
| UTE (Res. 775/2025) e RGST (Res. 777/2025) para experimentos | **[SEC]**, consultoria | Direto Legaliza | Validar no site da Anatel antes da campanha T3 |

## Três contribuições publicáveis, e onde levá-las

### Alegações fortes e alegações fracas

A alegação **mais forte** é a de um protocolo de adaptação negociada P2P (sem gateway) com instante de troca combinado, validação, âncora persistida e rollback em dois níveis, acompanhado de **verificação formal** de "nenhum desacordo permanente". Não encontrei verificação formal de LoRa P2P nem de negociação com rollback. Os precedentes de método existem: PRISM na descoberta Bluetooth ([Duflot et al., STTT](https://www.dcs.gla.ac.uk/~gethin/papers/sttt-bluetooth.pdf)), mCRL2 no TSCH ([Talebi et al.](https://ar5iv.labs.arxiv.org/html/1703.06572)) e Tamarin no join LoRaWAN ([lorawan-tamarin-analysis](https://github.com/lorawan-tamarin-analysis/lorawan-tamarin-analysis)). A busca bibliográfica foi limitada e precisa de uma rodada dedicada (Scholar/DBLP) antes de afirmar prioridade.

A **segunda** é a seleção de modo restrita por um perfil regulatório executável (BR-2026: tabela de modos × dwell × DEP × canais), com teste ou prova de que a adaptação nunca sai do envelope. Ela ganha força porque a mudança de 06/10/2026 é recente e afeta qualquer produto LoRa novo no Brasil.

A **terceira** é empírica e tem baixo risco: medições em SX1262 (Heltec V4 a 28 dBm) do custo do plano de controle, das curvas PDR×atenuação por modo, do ganho isolado de BW e CR, de um **microbenchmark de CAD multi-SF** (sem dados publicados para SX126x) e, se houver orçamento, uma **comparação controlada no mesmo hardware de Meshtastic, MeshCore, Reticulum, LoRaMesher e Légua**, que não existe na literatura.

São **fracas** as alegações de "adaptação de SF/BW/CR/potência", que já existe em AdapLoRa, RALoRa e na família ADR, e de "primeira avaliação 1 W FHSS P2P no Brasil", que é difícil de provar e atrai contestação. Isso serve como contribuição secundária. Superar o Meshtastic também não é alegação de novidade: ele é baseline, e a comparação só é justa em métricas de enlace com presets equivalentes.

### Venues por camada

Para o artigo de protocolo, SBRC, SBrT e LATINCOM servem a um trabalho com 2 a 15 nós. O JISA (SBC) já publica ADR para mobilidade da UFPI, o que o torna um destino natural para a parte de mobilidade ([LoRa-LQE, JISA](https://journals-sol.sbc.org.br/index.php/jisa/article/download/7298/4207/43118)). Em periódico, IEEE IoT-J, Ad Hoc Networks, Computer Networks, IEEE Access e Sensors. Venues do tipo ICNP/SenSys esperam testbeds de dezenas de nós com baseline forte, como o AdapLoRa com 20 nós e 4 gateways, e um trabalho P2P com poucos nós dificilmente basta. Para o artigo de software, o precedente direto é o **LoRaMesher na SoftwareX (2026)** ([UPC DSG](https://dsg.ac.upc.edu/bibcite/reference/1133)). O JOSS exige **repositório público há mais de 6 meses com desenvolvimento ativo**, software completo e declaração de uso de IA ([JOSS](https://joss.readthedocs.io/en/latest/submitting.html)). Para submeter em 2027, o repositório precisa abrir ainda em 2026. As normas de SBRC, SBrT, LATINCOM, IoT-J e SoftwareX (páginas, double-blind, APC) **não foram verificadas**.

### Nome e patentes

O nome "Légua" tem dois riscos. O primeiro é a colisão quase exata com o **AdapLoRa** (ICNP 2020), que confunde buscas e revisores. O segundo é que a Semtech lista como erro "usar ou incorporar a marca LoRa como parte de qualquer outro nome de produto" ([Semtech](https://blog.semtech.com/how-to-name-and-brand-your-lora-application)). O LoRaMesher publicou com a marca no nome, o que indica tolerância acadêmica, mas não autorização. Recomendo trocar o nome antes de abrir o repositório.

Quanto a patentes **[PAT]**, a **US 11778511 (Toshiba, até ~2040)** reivindica: detectar qualidade fora da faixa → transmitir **≥2 sondas com configurações distintas** → o par indica qual usar → aplicar ([Google Patents](https://patents.google.com/patent/US11778511B2/en)). Um PROPOSE de **um único** candidato, decidido com métricas já observadas no modo base e validado depois, parece ficar fora da letra das reivindicações independentes. O risco cresce se a biblioteca implementar "testar 2+ modos e o receptor escolhe". A **US 12184325** cobre receptor que **varre SF ciclicamente** ([Google Patents](https://patents.google.com/patent/US12184325)), e a recuperação deve usar o modo base fixo, não varredura cega de SF. Isto não é parecer jurídico: há doutrina de equivalentes, e convém consultar um advogado de patentes antes de comercializar.

## Escopo refinado: um par bem provado vale mais que uma malha meio pronta

A v1 deve entregar, em C99 puro com simulador de PC (como no Doc 03), uma máquina de estados **por enlace P2P**. Ela tem um modo base FHSS SF10/125/CR4/5 com controle de no máximo 24 B, uma tabela de modos parametrizada por perfil regulatório e uma **escada de degradação pré-acordada**: modo atual → modo mais robusto → âncora → base. Essa degradação é **unilateral e imediata**, sem PROPOSE/VOTE, porque todos conhecem a escada. Só a **aceleração** é negociada, e raramente. O controle de potência também é unilateral, já que mudar a potência de TX não exige nada do receptor. O estimador combina **SNR com EMA e penalidade por variância para propor** e **PDR/ACK na janela de validação para decidir COMMIT ou rollback**, com detecção de mudança (CUSUM/Page-Hinkley) para invalidar o estado aprendido. É o padrão do Wi-SUN (razão falhas/sucessos), dos bandits por ACK e do LoRa-LQE. A âncora e o contador anti-replay são gravados **juntos e só depois da validação**, com o rádio ocioso: o BLE perde o *instant* quando um erase de flash bloqueia a CPU **[SEC/HW]** ([Nordic DevZone 63219](https://devzone.nordicsemi.com/f/nordic-q-a/63219/ble_hci_instant_passed-disconnection-after-ll_channel_map_req-during-flash-erase/258673)). Todo o controle é autenticado (MAC truncado sob chave de rede, com o modo e a época ligados ao MIC, como o OCI do OCV). Os parâmetros de segurança ficam **fora** da negociação, porque esse é o vetor do KNOB ([Antonioli et al., ACM TOPS 2020](https://www.cs.ox.ac.uk/publications/publication14289-abstract.html)).

Entram como **cenário de avaliação, com implementação mínima**: grupos em estrela com coordenador, votos em slots TDMA atribuídos no PROPOSE e divisão do grupo quando há membro fraco; e flooding no modo base com contenção ponderada por SNR. Ficam **adiados para a v2**: o vetor de distância com custo ETX × ToA, a varredura de CAD multi-modo, SF5/SF6, BW abaixo de 125 kHz (o Doc 04 já mostrou que acrescentam pouco), bandits e a adaptação por GNSS, que entra apenas como prior e como gatilho para congelar acelerações. Ficam **cortados no perfil BR**: SF11/SF12 a 125 kHz, o modo base robusto SF12/125 e qualquer coordenação de conjuntos de salto entre enlaces distintos (10.2.8.1).

## Decisões do projeto que devem mudar

| # | Decisão atual (Docs 01–04) | Mudança recomendada | Base |
|---|---|---|---|
| 1 | Salto ≥50 canais, 0,4 s/20 s (FCC) | **≥35 canais, 0,4 s/14 s (<250 kHz); ≥17, 0,4 s/7 s (≥250 kHz); 1 W só com ≥35 canais**; 902–907,5 e 915–928 MHz | Ato 14.448 **[SEC, a verificar]** |
| 2 | "Potência máxima legal" | Teto do integrador (Doc 03) + redução para antena >6 dBi + **potência medida por unidade** (V4: 25,6 dBm medidos para 27 configurados) | [Heltec](https://wiki.heltec.org/news/heltec-v4-test-result/heltec-v4-test-result) **[SEC/HW]** |
| 3 | Perfil com "exceção de homologados" | Perfil **BR-2026 como padrão**; BR-legacy só como documentação; parâmetros regionais (faixas, N, janela de dwell, P_max, DEP) | GMA Labs **[SEC]** |
| 4 | Controle ≤ ~24 B, cabeçalho ≤8 B, corpo de 16 B | **Payload PHY total ≤24 B** (cabeçalho + MIC + corpo) a SF10/125/CR4/5; avaliar cabeçalho implícito | **[PRÓPRIO]** tabela de ToA |
| 5 | Modo base robusto SF12/125 a 28 dBm (S10) | **Remover no BR**; alcance longo via **SF12/500 digital** com verificação de DEP | idem |
| 6 | CR 4/5–4/8 adaptável em qualquer modo | CR adaptável só em SF≤9 (125 kHz) ou em 500 kHz | idem |
| 7 | Unanimidade em grupos | Coordenador com 2PC + votos em slots + **divisão de grupo** + modo do grupo limitado pelo pior membro, com limiar de exclusão | Modelo Π(1−p_i)³ **[PRÓPRIO]**; Doc 04 |
| 8 | Rollback → âncora → base, adaptação simétrica | **Degradar unilateral por escada pré-acordada; acelerar negociado**; potência unilateral | Wi-SUN **[DOC]**; LoRa-LQE **[SIM]** |
| 9 | Histerese de ≥10 min entre mudanças | Perfil móvel: *cooldown* curto para degradar, longo para acelerar; congelar aceleração acima de um limiar de velocidade GNSS ou de variância de SNR (a 50 km/h, 10 min equivalem a >8 km) | [Karunathilake](https://arxiv.org/pdf/2311.18070) **[HW-PP]** |
| 10 | Âncora em NVM (momento não especificado) | Gravar **após a validação**, com o rádio ocioso, junto com o contador anti-replay | Nordic/TI **[SEC/HW]** |
| 11 | AES-CCM com chave de rede | + MAC em todo o controle, modo e época ligados ao MIC, limite de taxa de rollback e alarme de rollback repetido sem queda de SNR (jamming) | OCV, KNOB **[PR]** |
| 12 | Sondagem para estimar o modo | **Um candidato por vez**; sem "2+ sondas e o par escolhe"; sem varredura cega de SF | US 11778511, US 12184325 **[PAT]** |
| 13 | Recomendação S6 (slots em janelas de grupo) e custo ponderado por interferência (S9) | Permitido coordenar tempo dentro do grupo; **proibido coordenar conjuntos de salto entre enlaces/grupos** para evitar frequências | 10.2.8.1 **[SEC]** |
| 14 | Multi-hop: flooding e depois DV | Flooding e controle **sempre no modo base**; negociação só em unicast estável; DV com custo ETX × ToA na v2 | Pueyo Centelles **[SIM-PR]**; Meshtastic **[DOC]** |
| 15 | LDRO conforme chip | **LDRO automático e não desligável** quando o símbolo é ≥16 ms; verificar se o V4 tem TCXO | Semtech AN **[DOC]** |
| 16 | GNSS opcional para adaptação | GNSS como prior/detector de tendência; **a SNR medida manda** | Inatel SBrT 2023 **[HW-PR]** |
| 17 | Rendezvous no ciclo de ~20 s | "Stay" escutando um canal fixo: pior caso ≈ **35 × 0,4 s ≈ 14 s**, média ≈7 s; bootstrap a frio assimétrico (um escuta, outro salta) | Jump-Stay **[TEÓRICO]**; **[PRÓPRIO]** |
| 18 | Nome "Légua" provisório | Renomear (colisão com AdapLoRa e marca Semtech) | ICNP 2020; Semtech |
| 19 | Fases 0–7 do Doc 03 | Inserir **verificação formal** (TLA+/UPPAAL/PRISM) antes da bancada; **abrir o repositório** já em 2026 | JOSS |

## Plano de testes em sete fases

> **Escopo (15/11/2026).** Neste repositório ficam os itens simulados do plano (`docs/06`). Os itens que exigem as
> placas Heltec (B1, medições reais de B2, B8, B9, B10, a bancada T2 e o campo T3) ficam para o repositório de
> bancada. O mapa item a item está em `docs/09`.

### Princípios transversais

Toda comparação é **pareada e intercalada**: configurações A/B/C alternam em rodízio no mesmo enlace, para que a variação temporal afete todas por igual, e o conjunto é repetido em **≥3 dias distintos**. Cada pacote leva número de sequência e é registrado em TX e em RX, em JSON lines. Os campos são: timestamp GNSS disciplinado por PPS, posição, velocidade, modo (SF/BW/CR/potência/canal), RSSI, SNR, FEI quando disponível, estado da máquina (BASE/NEGOTIATING/SWITCHING/VALIDATING/ANCHOR/DATA), temperatura e hash git do firmware. Isso torna o PDR exato, ao contrário do estudo de Bonn, em que as perdas eram invisíveis ([arXiv 2109.07768](https://arxiv.org/pdf/2109.07768)). O CRC fica sempre ligado, e os pacotes com CRC inválido são registrados.

### Tamanho de amostra

| Objetivo estatístico | Cálculo | n mínimo |
|---|---|---|
| PDR≈0,90 com IC95% ±2 pp | 1,96²·0,9·0,1/0,02² | **~865 pacotes/condição** (literatura: 1.000–4.300/ponto ([Jörke, PIMRC 2017](https://comnets.etit.tu-dortmund.de/storages/cni-etit/r/Research/Publications/2017/Joerke_PIMRC/Joerke_PIMRC_10_2017.pdf))) |
| PDR≈0,99 com IC95% ±0,5 pp | 1,96²·0,99·0,01/0,005² | **~1.520 pacotes** **[PRÓPRIO]** |
| Diferença de 5 pp (0,90 contra 0,95), α=0,05, poder de 80% | (1,96+0,84)²·(0,09+0,0475)/0,05² | **~430 por braço**, inflar ×2–3 por perdas em rajada **[PRÓPRIO]** |
| "Zero desacordo permanente" com limite superior <0,1% (regra de três) | 3/n | **≥3.000 negociações** com falha injetada **[PRÓPRIO]** |
| Curva de transição PDR×atenuação | degraus de 1–2 dB | **≥100 pacotes/degrau** ([Bonn](https://arxiv.org/pdf/2109.07768)) |
| Célula de mobilidade (velocidade × modo × ambiente) | 1 pkt/s | **≥30 min ≈ 1.800 pacotes** ([Bremen](https://arxiv.org/pdf/2311.18070)) |
| Ajuste de path loss (σ estável) | — | **20–30 mil amostras** agregadas; evitar <1.000 ([Bonn](https://arxiv.org/pdf/2109.07768)) |

Os pacotes LoRa perdem-se em rajadas ([RALoRa](https://par.nsf.gov/servlets/purl/10536073)). Por isso a unidade estatística correta é o **bloco** (sessão, dia), com IC de Wilson ou Clopper-Pearson por bloco e efeitos aleatórios entre dias. Contar pacotes independentes subestima a incerteza.

### Métricas

As métricas principais de enlace são o PDR com IC, o goodput, a **energia por bit útil entregue** (∫V·I dt / bits entregues), o airtime por pacote entregue e a latência via PPS. As métricas principais do protocolo são o **tempo até COMMIT**, a **energia e o airtime de controle por adaptação**, a taxa de rollback para âncora e para base, a **duração e a frequência de desacordo transitório**, o tempo fora do modo base, o tempo de recuperação após perda total, o número de trocas por hora e o MTTR de rendezvous. Na malha entram ETX, reachability e usefulness (as métricas do Meshtasticator ([GitHub](https://github.com/meshtastic/Meshtasticator))), ocupação de canal por nó e energia dos relays. Para conformidade, mede-se a **ocupação por canal em qualquer janela de 14 s** (ou 7 s), o número de canais efetivamente usados, a DEP e a potência conduzida medida.

### Fases e matrizes de cenários

**Fase 0: pré-requisitos regulatórios, jurídicos e de dados (bloqueante para T3).** Ler os textos consolidados (Atos 14.448, 14.158 e 4.746 e a Res. 680) e confirmar a homologação da Heltec V4 de 915 MHz. Consultar um OCD sobre firmware próprio e decidir se a campanha de campo pede **UTE** (Res. 775/2025: experimento não comercial por até 24 meses, pedido via Mosaico com ≥30 dias de antecedência, isenção de homologação só no período autorizado **[SEC]** ([Direto Legaliza](https://diretolegaliza.com/?p=12736))). Fechar o plano LGPD e o novo nome.

**Fase 1 (T0 + formal): correção e garantias.** Os testes unitários da máquina de estados devem cobrir 100% das transições. Os modelos formais têm três camadas. Em TLA+ ou SPIN, verificar a invariante ¬(validated_i ∧ validated_j ∧ mode_i≠mode_j) e a vivacidade ◇□acordo sob *fairness*, com perda, duplicação e reordenação, para 2–4 nós e perdas assimétricas. Em UPPAAL, verificar a coerência dos temporizadores (instante, validação, âncora, base, dwell). Em PRISM, calcular P(acordo ≤T) e o tempo esperado de reconvergência, incluindo um adversário MDP (jammer) contra a janela de validação. O critério de saída é zero contraexemplos de desacordo permanente nos cenários de estrela com membro fraco e de "ponte estreita".

**Fase 2 (T1): simulação e validação cruzada.** Reproduzir no adaptsim cenários do Meshtasticator e do LoRaSim (validação simulação×simulação). Rodar a nova tabela de modos BR-2026 e reexecutar as recomendações S1–S12 com a parede de 24 B. Preparar séries temporais para reprodução *trace-driven* em T2 e recalibrar com dados de T3 (expoente, σ de sombreamento, AR(1)).

**Fase 3 (T2): bancada conduzida.** A cadeia é TX → atenuador fixo de potência (≥40 dB, ≥2 W) → divisor → atenuador programável → RX, com cargas de 50 Ω e placas em caixa blindada. A maior parte do trabalho é feita em 0–10 dBm, com um **teste de vazamento** (cabo desconectado, nenhuma recepção). Com 28 dBm e sensibilidade de SF12 perto de −148 dBm, o orçamento de ~176 dB não fecha sem vazamento irradiado ([nota metodológica; Heltec mediu com 40 dB/10 W](https://wiki.heltec.org/news/heltec-v4-test-result/heltec-v4-test-result)).

| ID | Cenário de bancada | Variáveis | n / critério |
|---|---|---|---|
| B1 | Calibração RSSI/SNR e potência por unidade | 8 níveis de potência (0–28 dBm) × todas as placas | 100 pkt/nível; perda de inserção medida em VNA |
| B2 | Curvas PDR×atenuação por modo | SF7/9/10/125, SF11/250, SF12/500; CR 4/5 e 4/8 onde couber | ≥100 pkt/degrau de 1–2 dB; ganho isolado de BW e CR |
| B3 | Custo do plano de controle | Rodadas de negociação em SF10/125 com 0–30% de perda injetada | ≥1.000 negociações por nível: tempo até COMMIT, mJ, airtime |
| B4 | **Injeção de falhas** | Perda de PROPOSE/VOTE/COMMIT por lado, perda na validação, *reboot* durante a validação, flash ocupada no instante, deriva de relógio | **≥3.000 negociações**; zero desacordo permanente |
| B5 | Rendezvous | Nó novo em "stay"; bootstrap a frio com 2 nós; 35 canais | ≥200 junções: MTTR, pior caso ≤ ~14,4 s |
| B6 | Reprodução de traços | Séries do adaptsim e de T3 no atenuador programável | Mesma decisão de adaptação em SIM e T2 (concordância %) |
| B7 | Segurança | Replay, PROPOSE forjado, jamming da janela de validação (SDR com gr-lora ([arXiv 2002.08208](https://arxiv.org/pdf/2002.08208))) | Taxa de rollback induzido, detecção de alarme |
| B8 | Energia | Tabela corrente × potência × estado (TX/RX/CAD/sono) | PPK2 para sono, RX e TX baixo; shunt + INA226 ou osciloscópio para TX alto |
| B9 | Deriva térmica e LDRO | SF12/500 e SF11/250 a 28 dBm, pacotes longos, FEI | Deriva dentro da tolerância dinâmica |
| B10 | CAD multi-SF (opcional, publicável) | P(detecção)/P(falso) e duração por SF×SNR | ≥1.000 CADs/célula |
| B11 | Conformidade | Ocupação por canal em 14 s/7 s, nº de canais, DEP em 500 kHz | Analisador de espectro (TinySA) + log do firmware |

O PPK2 vai até **1 A** a 100 ksps ([Nordic](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2)), e a V4 tem picos de TX **próximos de 1 A** a 27 dBm, com operação errática abaixo de 3,45 V ([Heltec](https://wiki.heltec.org/news/heltec-v4-test-result/heltec-v4-test-result)). Por isso o TX de alta potência deve ser medido por shunt e osciloscópio, alimentando por Vin/bateria e não por USB. O INA226 serve para logging longo em campo, não para transientes.

**Fase 4 (T3a): campo fixo P2P, urbano e rural, 915 MHz.** São pontos de confiabilidade com ≥1.000 pacotes por ponto e configuração, em rodízio. Registrar a altura das duas antenas, o ganho e a perda de cabo, o perfil de terreno e o raio de Fresnel (SRTM/Copernicus), a vegetação, a temperatura e a chuva. O ChirpBox observou queda de enlace em períodos quentes ao longo de um ano ([ChirpBox](https://chrisye-liu.github.io/files/ye2024chirpbox.pdf)).

| ID | Ambiente | Distâncias / geometria | Configurações em rodízio |
|---|---|---|---|
| F1 | Urbano denso (centro) | 0,3–3 km, NLoS, um lado no telhado | Base SF10/125 FH; SF7/125 FH; SF12/500; Légua; ADR do lado do nó |
| F2 | Urbano residencial / suburbano | 1–5 km | idem |
| F3 | Indoor ↔ outdoor | 3 pontos internos | idem |
| F4 | Rural aberto (pasto, LoS) | 2–15 km, mastro de 5–10 m | idem + perfis de potência |
| F5 | Rural com relevo / mata ciliar | 1–8 km, obstrução de Fresnel | idem |
| F6 | Longa duração (2–4 semanas) | 2–3 enlaces F1 e F4 | Légua contra o melhor fixo: estabilidade, trocas por hora e rollbacks |

**Fase 5 (T3b): mobilidade.** A matriz parte do Bremen ([arXiv 2311.18070](https://arxiv.org/pdf/2311.18070)) e do estudo com UAV ([arXiv 1902.11243](https://arxiv.org/pdf/1902.11243)), com rotas fixas e trechos LoS/NLoS marcados.

| ID | Portador | Velocidade | Ambiente | Hipótese testada |
|---|---|---|---|---|
| M1 | Pedestre (mochila/peito) | 4–6 km/h | Urbano e rural | Negociação compensa (residência longa) |
| M2 | Bicicleta | 15–20 km/h | Urbano | Transição |
| M3 | Carro (teto, ~1,7 m) | 30–50 km/h | Urbano NLoS | Perfil móvel (degradação unilateral) supera a negociação |
| M4 | Carro em rodovia | 80–110 km/h | Rural | idem; deriva + Doppler em pacotes longos |
| M5 | **Passagem cruzada** de dois veículos | 2 × 50–80 km/h | Rodovia | Doppler dinâmico ±; LDRO obrigatório |
| M6 | Drone | 5–15 m/s, a 30/60/120 m | Urbano e rural | Ganho de altura; polarização |
| M7 | **Gado** (colar) | ≤ 6 km/h, dias | Fazenda | Caso mais favorável; perdas atrás de relevo ([AgroTrack](https://arxiv.org/html/2510.07322v1) [HW-PP]) |

Cada célula alterna (i) o modo base fixo, (ii) o modo rápido fixo, (iii) a Légua com perfil fixo e (iv) a Légua com perfil móvel, com ≥1.800 pacotes. Para drones vale observar regras próprias de operação de aeronaves não tripuladas, fora do escopo destas notas e não verificadas aqui. Gado exige o acordo do produtor e o bem-estar do animal, com colar leve e sem interferir no manejo.

**Fase 6 (T3c): topologias e baselines.** O mesmo hardware SX1262 (Heltec V4) é usado em todas as stacks.

| ID | Topologia | Nós | Comparação | Métrica decisiva |
|---|---|---|---|---|
| T1 | P2P | 2 | Légua contra presets fixos (SF7/125 FH, SF10/125 FH, SF12/500) e ADR do lado do nó (EMA-ADR na mesma biblioteca) | Energia/bit e PDR |
| T2 | Estrela homogênea | 1+4 | Unanimidade | Tempo até COMMIT |
| T3 | **Estrela com membro fraco** | 1+4 (um a −5/−10 dB) | Unanimidade contra divisão do grupo contra relay pelo membro forte | Energia do grupo, PDR do fraco |
| T4 | Malha em linha / ponte estreita | 5–6 | Flooding no base contra Meshtastic contra LoRaMesher | Latência, airtime |
| T5 | Malha em grade / aleatória | 10–15 | Légua (flooding + enlaces adaptados) contra Meshtastic 2.8 (hop limit automático), MeshCore, Reticulum/RNode, LoRaMesher | PDR com denominador conhecido, ocupação de canal, energia dos relays |
| T6 | Malha com 1–2 nós móveis | 10 + 2 | Reconvergência e *handover* de relay | Tempo de recuperação |

Há um cuidado com os baselines que costuma passar despercebido: as stacks comunitárias **não implementam o FHSS brasileiro** de 35 canais com 0,4 s/14 s, e presets longos ultrapassam 0,4 s por pacote. Em alta potência no ar, sob BR-2026, elas operariam fora do envelope. Por isso devem ser comparadas **em bancada conduzida** ou em campo sob **UTE** ou em potência baixa. O artigo deve declarar essa assimetria como parte do resultado: só a Légua e o SF12/500 fixo são conformes em alta potência. O suporte de MeshCore e Reticulum à Heltec V4 **não foi verificado**. A metodologia de "PDR com denominador conhecido" do Sending Stones é um bom modelo ([GitHub](https://github.com/OpenResearchInstitute/sending-stones)).

**Fase 7: consolidação e dados abertos.** Publicar o dataset em Zenodo com DOI e CC BY 4.0, no formato do dataset de Antwerp mais as colunas de modo e estado ([Zenodo](https://zenodo.org/records/1193563)), junto com o firmware, a configuração calibrada da bancada e os modelos formais. Recalibrar o adaptsim e publicar o erro sim↔hardware.

### Prioridade, critérios de parada e frota

A ordem de valor por esforço é Fase 0 → 1 → 3 (B1–B5, B8, B11) → 4 (F1, F4) → 5 (M1, M3, M7) → 6 (T1, T3) → o restante. A partir de B3/B4 já existe um artigo de workshop/SBrT (protocolo + verificação + bancada). Com F/M/T1–T3 chega-se a um artigo de periódico. T5 com todos os baselines é um terceiro artigo, independente. Há dois critérios de parada. Se o custo de controle em B3 superar a economia de energia projetada pelo Doc 04 para tráfegos típicos (por exemplo, menos de N mensagens entre adaptações), a aceleração negociada vira opcional e o produto se apoia em degradação unilateral com modos fixos. Se B4 encontrar desacordo permanente, a arquitetura volta à Fase 1. A frota mínima é de 6 placas V4 para bancada e P2P/estrela e de 12–16 para malha, cada uma com caixa IP67, bateria 2×18650 e, em nós fixos, painel solar, seguindo o desenho do ChirpBox ([ChirpBox](https://chrisye-liu.github.io/files/ye2024chirpbox.pdf)). O GNSS L76K com PPS serve à sincronização. Falta confirmar se o PPS está roteado para um GPIO com captura de interrupção na V4, o que não verifiquei.

## Cuidados regulatórios, LGPD e reprodutibilidade

No regime regulatório, a T2 conduzida em caixa blindada tem emissão irradiada mínima, mas deve ficar dentro de 915–928 MHz (ou 902–907,5 MHz). Na T3, se a V4 for homologada e o firmware se mantiver no envelope BR-2026 (FHSS conforme, potência medida ≤ 1 W conduzido, redução para antena acima de 6 dBi), é provável que não seja preciso autorização. Isso é inferência **[NV]**. Firmware que altere parâmetros de emissão pode descaracterizar a conformidade, e há precedente de multa por uso de produto não homologado ([Tecnoblog](https://tecnoblog.net/415013/anatel-multa-clinica-veterinaria-por-usar-produto-sem-homologacao/)). Os baselines comunitários em alta potência e modos fora do envelope pedem **UTE**. Fontes secundárias indicam que a Res. 777/2025 (RGST) substituiu o antigo regime científico/experimental e que a UTE isenta de homologação só no período autorizado ([Direto Legaliza](https://diretolegaliza.com/?p=12736)). O Sandbox Regulatório da Anatel é uma alternativa para testar um produto inovador ([Anatel](https://www.gov.br/anatel/pt-br/regulado/agenda-regulatoria/sandbox-regulatorio)). Para a biblioteca, a responsabilidade regulatória é do produto final certificado. A documentação deve dizer que os modos expostos precisam coincidir com os modos certificados.

Sobre a LGPD, trilhas GNSS de nós carregados por pessoas, veículos particulares ou gado de um produtor identificável são dados pessoais de geolocalização. Não encontrei orientação específica da ANPD para pesquisa em telecomunicações, e as medidas a seguir são **[NV]**, boas práticas por analogia. Elas incluem termo de consentimento para voluntários, motoristas e produtores, com a base legal de pesquisa definida junto ao encarregado da instituição. Antes de publicar, a precisão deve ser reduzida a uma grade de ~100 m, e trechos perto de origem e destino (residências, sedes de fazenda) removidos. Os timestamps absolutos devem ser deslocados por sessão. Os dados brutos ficam em armazenamento restrito, e só os derivados vão para o Zenodo.

Para reprodutibilidade, cada registro carrega o hash do firmware, as perdas calibradas da bancada ficam em arquivo versionado e os modelos formais, o adaptsim e os scripts de análise vão no mesmo repositório. Abrir o repositório cedo cumpre o requisito de 6 meses do JOSS e cria um histórico público de prioridade.

## Conclusão

A mudança de entendimento mais importante é que a pergunta deixou de ser "adaptar dá mais alcance?" e passou a ser "o que dá para provar sobre um acordo de modo entre rádios que não compartilham PHR nem gateway, dentro de um envelope legal que acabou de encolher?". A tabela de modos BR-2026 é estreita: SF≤10 a 125 kHz com 24 B, SF11/250 e SF12/500. Com ela, a adaptação vale menos como otimizador de alcance e mais como **mecanismo seguro de escolha entre poucos modos legais**, com degradação garantida. Isso favorece justamente a parte original do projeto, que é a semântica de acordo, validação e rollback, e reduz o peso da parte já publicada, a otimização de SF e potência. Um artigo que combine verificação formal, injeção de falhas em bancada e o custo medido do plano de controle é publicável mesmo que o ganho energético em campo seja modesto.

O segundo ponto é que a regulação brasileira atua ao mesmo tempo como restrição e como vantagem experimental. Nenhuma das stacks comunitárias usadas como baseline foi desenhada para 35 canais com 0,4 s/14 s, de modo que **a conformidade em si vira um resultado mensurável** (ocupação por canal, DEP, potência medida) e não uma nota de rodapé. A condição é que os números de salto e o alcance do Ato 14.158 sejam confirmados no texto oficial antes da primeira campanha no ar. Até lá, qualquer resultado de campo em alta potência precisa ser rotulado com a versão da interpretação regulatória usada.
