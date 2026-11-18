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
| tipo | 5 | 1 HELLO, 2 DATA, 3 ACK, 4 PROPOSE, 5 VOTE, 6 COMMIT, 7 RESYNC, 8 RESYNC_RSP |
| flags | 8 | bit0 ACKREQ, bit1 FRAG (reservado p/ fragmentação), bits 2-3 id da chave, bits 4-7 **zero** (descartar se não) |
| src, dst | 16 | endereço curto; `0xFFFF` = difusão. Derivado do identificador do nó, com detecção de colisão (a definir na Fase 1) |
| ctr16 | 16 | 16 bits baixos do contador de TX de 32 bits (anti-replay) |
| MIC | 32 | autenticação truncada sobre cabeçalho + corpo, com nonce (src, ctr32) e chave de id `key_id` |

Tamanho **fixo por tipo**: DATA 24 B, ACK 14 B, HELLO/PROPOSE/VOTE/COMMIT/RESYNC/RESYNC_RSP 16 B. Tamanho diferente do esperado
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
| HELLO (4) | `flags` u8 (bit0 REPLY), `speed` u8, `cap` u8, reservado 1 (zero) |
| PROPOSE (4) | `cand` u8 (byte de modo), `speed` u8, `cap` u8, reservado 1 |
| VOTE (4) | `cand` u8, `yes` u8, `speed` u8, `cap` u8 |
| COMMIT (4) | `cand` u8, `delay_ms` u16, `speed` u8 |
| RESYNC (4) | `nonce` u32 (aleatório, do pedinte; §6.3) |
| RESYNC_RSP (4) | `ctr32` u32 (contador completo de TX do respondente); o `nonce` do pedido entra só no MIC (§6.3) |

`dflags` do DATA: bit0 **VAL** (o remetente está validado neste modo), bit1 **HB** (heartbeat, sem payload de
aplicação), bits 2-7 **potência de TX**: `p_dbm = código - 9` (código 0 a 37, de -9 a 28 dBm, passo de 1 dB). O
receptor precisa da potência para medir o ganho do enlace (`RSSI - p_dbm`). Quadros que não são DATA saem na
potência do teto do modo (`min(teto do nó, teto do modo)`). **Teto do par (17/11/2026):** HELLO, PROPOSE e VOTE
levam o teto de TX do nó em `cap` (u8 = `cap_dbm + 9`, mesma escala do código de potência do DATA). O receptor o guarda
(`peer_cap`) e passa a (1) medir o ganho dos controles e do ACK com a potência real do par, `min(peer_cap, teto do
modo)`, e não com a sua; (2) calcular a margem do **pior sentido**: o próprio TX no ganho eu→par e o TX do par no
ganho par→eu, `min(cap_eu + g_eu→par, cap_par + g_par→eu) - sensibilidade`. Enquanto não ouviu nenhum dos três, supõe o
mesmo teto e a conta é a de antes (`cap + min(g)`); com tetos iguais o resultado é idêntico bit a bit. Antes disso, com
tetos diferentes, o ganho dos controles saía errado por `teto_par - teto_eu` e o proponente forte propunha modos que o
par fraco recusava ou desfazia na validação (rollbacks em série): ver o cenário `P` (assimétrico) e a medição de
17/11/2026 em docs/09 §10.

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
- A reconstrução **não dá a volta** nos 32 bits: um `delta` que passaria de `0xFFFFFFFF` é recusado (antes, um
  contador perto do topo aceitaria um valor baixo depois da volta).
- **Fim do contador:** a partir de `LEGUA_CTR_MAX` (`0xFFFFFF00`) o nó não transmite mais (`LEGUA_LOG_CTR_END`,
  uma vez). Contador e chave andam juntos: reusar contador com a mesma chave reabre o replay. A saída é
  reprovisionar o enlace com **chave nova** e registro de NVM zerado nas duas pontas (§6.1). Na prática é
  inalcançável (2^32 quadros), mas o núcleo não pode depender disso. Só o C tem a guarda; o simulador não chega lá.
- A rotação de chave (§6.2) **não** zera o contador: um contador só para todas as chaves, e a proteção contra
  replay vale entre chaves.
- O contador de TX é gravado em NVM em **blocos de 64**. Depois de um reinício o contador salta para
  `bloco × 64 + 64`, acima de tudo que já foi usado. Cada retransmissão usa um contador novo.
