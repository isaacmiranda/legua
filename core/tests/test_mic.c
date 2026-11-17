/* MIC v0 (AES-128-CMAC truncado): FIPS-197, RFC 4493, vetores do Python (simsuite.protocol.mic) e recusa sem chave. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "legua/legua.h"
#include "legua/mic_cmac.h"

static int fails;

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

static size_t unhex(const char *h, uint8_t *out, size_t max)
{
    size_t n = 0;
    while (n < max && hexval(h[0]) >= 0 && hexval(h[1]) >= 0) {
        out[n++] = (uint8_t)(hexval(h[0]) * 16 + hexval(h[1]));
        h += 2;
    }
    return n;
}

static void check(int ok, const char *what)
{
    if (!ok) { printf("FALHA %s\n", what); fails++; }
}

static uint32_t no_rand(void *ctx) { (void)ctx; return 4; }

static void fips197(void)
{
    uint8_t key[16], pt[16], ct[16], want[16], rk[176];
    unhex("000102030405060708090a0b0c0d0e0f", key, 16);
    unhex("00112233445566778899aabbccddeeff", pt, 16);
    unhex("69c4e0d86a7b0430d8cdb78070b4c55a", want, 16);
    legua_aes128_expand(key, rk);
    legua_aes128_encrypt(rk, pt, ct);
    check(memcmp(ct, want, 16) == 0, "AES-128 FIPS-197 C.1");
}

static void rfc4493(void)
{
    static const char *msg = "6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e51"
                             "30c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710";
    static const struct { size_t len; const char *tag; } v[] = {
        {0, "bb1d6929e95937287fa37d129b756746"}, {16, "070a16b46b4d4144f79bdd9dd04a287c"},
        {40, "dfa66747de9ae63030ca32611497c827"}, {64, "51f0bebf7e3b9d92fc49741779363cfe"}};
    uint8_t key[16], m[64], tag[16], want[16], k1[16];
    legua_cmac_key k;
    size_t i;
    unhex("2b7e151628aed2a6abf7158809cf4f3c", key, 16);
    unhex(msg, m, 64);
    legua_cmac_init(&k, key);
    unhex("fbeed618357133667c85e08f7236a8de", k1, 16);
    check(memcmp(k.k1, k1, 16) == 0, "RFC 4493 K1");
    for (i = 0; i < sizeof v / sizeof v[0]; i++) {
        unhex(v[i].tag, want, 16);
        legua_cmac(&k, m, v[i].len, tag);
        check(memcmp(tag, want, 16) == 0, "RFC 4493 etiqueta");
    }
}

/* Quadros reais assinados pelo Python: verify aceita, encode reproduz, um bit trocado e a chave errada recusam. */
static int vectors(const char *path)
{
    FILE *fh = fopen(path, "r");
    char line[256];
    legua_keyring ring, other;
    legua_env env, env_other;
    int n = 0;
    if (!fh) { perror("vetores do MIC"); return -1; }
    legua_keyring_clear(&ring);
    legua_keyring_clear(&other);
    env.mic = legua_keyring_mic; env.rand32 = no_rand; env.ctx = &ring;
    env_other = env; env_other.ctx = &other;
    while (fgets(line, sizeof line, fh)) {
        uint8_t raw[LEGUA_FRAME_MAX], again[LEGUA_FRAME_MAX], key[16];
        unsigned long kid, ctr;
        char *p;
        size_t len, nx;
        uint8_t ex[4];
        legua_frame f;
        if (line[0] == '#' || line[0] == '\n') continue;
        if (line[0] == 'K') {
            kid = strtoul(line + 1, &p, 10);
            while (*p == ' ') p++;
            if (unhex(p, key, 16) != 16) { check(0, "linha de chave"); continue; }
            legua_keyring_set(&ring, (uint8_t)kid, key);
            key[0] ^= 1u;                                       /* outra chave no mesmo key_id */
            legua_keyring_set(&other, (uint8_t)kid, key);
            continue;
        }
        kid = strtoul(line, &p, 10);
        ctr = strtoul(p, &p, 10);
        while (*p == ' ') p++;
        len = unhex(p, raw, sizeof raw);
        nx = 0;                                                 /* quarta coluna opcional: dado extra do MIC */
        p += len * 2;
        if (*p == ' ') nx = unhex(p + 1, ex, sizeof ex);
        check(legua_frame_decode(raw, len, &f) == 0, "decode do vetor");
        memcpy(f.extra, ex, nx); f.extra_len = (uint8_t)nx;
        check(((raw[1] >> 2) & 3u) == kid, "key_id do vetor");
        check(legua_frame_verify_x(raw, len, (uint32_t)ctr, &env, ex, nx) == 1, "MIC do vetor");
        check(legua_frame_encode(&f, (uint32_t)ctr, (uint8_t)kid, &env, again) == (int)len &&
              memcmp(raw, again, len) == 0, "encode reproduz o vetor");
        check(legua_frame_verify_x(raw, len, (uint32_t)ctr, &env_other, ex, nx) == 0, "chave errada recusa");
        check(legua_frame_verify_x(raw, len, (uint32_t)ctr + 0x10000u, &env, ex, nx) == 0, "contador alto errado recusa");
        raw[len / 2] ^= 0x10u;
        check(legua_frame_verify_x(raw, len, (uint32_t)ctr, &env, ex, nx) == 0, "adulteração recusa");
        raw[len / 2] ^= 0x10u;
        if (nx) check(legua_frame_verify(raw, len, (uint32_t)ctr, &env) == 0, "sem o dado extra recusa");
        n++;
    }
    fclose(fh);
    return n;
}

