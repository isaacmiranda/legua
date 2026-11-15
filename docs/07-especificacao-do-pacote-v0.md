# Especificação do pacote v0 (orçamento dos 24 bytes)

Referência executável: `simsuite/protocol/wire.py` (Python) e `core/src/frame.c` (C99). Vetores comuns em
`core/tests/vectors/frames.txt`. Esta é a versão **v0 de trabalho**: muda até o congelamento (Fase 7).

## 1. Restrição

No perfil BR-2026 (não verificado, ver docs/05) o salto em frequência limita a ocupação a 0,4 s por canal.
No SF10/125 kHz um quadro de 24 B leva 370,7 ms; 25 B já passa de 0,4 s. Logo o quadro de dados do modo base
tem **no máximo 24 B no ar**, incluindo autenticação.

## 2. Quadro (big-endian)

```
 0        1        2   3     4   5     6   7     8 ........ 8+n-1   +4
+--------+--------+--------+--------+--------+--------------+--------+
| ver|tipo| flags  |  src   |  dst   | ctr16  |    corpo     |  MIC   |
+--------+--------+--------+--------+--------+--------------+--------+
 cabeçalho: 8 B                                  n B            4 B
```

| Campo | Bits | Descrição |
|---|---|---|
| ver | 3 | versão do formato (0). Versão diferente: descartar |
| tipo | 5 | 1 HELLO, 2 DATA, 3 ACK, 4 PROPOSE, 5 VOTE, 6 COMMIT |
| flags | 8 | bit0 ACKREQ, bit1 FRAG (reservado p/ fragmentação), bits 2-3 id da chave, bits 4-7 **zero** (descartar se não) |
| src, dst | 16 | endereço curto; `0xFFFF` = difusão. Derivado do identificador do nó, com detecção de colisão (a definir na Fase 1) |
| ctr16 | 16 | 16 bits baixos do contador de TX de 32 bits (anti-replay) |
| MIC | 32 | autenticação truncada sobre cabeçalho + corpo, com nonce (src, ctr32) e chave de id `key_id` |

Tamanho **fixo por tipo**: DATA 24 B, ACK 14 B, HELLO/PROPOSE/VOTE/COMMIT 20 B. Tamanho diferente do esperado
para o tipo: descartar.

## 3. Orçamento

| Tipo | Cabeçalho | Corpo | MIC | Total | ToA SF10/125 (ms) |
|---|---|---|---|---|---|
| DATA | 8 | 12 | 4 | **24** | 370,7 |
| ACK | 8 | 2 | 4 | 14 | 288,8 |
| controle | 8 | 8 | 4 | 20 | 370,7 (mesmo custo do DATA: 20 B e 24 B têm o mesmo número de símbolos) |

O doc 03 (E8) propunha 13 B de sobrecarga com campo de grupo (1 B) e 11 B de corpo. A v0 usa **12 B de
sobrecarga** (sem grupo no cabeçalho; grupos usam faixa de `dst`, Fase 6) e entrega **9 B de payload** por DATA.

## 4. Corpos

| Tipo | Corpo (bytes) |
|---|---|
| DATA (12) | `seq` u8, `dflags` u8 (bit0 VAL, bit1 HB), `speed` u8 (0,5 m/s), `payload` 9 |
| ACK (2) | `seq` u8, `gain` u8 (`0xFF` = desconhecido; senão ganho = -60 - gain × 0,5 dB) |
| HELLO (8) | `flags` u8 (bit0 REPLY), `speed` u8, reservado 6 (zero) |
| PROPOSE (8) | `cand` u8 (byte de modo), `speed` u8, reservado 6 |
| VOTE (8) | `cand` u8, `yes` u8, `speed` u8, reservado 5 |
| COMMIT (8) | `cand` u8, `delay_ms` u16, `speed` u8, reservado 4 |

`delay_ms` do COMMIT é relativo ao fim da transmissão do COMMIT (os nós não compartilham relógio). O simulador
Python usa instante absoluto: é uma diferença conhecida, a alinhar na Fase 2.

**Byte de modo:** `(SF-5) << 5 | BWcode << 3 | (CR-1) << 1 | FHSS`, com BWcode 0 = 125, 1 = 250, 2 = 500 kHz.

## 5. Contador e anti-replay

- O contador de TX tem 32 bits, mas só 16 vão no quadro. O receptor reconstrói o valor completo a partir do
  último aceito: `delta = ctr16 - low16(último)` (mod 2^16); `delta == 0` ou `delta > 0x7FFF` é repetido ou antigo e
  é descartado. O MIC cobre o contador completo, então uma reconstrução errada falha no MIC.
- O último contador do par só avança depois do MIC válido.
- O contador de TX é gravado em NVM em **blocos de 64**. Depois de um reinício o contador salta para
  `bloco × 64 + 64`, acima de tudo que já foi usado. Cada retransmissão usa um contador novo.
- **Pendência (Fase 1):** o último contador do par ainda não é gravado em NVM; após reinício do receptor,
  quadros antigos ainda não vistos nesta execução poderiam ser aceitos. O núcleo já aceita `peer_ctr_floor`.

## 6. Cripto

O núcleo não traz cripto: o porte entrega `mic()` em `legua_env`. Proposta para produto: AES-CMAC ou CCM,
truncado a 4 B (a escolha é decisão aberta; o MIC de 4 B é aceitável pelo limite de 24 B e porque o canal é de
baixa taxa, mas o risco de forja é 2^-32 por tentativa). Não há chave padrão nem chave derivada do MAC. O MIC de
teste (FNV-1a com chave) existe só nos testes e **não é segurança**.

## 7. Diferenças em relação ao simulador (`endpoint.py`)

| Item | Simulador | Núcleo C v0 |
|---|---|---|
| ACK | 12 B | 14 B (agora também no simulador) |
| Número de sequência inicial | 0 após reinício | aleatório (evita ser tomado por duplicata do par) |
| Fila cheia | descarta o mais antigo | descarta o mais antigo que não está em voo |
| Velocidade | em todo quadro | em DATA, HELLO, PROPOSE, VOTE, COMMIT (não no ACK) |
| Negociação | completa | Fase 2 |

## 8. Pendências

1. Colisão de endereços curtos (16 bits) e como derivar do identificador.
2. Escolha do algoritmo de MIC e do formato de chave/rotação (`key_id`).
3. Fragmentação (flag FRAG) e payload maior que 9 B.
4. Compactar controle de 20 para 14–16 B, se o corpo reservado não for usado: no SF10/125, 16 B leva 330 ms e 14 B leva 289 ms, contra 371 ms hoje (ganho de 11% a 22% de tempo no ar por mensagem de controle).
