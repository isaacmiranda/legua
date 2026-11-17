/* Máquina de estados do enlace P2P da Légua. Porta de simsuite/protocol/endpoint.py: mesma ordem de
 * decisões, mesmos limiares, mesmos sorteios de recuo (o teste de equivalência confere os quadros
 * byte a byte). Tempos em ms (uint32, com aritmética de módulo 2^32); potências em dBm inteiros. */
#include <string.h>
#include "legua/legua.h"

#define DEADLINE_FHSS_MS 450u
#define DEADLINE_PLAIN_MS 50u
#define DEADLINE_MARGIN_MS 150u
#define VALID_EXTRA_MS 10u           /* +0,01 s nos prazos de validação e de silêncio (igual ao Python) */
#define RESEND_LO_MS 300u
#define RESEND_HI_MS 2000u
#define P_MIN_DBM (-9)
#define GAIN_BYTE_UNKNOWN 0xFFu
#define DF_VAL 0x01u
#define DF_HB  0x02u

static int reached(uint32_t now, uint32_t t) { return (int32_t)(now - t) >= 0; }
static int after(uint32_t a, uint32_t b) { return (int32_t)(a - b) > 0; }

/* ------------------------------------------------------------------ ações */
static legua_action *act_new(legua_actions *a, legua_act_kind k)
{
    legua_action *p;
    if (a->n >= LEGUA_MAX_ACTIONS) {
        a->overflow = 1;
        return NULL;
    }
    p = &a->a[a->n++];
    memset(p, 0, sizeof *p);
    p->kind = k;
    return p;
}

static void act_log(legua_actions *a, uint8_t code, uint32_t arg)
{
    legua_action *p = act_new(a, LEGUA_ACT_LOG);
    if (p) { p->u.log.code = code; p->u.log.arg = arg; }
}

static uint32_t rnd_range(const legua_endpoint *ep, uint32_t lo, uint32_t hi)
{
    return lo + (uint32_t)(((uint64_t)(hi - lo) * ep->env->rand32(ep->env->ctx)) >> 32);
}

static uint32_t min_u32(uint32_t a, uint32_t b) { return a < b ? a : b; }
static uint32_t max_u32(uint32_t a, uint32_t b) { return a > b ? a : b; }

/* ------------------------------------------------------------------ modos */
static const legua_mode_entry *ent(const legua_endpoint *ep, uint8_t i) { return &ep->cfg.modes[i]; }

static int mode_index(const legua_endpoint *ep, uint8_t mode_id)
{
    uint8_t i;
    for (i = 0; i < ep->cfg.n_modes; i++)
        if (ep->cfg.modes[i].mode_id == mode_id)
            return i;
    return -1;
}

static int cap_of(const legua_endpoint *ep, uint8_t mi)
{
    int c = ent(ep, mi)->cap_dbm;
    return c < ep->cfg.cap_dbm ? c : ep->cfg.cap_dbm;
}

static float sens_of(const legua_endpoint *ep, uint8_t mi) { return ent(ep, mi)->sens_dbm + ep->cfg.noise_rise_db; }
static float budget_of(const legua_endpoint *ep, uint8_t mi) { return (float)ent(ep, mi)->cap_dbm - sens_of(ep, mi); }

static uint32_t toa_ms_of(const legua_endpoint *ep, unsigned nbytes)
{
    return (legua_toa_us(&ep->mode, nbytes) + 999u) / 1000u;
}

/* Ganho do enlace: algum sentido conhecido. */
static int have_g(const legua_endpoint *ep) { return ep->g_me_set || ep->g_peer_set; }

/* Potência do par nos controles e no ACK do modo mi: o teto dele, se já o conhecemos; senão supõe o nosso. */
static int peer_cap_of(const legua_endpoint *ep, uint8_t mi)
{
    int c = ent(ep, mi)->cap_dbm;
    if (!ep->peer_cap_set)
        return cap_of(ep, mi);
    return c < ep->peer_cap ? c : ep->peer_cap;
}

/* Margem do pior sentido do modo mi: o nosso TX (potência p se use_p, senão o teto) com o ganho eu->par, e o TX do par
 * com o ganho par->eu. Sem o teto do par, vale cap + min(g), como antes. -99 se o ganho é desconhecido. */
static float margin_of(const legua_endpoint *ep, uint8_t mi, int use_p, int p)
{
    float g_out, g_in, mine, theirs;
    if (!have_g(ep))
        return -99.0f;
    g_out = ep->g_peer_set ? ep->g_peer : ep->g_me;       /* eu -> par */
    g_in = ep->g_me_set ? ep->g_me : ep->g_peer;          /* par -> eu */
    mine = (float)(use_p ? p : cap_of(ep, mi)) + g_out - sens_of(ep, mi);
    {
        int pc = peer_cap_of(ep, mi);
        if (use_p && p < pc)
            pc = p;                                   /* potência em teste: o par também é limitado a ela */
        theirs = (float)pc + g_in - sens_of(ep, mi);
    }
    return mine < theirs ? mine : theirs;
}

/* Variância populacional do SNR nas últimas n amostras (0 se houver menos de 4). */
static float snr_var_n(const legua_endpoint *ep, uint8_t n)
{
    float mu = 0.0f, v = 0.0f;
    uint8_t i, k = ep->snr_n < n ? ep->snr_n : n;
    if (k < 4)
        return 0.0f;
    for (i = 0; i < k; i++)
        mu += ep->snr[(ep->snr_pos + LEGUA_SNR_WIN - 1u - i) % LEGUA_SNR_WIN];
    mu /= (float)k;
    for (i = 0; i < k; i++) {
        float d = ep->snr[(ep->snr_pos + LEGUA_SNR_WIN - 1u - i) % LEGUA_SNR_WIN] - mu;
        v += d * d;
    }
    return v / (float)k;
}

static float snr_var(const legua_endpoint *ep) { return snr_var_n(ep, 10); }

/* Raiz quadrada por Newton (sem libm no núcleo). */
static float sqrt_nr(float x)
{
    float r;
    int i;
    if (x <= 0.0f)
        return 0.0f;
    r = x > 1.0f ? x : 1.0f;
    for (i = 0; i < 24; i++)
        r = 0.5f * (r + x / r);
    return r;
}

/* Margem exigida para acelerar: fixa + fade_k x variabilidade medida do SNR. */
static float need_up(const legua_endpoint *ep, float delta)
{
    const legua_params *c = &ep->cfg.params;
    float extra = c->fade_k != 0.0f ? c->fade_k * sqrt_nr(snr_var_n(ep, c->fade_window)) : 0.0f;
    return c->margin_up + delta + extra;
}

static int frozen(const legua_endpoint *ep)
{
    const legua_params *c = &ep->cfg.params;
    float sp = ep->speed > ep->peer_speed ? ep->speed : ep->peer_speed;
    if (!c->mobile)
        return 0;
    return sp > c->v_freeze || snr_var(ep) > c->snr_std_freeze * c->snr_std_freeze;
}

