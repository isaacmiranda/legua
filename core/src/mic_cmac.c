/* MIC v0: AES-128-CMAC truncado a 32 bits (docs/07 §6). Referência em Python: simsuite/protocol/mic.py. */
#include "legua/mic_cmac.h"

#include <string.h>

static const uint8_t SBOX[256] = {
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
};

static uint8_t xtime(uint8_t b)
{
    unsigned v = b;
    return (uint8_t)((v << 1) ^ ((v >> 7) * 0x1Bu));
}

void legua_aes128_expand(const uint8_t key[LEGUA_KEY_LEN], uint8_t rk[176])
{
    uint8_t rcon = 1, t[4];
    unsigned i, j;
    memcpy(rk, key, 16);
    for (i = 16; i < 176; i += 4) {
        for (j = 0; j < 4; j++)
            t[j] = rk[i - 4 + j];
        if (i % 16 == 0) {
            uint8_t u = t[0];
            t[0] = (uint8_t)(SBOX[t[1]] ^ rcon); t[1] = SBOX[t[2]]; t[2] = SBOX[t[3]]; t[3] = SBOX[u];
            rcon = xtime(rcon);
        }
        for (j = 0; j < 4; j++)
            rk[i + j] = (uint8_t)(rk[i - 16 + j] ^ t[j]);
    }
}

void legua_aes128_encrypt(const uint8_t rk[176], const uint8_t in[16], uint8_t out[16])
{
    uint8_t s[16], u[16];
    unsigned r, i, c;
    for (i = 0; i < 16; i++)
        s[i] = (uint8_t)(in[i] ^ rk[i]);
    for (r = 1; r <= 10; r++) {
        for (i = 0; i < 16; i++)                         /* SubBytes + ShiftRows (estado coluna-maior) */
            u[i] = SBOX[s[(i + 4u * (i % 4u)) % 16u]];
        if (r != 10) {
            for (c = 0; c < 16; c += 4) {                /* MixColumns */
                uint8_t a0 = u[c], a1 = u[c + 1], a2 = u[c + 2], a3 = u[c + 3];
                uint8_t x = (uint8_t)(a0 ^ a1 ^ a2 ^ a3);
                s[c]     = (uint8_t)(a0 ^ x ^ xtime((uint8_t)(a0 ^ a1)));
                s[c + 1] = (uint8_t)(a1 ^ x ^ xtime((uint8_t)(a1 ^ a2)));
                s[c + 2] = (uint8_t)(a2 ^ x ^ xtime((uint8_t)(a2 ^ a3)));
                s[c + 3] = (uint8_t)(a3 ^ x ^ xtime((uint8_t)(a3 ^ a0)));
            }
        } else {
            memcpy(s, u, 16);
        }
        for (i = 0; i < 16; i++)
            s[i] = (uint8_t)(s[i] ^ rk[16u * r + i]);
    }
    memcpy(out, s, 16);
}

static void dbl(const uint8_t in[16], uint8_t out[16])
{
    uint8_t carry = (uint8_t)(in[0] >> 7);
    unsigned i;
    for (i = 0; i < 15; i++)
        out[i] = (uint8_t)((in[i] << 1) | (in[i + 1] >> 7));
    out[15] = (uint8_t)((in[15] << 1) ^ (carry * 0x87u));
}

void legua_cmac_init(legua_cmac_key *k, const uint8_t key[LEGUA_KEY_LEN])
{
    uint8_t l[16] = {0};
    legua_aes128_expand(key, k->rk);
    legua_aes128_encrypt(k->rk, l, l);
    dbl(l, k->k1);
    dbl(k->k1, k->k2);
    memset(l, 0, sizeof l);
}

void legua_cmac(const legua_cmac_key *k, const uint8_t *msg, size_t len, uint8_t tag[16])
{
    uint8_t x[16] = {0}, last[16];
    size_t n = len ? (len + 15) / 16 : 1, rem = len - 16 * (n - 1), i, b;
    for (b = 0; b + 1 < n; b++) {
        for (i = 0; i < 16; i++)
            x[i] = (uint8_t)(x[i] ^ msg[16 * b + i]);
        legua_aes128_encrypt(k->rk, x, x);
    }
    for (i = 0; i < 16; i++) {
        uint8_t m = i < rem ? msg[16 * (n - 1) + i] : (i == rem ? 0x80u : 0u);
        last[i] = (uint8_t)(m ^ (rem == 16 ? k->k1[i] : k->k2[i]));
    }
    for (i = 0; i < 16; i++)
        x[i] = (uint8_t)(x[i] ^ last[i]);
    legua_aes128_encrypt(k->rk, x, tag);
}

int legua_mic_cmac(const legua_cmac_key *k, uint8_t key_id, uint16_t src, uint32_t ctr32,
                   const uint8_t *data, size_t len, uint32_t *out)
{
    uint8_t msg[16 + 255], tag[16];
    if (len > 255 || key_id >= LEGUA_N_KEYS)
        return -1;
    memset(msg, 0, 16);
    msg[0] = LEGUA_B0_DOMAIN; msg[1] = LEGUA_B0_FUNC_MIC; msg[2] = key_id;
    msg[3] = (uint8_t)(src >> 8); msg[4] = (uint8_t)src;
    msg[5] = (uint8_t)(ctr32 >> 24); msg[6] = (uint8_t)(ctr32 >> 16);
    msg[7] = (uint8_t)(ctr32 >> 8); msg[8] = (uint8_t)ctr32;
    msg[9] = (uint8_t)len;
    if (len)
        memcpy(msg + 16, data, len);
    legua_cmac(k, msg, 16 + len, tag);
    *out = ((uint32_t)tag[0] << 24) | ((uint32_t)tag[1] << 16) | ((uint32_t)tag[2] << 8) | tag[3];
    return 0;
}

void legua_keyring_clear(legua_keyring *r)
{
    volatile uint8_t *p = (volatile uint8_t *)r;
    size_t i;
    for (i = 0; i < sizeof *r; i++)                      /* volatile: o compilador não elimina a limpeza */
        p[i] = 0;
}

int legua_keyring_set(legua_keyring *r, uint8_t key_id, const uint8_t key[LEGUA_KEY_LEN])
{
    unsigned i, same = 1;
    if (!r || !key || key_id >= LEGUA_N_KEYS)
        return -1;
    for (i = 1; i < LEGUA_KEY_LEN; i++)
        same &= key[i] == key[0];
    if (same)
        return -2;
    legua_cmac_init(&r->key[key_id], key);
    r->present = (uint8_t)(r->present | (1u << key_id));
    return 0;
}

void legua_keyring_drop(legua_keyring *r, uint8_t key_id)
{
    volatile uint8_t *p;
    size_t i;
    if (!r || key_id >= LEGUA_N_KEYS)
        return;
    p = (volatile uint8_t *)&r->key[key_id];
    for (i = 0; i < sizeof r->key[key_id]; i++)
        p[i] = 0;
    r->present = (uint8_t)(r->present & ~(1u << key_id));
}

int legua_keyring_mic(void *ctx, uint8_t key_id, uint16_t src, uint32_t ctr32,
                      const uint8_t *data, size_t len, uint32_t *out)
{
    const legua_keyring *r = (const legua_keyring *)ctx;
    if (!r || key_id >= LEGUA_N_KEYS || !(r->present & (1u << key_id)))
        return -1;
    return legua_mic_cmac(&r->key[key_id], key_id, src, ctr32, data, len, out);
}
