/* Ponte de teste: expõe o núcleo C ao Python (ctypes) para o teste de equivalência contra
 * simsuite/protocol/endpoint.py. Só para teste; não faz parte do núcleo. MIC de teste, PRNG xorshift. */
#include <stddef.h>
#include <string.h>
#include "testenv.h"

#define NH 4
#define REC 32

typedef struct {
    legua_endpoint ep;
    legua_config cfg;
    test_rng rng;
    legua_env env;
    legua_mode_entry tab[LEGUA_MAX_MODES];
    int live;
} shim_t;

static shim_t S[NH];

typedef struct { const char *name; size_t off; int kind; } pdef;   /* kind: 0 float, 1 u32, 2 u8 */
#define PF(n) {#n, offsetof(legua_params, n), 0}
#define PU(n) {#n, offsetof(legua_params, n), 1}
#define PB(n) {#n, offsetof(legua_params, n), 2}
static const pdef PD[] = {
    PF(margin_target), PF(margin_up), PF(ladder_step), PF(max_budget_jump), PF(ema_a), PF(v_freeze),
    PF(snr_std_freeze), PF(fade_k), PB(fade_window), PU(cooldown_up_ms), PU(cooldown_back_ms), PU(hb_interval_ms), PU(t_silence_ms),
    PU(t_recovery_ms), PU(t_valid_ms), PU(vote_timeout_ms), PU(instant_delay_ms), PU(hello_interval_ms),
    PU(neg_backoff0_ms), PU(neg_backoff_max_ms), PB(n_up), PB(fail_streak_degrade), PB(retries), PB(k_valid),
    PB(f_valid), PB(rollback_alarm), PB(ladder_recovery_only), PB(persist_at_commit), PB(silence_descent),
    PB(validation), PB(mobile), PB(power_control)
};

/* Valor de um parâmetro de um perfil nomeado (para conferir com simsuite/protocol/perfis.py). */
int shim_profile_get(int profile, const char *name, double *v)
{
    legua_params p;
    size_t i;
    const uint8_t *base = (const uint8_t *)&p;
    if (legua_params_profile(&p, profile) < 0) return -2;
    for (i = 0; i < sizeof PD / sizeof PD[0]; i++) {
        if (strcmp(PD[i].name, name)) continue;
        if (PD[i].kind == 0) { float f; memcpy(&f, base + PD[i].off, sizeof f); *v = (double)f; }
        else if (PD[i].kind == 1) { uint32_t u; memcpy(&u, base + PD[i].off, sizeof u); *v = (double)u; }
        else { *v = (double)base[PD[i].off]; }
        return 0;
    }
    return -1;
}

/* Prepara a configuração do nó h (tabela de modos, ids, teto); parâmetros ficam nos padrões. */
int shim_setup(int h, const uint8_t *ids, const int8_t *caps, const float *sens, const uint32_t *toa,
               int n, int node_id, int peer_id, int base_id, int rec_id, int cap_dbm, float noise_rise)
{
    int i;
    if (h < 0 || h >= NH || n > LEGUA_MAX_MODES) return -1;
    memset(&S[h], 0, sizeof S[h]);
    for (i = 0; i < n; i++) {
        S[h].tab[i].mode_id = ids[i]; S[h].tab[i].cap_dbm = caps[i];
        S[h].tab[i].sens_dbm = sens[i]; S[h].tab[i].toa_data_us = toa[i];
    }
    S[h].cfg.id = (uint16_t)node_id; S[h].cfg.peer = (uint16_t)peer_id;
    S[h].cfg.modes = S[h].tab; S[h].cfg.n_modes = (uint8_t)n;
    S[h].cfg.base_mode_id = (uint8_t)base_id; S[h].cfg.rec_mode_id = (uint8_t)rec_id;
    S[h].cfg.cap_dbm = (int8_t)cap_dbm; S[h].cfg.noise_rise_db = noise_rise;
    legua_params_default(&S[h].cfg.params);
    return 0;
}

int shim_param(int h, const char *name, double v)
{
    size_t i;
    uint8_t *base = (uint8_t *)&S[h].cfg.params;
    for (i = 0; i < sizeof PD / sizeof PD[0]; i++) {
        if (strcmp(PD[i].name, name)) continue;
        if (PD[i].kind == 0) { float f = (float)v; memcpy(base + PD[i].off, &f, sizeof f); }
        else if (PD[i].kind == 1) { uint32_t u = (uint32_t)(v + 0.5); memcpy(base + PD[i].off, &u, sizeof u); }
        else { base[PD[i].off] = (uint8_t)(v + 0.5); }
        return 0;
    }
    return -1;
}