/* Sem chave padrão: key_id sem chave não assina nem aceita, qualquer que seja o MIC no quadro. */
static void missing_key(void)
{
    legua_keyring ring;
    legua_env env;
    legua_frame f;
    uint8_t buf[LEGUA_FRAME_MAX], key[16];
    uint32_t m;
    int len, i;
    for (i = 0; i < 16; i++) key[i] = (uint8_t)(0x5A + 7 * i);   /* não trivial */
    legua_keyring_clear(&ring);
    legua_keyring_set(&ring, 0, key);
    env.mic = legua_keyring_mic; env.rand32 = no_rand; env.ctx = &ring;
    memset(&f, 0, sizeof f);
    f.type = LEGUA_T_ACK; f.src = 0x1234; f.dst = 0x5678; f.body_len = 2;
    len = legua_frame_encode(&f, 77, 0, &env, buf);
    check(len == LEGUA_LEN_ACK && legua_frame_verify(buf, (size_t)len, 77, &env) == 1, "chave 0 assina");
    check(legua_frame_encode(&f, 78, 2, &env, buf) < 0, "key_id 2 sem chave não assina");
    check(legua_keyring_mic(&ring, 3, 1, 1, buf, 4, &m) < 0, "keyring sem chave 3");
    check(legua_keyring_mic(&ring, 4, 1, 1, buf, 4, &m) < 0, "key_id fora da faixa");
    len = legua_frame_encode(&f, 79, 0, &env, buf);
    buf[1] = (uint8_t)((buf[1] & ~0x0Cu) | (1u << 2));          /* quadro passa a dizer key_id 1 */
    for (i = 0; i < 4; i++) buf[len - 1 - i] = 0;               /* MIC zerado, que um valor fixo aceitaria */
    check(legua_frame_verify(buf, (size_t)len, 79, &env) == 0, "key_id 1 sem chave recusa MIC zerado");
    memset(key, 0, sizeof key);
    check(legua_keyring_set(&ring, 1, key) < 0, "recusa chave 00..00");
    memset(key, 0xFF, sizeof key);
    check(legua_keyring_set(&ring, 1, key) < 0, "recusa chave FF..FF");
    check(!(ring.present & 2u), "chave trivial não fica carregada");
    legua_keyring_drop(&ring, 0);
    check(ring.present == 0 && ring.key[0].rk[0] == 0, "drop apaga a chave 0");
    for (i = 0; i < 16; i++) key[i] = (uint8_t)(0x5A + 7 * i);   /* não trivial */
    legua_keyring_set(&ring, 0, key);
    legua_keyring_clear(&ring);
    check(ring.present == 0 && ring.key[0].rk[0] == 0, "clear apaga");
}

int main(int argc, char **argv)
{
    int n;
    if (argc < 2) { fprintf(stderr, "uso: test_mic mic.txt\n"); return 2; }
    fips197();
    rfc4493();
    missing_key();
    n = vectors(argv[1]);
    if (n <= 0) { printf("FALHA sem vetores\n"); fails++; }
    printf("test_mic: %d vetores de quadro, %s\n", n, fails ? "FALHOU" : "ok");
    return fails ? 1 : 0;
}
