# 06 — Suíte de simulação do plano de testes (simsuite)

> Nome do projeto: **Légua** (antes "AdaptLoRa"; ver decisão de nome na conversa de 15/11/2026). Os docs 01–05 ainda usam o nome antigo.

Data: 15/11/2026. Base: plano de testes do doc 05 (Fases 0–7, B1–B11, F1–F6, M1–M7, T1–T6).
Código: pacote `simsuite` (Python + numpy/scipy/matplotlib), 20 cenários, testes automatizados (Python, núcleo C e site); a escala rápida leva ~9,5 min com um processo (~4 min com quatro) e a longa ~1 h 06 min (`docs/09`).

> **Escopo (15/11/2026).** Só simulação. Os experimentos com as placas Heltec e o firmware ficam em outro repositório (`docs/09`), que devolverá a calibração dos parâmetros estimados.

## 1. O que do plano é simulável

| Item | Simulável | Como |
|---|---|---|
| Fase 0 — Anatel/OCD/LGPD | Não | Decisão regulatória; a leitura atual (BR-2026, fonte secundária) está codificada em `core/regulatory.py` |
| Fase 1 — verificação formal | Sim | Verificador de estados explícito (BFS) com perda adversária + cadeia de Markov da rodada de negociação |
| Fase 2 — simulação e validação cruzada | Sim | Simulador de eventos discretos com os dois lados do protocolo, rádio half-duplex, CAD/LBT, salto sincronizado, colisões com captura |
| B1 calibração RSSI/potência | Não | Medida física |
| B2 PDR × atenuação | Parcial | Curvas do modelo; indicam onde medir com passos finos |
| B3, B4, B5, B6, B7 | Sim | Custo de controle, injeção de falhas, rendezvous, reprodução de traço, segurança |
| B8 energia, B9 deriva/LDRO, B10 CAD | Parcial | Tolerâncias exatas; correntes e taxas de deriva são estimativas a medir |
| B11 conformidade | Sim | Verificador sobre o log de TX (o mesmo roda nos logs reais) |
| F7 sintonia da aceleração | Sim | Variantes de margem de aceleração em enlace marginal: estabilidade × energia |
| F1–F6, M1–M7 | Parcial | Canal estatístico (LoS/NLoS, sombreamento correlacionado, Rice, Doppler) — dimensiona e pré-registra hipóteses |
| T1 | Sim | Mesmas sementes de canal para todas as configurações |
| T2/T3, T4–T6 | Parcial | Modelos nível-2 de Meshtastic, MeshCore, Reticulum, LoRaMesher |
| Fase 7 — telemetria | Sim | Esquema JSONL + analisador comum a logs simulados e reais |

## 2. Arquitetura

- `core/`: rádio (ToA, sensibilidade, LDRO, tolerância a deriva/Doppler, corrente com FEM até 28 dBm), canal fixo e móvel, mobilidade (pedestre, bicicleta, carro, drone, gado), regulação (plano de canais, sequência de salto com guarda de 15 ms, verificador), DES, atenuador de bancada.
- `protocol/`: tabela de modos BR-2026 e endpoint AdaptLoRa como máquina de estados pura (doc 03 E1), variantes travadas.
- `formal/`, `analysis/`, `baselines/`, `scenarios/`, `run_suite.py`, `tests/`.

## 3. Resultados da escala rápida (indicativos)

**Formal.** Referência: 179.393 estados (com histórico fantasma), P1 (sem desacordo permanente), P3 (recuperação sempre possível) e P4 (âncora de um modo em que o par já esteve) verdadeiras, maior desacordo 38 ticks. Sem validação ou com âncora no COMMIT, P4 falha (P1 e P3 seguem verdadeiras). Sem descida por silêncio, P1 e P3 falham (contraexemplo: A em DATA, B em BASE) — a descida por silêncio é obrigatória. Markov com 10% de perda: 64% das rodadas ficam no modo novo de primeira, 22% passam por desacordo transitório.

**B4 falhas.** ~300 negociações por caso, 0 desacordos permanentes (limite superior 95% ≈ 0,01; a escala completa com 3.000 leva a ≈ 0,001). Maior episódio de desacordo cresce com reboots.

**B5 rendezvous.** Pior caso de 14 s só com beacon em todo slot (93% de ocupação). Beacon a cada 10 s: média ~5 min, p95 ~15 min. O intervalo de beacon é parâmetro de projeto a fixar.

