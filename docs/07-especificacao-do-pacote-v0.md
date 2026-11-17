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

Tamanho **fixo por tipo**: DATA 24 B, ACK 14 B, HELLO/PROPOSE/VOTE/COMMIT 16 B. Tamanho diferente do esperado
para o tipo: descartar.

## 3. Orçamento

| Tipo | Cabeçalho | Corpo | MIC | Total | ToA SF10/125 (ms) |
|---|---|---|---|---|---|
| DATA | 8 | 12 | 4 | **24** | 370,7 |
| ACK | 8 | 2 | 4 | 14 | 288,8 |
| controle | 8 | 4 | 4 | **16** | 329,7 (era 20 B e 370,7 ms; compactado em 15/11/2026: 11% menos tempo no ar por mensagem) |

O doc 03 (E8) propunha 13 B de sobrecarga com campo de grupo (1 B) e 11 B de corpo. A v0 usa **12 B de
sobrecarga** (sem grupo no cabeçalho; grupos usam faixa de `dst`, Fase 6) e entrega **9 B de payload** por DATA.

## 4. Corpos

| Tipo | Corpo (bytes) |
|---|---|
| DATA (12) | `seq` u8, `dflags` u8, `speed` u8 (0,5 m/s), `payload` 9 |
| ACK (2) | `seq` u8, `gain` u8 (`0xFF` = desconhecido; senão ganho = -60 - gain × 0,5 dB) |
| HELLO (4) | `flags` u8 (bit0 REPLY), `speed` u8, reservado 2 (zero) |
| PROPOSE (4) | `cand` u8 (byte de modo), `speed` u8, reservado 2 |
| VOTE (4) | `cand` u8, `yes` u8, `speed` u8, reservado 1 |
| COMMIT (4) | `cand` u8, `delay_ms` u16, `speed` u8 |

`dflags` do DATA: bit0 **VAL** (o remetente está validado neste modo), bit1 **HB** (heartbeat, sem payload de
aplicação), bits 2-7 **potência de TX**: `p_dbm = código - 9` (código 0 a 37, de -9 a 28 dBm, passo de 1 dB). O
receptor precisa da potência para medir o ganho do enlace (`RSSI - p_dbm`). Quadros que não são DATA saem na
potência do teto do modo (`min(teto do nó, teto do modo)`), que os dois lados conhecem; **os dois nós assumem o
mesmo teto** (nó mais fraco no par é pendência).

`delay_ms` do COMMIT é **relativo ao fim da transmissão do COMMIT** (os nós não compartilham relógio): quem
transmite conta a partir do `TX_DONE` do COMMIT; quem recebe, a partir do fim da recepção. O simulador Python usa
o mesmo critério desde 15/11/2026 (antes usava um instante absoluto). `ACK`: o ganho que o receptor mediu no DATA;
o transmissor o usa para saber o ganho no sentido contrário.

**Byte de modo:** `(SF-5) << 5 | BWcode << 3 | (CR-1) << 1 | FHSS`, com BWcode 0 = 125, 1 = 250, 2 = 500 kHz.

## 5. Contador e anti-replay

- O contador de TX tem 32 bits, mas só 16 vão no quadro. O receptor reconstrói o valor completo a partir do
  último aceito: `delta = ctr16 - low16(último)` (mod 2^16); `delta == 0` ou `delta > 0x7FFF` é repetido ou antigo e
  é descartado. O MIC cobre o contador completo, então uma reconstrução errada falha no MIC.
- O último contador do par só avança depois do MIC válido.
- O contador de TX é gravado em NVM em **blocos de 64**. Depois de um reinício o contador salta para
  `bloco × 64 + 64`, acima de tudo que já foi usado. Cada retransmissão usa um contador novo.
