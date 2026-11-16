/* GERADO por tools/gen_modetab.py a partir de simsuite.protocol.modes.table('BR-2026'). Não editar.
 * Perfil BR-2026: fonte secundária, nao_verificado (docs/05). Só para comparar e dimensionar. */
#ifndef LEGUA_PROFILE_BR2026_H
#define LEGUA_PROFILE_BR2026_H
#include "legua/legua.h"

#define LEGUA_BR2026_N_MODES 18
#define LEGUA_BR2026_BASE_MODE_ID 0xA1u   /* SF10/125/FH */
#define LEGUA_BR2026_REC_MODE_ID  0xC9u   /* SF11/250/FH */

/* mais rápido primeiro: {mode_id, cap_dbm, sens_dbm, toa_data_us}  // nome */
static const legua_mode_entry LEGUA_BR2026_MODES[LEGUA_BR2026_N_MODES] = {
    {0x50u, 28, -116.010300f, 15424u},  // SF7/500
    {0x70u, 28, -118.510300f, 28288u},  // SF8/500
    {0x49u, 28, -119.020600f, 30848u},  // SF7/250/FH
    {0x90u, 28, -121.010300f, 51456u},  // SF9/500
    {0x69u, 28, -121.520600f, 56576u},  // SF8/250/FH
    {0x41u, 28, -122.030900f, 61696u},  // SF7/125/FH
    {0x47u, 28, -123.030900f, 86272u},  // SF7/125/CR48/FH
    {0xB0u, 28, -123.510300f, 92672u},  // SF10/500
    {0x89u, 28, -124.020600f, 102912u},  // SF9/250/FH
    {0x61u, 28, -124.530900f, 113152u},  // SF8/125/FH
    {0x67u, 28, -125.530900f, 156160u},  // SF8/125/CR48/FH
    {0xA9u, 28, -126.520600f, 185344u},  // SF10/250/FH
    {0xD0u, 28, -126.010300f, 185344u},  // SF11/500
    {0x81u, 28, -127.030900f, 205824u},  // SF9/125/FH
    {0x87u, 28, -128.030900f, 279552u},  // SF9/125/CR48/FH
    {0xF0u, 28, -128.510300f, 329728u},  // SF12/500
    {0xA1u, 28, -129.530900f, 370688u},  // SF10/125/FH
    {0xC9u, 28, -129.020600f, 370688u},  // SF11/250/FH
};

#endif