**B7 segurança.** Replay/forjado: 478 rejeitados, sem efeito. Jammer reativo na validação prende o par no modo base e multiplica a energia por pacote (~3 → ~89 mJ); o alarme de rollback corta os rollbacks pela metade (36 → 18).

**B9 deriva.** Com cristal comum (sem TCXO), SF10/125, SF11/250 e SF12/500 falham a ≥22 dBm pelo aquecimento do PA. Exigir TCXO ou forçar LDRO.

**B11 conformidade.** AdaptLoRa e os presets com salto ficam conformes; LongFast fixo a 22 dBm não.

**F (campo fixo, energia mediana por pacote entregue).**
- Rural aberto/serra e curtas distâncias urbanas: ganhos grandes, mesma entrega (F4 3 km: 57 mJ contra 323–2074 mJ dos presets; F1 0,3 km: 114 contra 336–2363).
- Limite de alcance: AdaptLoRa acompanha o modo base (F4 26 km 0,97; F1 3 km 0,40 ≈ base).
- Zona intermediária urbana (F1 0,6–1,5 km): PDR 1–4 pontos abaixo do base fixo; energia abaixo do base mas por vezes acima do SF7 fixo. É o ponto fraco a atacar.

**M (mobilidade).** Perfil móvel fica próximo do base fixo em confiabilidade (M4 rodovia 0,996; M5 0,99). Perfil fixo troca entrega por energia (M1 urbano 0,87 a 510 mJ). Em pedestre/drone rural o perfil fixo entrega ≥0,99 com 40–90 mJ.

**T2/T3.** Unanimidade sofre com membro fraco; relay é a melhor política.

**T4–T6 malha.** Sem regra (22 dBm), AdaptLoRa+fallback por inundação empata ou supera as malhas existentes (T4 urbano 0,70 contra 0,40 do Meshtastic). Sob BR-2026 com as malhas de terceiros limitadas a −3 dBm (canal fixo estreito), só AdaptLoRa funciona (0,96–1,0 contra ≤0,09). O fallback por inundação resolve quebras de rota com nós móveis (T6 urbano 0,96 → 1,0).

## 4. Ajustes de protocolo que a simulação motivou

1. HELLO de resposta do lado B no modo base (impasse de descoberta).
2. Validar sempre na potência máxima do modo; ajuste de potência só depois.
3. Contador próprio para o ajuste de potência (antes zerava o contador de sucessos e bloqueava acelerações).
4. Aceleração limitada por orçamento (≤6 dB cedidos por passo), não por posição na tabela.
5. Escada de degradação pré-acordada (+6 dB por degrau, função determinística da tabela) em vez de cair direto para R; volta à âncora após 120 s estável. Reduziu a energia em F1 0,6 km de ~1760 para ~690 mJ/pacote.
6. Lista negra temporária do candidato após rollback; backoff exponencial de negociação.
7. Perfil móvel com t_silence ≥ 3× intervalo da aplicação e congelamento por velocidade do par.
8. Fila esvaziada na troca de modo; heartbeat só ocioso; LBT/CAD antes de transmitir.

9. **Margem de aceleração com desvanecimento (F7, opcional, desligada por padrão).** O F6 urbano mostrou a Légua oscilando
   em enlace marginal. A causa: a margem fixa de 8 dB ignora a variabilidade do SNR, então a Légua acelera e cai logo em
   seguida por falhas seguidas. `Config.fade_k` soma k × desvio do SNR (30 amostras) à margem. Resultado na **escala
   longa** (7 dias × 5 sementes por enlace, mesmas sementes para todas as variantes):

   | Enlace | Variante | PDR | mJ/pacote | Quedas ao base (por hora) | Desacordo (s/h) |
   |---|---|---|---|---|---|
   | urbano denso 1 km | SF10/125 fixo (referência) | 0,969 | 4599 | 0 | 0 |
   | urbano denso 1 km | Légua, margem 8 dB (atual) | 0,959 | 3138 | 2,05 | 55,6 |
   | urbano denso 1 km | Légua, margem 14 dB | 0,966 | 4037 | 0,97 | 21,2 |
   | urbano denso 1 km | Légua, fade_k 3 | 0,967 | 5705 | 0,61 | 13,8 |
   | urbano residencial 3 km | SF10/125 fixo (referência) | 0,944 | 4398 | 0 | 0 |
   | urbano residencial 3 km | Légua, margem 8 dB (atual) | 0,941 | 4253 | 0,76 | 16,4 |
   | urbano residencial 3 km | Légua, fade_k 3 | 0,945 | 6781 | 0,10 | 2,1 |

   Conclusões: (a) em enlace marginal a Légua atual **economiza energia** no urbano denso (−32% contra o SF10 fixo) com
   cerca de 1 ponto percentual a menos de PDR, mas oscila (2 quedas ao modo base por hora); no residencial a 3 km fica
   praticamente empatada com o fixo (−3%). (b) A margem proporcional reduz as quedas em 70% a 87% e o desacordo em 75% a
   87%, e recupera o PDR do modo fixo, **mas devolve a energia**: com `fade_k = 3` a Légua gasta mais que o fixo (+24% no
   denso, +54% no residencial). A margem fixa de 14 dB é um meio-termo. (c) Não há ganho gratuito: estabilidade e energia
   são um compromisso. O padrão continua `fade_k = 0`; um perfil "estável" pode usar `fade_k` de 1 a 3. (d) Na escala
   rápida (2 sementes × 1 dia) o urbano denso parecia empate energético (4861 contra 5157 mJ, −6%): a escala longa mudou
   a conclusão, o que justifica rodá-la antes de decidir parâmetros. O F6 longo confirma: urbano denso 1 km a Légua
   gasta 2822 mJ/pacote contra 4520 do fixo, e no rural a 8 km 131 contra 3836 mJ (−97%, PDR 0,9999).
