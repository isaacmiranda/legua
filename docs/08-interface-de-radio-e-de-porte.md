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
| dados da aplicação | `legua_on_app(ep, payload, len, now, acts)` |
| quadro recebido | `legua_on_rx(ep, raw, len, now, acts)` |
| fim de transmissão | `legua_on_tx_done(ep, raw, len, now, acts)` |
| prazo vencido | `legua_on_timer(ep, now, acts)`; `legua_next_deadline` diz quando |

| Ação | O que o porte faz |
|---|---|
| `LEGUA_ACT_TX` | `radio.start_tx(bytes, len)`; ao fim, chama `legua_on_tx_done` |
| `LEGUA_ACT_RX` | `radio.configure(mode_id, ...)` e `radio.start_rx` |
| `LEGUA_ACT_PERSIST` | grava `ctr_block` em NVM (`port.nvm_store`), de forma atômica |
| `LEGUA_ACT_DELIVER` | entrega `payload` (9 B) à aplicação |
| `LEGUA_ACT_LOG` | telemetria (código e argumento) |

Regras: o núcleo não guarda ponteiro para `raw`; `legua_actions` tem capacidade fixa
(`LEGUA_MAX_ACTIONS`); tempo em `uint32_t` de ms que dá a volta (comparação por diferença com sinal).

## 3. Porte (`port.h`)

`now_ms` monotônico; `nvm_load`/`nvm_store` atômicos (dois setores A/B ou equivalente), com `legua_nvm`
(bloco do contador, piso do contador do par, âncora de modo).

## 4. Driver de rádio (`radio.h`)

`configure(mode_id, canal, potência)`, `start_tx`, `start_rx`, `start_cad`, `sleep` e `poll_event`
(`TX_DONE`, `RX_DONE` com RSSI e SNR em décimos, `RX_TIMEOUT`, `CAD_DONE`). A potência já chega limitada ao teto
do integrador; o driver nunca transmite acima dele. SX1262 primeiro; SX127x só depois do protocolo congelado.

## 5. Ambiente criptográfico (`legua_env`)

`mic(ctx, key_id, src, ctr32, data, len)` e `rand32(ctx)`. Em produto, `mic` usa AES (hardware do ESP32-S3 ou
mbedTLS, no porte). Nada de terceiros no núcleo.

## 6. Fora do escopo da v0

Escolha de canal e salto, telemetria JSONL, negociação (PROPOSE/VOTE/COMMIT), âncora e rollback (Fases 2 a 4).