- **Registro em NVM** (uma gravação atômica por evento, nunca mais): `{âncora, bloco do contador de TX, piso do
  contador do par}`. Grava-se quando algum dos dois contadores cruza um múltiplo de 64 e quando a âncora muda.
  O **piso do par** é o último múltiplo de 64 visto; depois de um reinício o receptor só aceita contador acima
  dele, e a reconstrução de 16 para 32 bits parte dele. Consequências: (1) um replay de quadro **até 63 contadores
  acima do piso** que o receptor já tinha visto antes do reinício ainda é aceito (limite do esquema de blocos;
  reduzir o bloco encurta a janela e aumenta o desgaste da flash); (2) se o par transmitir mais de 32767 quadros
  enquanto o receptor está desligado, a reconstrução falha e é preciso ressincronizar (rechavear, pendência 2).

## 6. Cripto

**Algoritmo do MIC v0 (decidido em 16/11/2026): AES-128-CMAC truncado a 32 bits.**

```
B0  = 0x4C | 0x01 | key_id | src (2 B) | ctr32 (4 B) | len | 00 00 00 00 00 00      (16 B, big-endian)
MIC = os 4 primeiros bytes de AES-CMAC(K[key_id], B0 || cabeçalho || corpo)
```

- `0x4C` ('L') separa o domínio; `0x01` é a função "MIC v0". O valor `0x02` fica reservado para uma cifra futura
  (AES-CTR com a mesma chave), que terá de usar um bloco inicial diferente.
- `ctr32` é o contador **completo**: os 16 bits altos não vão no ar, mas entram no MIC. Uma reconstrução errada falha
  aqui (§5). `len` é o tamanho de cabeçalho + corpo (12 ACK, 16 controle, 20 DATA).
- Custo: o controle tem 32 B de entrada, dois blocos exatos, e três chamadas de AES contando a subchave (que o
  `legua_cmac_init` calcula uma vez por chave). O DATA tem três blocos. No ESP32-S3, o AES em hardware ou o mbedTLS
  do porte fazem isso em microssegundos.
- **Chaves:** `key_id` (2 bits) escolhe uma de até 4 chaves de 128 bits provisionadas pelo integrador. **Não há chave
  padrão nem chave derivada do MAC.** `key_id` sem chave carregada não assina nem aceita: `mic()` devolve erro e o
  quadro é descartado, qualquer que seja o MIC que ele traz (um valor fixo devolvido no lugar seria forja trivial,
  porque quem escolhe o `key_id` do quadro é o atacante). O formato de provisionamento e a rotação seguem abertos
  (pendência 2).
- **Implementação de referência:** `core/include/legua/mic_cmac.h` e `core/src/mic_cmac.c` (C99, sem terceiros,
  `legua_keyring_mic` tem a assinatura de `legua_env.mic`) e `simsuite/protocol/mic.py` (Python puro). Os dois
  conferem a FIPS-197 e a RFC 4493 e concordam nos 36 quadros de `core/tests/vectors/mic.txt` (`make -C core vectors`
  regenera). O AES em software usa tabela de substituição e **não é de tempo constante**; num porte com AES em
  hardware, prefira o hardware e confira contra os mesmos vetores.
- **Por que CMAC, e não CCM nem Ascon:** o payload de 9 B não pede sigilo, e o CMAC é só autenticação, com a menor
  superfície (sem nonce de cifra a gerir). É o MIC do LoRaWAN, é norma (NIST SP 800-38B) e tem AES em hardware no
  ESP32-S3 e em quase todo MCU. O CCM com tag de 4 B traria sigilo que ninguém pediu e exigiria nonce único por
  chave. O Ascon (NIST SP 800-232, 2025) é leve, mas a norma final traz AEAD, hash e XOF, sem MAC autônomo, e não tem
  hardware nos alvos.
- A simulação e o teste de equivalência continuam usando o MIC de teste (FNV-1a com chave, em `wire.py` e
  `core/tests/testenv.h`), que **não é segurança**: o comportamento do protocolo não depende do algoritmo, e o AES em
  Python puro deixaria a escala longa muito mais lenta.

**Análise do MIC de 4 B (tamanho mantido em 4 B na decisão acima).** Contas feitas aqui, a conferir com um
criptógrafo antes de fixar o formato:

| Cenário | Tentativas por segundo | Tempo médio até uma forja aceita (2^31 tentativas) |
|---|---|---|
| Atacante em alcance, SF7/125, controle de 16 B (~52 ms no ar) | ~19 | ~3,5 anos |
| Atacante em alcance, SF10/125 (~330 ms) | ~3 | ~22 anos |
| Atacante em alcance, SF12/125 (~1,3 s) | ~0,8 | ~90 anos |