10. **Laço sem avanço em `_descend` (corrigido).** Quando a escada de degradação descia para o próprio modo base com o
    estado ainda `RECUPERACAO` ou `DATA` (ou a âncora era o base) e o par ficava em silêncio, `_descend` retornava sem
    mudar nada e o prazo de silêncio vencia de novo no mesmo instante: 800 mil disparos de timer para 13 mil
    transmissões em 2 dias simulados (33 s de CPU em vez de 5 s). Agora o nó passa ao estado `BASE`. Efeito nos resultados
    da escala rápida: no máximo 0,014 de PDR em 3 de 50 células de M; P1 e P3 do verificador, B3, B4, B7, T23 e T456
    ficaram idênticos.

## 5. Recomendações para o plano de testes

- Fixar TCXO no hardware de referência (ou LDRO forçado) antes de B9/F.
- Definir o intervalo de beacon pelo compromisso rendezvous × ocupação (B5).
- Rodar F1 urbano na faixa 0,6–1,5 km como caso crítico, com histerese, escada e `fade_k` (F7) como variáveis.
- Escolher perfil móvel por padrão em nós com velocidade > 2 m/s.
- Em estrela, usar relay em vez de unanimidade; em malha, manter fallback por inundação no modo base.
- Usar o mesmo verificador de conformidade e analisador JSONL nos logs reais (Fase 7).

## 6. Limitações

Canal estatístico com parâmetros estimados; PER por curva logística; malhas de terceiros em nível 2; regras BR-2026 de fonte secundária (confirmar com OCD); corrente do FEM estimada. Números servem para comparar e dimensionar, não como previsão absoluta.

## 7. Como rodar

```bash
PYTHONPATH=. python3 -m simsuite.run_suite --escala quick           # ~40 s
PYTHONPATH=. python3 -m simsuite.run_suite --escala full --procs 1  # amostras do plano, ~1 h 06 min (results_full/)
PYTHONPATH=. python3 -m pytest -q simsuite/tests
~/.venvs/legua/bin/python tools/build_site.py                       # atualiza o site de resultados
```

## Validação cruzada e equivalência (rodada longa de 2026-11-16)
- **Núcleo C × simulador:** 150 cenários aleatórios nos quatro pares Py-Py, C-C, Py-C e C-Py, 525.412 eventos comparados, 0 divergências.
- **sim×sim (LoRaSim, regras portadas à mão, original não executado):** tempo no ar idêntico exceto SF12/250 (regra de LDRO); PDR ALOHA próximo do analítico; erro médio de sensibilidade 3,87 dB contra a tabela SX1272.
- **Controle de 16 B** (era 20 B): tempo no ar de controle em SF10/125 de 329,7 ms (era 370,7 ms).
- Resultados de simulação com parâmetros estimados, escala full; não são previsão de campo.
- **Originais executados (16/11/2026):** LoRaSim `loraDir.py` (sintaxe convertida) e Meshtasticator (`lib.phy`); detalhes em docs/09 §9.1.
- **Ausência longa:** 15 min a 12 h sem enlace, com ou sem reinício, ressincronizam em 0,3 a 7 min (docs/07 §8).
- **Teto assimétrico (formal):** com B nunca aceitando o modo mais rápido, P1, P2 = 0 e P4 valem; o par fica no modo base.