/* ------------------------------------------------------------------ emissão */
static void act_persist(legua_endpoint *ep, legua_actions *acts)
{
    legua_action *p = act_new(acts, LEGUA_ACT_PERSIST);
    ep->nv_dirty = 0;                                 /* o registro gravado já traz os contadores correntes */
    if (p) {
        p->u.persist.anchor_valid = ep->anchor_i != LEGUA_NO_MODE;
        p->u.persist.anchor_mode_id = ep->anchor_i != LEGUA_NO_MODE ? ent(ep, ep->anchor_i)->mode_id : 0;
        p->u.persist.ctr_block = ep->ctr / LEGUA_CTR_BLOCK;
        p->u.persist.peer_ctr_floor = ep->peer_blk * LEGUA_CTR_BLOCK;
        p->u.persist.key_id = ep->key_cur;
        p->u.persist.key_prev_ok = ep->key_prev_ok;
    }
}

static void flush_nv(legua_endpoint *ep, legua_actions *acts)
{
    if (ep->nv_dirty)
        act_persist(ep, acts);
}

/* Teto de TX deste nó no byte que antes era reservado de HELLO/PROPOSE/VOTE: cap_dbm - P_MIN_DBM (docs/07 §4). */
static uint8_t cap_byte(const legua_endpoint *ep)
{
    int c = ep->cfg.cap_dbm - P_MIN_DBM;
    return (uint8_t)(c < 0 ? 0 : (c > 254 ? 254 : c));
}

static uint8_t speed_byte(const legua_endpoint *ep)
{
    float v = ep->speed * 2.0f + 0.5f;
    return v <= 0.0f ? 0u : (v >= 255.0f ? 255u : (uint8_t)v);
}

/* Monta, numera e enfileira um quadro para transmissão (PERSIST do contador antes do TX). */
static void emit(legua_endpoint *ep, legua_actions *acts, legua_frame *f, int power)
{
    uint8_t buf[LEGUA_FRAME_MAX];
    int n;
    legua_action *p;

    if (ep->ctr >= LEGUA_CTR_MAX) {                   /* nunca reusar contador com a mesma chave */
        if (!ep->ctr_end)
            act_log(acts, LEGUA_LOG_CTR_END, ep->ctr);
        ep->ctr_end = 1;
        return;
    }
    ep->ctr++;
    if (f->type == LEGUA_T_RESYNC_RSP) {              /* o contador completo vai no corpo (docs/07 §6.3) */
        f->body[0] = (uint8_t)(ep->ctr >> 24); f->body[1] = (uint8_t)(ep->ctr >> 16);
        f->body[2] = (uint8_t)(ep->ctr >> 8);  f->body[3] = (uint8_t)ep->ctr;
    }
    n = legua_frame_encode(f, ep->ctr, ep->key_cur, ep->env, buf);
    if (n < 0)
        return;
    if (ep->ctr % LEGUA_CTR_BLOCK == 0)
        ep->nv_dirty = 1;                             /* o registro sai no fim do evento (um só por evento) */
    p = act_new(acts, LEGUA_ACT_TX);
    if (p) {
        memcpy(p->u.tx.bytes, buf, (size_t)n);
        p->u.tx.len = (uint8_t)n;
        p->u.tx.mode_id = ent(ep, ep->mode_i)->mode_id;
        p->u.tx.power_dbm = (int8_t)power;
        ep->st.tx++;
    }
}

static void ctrl_frame(legua_endpoint *ep, legua_actions *acts, uint8_t type, uint8_t b0, uint8_t b1,
                       uint8_t b2, uint8_t b3)
{
    legua_frame f;
    memset(&f, 0, sizeof f);
    f.type = type;
    f.src = ep->cfg.id;
    f.dst = ep->cfg.peer;
    f.body_len = 4;
    f.body[0] = b0; f.body[1] = b1; f.body[2] = b2; f.body[3] = b3;
    emit(ep, acts, &f, cap_of(ep, ep->mode_i));
}

static void send_data(legua_endpoint *ep, legua_actions *acts)
{
    legua_frame f;
    const legua_qitem *it = &ep->q[ep->q_head];
    unsigned dflags = (ep->state == LEGUA_S_DATA ? DF_VAL : 0u) | (it->hb ? DF_HB : 0u) |
                      ((unsigned)(ep->p - P_MIN_DBM) << 2);

    memset(&f, 0, sizeof f);
    f.type = LEGUA_T_DATA;
    f.flags = LEGUA_F_ACKREQ;
    f.src = ep->cfg.id;
    f.dst = ep->cfg.peer;
    f.body_len = 12;
    f.body[0] = it->seq;
    f.body[1] = (uint8_t)dflags;
    f.body[2] = speed_byte(ep);
    memcpy(f.body + 3, it->payload, LEGUA_DATA_PAYLOAD);
    emit(ep, acts, &f, ep->p);
}

static void pump(legua_endpoint *ep, legua_actions *acts)
{
    if (ep->out_valid || ep->pend_active || ep->q_n == 0)
        return;
    if (ep->state == LEGUA_S_BASE && !ep->g_me_set)
        return;                                   /* no base, só envia dados depois de ouvir o par */
    ep->out_valid = 1;
    ep->out_att = 1;
    ep->out_deadline_set = 0;
    ep->out_resend_set = 0;
    send_data(ep, acts);
}

static void q_pop_head(legua_endpoint *ep)
{
    ep->q_head = (uint8_t)((ep->q_head + 1u) % LEGUA_QUEUE_LEN);
    ep->q_n--;
}

static void enqueue(legua_endpoint *ep, const uint8_t *payload, size_t len, int hb, legua_actions *acts)
{
    legua_qitem *it;
    if (ep->q_n >= LEGUA_QUEUE_LEN) {
        /* cheia: descarta o mais antigo que não esteja em voo */
        unsigned i;
        unsigned first = ep->out_valid ? 1u : 0u;
        for (i = first; i + 1u < ep->q_n; i++)
            ep->q[(ep->q_head + i) % LEGUA_QUEUE_LEN] = ep->q[(ep->q_head + i + 1u) % LEGUA_QUEUE_LEN];
        ep->q_n--;
        ep->st.perdidos++;
        act_log(acts, LEGUA_LOG_QUEUE_DROP, 0);
    }
    it = &ep->q[(ep->q_head + ep->q_n) % LEGUA_QUEUE_LEN];
    memset(it, 0, sizeof *it);
    it->seq = ++ep->seq;
    it->hb = (uint8_t)hb;
    if (payload)
        memcpy(it->payload, payload, len < LEGUA_DATA_PAYLOAD ? len : LEGUA_DATA_PAYLOAD);
    ep->q_n++;
}

