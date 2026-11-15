#include <string.h>
#include "legua/legua.h"

#define DEADLINE_FHSS_MS 450u
#define DEADLINE_PLAIN_MS 50u
#define DEADLINE_MARGIN_MS 150u
#define RESEND_MIN_MS 300u
#define RESEND_SPAN_MS 1700u

static int reached(uint32_t now, uint32_t t) { return (int32_t)(now - t) >= 0; }

static legua_action *act_new(legua_actions *a, legua_act_kind k)
{
    legua_action *p;
    if (a->n >= LEGUA_MAX_ACTIONS)
        return NULL;
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

/* Monta, numera e enfileira um quadro para transmissão. */
static void emit(legua_endpoint *ep, legua_actions *acts, legua_frame *f)
{
    uint8_t buf[LEGUA_FRAME_MAX];
    int n;
    legua_action *p;

    ep->ctr++;
    n = legua_frame_encode(f, ep->ctr, ep->cfg.key_id, ep->env, buf);
    if (n < 0)
        return;
    if (ep->ctr % LEGUA_CTR_BLOCK == 0) {
        p = act_new(acts, LEGUA_ACT_PERSIST);
        if (p) p->u.persist.ctr_block = ep->ctr / LEGUA_CTR_BLOCK;
    }
    p = act_new(acts, LEGUA_ACT_TX);
    if (p) {
        memcpy(p->u.tx.bytes, buf, (size_t)n);
        p->u.tx.len = (uint8_t)n;
        ep->n_tx++;
    }
}

static void send_data(legua_endpoint *ep, legua_actions *acts)
{
    legua_frame f;
    const legua_qitem *it = &ep->q[ep->q_head];

    memset(&f, 0, sizeof f);
    f.type = LEGUA_T_DATA;
    f.flags = LEGUA_F_ACKREQ;
    f.src = ep->cfg.id;
    f.dst = ep->cfg.peer;
    f.body_len = 12;
    f.body[0] = it->seq;
    memcpy(f.body + 3, it->payload, LEGUA_DATA_PAYLOAD);
    emit(ep, acts, &f);
}

static void pump(legua_endpoint *ep, legua_actions *acts)
{
    if (ep->out_valid || ep->q_n == 0)
        return;
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

int legua_init(legua_endpoint *ep, const legua_config *cfg, const legua_env *env,
               legua_actions *acts)
{
    legua_action *p;
    if (!ep || !cfg || !env || !env->mic || !env->rand32 || cfg->id == cfg->peer ||
        cfg->id == LEGUA_BROADCAST)
        return -1;
    memset(ep, 0, sizeof *ep);
    ep->cfg = *cfg;
    ep->env = env;
    if (legua_mode_unpack(cfg->mode_id, &ep->mode) < 0)
        return -1;
    ep->ctr = cfg->ctr_block_nvm * LEGUA_CTR_BLOCK + LEGUA_CTR_BLOCK;
    ep->peer_last = cfg->peer_ctr_floor;
    ep->seq = (uint8_t)env->rand32(env->ctx);
    acts->n = 0;
    p = act_new(acts, LEGUA_ACT_RX);
    if (p) p->u.rx.mode_id = cfg->mode_id;
    return 0;
}

void legua_on_app(legua_endpoint *ep, const uint8_t *payload, size_t len, uint32_t now_ms,
                  legua_actions *acts)
{
    legua_qitem *it;
    (void)now_ms;
    if (ep->q_n >= LEGUA_QUEUE_LEN) {
        /* cheia: descarta o mais antigo que não esteja em voo */
        unsigned i;
        unsigned first = ep->out_valid ? 1u : 0u;
        for (i = first; i + 1u < ep->q_n; i++)
            ep->q[(ep->q_head + i) % LEGUA_QUEUE_LEN] = ep->q[(ep->q_head + i + 1u) % LEGUA_QUEUE_LEN];
        ep->q_n--;
        ep->n_lost++;
        act_log(acts, LEGUA_LOG_QUEUE_DROP, 0);
    }
    it = &ep->q[(ep->q_head + ep->q_n) % LEGUA_QUEUE_LEN];
    memset(it, 0, sizeof *it);
    it->seq = ++ep->seq;
    memcpy(it->payload, payload, len < LEGUA_DATA_PAYLOAD ? len : LEGUA_DATA_PAYLOAD);
    ep->q_n++;
    pump(ep, acts);
}

void legua_on_tx_done(legua_endpoint *ep, const uint8_t *raw, size_t len, uint32_t now_ms,
                      legua_actions *acts)
{
    (void)acts;
    if (len >= LEGUA_HDR_LEN + 1u && (raw[0] & 0x1Fu) == LEGUA_T_DATA && ep->out_valid &&
        raw[LEGUA_HDR_LEN] == ep->q[ep->q_head].seq) {
        legua_mode ack_mode = ep->mode;
        uint32_t wait = legua_toa_us(&ack_mode, LEGUA_LEN_ACK) / 1000u +
                        (ep->mode.fhss ? DEADLINE_FHSS_MS : DEADLINE_PLAIN_MS) + DEADLINE_MARGIN_MS;
        ep->out_deadline_ms = now_ms + wait;
        ep->out_deadline_set = 1;
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

void legua_on_rx(legua_endpoint *ep, const uint8_t *raw, size_t len, uint32_t now_ms,
                 legua_actions *acts)
{
    legua_frame f;
    uint32_t ctr32;
    (void)now_ms;

    if (legua_frame_decode(raw, len, &f) < 0) {
        ep->n_rej++;
        act_log(acts, LEGUA_LOG_REJ_FORMAT, 0);
        return;
    }
    if ((f.dst != ep->cfg.id && f.dst != LEGUA_BROADCAST) || f.src != ep->cfg.peer)
        return;                                       /* não é para nós */
    if (!legua_ctr_reconstruct(ep->peer_last, f.ctr16, &ctr32)) {
        ep->n_rej++;
        act_log(acts, LEGUA_LOG_REJ_REPLAY, f.ctr16);
        return;
    }
    if (!legua_frame_verify(raw, len, ctr32, ep->env)) {
        ep->n_rej++;
        act_log(acts, LEGUA_LOG_REJ_MIC, f.ctr16);
        return;
    }
    ep->peer_last = ctr32;

    if (f.type == LEGUA_T_DATA) {
        legua_frame ack;
        uint8_t seq = f.body[0];
        if (seq_is_new(ep, seq)) {
            legua_action *p = act_new(acts, LEGUA_ACT_DELIVER);
            if (p) {
                p->u.deliver.seq = seq;
                memcpy(p->u.deliver.payload, f.body + 3, LEGUA_DATA_PAYLOAD);
            }
            ep->n_delivered++;
        } else {
            ep->n_dup++;
            act_log(acts, LEGUA_LOG_DUP_DATA, seq);
        }
        memset(&ack, 0, sizeof ack);
        ack.type = LEGUA_T_ACK;
        ack.src = ep->cfg.id;
        ack.dst = ep->cfg.peer;
        ack.body_len = 2;
        ack.body[0] = seq;
        ack.body[1] = 0xFF;                           /* ganho desconhecido (Fase 1 mede) */
        emit(ep, acts, &ack);
    } else if (f.type == LEGUA_T_ACK) {
        if (ep->out_valid && f.body[0] == ep->q[ep->q_head].seq) {
            ep->n_acked++;
            q_pop_head(ep);
            ep->out_valid = 0;
            ep->out_deadline_set = ep->out_resend_set = 0;
            pump(ep, acts);
        }
    }
    /* HELLO/PROPOSE/VOTE/COMMIT: Fase 2 */
}

void legua_on_timer(legua_endpoint *ep, uint32_t now_ms, legua_actions *acts)
{
    if (ep->out_valid && ep->out_deadline_set && reached(now_ms, ep->out_deadline_ms)) {
        ep->out_deadline_set = 0;
        if (ep->out_att <= ep->cfg.retries) {
            ep->out_resend_ms = now_ms + RESEND_MIN_MS + ep->env->rand32(ep->env->ctx) % RESEND_SPAN_MS;
            ep->out_resend_set = 1;
            act_log(acts, LEGUA_LOG_RETRY, ep->out_att);
        } else {
            ep->n_lost++;
            act_log(acts, LEGUA_LOG_GIVEUP, ep->q[ep->q_head].seq);
            q_pop_head(ep);
            ep->out_valid = 0;
            pump(ep, acts);
        }
    }
    if (ep->out_valid && ep->out_resend_set && reached(now_ms, ep->out_resend_ms)) {
        ep->out_resend_set = 0;
        ep->out_att++;
        send_data(ep, acts);                          /* contador novo a cada retransmissão */
    }
}

int legua_next_deadline(const legua_endpoint *ep, uint32_t *at)
{
    int have = 0;
    uint32_t best = 0;
    if (ep->out_valid && ep->out_deadline_set) { best = ep->out_deadline_ms; have = 1; }
    if (ep->out_valid && ep->out_resend_set &&
        (!have || (int32_t)(ep->out_resend_ms - best) < 0)) {
        best = ep->out_resend_ms; have = 1;
    }
    if (have) *at = best;
    return have;
}
