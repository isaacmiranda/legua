/* Simulador mínimo (Fase 0): dois nós virtuais trocam DATA/ACK por um canal com perda,
 * em tempo virtual e semente fixa. Critério de saída: entrega com ACK, sem duplicata,
 * rejeição de replay e de MIC inválido. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "testenv.h"

#define MAXEV 64

typedef struct { uint32_t t; int to; uint8_t len; uint8_t bytes[LEGUA_FRAME_MAX]; int txdone_for; } ev_t;

typedef struct {
    legua_endpoint ep;
    test_rng rng;
    legua_env env;
    uint32_t delivered_n;
    uint8_t  delivered[256];     /* marca por seq entregue */
    uint32_t persist_n;
} node_t;

static node_t N[2];
static ev_t Q[MAXEV];
static int nq;
static uint32_t now;
static test_rng chan;
static unsigned loss_pct;
static uint32_t n_ch_tx, n_ch_drop;

static void sched(ev_t e)
{
    if (nq < MAXEV) Q[nq++] = e;
}

static void apply(int who, legua_actions *a)
{
    uint8_t i;
    legua_mode m = N[who].ep.mode;
    for (i = 0; i < a->n; i++) {
        legua_action *x = &a->a[i];
        if (x->kind == LEGUA_ACT_TX) {
            ev_t e;
            uint32_t toa_ms = (legua_toa_us(&m, x->u.tx.len) + 999u) / 1000u;
            int drop = (test_rand32(&chan) % 100u) < loss_pct;
            n_ch_tx++;
            memset(&e, 0, sizeof e);
            e.t = now + toa_ms; e.to = who; e.txdone_for = 1;                     /* TX_DONE no remetente */
            e.len = x->u.tx.len; memcpy(e.bytes, x->u.tx.bytes, e.len);
            sched(e);
            if (drop) { n_ch_drop++; continue; }
            e.to = 1 - who; e.txdone_for = 0;
            sched(e);
        } else if (x->kind == LEGUA_ACT_DELIVER) {
            N[who].delivered[x->u.deliver.seq] = 1;
            N[who].delivered_n++;
            if (x->u.deliver.payload[0] != (uint8_t)(x->u.deliver.seq ^ 0x5A)) {
                printf("FALHA payload corrompido seq=%u\n", x->u.deliver.seq);
                exit(1);
            }
        } else if (x->kind == LEGUA_ACT_PERSIST) {
            N[who].persist_n++;
        }
    }
}

static int pop_next(uint32_t *tmax, ev_t *out)
{
    int i, best = -1;
    for (i = 0; i < nq; i++)
        if (Q[i].t <= *tmax && (best < 0 || Q[i].t < Q[best].t)) best = i;
    if (best < 0) return 0;
    *out = Q[best];
    Q[best] = Q[--nq];
    return 1;
}

/* Avança o tempo virtual até t_end processando eventos e prazos dos dois nós. */
static void run_until(uint32_t t_end)
{
    for (;;) {
        uint32_t t_next = t_end, d;
        ev_t e;
        int i, have_ev = 0;
        for (i = 0; i < nq; i++) if (Q[i].t < t_next) t_next = Q[i].t;
        for (i = 0; i < 2; i++)
            if (legua_next_deadline(&N[i].ep, &d) && (int32_t)(d - t_next) < 0 && (int32_t)(d - now) >= 0) t_next = d;
        if ((int32_t)(t_next - now) > 0) now = t_next;
        while (pop_next(&now, &e)) {
            legua_actions a; a.n = 0; have_ev = 1;
            if (e.txdone_for) legua_on_tx_done(&N[e.to].ep, e.bytes, e.len, now, &a);
            else legua_on_rx(&N[e.to].ep, e.bytes, e.len, now, &a);
            apply(e.to, &a);
        }
        for (i = 0; i < 2; i++) {
            legua_actions a; a.n = 0;
            legua_on_timer(&N[i].ep, now, &a);
            if (a.n) { apply(i, &a); have_ev = 1; }
        }
        if (now >= t_end && !have_ev) break;
        if (now >= t_end) { int pending = 0; for (i = 0; i < nq; i++) if (Q[i].t <= now) pending = 1; if (!pending) break; }
    }
}

static int setup(uint32_t seed, unsigned loss, uint8_t retries)
{
    static const legua_mode base = {10, 125, 1, 1};
    legua_config c;
    legua_actions a;
    uint8_t mid;
    int i;
    memset(N, 0, sizeof N); nq = 0; now = 1000; n_ch_tx = n_ch_drop = 0;
    chan.s = seed * 2654435761u + 7u; loss_pct = loss;
    legua_mode_pack(&base, &mid);
    for (i = 0; i < 2; i++) {
        N[i].env = test_env(&N[i].rng, seed + 100u * (unsigned)(i + 1));
        memset(&c, 0, sizeof c);
        c.id = (uint16_t)(i + 1); c.peer = (uint16_t)(2 - i); c.mode_id = mid; c.retries = retries;
        if (legua_init(&N[i].ep, &c, &N[i].env, &a) < 0) return -1;
    }
    return 0;
}

static int fails;
#define CHECK(c, msg) do { if (!(c)) { printf("FALHA: %s\n", msg); fails++; } } while (0)