- **Registro em NVM** (uma gravação atômica por evento, nunca mais): `{âncora, bloco do contador de TX, piso do
  contador do par, chave de TX, rotação em curso}`. Grava-se quando algum dos dois contadores cruza um múltiplo de
  64, quando a âncora muda e quando o estado da chave muda (§6.2).
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
- **Chaves:** `key_id` (2 bits) escolhe uma de até 4 chaves de 128 bits. **Não há chave padrão nem chave derivada
  do MAC.** `key_id` sem chave carregada não assina nem aceita: `mic()` devolve erro e o quadro é descartado,
  qualquer que seja o MIC que ele traz (um valor fixo devolvido no lugar seria forja trivial, porque quem escolhe o
  `key_id` do quadro é o atacante). Provisionamento em §6.1, rotação em §6.2.
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
MIC inválido numa janela e travar a aceleração.

**Limite de falhas de MIC (requisito, implementado em 17/11/2026).** Conta-se como falha o quadro do par (`src` e
`dst` conferem) cujo contador está na janela e cujo MIC é inválido. O replay, recusado antes pelo contador, não
conta. Depois de `mic_fail_n` falhas (padrão 5, até 8) em `mic_fail_window` (600 s), o nó congela a negociação por
`mic_fail_hold` (3600 s): não propõe e vota "não" a qualquer PROPOSE. Falhas que continuam renovam o congelamento.
O alarme sai como `LEGUA_LOG_MIC_ALARM` e na estatística `alarmes_mic`. `mic_fail_n = 0` desliga o limite.

- **Por que manter o modo, e não voltar ao base** (a recomendação anterior): voltar ao base daria ao atacante uma
  alavanca barata de rebaixamento, com um quadro forjado a cada poucos minutos forçando o modo mais lento (mais
  tempo no ar e mais energia para o par). Congelar só tira dele a chance de tentar uma aceleração forjada. O
  enlace continua no modo em que estava, com a degradação normal (escada, silêncio) intacta.
- **Custo:** quem forja quadros com frequência impede o enlace de acelerar. Um atacante em alcance já consegue
  isso por interferência, então o limite não abre uma porta nova. Durante o congelamento de B, A continua propondo
  e recebendo "não", contido pelo recuo exponencial da negociação (`neg_backoff`).
- Com os padrões, a chance de forjar um quadro antes de o congelamento começar é de 5 × 2^-32 por janela, contra
  2^-31 tentativas em média sem o limite. A truncagem de CMAC a 32 bits é permitida pela
NIST SP 800-38B, que a condiciona a um limite de verificações falhas; **conferir o texto atual da norma**. CCM com tag
de 4 B (como no 802.15.4) é a alternativa que já traz confidencialidade, mas o payload de 9 B não pede sigilo.
Impacto no ar: passar de 4 B para 8 B de MIC acrescenta 4 B por quadro (SF10/125: +~41 ms por quadro de controle).

### 6.1 Provisionamento (decidido em 17/11/2026)

- **Uma chave por enlace.** Cada par de nós tem a sua chave de 128 bits. Chave de rede compartilhada não é usada:
  quem extrai a chave de um nó passaria a se passar por qualquer outro.
- **Geração:** fora do nó, por gerador criptográfico (`/dev/urandom`, `secrets.token_bytes(16)`), na ferramenta de
  provisionamento do integrador. Nunca derivada de MAC, número de série, nome ou data. `legua_keyring_set` recusa
  chave trivial (todos os bytes iguais, como `00..00` e `FF..FF`), que é a cara de um valor padrão esquecido.
- **Instalação:** a mesma chave vai às duas pontas por canal fora do ar (cabo, gravação em fábrica), no `key_id` 0, com
  o registro de NVM zerado (contador, piso do par e chave de TX = 0).
- **Guarda:** é do porte. A chave fica em armazenamento protegido (no ESP32-S3, flash criptografada com NVS
  criptografado, ou bloco de chave em eFuse). Nunca aparece em log, telemetria, `calibracao.json`, nem no git.
- **Reprovisionar** (troca de par, chave vazada, contador esgotado): chave nova e registro de NVM zerado nas duas
  pontas. Reaproveitar uma chave com registro zerado reabre o replay de tudo que já foi transmitido com ela.

### 6.2 Rotação de chave (decidida em 17/11/2026)

Serve para trocar a chave sem parar o enlace (política de validade, suspeita de vazamento). As chaves andam em ciclo
pelo `key_id`: a próxima de `k` é `(k + 1) mod 4`.

