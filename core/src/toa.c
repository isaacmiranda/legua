#include "legua/legua.h"

/* Aritmética inteira; tsym = 2^sf * 1000 / bw_khz µs é exato para BW 125/250/500. */
uint32_t legua_toa_us(const legua_mode *m, unsigned nbytes)
{
    uint32_t tsym = ((uint32_t)1u << m->sf) * 1000u / m->bw_khz;
    int de = tsym > 16000u;
    int32_t num, den, nsym, sym;
    int32_t pl = (int32_t)nbytes, sf = (int32_t)m->sf;

    if (m->sf >= 7) {
        num = 8 * pl - 4 * sf + 28 + 16;            /* CRC ligado, cabeçalho explícito */
        den = 4 * (sf - 2 * de);
    } else {
        num = 8 * pl + 16 - 4 * sf + 20;
        den = 4 * sf;
    }
    sym = num <= 0 ? 0 : ((num + den - 1) / den) * (int32_t)(m->cr + 4);
    nsym = 8 + sym;
    /* (preâmbulo + 4,25 ou 6,25 + nsym) * tsym, em quartos de símbolo */
    {
        uint32_t quarters = (uint32_t)(m->sf >= 7 ? 8 * 4 + 17 : 8 * 4 + 25) + 4u * (uint32_t)nsym;
        return (uint32_t)(((uint64_t)quarters * tsym) / 4u);
    }
}