A conta assume que cada tentativa ocupa o ar por um quadro inteiro e que o receptor **não** limita falhas. Duas
defesas já previstas fecham a margem: (1) o contador anti-replay (quadro com contador fora da janela é descartado
antes do MIC) obriga o atacante a acertar também o contador, e (2) o alarme do protocolo (B7) pode contar quadros com
MIC inválido numa janela e travar a aceleração. Recomenda-se escrever (2) como requisito: após *n* falhas de MIC em
*T* segundos, parar de aceitar PROPOSE e voltar ao modo base. A truncagem de CMAC a 32 bits é permitida pela
NIST SP 800-38B, que a condiciona a um limite de verificações falhas; **conferir o texto atual da norma**. CCM com tag
de 4 B (como no 802.15.4) é a alternativa que já traz confidencialidade, mas o payload de 9 B não pede sigilo.
Impacto no ar: passar de 4 B para 8 B de MIC acrescenta 4 B por quadro (SF10/125: +~41 ms por quadro de controle).

## 7. Diferenças em relação ao simulador (`endpoint.py`)

Desde 15/11/2026 o núcleo C implementa também a negociação (PROPOSE/VOTE/COMMIT), a validação, o rollback, a descida
por silêncio e o controle de potência, e é **equivalente** ao simulador: o teste de equivalência
(`simsuite/tests/test_equivalencia.py`, docs/09 §8) roda os dois por bytes reais e compara quadro a quadro.
Diferenças que restam, todas de representação:

| Item | Simulador | Núcleo C |
|---|---|---|
| Tempo | segundos em ponto flutuante | ms inteiros; tempo no ar arredondado ao ms para cima |
| Número de sequência | inteiro sem limite internamente; 8 bits no fio | 8 bits, com janela de 32 para duplicatas |
| Número de sequência inicial | 0 após reinício | aleatório (o par não confunde com duplicata) |
| Cálculo | `double` | `float`; `sqrt` por Newton (sem libm) |
| Parâmetros | `Config` | `legua_params` (mesmos campos; perfis nomeados em `legua_params_profile`) |
| Velocidade | em todo quadro | em DATA, HELLO, PROPOSE, VOTE, COMMIT (não no ACK) |

## 8. Pendências

1. Colisão de endereços curtos (16 bits) e como derivar do identificador.
2. (algoritmo decidido em 16/11/2026: AES-128-CMAC truncado, §6) Falta o formato de provisionamento e de rotação
   das chaves (`key_id`), e o requisito de limitar falhas de MIC (*n* falhas em *T* segundos travam a aceleração,
   §6), que muda o protocolo e entra junto em `endpoint.py` e `endpoint.c`. A **ressincronização depois
   de uma ausência longa** foi verificada na simulação (teste `test_ausencia_longa_ressincroniza`, nos quatro
   pares Py/C): com 15 min a 12 h sem enlace, com ou sem reinício de um dos nós ao voltar, os dois voltam a DATA no
   mesmo modo em 0,3 a 7 min (descida por silêncio até o modo base, HELLO e nova negociação). O que continua
   aberto é o contador do par fora da janela de 32767 (ausência de mais de 32767 quadros sem reinício do par), que
   exige um procedimento de ressincronização autenticado.
3. Fragmentação (flag FRAG) e payload maior que 9 B.
4. (feito em 15/11/2026) Controle compactado de 20 para 16 B. Ir a 14 B exigiria tirar a velocidade ou o `yes`
   do corpo (ganho extra de 12% no tempo no ar do controle); não vale enquanto o perfil móvel usa a velocidade.
5. Potência de TX diferente por nó (teto assimétrico): o receptor hoje supõe o mesmo teto nos dois lados. No modelo
   formal, o caso extremo (B nunca aceita um modo mais rápido) mantém P1, P2 = 0 e P4: os dois ficam no modo base, sem
   aceleração (docs/06). O efeito sobre o orçamento de enlace (ganho do ACK, controle de potência) segue sem modelo.
