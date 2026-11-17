/* Robustez do núcleo: entradas hostis nunca derrubam a máquina de estados. Roda com ASan e UBSan (make fuzz).
 *  1) bytes aleatórios, quadros truncados e adulterados no decodificador e em legua_on_rx;
 *  2) quadros com MIC VÁLIDO e campos absurdos (modo inexistente, voto 255, atraso enorme, potência 54 dBm, velocidade
 *     255) em todos os estados, intercalados com tempo, dados e reinícios de sequência.
 * Invariantes depois de cada chamada: índices dentro da tabela, potência no intervalo, estado válido, fila no limite,
 * ações sem estouro, contador de TX estritamente crescente, piso do par <= último contador aceito. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "testenv.h"
#include "../profiles/br2026.h"

static legua_endpoint EP;
static test_rng rng, src;
static legua_env env;
static uint32_t now;
static uint32_t last_ctr;
static unsigned long calls;

#define FAIL(msg) do { printf("FALHA (chamada %lu): %s\n", calls, msg); exit(1); } while (0)

static uint32_t R(uint32_t n) { return n ? test_rand32(&src) % n : 0u; }

static void check(const legua_actions *a)
{
    unsigned i;
    calls++;
    if (a->overflow || a->n > LEGUA_MAX_ACTIONS) FAIL("ações estouraram");
    if (EP.mode_i >= EP.cfg.n_modes || EP.base_i >= EP.cfg.n_modes || EP.rec_i >= EP.cfg.n_modes) FAIL("índice de modo");
    if (EP.anchor_i != LEGUA_NO_MODE && EP.anchor_i >= EP.cfg.n_modes) FAIL("índice de âncora");
    if (EP.state > LEGUA_S_RECOV) FAIL("estado inválido");
    if (EP.p < -9 || EP.p > EP.cfg.cap_dbm) FAIL("potência fora do intervalo");
    if (EP.q_n > LEGUA_QUEUE_LEN || EP.q_head >= LEGUA_QUEUE_LEN) FAIL("fila");
    if (EP.out_valid && EP.q_n == 0) FAIL("pacote em voo sem fila");
    if (EP.ctr < last_ctr) FAIL("contador de TX retrocedeu");
    last_ctr = EP.ctr;
    if (EP.peer_blk * LEGUA_CTR_BLOCK > EP.peer_last) FAIL("piso do par acima do último contador");
    for (i = 0; i < a->n; i++) {
        const legua_action *x = &a->a[i];
        if (x->kind == LEGUA_ACT_TX && (x->u.tx.len > LEGUA_FRAME_MAX || x->u.tx.len < LEGUA_HDR_LEN + LEGUA_MIC_LEN))
            FAIL("tamanho de TX");
        if (x->kind > LEGUA_ACT_LOG) FAIL("tipo de ação");
    }
}

static void boot(uint32_t seed)
{
    legua_config c;
    legua_actions a;
    memset(&c, 0, sizeof c);
    c.id = 1; c.peer = 2; c.modes = LEGUA_BR2026_MODES; c.n_modes = LEGUA_BR2026_N_MODES;
    c.base_mode_id = LEGUA_BR2026_BASE_MODE_ID; c.rec_mode_id = LEGUA_BR2026_REC_MODE_ID; c.cap_dbm = 28;
    legua_params_default(&c.params);
    if (seed & 1u) c.params.mobile = 1;
    if (seed & 2u) c.params.fade_k = 3.0f;
    if (seed & 4u) { c.anchor_valid = 1; c.anchor_mode_id = LEGUA_BR2026_MODES[3].mode_id; c.ctr_block_nvm = 7; c.peer_ctr_floor = 640; }
    env = test_env(&rng, seed | 1u);
    if (legua_init(&EP, &c, &env, now, &a) < 0) FAIL("init");
    last_ctr = 0;
    check(&a);
}

/* Quadro com MIC válido do par (id 2 -> 1), contador à frente, corpo arbitrário. */
static unsigned build_valid(uint8_t *out, uint8_t type, uint32_t ctr)
{
    legua_frame f;
    int n;
    unsigned i;
    memset(&f, 0, sizeof f);
    f.type = type; f.flags = (uint8_t)(R(2) ? LEGUA_F_ACKREQ : 0u); f.src = 2; f.dst = 1;
    f.body_len = (uint8_t)(legua_frame_len(type) - LEGUA_HDR_LEN - LEGUA_MIC_LEN);
    for (i = 0; i < f.body_len; i++) f.body[i] = (uint8_t)R(256);
    if (R(2) && f.body_len) f.body[0] = LEGUA_BR2026_MODES[R(LEGUA_BR2026_N_MODES)].mode_id;   /* candidato plausível */
    n = legua_frame_encode(&f, ctr, 0, &env, out);
    return n < 0 ? 0u : (unsigned)n;
}

int main(void)
{
    uint32_t peer_ctr = 700, round, i;
    unsigned long ok_frames = 0;
    src.s = 0x9E3779B9u;
    for (round = 0; round < 16; round++) {
        boot(round);
        for (i = 0; i < 12000; i++) {
            legua_actions a;
            uint8_t buf[40];
            legua_rxinfo rx;
            unsigned len, kind = R(10);
            now += 1u + R(4000);
            a.n = 0; a.overflow = 0;
            rx.rssi_x10 = (int16_t)(-1400 + (int)R(900)); rx.snr_x10 = (int16_t)(-200 + (int)R(300));
            if (kind == 0) {                                 /* bytes aleatórios de tamanho aleatório */
                len = R(40);
                { unsigned j; for (j = 0; j < len; j++) buf[j] = (uint8_t)R(256); }
                legua_on_rx(&EP, buf, len, &rx, now, &a);
            } else if (kind == 1 || kind == 2) {             /* válido, adulterado ou truncado */
                len = build_valid(buf, (uint8_t)(1u + R(6)), peer_ctr + 1u + R(3));
                if (len) {
                    if (kind == 1) buf[R(len)] ^= (uint8_t)(1u << R(8));
                    else len = R(len + 1u);
                    legua_on_rx(&EP, buf, len, &rx, now, &a);
                }
            } else if (kind <= 6) {                          /* válido com campos absurdos: todos os tipos */
                uint8_t type = (uint8_t)(1u + R(8));
                peer_ctr += 1u + R(2);
                len = build_valid(buf, type, peer_ctr);
                if (len) { legua_on_rx(&EP, buf, len, &rx, now, &a); ok_frames++; }
            } else if (kind == 7) {
                legua_on_app(&EP, buf, R(15), now, &a);
            } else if (kind == 8) {
                legua_on_tx_done(&EP, buf, R(24), (uint8_t)R(256), now, &a);
            } else {
                uint32_t d;
                if (legua_next_deadline(&EP, &d) && (int32_t)(d - now) > 0) now = d;
                legua_on_timer(&EP, now, &a);
                legua_set_speed(&EP, (float)R(30) * 0.5f);
            }
            check(&a);
        }
    }
    printf("fuzz: ok (%lu chamadas, %lu quadros válidos com campos aleatórios)\n", calls, ok_frames);
    return 0;
}