static void traffic(int n_pkts, uint32_t gap_ms)
{
    int k;
    for (k = 0; k < n_pkts; k++) {
        legua_actions a; uint8_t pl[LEGUA_DATA_PAYLOAD];
        uint8_t seq_next;
        a.n = 0;
        seq_next = (uint8_t)(N[0].ep.seq + 1u);
        memset(pl, 0, sizeof pl); pl[0] = (uint8_t)(seq_next ^ 0x5A);
        legua_on_app(&N[0].ep, pl, sizeof pl, now, &a);
        apply(0, &a);
        run_until(now + gap_ms);
    }
    run_until(now + 20000u);
}

int main(void)
{
    /* 1) canal sem perda: tudo entregue e confirmado, sem retransmissão */
    CHECK(setup(1, 0, 3) == 0, "setup 0%");
    traffic(100, 5000);
    printf("sem perda: entregues=%u acked=%u tx=%u perdidos=%u dup=%u\n", (unsigned)N[1].ep.n_delivered,
           (unsigned)N[0].ep.n_acked, (unsigned)N[0].ep.n_tx, (unsigned)N[0].ep.n_lost, (unsigned)N[1].ep.n_dup);
    CHECK(N[1].ep.n_delivered == 100 && N[0].ep.n_acked == 100, "100 pacotes entregues e confirmados");
    CHECK(N[0].ep.n_tx == 100 && N[1].ep.n_dup == 0 && N[0].ep.n_lost == 0, "sem retransmissão no canal limpo");
    CHECK(N[0].persist_n >= 1, "contador cruzou um bloco e pediu persistência");

    /* 2) perda de 30% por quadro: retransmite, deduplica, entrega quase tudo */
    CHECK(setup(2, 30, 3) == 0, "setup 30%");
    traffic(200, 5000);
    printf("perda 30%%: entregues=%u acked=%u tx=%u perdidos=%u dup=%u (canal: %u tx, %u perdidos)\n",
           (unsigned)N[1].ep.n_delivered, (unsigned)N[0].ep.n_acked, (unsigned)N[0].ep.n_tx,
           (unsigned)N[0].ep.n_lost, (unsigned)N[1].ep.n_dup, (unsigned)n_ch_tx, (unsigned)n_ch_drop);
    CHECK(N[1].ep.n_delivered >= 180, "perda 30%: entrega >= 90%");
    CHECK(N[1].ep.n_delivered + N[0].ep.n_lost >= 200 && N[1].ep.n_delivered <= 200, "entregues + desistidos cobrem tudo, sem entrega dupla");
    CHECK(N[1].ep.n_dup > 0, "perda de ACK gerou duplicata detectada");

    /* 3) segurança: replay, MIC adulterado e destino errado */
    CHECK(setup(3, 0, 3) == 0, "setup segurança");
    traffic(3, 5000);
    {
        legua_actions a; uint8_t pl[LEGUA_DATA_PAYLOAD]; uint8_t raw[LEGUA_FRAME_MAX];
        uint32_t del, rej;
        a.n = 0; memset(pl, 0, sizeof pl);
        pl[0] = (uint8_t)((uint8_t)(N[0].ep.seq + 1u) ^ 0x5A);
        legua_on_app(&N[0].ep, pl, sizeof pl, now, &a);
        /* pega o quadro DATA gerado e entrega duas vezes ao receptor */
        CHECK(a.n >= 1 && a.a[a.n - 1].kind == LEGUA_ACT_TX, "DATA gerado");
        memcpy(raw, a.a[a.n - 1].u.tx.bytes, a.a[a.n - 1].u.tx.len);
        del = N[1].ep.n_delivered; rej = N[1].ep.n_rej;
        { legua_actions b; b.n = 0; legua_on_rx(&N[1].ep, raw, LEGUA_LEN_DATA, now, &b); }
        CHECK(N[1].ep.n_delivered == del + 1, "primeira entrega aceita");
        { legua_actions b; b.n = 0; legua_on_rx(&N[1].ep, raw, LEGUA_LEN_DATA, now, &b); }
        CHECK(N[1].ep.n_delivered == del + 1 && N[1].ep.n_rej == rej + 1, "replay rejeitado");
        /* quadro novo com MIC adulterado */
        raw[LEGUA_LEN_DATA - 1] ^= 0x01;
        raw[7] = (uint8_t)(raw[7] + 1u);                      /* contador à frente, MIC não confere */
        { legua_actions b; b.n = 0; legua_on_rx(&N[1].ep, raw, LEGUA_LEN_DATA, now, &b);
          CHECK(N[1].ep.n_rej == rej + 2 && N[1].ep.n_delivered == del + 1, "MIC inválido rejeitado"); }
        /* lixo e tamanho errado */
        { legua_actions b; uint8_t junk[5] = {1, 2, 3, 4, 5}; b.n = 0;
          legua_on_rx(&N[1].ep, junk, sizeof junk, now, &b);
          CHECK(N[1].ep.n_rej == rej + 3, "quadro malformado rejeitado"); }
    }
    if (fails) { printf("sim: %d falhas\n", fails); return 1; }
    puts("sim: ok");
    return 0;
}
