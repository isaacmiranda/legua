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