/* ------------------------------------------------------------------ transições */
static void set_mode(legua_endpoint *ep, uint8_t mi, uint8_t state, uint32_t now, uint8_t why,
                     legua_actions *acts)
{
    legua_action *p;
    ep->degraded = (uint8_t)(state == LEGUA_S_RECOV ||
                             (ep->degraded && state == LEGUA_S_DATA && mi != ep->anchor_i));
    ep->mode_i = mi;
    legua_mode_unpack(ent(ep, mi)->mode_id, &ep->mode);
    ep->state = state;
    ep->entered = now;
    ep->p = (int8_t)cap_of(ep, mi);
    ep->fail_streak = 0;
    ep->consec_ok = 0;
    ep->peer_heard = now;
    ep->out_valid = 0;                            /* o pacote pendente continua na fila e sai no novo modo */
    ep->out_deadline_set = ep->out_resend_set = 0;
    p = act_new(acts, LEGUA_ACT_RX);
    if (p) p->u.rx.mode_id = ent(ep, mi)->mode_id;
    act_log(acts, LEGUA_LOG_MODE, (uint32_t)ent(ep, mi)->mode_id | ((uint32_t)state << 8) | ((uint32_t)why << 16));
}

static void neg_fail(legua_endpoint *ep, uint32_t now, legua_actions *acts)
{
    const legua_params *c = &ep->cfg.params;
    ep->st.neg_fail++;
    ep->pend_active = 0;
    if (ep->state == LEGUA_S_NEG || ep->state == LEGUA_S_PEND)
        ep->state = LEGUA_S_DATA;
    if (ep->state == LEGUA_S_BASE) {
        ep->neg_block = now + c->hello_interval_ms;
    } else {
        ep->neg_block = now + ep->neg_backoff;
        ep->neg_backoff = min_u32(c->neg_backoff_max_ms, ep->neg_backoff * 2u);
    }
    act_log(acts, LEGUA_LOG_NEG_FAIL, 0);
}

static int step_down(const legua_endpoint *ep, uint8_t mi)
{
    const legua_params *c = &ep->cfg.params;
    float b;
    int best = -1;
    uint8_t i;
    if (c->ladder_recovery_only)
        return mi != ep->rec_i ? (int)ep->rec_i : -1;
    b = budget_of(ep, mi) + c->ladder_step;
    for (i = 0; i < ep->cfg.n_modes; i++) {
        if (budget_of(ep, i) < b - 1e-4f)
            continue;
        if (best < 0 || ent(ep, i)->toa_data_us < ent(ep, (uint8_t)best)->toa_data_us ||
            (ent(ep, i)->toa_data_us == ent(ep, (uint8_t)best)->toa_data_us &&
             budget_of(ep, i) > budget_of(ep, (uint8_t)best)))
            best = i;
    }
    return best;
}

static void descend(legua_endpoint *ep, uint32_t now, uint8_t why, legua_actions *acts)
{
    int nxt;
    if (ep->mode_i == ep->base_i) {
        if (ep->state == LEGUA_S_BASE)
            return;
        /* no modo base mas ainda em DATA/RECUPERAÇÃO: sem esta transição o prazo de silêncio vencia de novo
         * no mesmo instante (laço sem avanço) */
        ep->st.quedas_base++;
        set_mode(ep, ep->base_i, LEGUA_S_BASE, now, why, acts);
        return;
    }
    nxt = step_down(ep, ep->mode_i);
    if (nxt >= 0 && nxt != (int)ep->mode_i) {
        ep->st.degradacoes++;
        set_mode(ep, (uint8_t)nxt, LEGUA_S_RECOV, now, why, acts);
        return;
    }
    ep->st.quedas_base++;
    set_mode(ep, ep->base_i, LEGUA_S_BASE, now, why, acts);
}

static void rollback(legua_endpoint *ep, uint32_t now, uint8_t why, legua_actions *acts)
{
    const legua_params *c = &ep->cfg.params;
    uint8_t i, k = 0, tgt;
    ep->st.rollbacks++;
    for (i = 0; i < ep->rb_n; i++)
        if (!(now - ep->rb_times[i] >= 3600000u))
            ep->rb_times[k++] = ep->rb_times[i];
    if (k >= LEGUA_RB_RING)
        k = (uint8_t)(LEGUA_RB_RING - 1u);
    ep->rb_times[k++] = now;
    ep->rb_n = k;
    if (ep->rb_n >= c->rollback_alarm && snr_var(ep) < 4.0f) {
        ep->st.alarmes++;
        ep->freeze_until = now + 3600000u;
        act_log(acts, LEGUA_LOG_ALARM, 0);
    }
    ep->bad_set[ep->mode_i] = 1;
    ep->bad_until[ep->mode_i] = now + 3u * ep->neg_backoff;
    tgt = ep->prev_i;
    ep->neg_block = now + ep->neg_backoff;
    ep->neg_backoff = min_u32(c->neg_backoff_max_ms, ep->neg_backoff * 2u);
    set_mode(ep, tgt, tgt == ep->base_i ? LEGUA_S_BASE : LEGUA_S_DATA, now, why, acts);
}

static void validated(legua_endpoint *ep, legua_actions *acts)
{
    ep->state = LEGUA_S_DATA;
    ep->st.neg_ok++;
    ep->neg_backoff = ep->cfg.params.neg_backoff0_ms;
    ep->prev_i = ep->mode_i;
    act_log(acts, LEGUA_LOG_VALIDATED, ent(ep, ep->mode_i)->mode_id);
    if (!ep->cfg.params.persist_at_commit) {
        ep->anchor_i = ep->mode_i;
        act_persist(ep, acts);
    }
}

static void do_switch(legua_endpoint *ep, uint32_t now, legua_actions *acts)
{
    uint8_t cand = ep->pend_cand;
    const legua_params *c = &ep->cfg.params;
    ep->prev_i = ep->state != LEGUA_S_BASE ? ep->mode_i : ep->base_i;
    ep->pend_active = 0;
    ep->st.trocas++;
    ep->last_change = now;
    ep->val_active = 1; ep->val_ok = 0; ep->val_fails = 0; ep->val_done = 0; ep->val_t0 = now;
    set_mode(ep, cand, c->validation ? LEGUA_S_VALID : LEGUA_S_DATA, now, LEGUA_R_SWITCH, acts);
    ep->next_hb = now + rnd_range(ep, 200u, 2000u);
    ep->p = (int8_t)cap_of(ep, cand);
    if (c->persist_at_commit || !c->validation) {
        ep->anchor_i = cand;
        act_persist(ep, acts);
    }
}

static int candidate(const legua_endpoint *ep, uint32_t now, int initial)
{
    const legua_params *c = &ep->cfg.params;
    float cur_b = budget_of(ep, ep->mode_i);
    uint32_t cur_toa = ent(ep, ep->mode_i)->toa_data_us;
    uint8_t i;
    for (i = 0; i < ep->cfg.n_modes; i++) {
        if (!initial && ((uint64_t)ent(ep, i)->toa_data_us * 10u >= (uint64_t)cur_toa * 9u ||
                         budget_of(ep, i) < cur_b - c->max_budget_jump))
            continue;
        if (ep->bad_set[i] && after(ep->bad_until[i], now))
            continue;
        if (margin_of(ep, i, 0, 0) >= need_up(ep, 0.0f))
            return i;                             /* tabela ordenada do mais rápido */
    }
    return -1;
}

