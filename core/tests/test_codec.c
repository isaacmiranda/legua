/* Confere o codec C contra os vetores gerados pelo Python (simsuite.protocol.wire). */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "testenv.h"

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

int main(int argc, char **argv)
{
    FILE *fh;
    char line[256];
    test_rng r;
    legua_env env = test_env(&r, 1);
    int n_ok = 0, fails = 0;
    uint32_t t;

    if (argc < 2) { fprintf(stderr, "uso: test_codec vetores.txt\n"); return 2; }
    fh = fopen(argv[1], "r");
    if (!fh) { perror("vetores"); return 2; }
    while (fgets(line, sizeof line, fh)) {
        unsigned long ctr;
        char *hex;
        uint8_t raw[LEGUA_FRAME_MAX], again[LEGUA_FRAME_MAX];
        size_t len = 0, i;
        legua_frame f;
        uint32_t rebuilt;
        if (line[0] == '#' || line[0] == '\n') continue;
        ctr = strtoul(line, &hex, 10);
        while (*hex == ' ') hex++;
        for (i = 0; hexval(hex[i]) >= 0 && hexval(hex[i + 1]) >= 0 && len < sizeof raw; i += 2)
            raw[len++] = (uint8_t)(hexval(hex[i]) * 16 + hexval(hex[i + 1]));
        if (legua_frame_decode(raw, len, &f) < 0) { printf("FALHA decode ctr=%lu\n", ctr); fails++; continue; }
        if (!legua_frame_verify(raw, len, (uint32_t)ctr, &env)) { printf("FALHA mic ctr=%lu\n", ctr); fails++; continue; }
        if (legua_frame_encode(&f, (uint32_t)ctr, (uint8_t)((f.flags >> 2) & 3u), &env, again) != (int)len ||
            memcmp(raw, again, len) != 0) { printf("FALHA reencode ctr=%lu\n", ctr); fails++; continue; }
        /* reconstrução: com last = ctr - 5 deve devolver ctr */
        if (ctr > 5 && (!legua_ctr_reconstruct((uint32_t)ctr - 5u, f.ctr16, &rebuilt) || rebuilt != (uint32_t)ctr)) {
            printf("FALHA reconstrucao ctr=%lu\n", ctr); fails++; continue;
        }
        /* adulteração de um bit deve falhar no MIC */
        raw[LEGUA_HDR_LEN] ^= 1u;
        if (legua_frame_verify(raw, len, (uint32_t)ctr, &env)) { printf("FALHA adulteracao ctr=%lu\n", ctr); fails++; continue; }
        n_ok++;
    }
    fclose(fh);
    /* regras de reconstrução do contador */
    if (legua_ctr_reconstruct(100u, 100u, &t)) { puts("FALHA repetido aceito"); fails++; }
    if (legua_ctr_reconstruct(100u, 50u, &t)) { puts("FALHA antigo aceito"); fails++; }
    if (!legua_ctr_reconstruct(0xFFFFu, 3u, &t) || t != 0x10003u) { puts("FALHA virada de 16 bits"); fails++; }
    printf("codec: %d vetores ok, %d falhas\n", n_ok, fails);
    return fails ? 1 : 0;
}