```
estado por nó: k = key_id de TX; ant = ainda aceita k-1 (rotação em curso)
aceita na RX:  k;  k-1 se ant;  k+1 (o par começou uma rotação)   -- outro key_id: recusado antes do MIC
legua_key_rotate:           k <- k+1, ant <- 1       (recusada se ant já é 1)
quadro autêntico com k:     ant <- 0                 (o par já usa a nova: aposenta a anterior)
quadro autêntico com k+1:   k <- k+1, ant <- 0       (segue o par e aposenta a anterior)
```

1. O integrador carrega a chave `k+1` nas **duas** pontas (por fora do ar, ou por um canal de aplicação autenticado
   com a chave corrente) e confirma que as duas a têm.
2. Uma ponta chama `legua_key_rotate`. Ela passa a transmitir com `k+1` e ainda aceita `k`.
3. A outra ponta recebe o primeiro quadro autêntico com `k+1`, passa a transmitir com ela e para de aceitar `k`.
4. A primeira ponta ouve o par em `k+1` e para de aceitar `k`. Cada mudança sai em `LEGUA_LOG_KEY` (arg = `k |
   ant << 8`). Com `ant = 0`, o porte apaga a chave `k-1` (`legua_keyring_drop`).

- **Persistência:** `k` e `ant` vão no registro de NVM. Um reinício no meio da rotação não volta à chave antiga.
- **Recusa:** quadro com `key_id` fora do aceito é recusado antes do MIC (`LEGUA_LOG_REJ_KEY`) e conta como falha
  de MIC (§6). Depois de aposentada, a chave antiga não serve mais nem para quem a tenha vazado.
- **Janela de exposição:** durante a rotação, a chave anterior ainda é aceita. Quem a tiver vazado pode forjar
  quadros até o par confirmar a nova, normalmente o próximo quadro. Se a rotação é por vazamento, reprovisionar
  (§6.1) é o caminho seguro.
- **Erro do integrador:** se a outra ponta não tem a chave `k+1`, ela recusa tudo o que chega com `k+1` (falhas de
  MIC, alarme do §6, descida por silêncio) e continua transmitindo com `k`, que a primeira ponta ainda aceita.
  Quando a chave chega, a rotação termina sozinha. Uma ponta sem a chave de TX não transmite (`mic()` falha).
- **Verificação:** o teste de equivalência roda rotações aleatórias (variante `chave`, com reinícios, chave
  carregada tarde e quadros autênticos montados com a chave anterior) nos quatro pares Py/C, mais dois testes
  dirigidos (`test_rotacao_*`).

### 6.3 Ressincronização do contador do par (implementada em 17/11/2026, núcleo C e simulador, quatro pares Py/C)

Problema: o par transmitiu mais de 32767 quadros enquanto o receptor estava fora do ar ou fora de alcance, sem o
receptor reiniciar. A reconstrução de 16 para 32 bits (§5) erra, todo quadro do par falha no MIC e o enlace não
volta sozinho. Testar candidatos para os 16 bits altos custaria até 65536 CMACs por quadro e multiplicaria por 2^16
a chance de uma falsificação passar; descartado.

Em desafio e resposta (o receptor perdido é quem pede):
- **RESYNC** (tipo 7, 16 B, corpo = `nonce` aleatório de 32 bits do pedinte). Vai com o contador de TX do próprio
  pedinte, que o par reconstrói normalmente.
- **RESYNC_RSP** (tipo 8, 16 B, corpo = `ctr32` de TX atual do respondente). O `nonce` **não vai no ar**: entra no MIC
  como dado extra depois do corpo (`CMAC(B0 || cabeçalho || corpo || nonce)`). Só quem conhece o nonce recém-sorteado
  valida, e uma resposta antiga falha porque o nonce é outro. O pedinte confere `low16(ctr32) == ctr16` e, com o MIC
  válido, **sobe** o piso do par para `ctr32` (nunca desce) e grava o registro de NVM.
- **Gatilho (como ficou):** `resync_n` quadros do par recusados seguidos (contador antigo, `key_id` fora do aceito ou MIC
  inválido), sem nenhum quadro válido dele no meio (padrão 8; 0 desliga). Contam também os recusados por contador
  "antigo": com o par entre 32768 e 65535 quadros à frente, todo quadro cai nesse caso e nenhum chega ao MIC.
  Pedidos com recuo exponencial (`t_resync_min` = 30 s, dobrando até `t_resync_max` = 600 s), um por vez, nonce novo a
  cada pedido (o anterior deixa de valer). O pedido sai no instante da recusa que completa a contagem, sem temporizador.
  O respondente atende no máximo um pedido por `t_resync_min`. O nonce vale até ser substituído ou usado; não há
  `t_resync_timeout` separado, porque cada pedido já invalida o anterior.