static void propose(legua_endpoint *ep, uint32_t now, int initial, int target, legua_actions *acts)
{
    const legua_params *c = &ep->cfg.params;
    int cand = target >= 0 ? target : candidate(ep, now, initial);
    if (cand < 0 || cand == (int)ep->mode_i)
        return;
    ep->pend_active = 1;
    ep->pend_cand = (uint8_t)cand;
    ep->pend_role_a = 1;
    ep->pend_committed = 0;
    ep->pend_inst_set = 0;
    ep->pend_deadline = now + c->vote_timeout_ms + 2u * toa_ms_of(ep, LEGUA_LEN_CTRL);
    if (ep->state != LEGUA_S_BASE)
        ep->state = LEGUA_S_NEG;
    ep->st.tx_ctrl++;
    ctrl_frame(ep, acts, LEGUA_T_PROPOSE, ent(ep, (uint8_t)cand)->mode_id, speed_byte(ep), cap_byte(ep), 0);
    act_log(acts, LEGUA_LOG_PROPOSE, ent(ep, (uint8_t)cand)->mode_id);
}

static void power_trim(legua_endpoint *ep)
{
    const legua_params *c = &ep->cfg.params;
    int p2;
    if (ep->ok_since_p < 255u)
        ep->ok_since_p++;
    if (!c->power_control || ep->ok_since_p < 10u || ep->state != LEGUA_S_DATA)
        return;
    p2 = ep->p - 2;
    if (p2 >= P_MIN_DBM && margin_of(ep, ep->mode_i, 1, p2) >= c->margin_target + 2.0f) {
        ep->p = (int8_t)p2;
        ep->ok_since_p = 0;
    }
}

/* ------------------------------------------------------------------ inicialização */
void legua_params_default(legua_params *p)
{
    memset(p, 0, sizeof *p);
    p->margin_target = 5.0f; p->margin_up = 8.0f; p->ladder_step = 6.0f; p->max_budget_jump = 6.0f;
    p->ema_a = 0.3f; p->v_freeze = 2.0f; p->snr_std_freeze = 3.0f; p->fade_window = 30;
    p->cooldown_up_ms = 600000u; p->cooldown_back_ms = 120000u; p->hb_interval_ms = 60000u;
    p->t_silence_ms = 90000u; p->t_recovery_ms = 180000u; p->t_valid_ms = 45000u;
    p->vote_timeout_ms = 4000u; p->instant_delay_ms = 2500u; p->hello_interval_ms = 10000u;
    p->neg_backoff0_ms = 60000u; p->neg_backoff_max_ms = 960000u;
    p->n_up = 20; p->fail_streak_degrade = 3; p->retries = 3; p->k_valid = 3; p->f_valid = 3;
    p->rollback_alarm = 3;
    p->mic_fail_n = 5; p->mic_fail_window_ms = 600000u; p->mic_fail_hold_ms = 3600000u;
    p->resync_n = 8; p->t_resync_min_ms = 30000u; p->t_resync_max_ms = 600000u;
    p->silence_descent = 1; p->validation = 1; p->power_control = 1;
}

int legua_params_profile(legua_params *p, int profile)
{
    legua_params_default(p);
    switch (profile) {
    case LEGUA_PROFILE_DEFAULT:
        return 0;
    case LEGUA_PROFILE_STABLE:          /* aceleração exige margem + 3 desvios do SNR: menos quedas, mais energia */
        p->fade_k = 3.0f;
        return 0;
    case LEGUA_PROFILE_CAUTIOUS:        /* aceleração exige 14 dB de margem fixa */
        p->margin_up = 14.0f;
        return 0;
    default:
        return -1;
    }
}

int legua_init(legua_endpoint *ep, const legua_config *cfg, const legua_env *env, uint32_t now_ms,
               legua_actions *acts)
{
    legua_action *p;
    int b, r, a = -1;
    if (!ep || !cfg || !env || !env->mic || !env->rand32 || !cfg->modes || cfg->n_modes == 0 ||
        cfg->n_modes > LEGUA_MAX_MODES || cfg->id == cfg->peer || cfg->id == LEGUA_BROADCAST ||
        cfg->params.mic_fail_n > LEGUA_MIC_RING ||
        (cfg->params.resync_n && (!cfg->params.t_resync_min_ms || cfg->params.t_resync_max_ms < cfg->params.t_resync_min_ms)) || cfg->key_id > 3u || cfg->key_prev_ok > 1u)
        return -1;
    memset(ep, 0, sizeof *ep);
    ep->cfg = *cfg;
    ep->env = env;
    b = mode_index(ep, cfg->base_mode_id);
    r = mode_index(ep, cfg->rec_mode_id);
    if (cfg->anchor_valid)
        a = mode_index(ep, cfg->anchor_mode_id);
    if (b < 0 || r < 0 || (cfg->anchor_valid && a < 0))
        return -1;
    ep->base_i = (uint8_t)b;
    ep->rec_i = (uint8_t)r;
    ep->anchor_i = a >= 0 ? (uint8_t)a : LEGUA_NO_MODE;
    ep->mode_i = ep->anchor_i != LEGUA_NO_MODE ? ep->anchor_i : ep->base_i;
    ep->prev_i = ep->mode_i;
    ep->role_a = cfg->id < cfg->peer;
    ep->state = ep->anchor_i != LEGUA_NO_MODE ? LEGUA_S_DATA : LEGUA_S_BASE;
    legua_mode_unpack(ent(ep, ep->mode_i)->mode_id, &ep->mode);
    ep->p = (int8_t)cap_of(ep, ep->mode_i);
    ep->ctr = cfg->ctr_block_nvm * LEGUA_CTR_BLOCK + LEGUA_CTR_BLOCK;   /* salta para o próximo bloco */
    ep->peer_blk = cfg->peer_ctr_floor / LEGUA_CTR_BLOCK;
    ep->peer_last = ep->peer_blk * LEGUA_CTR_BLOCK;
    ep->peer_heard = ep->entered = ep->last_change = ep->neg_block = ep->freeze_until = ep->mic_block = now_ms;
    ep->key_cur = cfg->key_id;
    ep->key_prev_ok = cfg->key_prev_ok;
    ep->neg_backoff = cfg->params.neg_backoff0_ms;
    ep->rs_next = now_ms;
    ep->rs_backoff = cfg->params.t_resync_min_ms;
    ep->next_hello = now_ms + rnd_range(ep, 0u, cfg->params.hello_interval_ms);
    ep->next_hb = now_ms + cfg->params.hb_interval_ms;
    ep->seq = (uint8_t)env->rand32(env->ctx);       /* início aleatório: o par não confunde com duplicata */
    acts->n = 0;
    acts->overflow = 0;
    p = act_new(acts, LEGUA_ACT_RX);
    if (p) p->u.rx.mode_id = ent(ep, ep->mode_i)->mode_id;
    return 0;
}

void legua_set_speed(legua_endpoint *ep, float speed_mps) { ep->speed = speed_mps; }

/* ------------------------------------------------------------------ eventos */

void legua_on_app(legua_endpoint *ep, const uint8_t *payload, size_t len, uint32_t now_ms,
                  legua_actions *acts)
{
    (void)now_ms;
    ep->st.gerados++;
    enqueue(ep, payload, len, 0, acts);
    pump(ep, acts);
    flush_nv(ep, acts);
}

