/* Bordas do codec e do tempo no ar que os demais testes não alcançam (entradas inválidas, SF5/SF6). */
#include <stdio.h>
#include <stdlib.h>
#include "legua/legua.h"

static int fails;
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "falhou: %s (linha %d)\n", #c, __LINE__); fails++; } } while (0)

static uint32_t absdiff(uint32_t a, uint32_t b) { return a > b ? a - b : b - a; }

int main(void)
{
    legua_mode m, u;
    uint8_t id = 0;
    unsigned sf, cr, k;
    static const uint16_t bws[3] = {125, 250, 500};
    uint8_t raw[LEGUA_FRAME_MAX] = {0};
    legua_frame f;

    /* ida e volta de todos os modos válidos */
    for (sf = 5; sf <= 12; sf++)
        for (k = 0; k < 3; k++)
            for (cr = 1; cr <= 4; cr++) {
                m.sf = (uint8_t)sf; m.bw_khz = bws[k]; m.cr = (uint8_t)cr; m.fhss = (uint8_t)(cr & 1u);
                CHECK(legua_mode_pack(&m, &id) == 0);
                CHECK(legua_mode_unpack(id, &u) == 0);
                CHECK(u.sf == m.sf && u.bw_khz == m.bw_khz && u.cr == m.cr && u.fhss == m.fhss);
            }
    /* fora do formato */
    m.sf = 4; m.bw_khz = 125; m.cr = 1; m.fhss = 0;  CHECK(legua_mode_pack(&m, &id) < 0);
    m.sf = 13;                                       CHECK(legua_mode_pack(&m, &id) < 0);
    m.sf = 7; m.cr = 0;                              CHECK(legua_mode_pack(&m, &id) < 0);
    m.cr = 5;                                        CHECK(legua_mode_pack(&m, &id) < 0);
    m.cr = 1; m.bw_khz = 62;                         CHECK(legua_mode_pack(&m, &id) < 0);

    /* SF5 e SF6 (cabeçalho implícito do SX126x): valores de simsuite.core.radio.toa_s, tolerância de 2 us */
    m.sf = 5; m.bw_khz = 125; m.cr = 1; m.fhss = 0;  CHECK(absdiff(legua_toa_us(&m, 10), 12096u) <= 2);
    m.sf = 6; m.bw_khz = 250; m.cr = 2;              CHECK(absdiff(legua_toa_us(&m, 24), 19520u) <= 2);
    m.sf = 5; m.bw_khz = 500; m.cr = 4;              CHECK(absdiff(legua_toa_us(&m, 3), 2448u) <= 2);

    /* decodificação de lixo: tamanho zero, curto e tipo inválido não podem passar */
    CHECK(legua_frame_decode(raw, 0, &f) < 0);
    CHECK(legua_frame_decode(raw, 3, &f) < 0);
    raw[0] = 0xFF;
    CHECK(legua_frame_decode(raw, sizeof raw, &f) < 0);

    if (fails) { fprintf(stderr, "edge: %d falhas\n", fails); return 1; }
    printf("edge: ok\n");
    return 0;
}