## Cenário P: varredura da potência de TX (16/11/2026)
`simsuite/scenarios/power.py`, aba "Potência de TX" do site. Ambiente urbano residencial, enlace fixo, distâncias de 1 a 4 km,
tetos de 2 a 28 dBm, mesmas sementes de canal em todas as células.
- **Simétrico:** cada distância tem um teto mínimo para fechar o enlace; abaixo dele o PDR cai a zero. Em enlace curto o menor
  consumo de energia por pacote não está no teto máximo (depende da corrente do PA, estimada).
- **Assimétrico (A em 28 dBm, B variável):** o PDR se mantém, mas a energia por pacote sobe muito porque o nó fraco arrasta o par
  para modos lentos. Tráfego só de A para B; com tráfego nos dois sentidos o efeito no PDR seria maior.
- **Controle de potência ligado × desligado:** diferença pequena de PDR e de energia neste modelo.
Números exatos: a aba do site e a página consolidada (seção P). Resultados de simulação com corrente do PA estimada.

## Varredura de teto de TX em todos os cenários e varreduras de mecanismo V e S (16/11/2026)

Fonte: `simsuite/results_full/teto_{8,14,20}/` (escala longa, 5 sementes onde o cenário usa 5) e `V.json`, `S.json`.
Simulação com parâmetros estimados; vale para comparar, não para prever campo.

**Teto de TX global** (`run_suite --teto N`, `tools/varredura_teto.sh`). O teto nunca sobe um valor que o cenário já
fixou mais baixo; por isso B2–B5, B7, B11 e os baselines de malha não mudam. Nos cenários F, F6, M e T23:
- Os modos fixos transmitem sempre no teto: a energia por pacote entregue cresce muito de 8 para 28 dBm (F1, 0,3 km,
  SF10/125: 97 → 2.394 mJ), enquanto a Légua reduz a potência quando sobra margem (114 mJ a 28 dBm no mesmo ponto).
- Em F6 rural 8 km, a Légua entrega 0,9998 a 14 dBm contra 1,0000 do modo fixo, com 103 mJ contra 184 mJ por pacote; a
  28 dBm são 145 mJ contra 3.847 mJ.
- O preço aparece em enlaces já marginais: em M1 pedestre urbano o PDR da Légua é menor que o do modo fixo a 28 dBm
  (0,79 contra 0,95 em um dos perfis), porque a adaptação perde pacotes na troca.
- Com teto baixo (8 dBm) o PDR cai igual para todos quando falta enlace; abaixo de certo teto nenhum protocolo recupera.

**V: janela de validação** (urbano residencial, 2 e 3 km, enlace marginal):
- `f_valid = 1` (um único fracasso desfaz o modo) produz rollbacks falsos: 0,6 a 1,4 por hora com k = 3 ou 5, contra
  0,03 a 0,3 com f ≥ 3. O padrão k = 3, f = 3 está na faixa segura; k = 2/f = 3 tem menos trocas, com PDR igual.
- Janela de 15 s é curta demais: 3 a 6 rollbacks por hora e PDR 2 a 3 pontos abaixo; 45 s e 90 s são equivalentes
  (PDR 0,98 a 2 km, 0,93 a 3 km). Manter 45 s.
- Na escala rápida (2 h, 2 sementes) k = 1 parecia livre de rollbacks; na longa ele passa a ter rollbacks e energia
  maior que k = 2 a 2 km. **Não** usar a escala rápida para ajustar essa sintonia: o ruído é do tamanho do efeito.

**S: descida por silêncio** (`t_silence` × intervalo da aplicação):
- `t_silence = 30 s` com tráfego esparso (aplicação a 60 s ou 300 s) causa descidas falsas em massa: a 2 km, 700 a 760
  quedas ao base em 6 h × 5 sementes e PDR 0,88 a 0,92, contra 10 a 17 quedas e 0,99 com 90 s.
- `t_silence = 60 s` também falha com aplicação esparsa (PDR 0,96 a 2 km; 280 a 415 quedas), porque é igual ao
  heartbeat de 60 s.
- 90 s é o menor valor sem descida falsa; 180 s e 300 s dão resultado idêntico, pois o heartbeat limita o silêncio
  observável. **Regra:** `t_silence` ≥ 1,5 × `hb_interval`.
- A 3 km o efeito do `t_silence` some sob o ruído do enlace marginal (PDR entre 0,91 e 0,94 em quase todas as
  células), então a regra vale para enlace bom e médio; não foi demonstrada para enlace no limite.