void legua_on_tx_done(legua_endpoint *ep, const uint8_t *raw, size_t len, uint8_t mode_id, uint32_t now_ms,
                      legua_actions *acts)
{
    uint8_t type;
    (void)acts;
    if (len < LEGUA_HDR_LEN + 1u)
        return;
    type = raw[0] & 0x1Fu;
    if (type == LEGUA_T_DATA && ep->out_valid && raw[LEGUA_HDR_LEN] == ep->q[ep->q_head].seq &&
        mode_id == ent(ep, ep->mode_i)->mode_id) {
        uint32_t wait = toa_ms_of(ep, LEGUA_LEN_ACK) +
                        (ep->mode.fhss ? DEADLINE_FHSS_MS : DEADLINE_PLAIN_MS) + DEADLINE_MARGIN_MS;
        ep->out_deadline_ms = now_ms + wait;
        ep->out_deadline_set = 1;
    } else if (type == LEGUA_T_COMMIT && ep->pend_active && ep->pend_role_a && ep->pend_committed &&
               !ep->pend_inst_set) {
        /* delay_ms é contado do fim do COMMIT, e o COMMIT acabou de terminar */
        ep->pend_instant = now_ms + ((uint32_t)raw[LEGUA_HDR_LEN + 1] << 8 | raw[LEGUA_HDR_LEN + 2]);
        ep->pend_inst_set = 1;
    }
}

/* Janela de 32 números de sequência: devolve 1 se é novo (entregar), 0 se repetido. */
static int seq_is_new(legua_endpoint *ep, uint8_t seq)
{
    uint8_t d;
    if (!ep->rx_seq_any) {
        ep->rx_seq_any = 1; ep->rx_seq_top = seq; ep->rx_seq_map = 1u;
        return 1;
    }
    d = (uint8_t)(seq - ep->rx_seq_top);
    if (d == 0)
        return 0;
    if (d < 128u) {                                  /* à frente: desliza a janela */
        ep->rx_seq_map = d >= 32u ? 0u : (ep->rx_seq_map << d);
        ep->rx_seq_map |= 1u;
        ep->rx_seq_top = seq;
        return 1;
    }
    d = (uint8_t)(ep->rx_seq_top - seq);             /* atrás */
    if (d < 32u) {
        if (ep->rx_seq_map & (1u << d))
            return 0;
        ep->rx_seq_map |= (1u << d);
        return 1;
    }
    ep->rx_seq_top = seq; ep->rx_seq_map = 1u;       /* longe demais: novo ciclo do par */
    return 1;
}

/* Ressincronização do contador do par (docs/07 §6.3): resync_n quadros do par recusados seguidos, sem nenhum válido,
 * pedem um RESYNC com nonce novo; recuo exponencial entre pedidos. */
static void rs_note_fail(legua_endpoint *ep, uint32_t now, legua_actions *acts)
{
    const legua_params *c = &ep->cfg.params;
    legua_frame f;
    if (!c->resync_n)
        return;
    if (ep->rs_fails < 255u)
        ep->rs_fails++;
    if (ep->rs_fails < c->resync_n || !reached(now, ep->rs_next))
        return;
    ep->rs_nonce = rnd_range(ep, 1u, 0xFFFFFFFFu);
    ep->rs_nonce_set = 1;
    ep->rs_next = now + ep->rs_backoff;
    ep->rs_backoff = min_u32(ep->rs_backoff * 2u, c->t_resync_max_ms);
    memset(&f, 0, sizeof f);
    f.type = LEGUA_T_RESYNC;
    f.src = ep->cfg.id;
    f.dst = ep->cfg.peer;
    f.body_len = 4;
    f.body[0] = (uint8_t)(ep->rs_nonce >> 24); f.body[1] = (uint8_t)(ep->rs_nonce >> 16);
    f.body[2] = (uint8_t)(ep->rs_nonce >> 8);  f.body[3] = (uint8_t)ep->rs_nonce;
    emit(ep, acts, &f, cap_of(ep, ep->mode_i));
    ep->st.tx_ctrl++;
    ep->st.resync_pedidos++;
    act_log(acts, LEGUA_LOG_RESYNC, 0);
}

/* Limite de falhas de MIC: mic_fail_n falhas na janela congelam a negociação, sem mudar de modo (docs/07 §6). */
static void mic_fail(legua_endpoint *ep, uint32_t now, legua_actions *acts)
{
    const legua_params *c = &ep->cfg.params;
    uint8_t i, k = 0;
    uint32_t until;
    if (!c->mic_fail_n)
        return;
    for (i = 0; i < ep->mic_n; i++)
        if (now - ep->mic_times[i] < c->mic_fail_window_ms)
            ep->mic_times[k++] = ep->mic_times[i];
    if (k >= c->mic_fail_n) {                         /* guarda só as n - 1 mais recentes antes da nova */
        uint8_t drop = (uint8_t)(k - c->mic_fail_n + 1u);
        for (i = 0; i + drop < k; i++)
            ep->mic_times[i] = ep->mic_times[i + drop];
        k = (uint8_t)(k - drop);
    }
    ep->mic_times[k++] = now;
    ep->mic_n = k;
    if (k < c->mic_fail_n)
        return;
    ep->mic_n = 0;
    ep->st.alarmes_mic++;
    until = now + c->mic_fail_hold_ms;
    ep->mic_block = until;
    if (reached(until, ep->freeze_until))
        ep->freeze_until = until;
    act_log(acts, LEGUA_LOG_MIC_ALARM, 0);
}

/* Chaves (docs/07 §6.2). Aceitas na recepção: key_cur; key_cur - 1 durante a rotação; key_cur + 1 (o par começou
 * uma rotação: segue). Devolve 0 se o key_id não é aceito. */
static int key_acceptable(const legua_endpoint *ep, uint8_t k)
{
    return k == ep->key_cur || (ep->key_prev_ok && k == ((ep->key_cur + 3u) & 3u)) ||
           k == ((ep->key_cur + 1u) & 3u);
}

static void key_log(legua_endpoint *ep, legua_actions *acts)
{
    ep->nv_dirty = 1;
    act_log(acts, LEGUA_LOG_KEY, (uint32_t)ep->key_cur | ((uint32_t)ep->key_prev_ok << 8));
}

/* Quadro autenticado com a chave k: confirma ou segue a rotação. */
static void key_seen(legua_endpoint *ep, uint8_t k, legua_actions *acts)
{
    if (k == ep->key_cur && ep->key_prev_ok) {       /* o par já usa a nova: aposenta a anterior */
        ep->key_prev_ok = 0;
        key_log(ep, acts);
    } else if (k == ((ep->key_cur + 1u) & 3u)) {     /* o par começou a rotação: segue e aposenta a anterior */
        ep->key_cur = k;
        ep->key_prev_ok = 0;
        key_log(ep, acts);
    }
}

int legua_key_rotate(legua_endpoint *ep, uint32_t now_ms, legua_actions *acts)
{
    (void)now_ms;
    acts->n = 0;
    acts->overflow = 0;
    if (ep->key_prev_ok)
        return -1;
    ep->key_cur = (uint8_t)((ep->key_cur + 1u) & 3u);
    ep->key_prev_ok = 1;
    key_log(ep, acts);
    flush_nv(ep, acts);
    return 0;
}