- **Resposta sem pedido pendente** é recusada (não há nonce para conferir) e conta como falha de MIC.
- **Segurança:** o que o atacante ganha com RESYNC é uma resposta que ele não consegue ler nem usar sem a chave; a
  resposta só vale para o nonce pendente, uma vez, dentro de `t_resync_timeout`. Um único candidato por quadro, então
  a chance de falsificação segue 2^-32 por tentativa. O custo para o respondente é um quadro por pedido autenticado.
  As falhas que levam ao pedido já contam no alarme de MIC (§6): a negociação fica congelada até a volta.
- **Repetição em massa (medido, 18/11/2026, simulador, 1 h, SF10/125, 16 B = 0,33 s no ar):** o atacante repete quadros
  antigos do par; cada um é recusado por contador "antigo". Com uma repetição a cada 10 s ou mais devagar, nada acontece
  (os quadros válidos zeram a contagem). A partir de uma a cada ~3 s o alvo pede RESYNC e o par responde, e o recuo
  **não contém** isso como se esperava: toda resposta válida volta o recuo a `t_resync_min`, então o teto é uma resposta
  por 30 s (cerca de 110 por hora). Com 0,5 repetição/s: 193 pedidos do alvo e 100 respostas por hora (cerca de 65 s e
  33 s de tempo no ar, 1,8 % e 0,9 % do ciclo); com 10 repetições/s: 219 e 114. O enlace legítimo não muda (mesmas
  entregas, trocas e rollbacks que sem ataque; `test_replay_em_massa_provoca_resync_mas_nao_prejudica_o_enlace`), e o
  alarme de MIC já dispara pelas recusas (§6). O custo é energia e ocupação do canal, não perda de dados. Mitigação
  possível, **não implementada** (mudaria o comportamento nos dois núcleos, sem mexer no fio): só voltar o recuo a
  `t_resync_min` se a resposta subir o piso do par em mais de 32767; senão manter o recuo dobrando até 600 s.
- **Não resolve:** par que perdeu a NVM e voltou com contador **menor** (parece replay; só reprovisionando, §6.1) e
  chave divergente (§6.2).
- **Custo no formato (pago):** dois tipos novos e o dado extra do MIC (`legua_frame_verify_x`, campo `extra` de
  `legua_frame`); vetores regenerados (terceira coluna opcional com o nonce). Testes: ausência com mais de 32767
  quadros nos quatro pares Py/C (`test_ressincroniza_o_contador_do_par_perdido`), resposta sem pedido recusada, um quinto
  das sementes aleatórias de equivalência com contador defasado, e fuzz com os oito tipos.
- **Telemetria:** `LEGUA_LOG_RESYNC` (arg 0 = pedido enviado, 1 = concluída) e as estatísticas `resync_pedidos` e `resync_ok`.

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
2. (algoritmo decidido em 16/11/2026: AES-128-CMAC truncado, §6; limite de falhas de MIC, provisionamento e
   rotação de chave decididos e implementados em 17/11/2026, §6, §6.1 e §6.2.) A **ressincronização depois
   de uma ausência longa** foi verificada na simulação (teste `test_ausencia_longa_ressincroniza`, nos quatro
   pares Py/C): com 15 min a 12 h sem enlace, com ou sem reinício de um dos nós ao voltar, os dois voltam a DATA no
   mesmo modo em 0,3 a 7 min (descida por silêncio até o modo base, HELLO e nova negociação). O que ficava
   aberto era o contador do par fora da janela de 32767 (ausência de mais de 32767 quadros sem reinício do par), que
   foi resolvido com o procedimento de ressincronização autenticado de §6.3 (implementado em 17/11/2026).
3. Fragmentação (flag FRAG) e payload maior que 9 B.
4. (feito em 15/11/2026) Controle compactado de 20 para 16 B. Ir a 14 B exigiria tirar a velocidade ou o `yes`
   do corpo (ganho extra de 12% no tempo no ar do controle); não vale enquanto o perfil móvel usa a velocidade.
5. (resolvido em 17/11/2026, §4: o teto do par viaja nos controles e a margem vale o pior sentido.) Potência de TX
   diferente por nó (teto assimétrico): antes o receptor supunha o mesmo teto nos dois lados. No modelo
   formal, o caso extremo (B nunca aceita um modo mais rápido) mantém P1, P2 = 0 e P4: os dois ficam no modo base, sem
   aceleração (docs/06). O efeito sobre o orçamento de enlace (ganho do ACK, controle de potência) segue sem modelo.
