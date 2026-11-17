/* Ambiente de teste: MIC com hash FNV-1a com chave (SÓ PARA TESTE, não é segurança) e PRNG xorshift. */
#ifndef TESTENV_H
#define TESTENV_H
#include "legua/legua.h"

typedef struct { uint32_t s; uint8_t keys; } test_rng;   /* keys: bit i = chave i carregada */

static int test_mic(void *ctx, uint8_t key_id, uint16_t src, uint32_t ctr32,
                    const uint8_t *data, size_t len, uint32_t *out)
{
    uint32_t h = 0x811C9DC5u;
    size_t i;
    uint8_t pre[6];
    if (!(((const test_rng *)ctx)->keys & (1u << key_id)))
        return -1;
    pre[0] = (uint8_t)(src >> 8); pre[1] = (uint8_t)src;
    pre[2] = (uint8_t)(ctr32 >> 24); pre[3] = (uint8_t)(ctr32 >> 16);
    pre[4] = (uint8_t)(ctr32 >> 8); pre[5] = (uint8_t)ctr32;
    for (i = 0; i < 16; i++) { h ^= (uint8_t)i; h *= 0x01000193u; }          /* chave 00..0f */
    for (i = 0; i < 6; i++) { h ^= pre[i]; h *= 0x01000193u; }
    for (i = 0; i < len; i++) { h ^= data[i]; h *= 0x01000193u; }
    *out = h;
    return 0;
}

static uint32_t test_rand32(void *ctx)
{
    test_rng *r = (test_rng *)ctx;
    r->s ^= r->s << 13; r->s ^= r->s >> 17; r->s ^= r->s << 5;
    return r->s;
}

static legua_env test_env(test_rng *r, uint32_t seed)
{
    legua_env e;
    r->s = seed ? seed : 1u;
    r->keys = 0x0Fu;
    e.mic = test_mic; e.rand32 = test_rand32; e.ctx = r;
    return e;
}
#endif