static void on_propose(legua_endpoint *ep, const legua_frame *f, uint32_t now, legua_actions *acts)
{
    const legua_params *c = &ep->cfg.params;
    int ci = mode_index(ep, f->body[0]);
    int ok = ci >= 0 && (margin_of(ep, (uint8_t)ci, 0, 0) >= need_up(ep, -2.0f) || ep->state == LEGUA_S_BASE ||
                         !ep->g_me_set || ci == (int)ep->rec_i);
    if (frozen(ep) || !reached(now, ep->mic_block))
        ok = 0;
    ep->st.tx_ctrl++;
    if (ok) {
        ep->pend_active = 1;
        ep->pend_cand = (uint8_t)ci;
        ep->pend_role_a = 0;
        ep->pend_committed = 0;
        ep->pend_inst_set = 0;
        ep->pend_deadline = now + c->vote_timeout_ms + 3u * toa_ms_of(ep, LEGUA_LEN_CTRL) + c->instant_delay_ms;
        if (ep->state != LEGUA_S_BASE)
            ep->state = LEGUA_S_PEND;
    }
    ctrl_frame(ep, acts, LEGUA_T_VOTE, f->body[0], (uint8_t)(ok ? 1 : 0), speed_byte(ep), cap_byte(ep));
}

static void on_vote(legua_endpoint *ep, const legua_frame *f, uint32_t now, legua_actions *acts)
{
    uint16_t d = (uint16_t)ep->cfg.params.instant_delay_ms;
    if (!(ep->pend_active && ep->pend_role_a && f->body[0] == ent(ep, ep->pend_cand)->mode_id))
        return;
    if (!f->body[1]) {
        ep->st.neg_recusa++;
        neg_fail(ep, now, acts);
        return;
    }
    ep->pend_inst_set = 0;                            /* o instante vem do fim do COMMIT (on_tx_done) */
    ep->pend_committed = 1;
    ep->st.tx_ctrl++;
    ctrl_frame(ep, acts, LEGUA_T_COMMIT, ent(ep, ep->pend_cand)->mode_id, (uint8_t)(d >> 8), (uint8_t)d,
               speed_byte(ep));
}

