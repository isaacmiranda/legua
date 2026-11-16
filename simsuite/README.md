# Légua — suíte de simulação (`simsuite`)

> **Légua**: acordo de modo, validação e rollback para enlaces LoRa ponto a ponto (nome de trabalho).

Suíte de simulação do plano de testes da Légua

Suíte de simulação derivada do plano de testes (doc 05: Fases 0–7, B1–B11, F1–F6, M1–M7, T1–T6).
Python 3 puro + numpy/matplotlib. Sem dependência de hardware.

## Como rodar

```bash
cd <pasta que contém simsuite>
PYTHONPATH=. python3 -m simsuite.run_suite --escala quick          # ~40 s, todos os cenários
PYTHONPATH=. python3 -m simsuite.run_suite --escala full --procs 8 # amostras do plano (horas)
PYTHONPATH=. python3 -m simsuite.run_suite --so B4,B7,T456          # só alguns cenários
PYTHONPATH=. python3 -m pytest -q simsuite/tests                    # 11 testes
```

Saídas em `simsuite/results/`: um `<cenário>.json` por cenário, `relatorio.md` (tabelas + mapa do que é
simulável) e figuras `fig_*.png`. `exemplo_telemetria.jsonl` mostra o esquema de telemetria da Fase 7.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `core/` | rádio (ToA, sensibilidade, LDRO, Doppler/deriva, corrente), canal estático, enlaces móveis (LoS/NLoS, sombreamento correlacionado, Rice), mobilidade, regulação BR-2026 (plano de canais, sequência de salto, verificador de conformidade), simulador de eventos discretos (half-duplex, CAD/LBT, colisões com captura, flash stall), bancada com atenuador programável |
| `protocol/` | tabela de modos BR-2026 e o endpoint Légua (máquina de estados pura: BASE/DATA/NEGOCIANDO/AGUARDA_COMMIT/VALIDANDO/RECUPERACAO, PROPOSE/VOTE/COMMIT, validação, âncora em NVM, rollback, alarme, perfil móvel, escada de degradação, volta à âncora) + variantes (modo travado, teste de negociação) |
| `formal/` | verificador de estados explícito (BFS) das propriedades P1–P3 com perda adversária, ablações e cadeia de Markov da rodada de negociação |
| `analysis/` | estatística (Wilson, Clopper-Pearson, tamanhos de amostra, bootstrap em blocos), leitura de telemetria JSONL, relatório |
| `baselines/` | modelos nível-2 de Meshtastic, MeshCore, Reticulum, LoRaMesher e Légua em malha |
| `scenarios/` | bancada (B2–B11), campo fixo (F1–F6), mobilidade (M1–M7), topologias (T2–T6) |

## Mapa plano de testes → simulação

| Item | Simulável? | O que a suíte faz |
|---|---|---|
| Fase 0 (Anatel, OCD, LGPD) | Não | decisão regulatória; a leitura atual está codificada em `core/regulatory.py` |
| Fase 1 (verificação formal) | Sim | P1–P3, ablações, Markov |
| Fase 2 (simulação/validação cruzada) | Sim | DES de dois lados + modelos de malha; tamanhos de amostra do plano |
| B1 (calibração RSSI/potência) | Não | medida física |
| B2 PDR × atenuação | Parcial | curvas por modo; calibrar com bancada |
| B3 custo de controle, B4 injeção de falhas, B5 rendez-vous, B6 replay de traço, B7 segurança | Sim | |
| B8 energia, B9 deriva/LDRO, B10 CAD | Parcial | tabelas do datasheet; medir no hardware |
| B11 conformidade BR-2026 | Sim | verificador sobre o log de TX |
| F1–F6, M1–M7 | Parcial | canal estatístico; serve para dimensionar e pré-registrar hipóteses |
| T1 | Sim | |
| T2/T3, T4–T6 | Parcial | modelos nível-2 das pilhas de malha |
| Fase 7 (telemetria) | Sim | esquema JSONL + analisador |

## Limitações

Canal estatístico (não ray-tracing); PER por curva logística; malhas de terceiros modeladas em nível 2
(não o firmware real); regras BR-2026 vêm de fonte secundária e precisam ser confirmadas com o OCD;
corrente do FEM (~1 A a 28 dBm) é estimativa. Os números servem para comparar alternativas e
dimensionar campanhas, não como previsão absoluta de campo.
