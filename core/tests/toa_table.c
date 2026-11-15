/* Imprime "sf bw cr nbytes toa_us" para conferência com simsuite.core.radio.toa_s. */
#include <stdio.h>
#include "legua/legua.h"

int main(void)
{
    static const unsigned bws[3] = {125, 250, 500};
    static const unsigned nb[4] = {12, 14, 20, 24};
    unsigned b, sf, cr, n;
    for (b = 0; b < 3; b++)
        for (sf = 7; sf <= 12; sf++)
            for (cr = 1; cr <= 4; cr++)
                for (n = 0; n < 4; n++) {
                    legua_mode m;
                    m.sf = (uint8_t)sf; m.bw_khz = (uint16_t)bws[b]; m.cr = (uint8_t)cr; m.fhss = 0;
                    printf("%u %u %u %u %u\n", sf, bws[b], cr, nb[n], (unsigned)legua_toa_us(&m, nb[n]));
                }
    return 0;
}