static void on_rx_impl(legua_endpoint *ep, const uint8_t *raw, size_t len, const legua_rxinfo *rx,
                       uint32_t now, legua_actions *acts)
{
    const legua_params *c = &ep->cfg.params;
    legua_frame f;
    uint32_t ctr32;
    float g, rssi, snr;
    int p_tx, rsp = 0, ok;

    if (legua_frame_decode(raw, len, &f) < 0) {
        ep->st.rejeitados++;
        act_log(acts, LEGUA_LOG_REJ_FORMAT, 0);
        return;
    }
    if ((f.dst != ep->cfg.id && f.dst != LEGUA_BROADCAST) || f.src != ep->cfg.peer)
        return;                                       /* não é para nós */
    if (f.type == LEGUA_T_RESYNC_RSP) {               /* o contador completo vem no corpo (o receptor está perdido) */
        ctr32 = ((uint32_t)f.body[0] << 24) | ((uint32_t)f.body[1] << 16) | ((uint32_t)f.body[2] << 8) | f.body[3];
        rsp = 1;
        if ((uint16_t)ctr32 != f.ctr16 || ctr32 <= ep->peer_last) {      /* nunca desce o piso do par */
            ep->st.rejeitados++;
            act_log(acts, LEGUA_LOG_REJ_REPLAY, f.ctr16);
            rs_note_fail(ep, now, acts);
            return;
        }
    } else if (!legua_ctr_reconstruct(ep->peer_last, f.ctr16, &ctr32)) {
        ep->st.rejeitados++;
        act_log(acts, LEGUA_LOG_REJ_REPLAY, f.ctr16);
        rs_note_fail(ep, now, acts);
        return;
    }
    if (!key_acceptable(ep, (uint8_t)((f.flags >> 2) & 3u))) {
        ep->st.rejeitados++;
        act_log(acts, LEGUA_LOG_REJ_KEY, f.ctr16);
        mic_fail(ep, now, acts);
        rs_note_fail(ep, now, acts);
        return;
    }
    if (rsp) {                                        /* o nonce pendente entra no MIC como dado extra */
        uint8_t nb[4];
        nb[0] = (uint8_t)(ep->rs_nonce >> 24); nb[1] = (uint8_t)(ep->rs_nonce >> 16);
        nb[2] = (uint8_t)(ep->rs_nonce >> 8);  nb[3] = (uint8_t)ep->rs_nonce;
        ok = ep->rs_nonce_set && legua_frame_verify_x(raw, len, ctr32, ep->env, nb, 4);
    } else {
        ok = legua_frame_verify(raw, len, ctr32, ep->env);
    }
    if (!ok) {
        ep->st.rejeitados++;
        act_log(acts, LEGUA_LOG_REJ_MIC, f.ctr16);
        mic_fail(ep, now, acts);
        rs_note_fail(ep, now, acts);
        return;
    }
    ep->peer_last = ctr32;
    if (ctr32 / LEGUA_CTR_BLOCK > ep->peer_blk) {     /* piso do par: grava a cada bloco de 64 */
        ep->peer_blk = ctr32 / LEGUA_CTR_BLOCK;
        ep->nv_dirty = 1;
    }
    key_seen(ep, (uint8_t)((f.flags >> 2) & 3u), acts);
    ep->rs_fails = 0;
    if (rsp) {                                        /* ressincronizado: o piso do par subiu para o contador do par */
        ep->rs_nonce_set = 0;
        ep->rs_backoff = c->t_resync_min_ms;
        ep->rs_next = now;
        ep->st.resync_ok++;
        act_log(acts, LEGUA_LOG_RESYNC, 1);
        return;
    }
    if (f.type == LEGUA_T_RESYNC) {                   /* o par perdeu o contador: responde (no máximo um por t_resync_min) */
        if (c->resync_n && reached(now, ep->rs_rsp_next)) {
            legua_frame r;
            memset(&r, 0, sizeof r);
            r.type = LEGUA_T_RESYNC_RSP;
            r.src = ep->cfg.id;
            r.dst = ep->cfg.peer;
            r.body_len = 4;
            r.extra_len = 4;
            memcpy(r.extra, f.body, 4);               /* o nonce do pedido: entra no MIC e não vai ao ar */
            ep->rs_rsp_next = now + c->t_resync_min_ms;
            emit(ep, acts, &r, cap_of(ep, ep->mode_i));
            ep->st.tx_ctrl++;
        }
        return;
    }
    ep->peer_heard = now;
    if (f.type == LEGUA_T_DATA || f.type == LEGUA_T_ACK) {
        uint32_t k = ep->state != LEGUA_S_VALID ? c->hb_interval_ms : c->hb_interval_ms / 10u;
        ep->next_hb = max_u32(ep->next_hb, now + k);
    }
    /* teto do par: HELLO, PROPOSE e VOTE o levam no corpo (byte antes reservado) */
    if (f.type == LEGUA_T_HELLO || f.type == LEGUA_T_PROPOSE || f.type == LEGUA_T_VOTE) {
        ep->peer_cap = (int8_t)((int)f.body[f.type == LEGUA_T_VOTE ? 3 : 2] + P_MIN_DBM);
        ep->peer_cap_set = 1;
    }
    /* potência do par: DATA a leva no quadro; os demais usam o teto dele no modo (ou o nosso, se ainda não o conhecemos) */
    p_tx = f.type == LEGUA_T_DATA ? (int)((f.body[1] >> 2) & 0x3Fu) + P_MIN_DBM : peer_cap_of(ep, ep->mode_i);
    rssi = (float)rx->rssi_x10 / 10.0f;
    snr = (float)rx->snr_x10 / 10.0f;
    g = rssi - (float)p_tx;
    if (!ep->g_me_set) { ep->g_me = g; ep->g_me_set = 1; }
    else ep->g_me = (1.0f - c->ema_a) * ep->g_me + c->ema_a * g;
    ep->snr[ep->snr_pos] = snr;
    ep->snr_pos = (uint8_t)((ep->snr_pos + 1u) % LEGUA_SNR_WIN);
    if (ep->snr_n < LEGUA_SNR_WIN) ep->snr_n++;
    if (f.type != LEGUA_T_ACK) {
        uint8_t sb = f.type == LEGUA_T_DATA ? f.body[2] : (f.type == LEGUA_T_VOTE ? f.body[2] : f.body[1]);
        if (f.type == LEGUA_T_COMMIT) sb = f.body[3];
        ep->peer_speed = (float)sb / 2.0f;
    }

    switch (f.type) {
    case LEGUA_T_HELLO:
        if (ep->state == LEGUA_S_BASE && !ep->role_a && !(f.body[0] & 1u)) {
            /* descoberta bidirecional: responde para o proponente também ouvir */
            ctrl_frame(ep, acts, LEGUA_T_HELLO, 1u, speed_byte(ep), cap_byte(ep), 0);
            ep->st.tx_ctrl++;
        }
        if (ep->state == LEGUA_S_BASE && ep->role_a && !ep->pend_active && reached(now, ep->neg_block) &&
            reached(now, ep->freeze_until) && !frozen(ep))
            propose(ep, now, 1, -1, acts);
        break;
    case LEGUA_T_DATA: {
        legua_frame ack;
        uint8_t seq = f.body[0], dflags = f.body[1];
        int hb = (dflags & DF_HB) != 0;
        float gq;
        long gb;
        if (seq_is_new(ep, seq)) {
            if (!hb) {
                legua_action *a = act_new(acts, LEGUA_ACT_DELIVER);
                if (a) {
                    a->u.deliver.seq = seq;
                    memcpy(a->u.deliver.payload, f.body + 3, LEGUA_DATA_PAYLOAD);
                }
                ep->st.entregues++;
            }
        } else {
            ep->st.duplicados++;
            act_log(acts, LEGUA_LOG_DUP_DATA, seq);
        }
        memset(&ack, 0, sizeof ack);
        ack.type = LEGUA_T_ACK;
        ack.src = ep->cfg.id;
        ack.dst = ep->cfg.peer;
        ack.body_len = 2;
        ack.body[0] = seq;
        gq = (-60.0f - g) * 2.0f + 0.5f;              /* ganho = -60 - byte x 0,5 dB (docs/07) */
        gb = gq <= 0.0f ? 0 : (gq >= 254.0f ? 254 : (long)gq);
        ack.body[1] = (uint8_t)gb;
        emit(ep, acts, &ack, cap_of(ep, ep->mode_i));
        if (ep->state == LEGUA_S_RECOV) {
            ep->consec_ok++;
            if (ep->consec_ok >= 3u)
                ep->state = LEGUA_S_DATA;
        }
        if (ep->state == LEGUA_S_VALID && !ep->role_a && (dflags & DF_VAL))
            validated(ep, acts);
        break;
    }
    case LEGUA_T_ACK:
        if (ep->out_valid && f.body[0] == ep->q[ep->q_head].seq) {
            if (f.body[1] != GAIN_BYTE_UNKNOWN) {
                float gp = -60.0f - (float)f.body[1] * 0.5f;
                if (!ep->g_peer_set) { ep->g_peer = gp; ep->g_peer_set = 1; }
                else ep->g_peer = (1.0f - c->ema_a) * ep->g_peer + c->ema_a * gp;
            }
            ep->st.acked++;
            q_pop_head(ep);
            ep->out_valid = 0;
            ep->out_deadline_set = ep->out_resend_set = 0;
            if (ep->consec_ok < 255u) ep->consec_ok++;
            ep->fail_streak = 0;
            if (ep->state == LEGUA_S_VALID && ep->role_a) {
                ep->val_ok++;
                if (ep->val_ok >= c->k_valid && !ep->val_done) {
                    ep->val_done = 1;
                    validated(ep, acts);
                }
            } else if (ep->state == LEGUA_S_RECOV && ep->consec_ok >= 3u) {
                ep->state = LEGUA_S_DATA;
            }
            power_trim(ep);
            pump(ep, acts);
        }
        break;
    case LEGUA_T_PROPOSE:
        on_propose(ep, &f, now, acts);
        break;
    case LEGUA_T_VOTE:
        on_vote(ep, &f, now, acts);
        break;
    case LEGUA_T_COMMIT:
        if (ep->pend_active && !ep->pend_role_a && f.body[0] == ent(ep, ep->pend_cand)->mode_id) {
            ep->pend_committed = 1;
            ep->pend_instant = now + ((uint32_t)f.body[1] << 8 | f.body[2]);   /* relativo ao fim do COMMIT */
            ep->pend_inst_set = 1;
            act_log(acts, LEGUA_LOG_COMMIT_RX, 0);
        }
        break;
    default:
        break;
    }
}

void legua_on_rx(legua_endpoint *ep, const uint8_t *raw, size_t len, const legua_rxinfo *rx,
                 uint32_t now, legua_actions *acts)
{
    on_rx_impl(ep, raw, len, rx, now, acts);
    flush_nv(ep, acts);
}