static int dump(const legua_actions *a, uint8_t *out)
{
    int i;
    for (i = 0; i < a->n; i++) {
        const legua_action *x = &a->a[i];
        uint8_t *r = out + i * REC;
        memset(r, 0, REC);
        r[0] = (uint8_t)x->kind;
        switch (x->kind) {
        case LEGUA_ACT_TX: r[1] = x->u.tx.len; r[2] = x->u.tx.mode_id; r[3] = (uint8_t)x->u.tx.power_dbm;
            memcpy(r + 4, x->u.tx.bytes, LEGUA_FRAME_MAX); break;
        case LEGUA_ACT_RX: r[2] = x->u.rx.mode_id; break;
        case LEGUA_ACT_PERSIST: r[1] = x->u.persist.anchor_valid; r[2] = x->u.persist.anchor_mode_id;
            memcpy(r + 4, &x->u.persist.ctr_block, 4); memcpy(r + 8, &x->u.persist.peer_ctr_floor, 4); break;
        case LEGUA_ACT_DELIVER: r[1] = x->u.deliver.seq; break;
        case LEGUA_ACT_LOG: r[1] = x->u.log.code; memcpy(r + 4, &x->u.log.arg, 4); break;
        }
    }
    return a->overflow ? -1 : a->n;
}

int shim_init(int h, uint32_t seed, int anchor_valid, int anchor_mode_id, uint32_t ctr_block,
              uint32_t peer_floor, uint32_t now, uint8_t *out)
{
    legua_actions a;
    if (seed) S[h].env = test_env(&S[h].rng, seed);      /* seed 0: mantém o PRNG (reinício) */
    S[h].cfg.anchor_valid = (uint8_t)anchor_valid; S[h].cfg.anchor_mode_id = (uint8_t)anchor_mode_id;
    S[h].cfg.ctr_block_nvm = ctr_block; S[h].cfg.peer_ctr_floor = peer_floor;
    if (legua_init(&S[h].ep, &S[h].cfg, &S[h].env, now, &a) < 0) return -2;
    S[h].live = 1;
    return dump(&a, out);
}

int shim_on_app(int h, uint32_t now, uint8_t *out)
{
    legua_actions a; uint8_t pl[LEGUA_DATA_PAYLOAD];
    memset(pl, 0, sizeof pl); a.n = 0; a.overflow = 0;
    legua_on_app(&S[h].ep, pl, sizeof pl, now, &a);
    return dump(&a, out);
}

int shim_on_rx(int h, const uint8_t *raw, int len, int rssi10, int snr10, uint32_t now, uint8_t *out)
{
    legua_actions a; legua_rxinfo rx;
    rx.rssi_x10 = (int16_t)rssi10; rx.snr_x10 = (int16_t)snr10; a.n = 0; a.overflow = 0;
    legua_on_rx(&S[h].ep, raw, (size_t)len, &rx, now, &a);
    return dump(&a, out);
}

int shim_on_tx_done(int h, const uint8_t *raw, int len, int mode_id, uint32_t now, uint8_t *out)
{
    legua_actions a; a.n = 0; a.overflow = 0;
    legua_on_tx_done(&S[h].ep, raw, (size_t)len, (uint8_t)mode_id, now, &a);
    return dump(&a, out);
}

int shim_on_timer(int h, uint32_t now, uint8_t *out)
{
    legua_actions a; a.n = 0; a.overflow = 0;
    legua_on_timer(&S[h].ep, now, &a);
    return dump(&a, out);
}

int shim_next_deadline(int h, uint32_t *at) { return legua_next_deadline(&S[h].ep, at); }
void shim_set_speed(int h, float v) { legua_set_speed(&S[h].ep, v); }
int shim_state(int h) { return S[h].ep.state; }
int shim_mode_id(int h) { return S[h].ep.cfg.modes[S[h].ep.mode_i].mode_id; }
int shim_power(int h) { return S[h].ep.p; }
int shim_anchor_id(int h) { return S[h].ep.anchor_i == LEGUA_NO_MODE ? -1 : S[h].ep.cfg.modes[S[h].ep.anchor_i].mode_id; }
void shim_stats(int h, uint32_t *o) { memcpy(o, &S[h].ep.st, sizeof S[h].ep.st); }
int shim_nstats(void) { return (int)(sizeof(legua_stats) / sizeof(uint32_t)); }

/* depuração: [g_me_set, g_peer_set, q_n, out_valid, pend_active, consec_ok] */
void shim_dbg(int h, int *o)
{
    o[0] = S[h].ep.g_me_set; o[1] = S[h].ep.g_peer_set; o[2] = S[h].ep.q_n; o[3] = S[h].ep.out_valid;
    o[4] = S[h].ep.pend_active; o[5] = S[h].ep.consec_ok;
}
