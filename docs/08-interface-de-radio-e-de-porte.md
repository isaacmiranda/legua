# Interface de rádio e de porte (v0)

Cabeçalhos: `core/include/legua/legua.h` (núcleo), `radio.h` (driver) e `port.h` (plataforma).

## 1. Camadas

```
aplicação
   │  legua_on_app / DELIVER
┌──▼───────────────────────────┐
│ núcleo (legua.h)             │  puro: sem E/S, sem alocação, C99
│  eventos ──► máquina ──► ações│
└──▲───────────────────────────┘
   │  laço do porte (runner)
┌──┴──────────┐  ┌───────────────┐  ┌───────────────┐
│ radio.h     │  │ port.h        │  │ legua_env     │
│ driver SX12xx│  │ relógio, NVM  │  │ MIC, aleatório│
└─────────────┘  └───────────────┘  └───────────────┘
```

## 2. Núcleo: eventos de entrada e ações de saída

| Evento | Função |
|---|---|
| inicialização / reinício | `legua_init(ep, cfg, env, now, acts)`; `cfg` traz o registro lido da NVM |
| dados da aplicação | `legua_on_app(ep, payload, len, now, acts)` |
| quadro recebido | `legua_on_rx(ep, raw, len, &rxinfo, now, acts)`; `rxinfo` = RSSI e SNR em décimos de dB |
| fim de transmissão | `legua_on_tx_done(ep, raw, len, mode_id, now, acts)`; `mode_id` é o modo em que o quadro saiu |
| prazo vencido | `legua_on_timer(ep, now, acts)`; `legua_next_deadline` diz quando |
| velocidade GNSS (perfil móvel) | `legua_set_speed(ep, m/s)` |
| rotação de chave (`docs/07` §6.2) | `legua_key_rotate(ep, now, acts)`; <0 se já há uma em curso |

| Ação | O que o porte faz |
|---|---|
| `LEGUA_ACT_TX` | `radio.configure(tx.mode_id, canal, tx.power_dbm)`, `start_tx(bytes, len)`; ao fim, chama `legua_on_tx_done` |
| `LEGUA_ACT_RX` | `radio.configure(mode_id, ...)` e `start_rx`; **descarta transmissões ainda não iniciadas em outro modo** |
| `LEGUA_ACT_PERSIST` | grava o registro inteiro em NVM (`port.nvm_store`), de forma atômica: âncora, bloco do contador de TX, piso do contador do par, chave de TX e rotação em curso. No máximo uma por evento |
| `LEGUA_ACT_DELIVER` | entrega `payload` (9 B) à aplicação (heartbeats não são entregues) |
| `LEGUA_ACT_LOG` | telemetria (código e argumento): `MODE` (modo, estado e motivo), `PROPOSE`, `NEG_FAIL`, `VALIDATED`, `COMMIT_RX`, `ALARM`, `MIC_ALARM`, `KEY` (estado da chave: com a anterior aposentada, o porte apaga a chave antiga), `CTR_END`, `RESYNC` (arg 0 = pedido enviado, 1 = contador do par ressincronizado), rejeições (`REJ_MIC`, `REJ_REPLAY`, `REJ_FORMAT`, `REJ_KEY`), retransmissão |

**Tabela de modos.** O núcleo não tem RF embutida. O integrador passa em `legua_config.modes` uma tabela ordenada do
mais rápido ao mais lento, com `{mode_id, cap_dbm, sens_dbm, toa_data_us}` por modo, mais o modo base e o de
recuperação. Para o perfil BR-2026 (`nao_verificado`) existe `core/profiles/br2026.h`, **gerado** do simulador por
`tools/gen_modetab.py` (um teste confere que está em sincronia). Assim o núcleo e o Python usam os mesmos modos,
tetos e sensibilidades; a calibração da bancada (docs/09 §4) entra por essa tabela.

**Parâmetros.** `legua_params` espelha `Config` do simulador (tempos em ms). `legua_params_default` dá o padrão e
`legua_params_profile` os perfis nomeados da sintonia F7 (`DEFAULT`, `STABLE`, `CAUTIOUS`).

Regras: o núcleo não guarda ponteiro para `raw` nem para a tabela de modos (que deve sobreviver ao endpoint);
`legua_actions` tem capacidade fixa (`LEGUA_MAX_ACTIONS` = 12) e o campo `overflow` acusa descarte (os testes exigem
que nunca aconteça); tempo em `uint32_t` de ms que dá a volta (comparação por diferença com sinal). Estados e
motivos em `enum legua_state` e `enum legua_reason`.

## 3. Porte (`port.h`)

`now_ms` monotônico; `nvm_load`/`nvm_store` atômicos (dois setores A/B ou equivalente), com `legua_nvm`
(bloco do contador, piso do contador do par, âncora de modo, chave de TX e rotação em curso).

## 4. Driver de rádio (`radio.h`)

`configure(mode_id, canal, potência)`, `start_tx`, `start_rx`, `start_cad`, `sleep` e `poll_event`
(`TX_DONE`, `RX_DONE` com RSSI e SNR em décimos, `RX_TIMEOUT`, `CAD_DONE`). A potência já chega limitada ao teto
do integrador; o driver nunca transmite acima dele. SX1262 primeiro; SX127x só depois do protocolo congelado.

## 5. Ambiente criptográfico (`legua_env`)

`mic(ctx, key_id, src, ctr32, data, len, &out)` e `rand32(ctx)`. `mic` grava o MIC de 32 bits em `out` e devolve 0,
ou um valor negativo se não houver chave para `key_id`. Nesse caso o codec recusa: `legua_frame_encode` devolve <0
e `legua_frame_verify` devolve 0. O algoritmo v0 é AES-128-CMAC truncado a 4 B (`docs/07` §6). O núcleo traz uma
implementação de referência opcional em `legua/mic_cmac.h` (`legua_keyring_set`, que recusa chave trivial,
`legua_keyring_drop` e `legua_keyring_mic`). Em produto,
o porte pode usá-la ou trocar o AES pelo hardware do ESP32-S3 ou pelo mbedTLS, conferindo contra
`core/tests/vectors/mic.txt`. Nada de terceiros no núcleo.

## 6. Fora do escopo da v0

Escolha de canal e salto, telemetria JSONL, driver SX1262, armazenamento protegido das chaves (no porte), CAD/LBT e coexistência. A negociação (PROPOSE/VOTE/COMMIT), a validação, a âncora e o rollback já estão no núcleo (Fase 2, equivalente ao simulador).