/* ------------------------------------------------------------------ tempo */
static void on_timer_impl(legua_endpoint *ep, uint32_t now, legua_actions *acts)
{
    const legua_params *c = &ep->cfg.params;
    uint32_t anc_ok;

    /* ACK expirado */
    if (ep->out_valid && ep->out_deadline_set && reached(now, ep->out_deadline_ms)) {
        ep->out_deadline_set = 0;
        ep->fail_streak = (uint8_t)(ep->fail_streak + (ep->fail_streak < 255u));
        ep->consec_ok = 0;
        if (ep->state == LEGUA_S_VALID)
            ep->val_fails++;
        ep->ok_since_p = 0;
        if (ep->p < cap_of(ep, ep->mode_i)) {
            int np = ep->p + 6;
            ep->p = (int8_t)(np < cap_of(ep, ep->mode_i) ? np : cap_of(ep, ep->mode_i));   /* potência é unilateral */
        }
        if (ep->out_att <= c->retries) {
            ep->out_resend_ms = now + rnd_range(ep, RESEND_LO_MS, RESEND_HI_MS);
            ep->out_resend_set = 1;
            act_log(acts, LEGUA_LOG_RETRY, ep->out_att);
        } else {
            ep->st.perdidos++;
            act_log(acts, LEGUA_LOG_GIVEUP, ep->q[ep->q_head].seq);
            if (ep->q_n)
                q_pop_head(ep);
            ep->out_valid = 0;
        }
        if (ep->state == LEGUA_S_VALID && ep->role_a && ep->val_fails >= c->f_valid) {
            rollback(ep, now, LEGUA_R_VALID_FAILED, acts);
            return;
        }
        if (ep->state == LEGUA_S_DATA && ep->fail_streak >= c->fail_streak_degrade &&
            ep->p >= cap_of(ep, ep->mode_i)) {
            descend(ep, now, LEGUA_R_FAILS, acts);
            return;
        }
    }
    /* retransmissão após recuo aleatório (contador novo a cada tentativa) */
    if (ep->out_valid && ep->out_resend_set && reached(now, ep->out_resend_ms)) {
        ep->out_resend_set = 0;
        ep->out_att++;
        ep->out_deadline_set = 0;
        send_data(ep, acts);
    }
    /* validação expirada */
    if (ep->state == LEGUA_S_VALID && after(now - ep->val_t0, c->t_valid_ms)) {
        rollback(ep, now, LEGUA_R_VALID_EXPIRED, acts);
        return;
    }
    /* negociação: voto ou commit não chegou */
    if (ep->pend_active) {
        if (ep->pend_committed && ep->pend_inst_set && reached(now, ep->pend_instant))
            do_switch(ep, now, acts);
        else if (!ep->pend_committed && reached(now, ep->pend_deadline))
            neg_fail(ep, now, acts);
    }
    /* silêncio */
    if (c->silence_descent) {
        if (ep->state == LEGUA_S_DATA && after(now - ep->peer_heard, c->t_silence_ms)) {
            ep->st.desc_silencio++;
            descend(ep, now, LEGUA_R_SILENCE, acts);
        } else if (ep->state == LEGUA_S_RECOV && after(now - ep->peer_heard, c->t_recovery_ms)) {
            ep->st.desc_silencio++;
            descend(ep, now, LEGUA_R_SILENCE_REC, acts);
        }
    }
    /* base: proposta inicial e HELLO periódico */
    if (ep->state == LEGUA_S_BASE && ep->role_a && !ep->pend_active && reached(now, ep->neg_block) &&
        reached(now, ep->freeze_until) && ep->consec_ok >= 5u && !ep->out_valid && !frozen(ep))
        propose(ep, now, 1, -1, acts);
    if (ep->state == LEGUA_S_BASE && reached(now, ep->next_hello) &&
        after(now - ep->peer_heard, 3u * c->hello_interval_ms)) {
        ep->next_hello = now + c->hello_interval_ms * rnd_range(ep, 700u, 1300u) / 1000u;
        ep->st.tx_ctrl++;
        ctrl_frame(ep, acts, LEGUA_T_HELLO, 0, speed_byte(ep), cap_byte(ep), 0);
    }
    /* heartbeat */
    if ((ep->state == LEGUA_S_DATA || ep->state == LEGUA_S_RECOV || ep->state == LEGUA_S_VALID) &&
        reached(now, ep->next_hb) && !(ep->state == LEGUA_S_VALID && !ep->role_a)) {
        uint32_t base_ms = ep->state == LEGUA_S_VALID ? 4000u : c->hb_interval_ms;
        ep->next_hb = now + base_ms * rnd_range(ep, 750u, 1250u) / 1000u;
        if (ep->q_n == 0 && !ep->out_valid) {
            enqueue(ep, NULL, 0, 1, acts);
            pump(ep, acts);
        }
    }
    /* retorno à âncora depois de uma degradação (mais rápido que a aceleração normal) */
    anc_ok = ep->anchor_i != LEGUA_NO_MODE &&
             !(ep->bad_set[ep->anchor_i] && after(ep->bad_until[ep->anchor_i], now));
    if (ep->state == LEGUA_S_DATA && ep->role_a && !ep->pend_active && !ep->out_valid && ep->degraded &&
        ep->anchor_i != LEGUA_NO_MODE && ep->anchor_i != ep->mode_i && ep->consec_ok >= 10u &&
        reached(now - ep->entered, c->cooldown_back_ms) && reached(now, ep->neg_block) &&
        reached(now, ep->freeze_until) && !frozen(ep) &&
        margin_of(ep, ep->anchor_i, 0, 0) >= need_up(ep, -2.0f) && anc_ok) {
        propose(ep, now, 0, ep->anchor_i, acts);
    } else if (ep->state == LEGUA_S_DATA && ep->role_a && !ep->pend_active && !ep->out_valid &&
               ep->consec_ok >= c->n_up && reached(now - ep->last_change, c->cooldown_up_ms) &&
               reached(now, ep->neg_block) && reached(now, ep->freeze_until)) {
        if (!frozen(ep))
            propose(ep, now, 0, -1, acts);
    }
    if (ep->state != LEGUA_S_NEG && ep->state != LEGUA_S_PEND)
        pump(ep, acts);
}

void legua_on_timer(legua_endpoint *ep, uint32_t now, legua_actions *acts)
{
    on_timer_impl(ep, now, acts);
    flush_nv(ep, acts);
}

int legua_next_deadline(const legua_endpoint *ep, uint32_t *at)
{
    const legua_params *c = &ep->cfg.params;
    int have = 0;
    uint32_t best = 0;
#define CAND(t) do { uint32_t t_ = (t); if (!have || (int32_t)(t_ - best) < 0) { best = t_; have = 1; } } while (0)
    if (ep->state == LEGUA_S_BASE) {
        uint32_t h = ep->peer_heard + 3u * c->hello_interval_ms;
        CAND(after(ep->next_hello, h) ? ep->next_hello : h);
    }
    if (ep->state == LEGUA_S_DATA || ep->state == LEGUA_S_RECOV || (ep->state == LEGUA_S_VALID && ep->role_a))
        CAND(ep->next_hb);
    if (ep->out_valid && ep->out_deadline_set) CAND(ep->out_deadline_ms);
    if (ep->out_valid && ep->out_resend_set) CAND(ep->out_resend_ms);
    if (ep->pend_active) {
        if (ep->pend_committed) { if (ep->pend_inst_set) CAND(ep->pend_instant); }
        else CAND(ep->pend_deadline);
    }
    if (ep->state == LEGUA_S_VALID) CAND(ep->val_t0 + c->t_valid_ms + VALID_EXTRA_MS);
    if (ep->state == LEGUA_S_DATA && c->silence_descent) CAND(ep->peer_heard + c->t_silence_ms + VALID_EXTRA_MS);
    if (ep->state == LEGUA_S_RECOV && c->silence_descent) CAND(ep->peer_heard + c->t_recovery_ms + VALID_EXTRA_MS);
#undef CAND
    if (have) *at = best;
    return have;
}
