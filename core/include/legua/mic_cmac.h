/* Légua: MIC v0 de referência, AES-128-CMAC truncado a 32 bits (docs/07 §6). Módulo opcional do núcleo.
 * C99, sem alocação, sem biblioteca de terceiros. O AES aqui é em software, com tabela de substituição: não é de
 * tempo constante (cache). Num porte com AES em hardware (ESP32-S3) ou mbedTLS, prefira o hardware e confira o
 * resultado contra core/tests/vectors/mic.txt. A máquina de estados não depende deste módulo: o porte entrega
 * mic() em legua_env e pode usar legua_keyring_mic() como implementação. */
#ifndef LEGUA_MIC_CMAC_H
#define LEGUA_MIC_CMAC_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LEGUA_KEY_LEN      16
#define LEGUA_N_KEYS       4      /* key_id tem 2 bits no byte de flags */
#define LEGUA_B0_DOMAIN    0x4Cu  /* 'L' */
#define LEGUA_B0_FUNC_MIC  0x01u  /* 0x02 reservado para uma cifra futura */

/* Chave expandida e subchaves do CMAC, calculadas uma vez por chave. */
typedef struct {
    uint8_t rk[176];
    uint8_t k1[16], k2[16];
} legua_cmac_key;

void legua_aes128_expand(const uint8_t key[LEGUA_KEY_LEN], uint8_t rk[176]);
void legua_aes128_encrypt(const uint8_t rk[176], const uint8_t in[16], uint8_t out[16]);

void legua_cmac_init(legua_cmac_key *k, const uint8_t key[LEGUA_KEY_LEN]);
/* AES-CMAC (NIST SP 800-38B, RFC 4493), etiqueta completa de 16 B. */
void legua_cmac(const legua_cmac_key *k, const uint8_t *msg, size_t len, uint8_t tag[16]);

/* MIC do quadro: 4 primeiros bytes de CMAC(B0 || data), em big-endian. data = cabeçalho + corpo (até 255 B).
 * B0 = 0x4C | 0x01 | key_id | src (BE) | ctr32 (BE) | len | 6 x 0x00.  0 ok; <0 se len > 255. */
int legua_mic_cmac(const legua_cmac_key *k, uint8_t key_id, uint16_t src, uint32_t ctr32,
                   const uint8_t *data, size_t len, uint32_t *out);

/* Até quatro chaves, uma por key_id. Sem chave padrão: posição vazia recusa (o quadro é descartado). */
typedef struct {
    legua_cmac_key key[LEGUA_N_KEYS];
    uint8_t present;              /* bit i = chave i carregada */
} legua_keyring;

void legua_keyring_clear(legua_keyring *r);   /* apaga as chaves (zera a memória) */
int legua_keyring_set(legua_keyring *r, uint8_t key_id, const uint8_t key[LEGUA_KEY_LEN]);   /* 0 ok */
/* Assinatura igual à de legua_env.mic: ctx aponta para um legua_keyring. <0 se a chave não está carregada. */
int legua_keyring_mic(void *ctx, uint8_t key_id, uint16_t src, uint32_t ctr32,
                      const uint8_t *data, size_t len, uint32_t *out);

#ifdef __cplusplus
}
#endif
#endif
