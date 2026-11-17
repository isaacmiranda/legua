/* Légua: núcleo C99 (Fases 0 e 2). Máquina de estados pura: recebe eventos, devolve ações.
 * Sem alocação dinâmica, sem E/S, sem biblioteca de terceiros. Formato em docs/07, contratos em docs/08.
 * Espelha simsuite/protocol/endpoint.py (teste de equivalência: simsuite/tests/test_equivalencia.py). */
#ifndef LEGUA_H
#define LEGUA_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---- Formato do pacote v0 (docs/07) ---- */
#define LEGUA_VERSION      0
#define LEGUA_HDR_LEN      8
#define LEGUA_MIC_LEN      4
#define LEGUA_FRAME_MAX    24
#define LEGUA_LEN_DATA     24
#define LEGUA_LEN_ACK      14
#define LEGUA_LEN_CTRL     16
#define LEGUA_DATA_PAYLOAD 9
#define LEGUA_BROADCAST    0xFFFFu
#define LEGUA_KEY_LEN      16

enum legua_type {
    LEGUA_T_HELLO = 1, LEGUA_T_DATA = 2, LEGUA_T_ACK = 3,
    LEGUA_T_PROPOSE = 4, LEGUA_T_VOTE = 5, LEGUA_T_COMMIT = 6
};

#define LEGUA_F_ACKREQ 0x01u
#define LEGUA_F_FRAG   0x02u

typedef struct {
    uint8_t  type;
    uint8_t  flags;
    uint16_t src;
    uint16_t dst;
    uint16_t ctr16;                 /* 16 bits baixos do contador */
    uint8_t  body_len;
    uint8_t  body[12];
} legua_frame;

/* Modo de rádio. O byte de modo (mode_id) é SF-5 (3b) | BW (2b) | CR-1 (2b) | FHSS (1b). */
typedef struct {
    uint8_t  sf;
    uint16_t bw_khz;                /* 125, 250 ou 500 */
    uint8_t  cr;                    /* 1..4 = 4/5..4/8 */
    uint8_t  fhss;
} legua_mode;

int legua_mode_pack(const legua_mode *m, uint8_t *id);          /* 0 ok, <0 fora do formato */
int legua_mode_unpack(uint8_t id, legua_mode *m);

/* Tempo no ar em microssegundos (AN1200.13; preâmbulo 8, cabeçalho explícito, CRC ligado). */
uint32_t legua_toa_us(const legua_mode *m, unsigned nbytes);

/* ---- Cripto injetada pelo porte (sem biblioteca de terceiros no núcleo) ----
 * mic() calcula o MIC de 32 bits sobre data[0..len) (cabeçalho+corpo) para a chave key_id, origem src e
 * contador completo ctr32, e o grava em *out. Devolve 0, ou <0 se não há chave para key_id (o quadro é
 * descartado na recepção e não sai na transmissão). Algoritmo v0: AES-128-CMAC truncado a 4 B (docs/07 §6);
 * implementação de referência em legua/mic_cmac.h (legua_keyring_mic). */
typedef struct {
    int (*mic)(void *ctx, uint8_t key_id, uint16_t src, uint32_t ctr32,
               const uint8_t *data, size_t len, uint32_t *out);
    uint32_t (*rand32)(void *ctx);  /* aleatório para recuo de retransmissão */
    void *ctx;
} legua_env;

/* ---- Codec ---- */
int legua_frame_len(uint8_t type);                              /* tamanho total ou -1 */
int legua_frame_encode(const legua_frame *f, uint32_t ctr32, uint8_t key_id,
                       const legua_env *env, uint8_t *out);     /* tamanho ou <0 (formato ou sem chave) */
/* Decodifica e valida versão, tipo, tamanho e flags reservadas. Não confere MIC. */
int legua_frame_decode(const uint8_t *raw, size_t len, legua_frame *f);
/* Confere o MIC com o contador completo já reconstruído. 1 = válido; 0 = inválido ou sem chave. */
int legua_frame_verify(const uint8_t *raw, size_t len, uint32_t ctr32,
                       const legua_env *env);
/* Reconstrói ctr32 a partir de ctr16 e do último aceito. 0 se repetido ou antigo. */
int legua_ctr_reconstruct(uint32_t last32, uint16_t ctr16, uint32_t *out);

/* ---- Ações devolvidas ao laço do porte ---- */
typedef enum {
    LEGUA_ACT_TX,        /* transmitir tx.bytes[0..len) no modo tx.mode_id com tx.power_dbm */
    LEGUA_ACT_RX,        /* configurar recepção no modo mode_id */
    LEGUA_ACT_PERSIST,   /* gravar em NVM o registro inteiro: âncora, bloco do contador, piso do par */
    LEGUA_ACT_DELIVER,   /* entregar payload recebido à aplicação */
    LEGUA_ACT_LOG        /* telemetria: code, arg */
} legua_act_kind;

enum legua_log {
    LEGUA_LOG_REJ_MIC = 1, LEGUA_LOG_REJ_REPLAY, LEGUA_LOG_REJ_FORMAT, LEGUA_LOG_DUP_DATA,
    LEGUA_LOG_RETRY, LEGUA_LOG_GIVEUP, LEGUA_LOG_QUEUE_DROP,
    LEGUA_LOG_MODE,          /* arg = mode_id | estado << 8 | motivo << 16 */
    LEGUA_LOG_PROPOSE,       /* arg = mode_id do candidato */
    LEGUA_LOG_NEG_FAIL,
    LEGUA_LOG_VALIDATED,     /* arg = mode_id */
    LEGUA_LOG_COMMIT_RX,
    LEGUA_LOG_ALARM          /* rollbacks repetidos sem queda de SNR (possível jamming) */
};

enum legua_state {
    LEGUA_S_BASE, LEGUA_S_DATA, LEGUA_S_NEG, LEGUA_S_PEND, LEGUA_S_VALID, LEGUA_S_RECOV
};

enum legua_reason {
    LEGUA_R_BOOT, LEGUA_R_SWITCH, LEGUA_R_FAILS, LEGUA_R_SILENCE, LEGUA_R_SILENCE_REC,
    LEGUA_R_VALID_FAILED, LEGUA_R_VALID_EXPIRED
};

typedef struct {
    legua_act_kind kind;
    union {
        struct { uint8_t bytes[LEGUA_FRAME_MAX]; uint8_t len; uint8_t mode_id; int8_t power_dbm; } tx;
        struct { uint8_t mode_id; } rx;
        struct { uint8_t anchor_valid; uint8_t anchor_mode_id; uint32_t ctr_block; uint32_t peer_ctr_floor; } persist;
        struct { uint8_t seq; uint8_t payload[LEGUA_DATA_PAYLOAD]; } deliver;
        struct { uint8_t code; uint32_t arg; } log;
    } u;
} legua_action;

#define LEGUA_MAX_ACTIONS 12
typedef struct {
    legua_action a[LEGUA_MAX_ACTIONS];
    uint8_t n;
    uint8_t overflow;               /* 1 se alguma ação foi descartada (não deve acontecer) */
} legua_actions;

/* Informação de recepção medida pelo rádio, em décimos de dB. */
typedef struct { int16_t rssi_x10; int16_t snr_x10; } legua_rxinfo;

/* ---- Tabela de modos (fornecida pelo integrador; ordenada do mais rápido ao mais lento) ----
 * Ex.: core/profiles/br2026.h (gerado por tools/gen_modetab.py a partir do simulador). */
#define LEGUA_MAX_MODES 40
typedef struct {
    uint8_t  mode_id;               /* byte de modo (docs/07) */
    int8_t   cap_dbm;               /* teto de potência do modo (regulação) */
    float    sens_dbm;              /* sensibilidade com o piso de ruído de referência */
    uint32_t toa_data_us;           /* tempo no ar do DATA (LEGUA_LEN_DATA) */
} legua_mode_entry;

/* Parâmetros do protocolo: espelham `Config` de simsuite/protocol/endpoint.py (tempos em ms). */
typedef struct {
    float    margin_target, margin_up, ladder_step, max_budget_jump, ema_a, v_freeze, snr_std_freeze;
    float    fade_k;                /* margem de aceleração += fade_k x desvio do SNR (0 = desligado; sintonia F7) */
    uint8_t  fade_window;           /* amostras de SNR para o desvio (até LEGUA_SNR_WIN) */
    uint32_t cooldown_up_ms, cooldown_back_ms, hb_interval_ms, t_silence_ms, t_recovery_ms, t_valid_ms,
             vote_timeout_ms, instant_delay_ms, hello_interval_ms, neg_backoff0_ms, neg_backoff_max_ms;
    uint8_t  n_up, fail_streak_degrade, retries, k_valid, f_valid, rollback_alarm;
    uint8_t  ladder_recovery_only;  /* 0 = degraus de ladder_step dB; 1 = só o modo de recuperação */
    uint8_t  persist_at_commit;     /* ablação: grava a âncora no COMMIT em vez de na validação */
    uint8_t  silence_descent;       /* ablação: 0 desliga a descida por silêncio */
    uint8_t  validation;            /* ablação: 0 desliga a janela de validação */
    uint8_t  mobile;                /* perfil móvel: congela a aceleração em movimento */
    uint8_t  power_control;
} legua_params;

void legua_params_default(legua_params *p);

/* Perfis nomeados (resultado da sintonia F7, docs/06 §F7); espelham simsuite/protocol/perfis.py. */
enum legua_profile { LEGUA_PROFILE_DEFAULT = 0, LEGUA_PROFILE_STABLE = 1, LEGUA_PROFILE_CAUTIOUS = 2 };
int legua_params_profile(legua_params *p, int profile);      /* 0 ou <0 se o perfil não existe */

/* ---- Endpoint (enlace P2P com negociação de modo) ---- */
#ifndef LEGUA_QUEUE_LEN
#define LEGUA_QUEUE_LEN 10
#endif
#define LEGUA_CTR_BLOCK 64u
#define LEGUA_NO_MODE   0xFFu

typedef struct {
    uint16_t id, peer;
    uint8_t  key_id;
    const legua_mode_entry *modes;  /* tabela do integrador (deve sobreviver ao endpoint) */
    uint8_t  n_modes;
    uint8_t  base_mode_id, rec_mode_id;
    int8_t   cap_dbm;               /* teto de potência do nó (min com o do modo) */
    float    noise_rise_db;         /* elevação do piso de ruído (interferência), 0 se limpo */
    /* registro lido da NVM (zeros se o nó é novo) */
    uint8_t  anchor_valid, anchor_mode_id;
    uint32_t ctr_block_nvm;         /* último bloco de contador de TX gravado */
    uint32_t peer_ctr_floor;        /* piso do contador do par (múltiplo de 64) gravado */
    legua_params params;
} legua_config;

typedef struct {
    uint8_t seq;
    uint8_t hb;                     /* 1 = heartbeat (sem payload de aplicação) */
    uint8_t payload[LEGUA_DATA_PAYLOAD];
} legua_qitem;

typedef struct {
    uint32_t trocas, rollbacks, degradacoes, quedas_base, neg_ok, neg_fail, neg_recusa, desc_silencio,
             alarmes, rejeitados, tx_ctrl, entregues, gerados, perdidos, duplicados, acked, tx;
} legua_stats;

#define LEGUA_SNR_WIN 30
#define LEGUA_RB_RING 8

typedef struct {
    legua_config cfg;
    legua_mode   mode;              /* modo atual decodificado (para o tempo no ar) */
    const legua_env *env;
    uint8_t  base_i, rec_i, mode_i, prev_i, anchor_i;
    uint8_t  state, role_a, degraded, nv_dirty;
    uint32_t ctr, peer_last, peer_blk;
    uint8_t  seq;
    legua_qitem q[LEGUA_QUEUE_LEN];
    uint8_t  q_head, q_n;
    /* pacote aguardando ACK */
    uint8_t  out_valid, out_att, out_deadline_set, out_resend_set;
    uint32_t out_deadline_ms, out_resend_ms;
    /* deduplicação de DATA recebido: janela de 32 números de sequência */
    uint8_t  rx_seq_top, rx_seq_any;
    uint32_t rx_seq_map;
    /* estado do protocolo */
    int8_t   p;                     /* potência de DATA */
    uint32_t peer_heard, entered, last_change, neg_block, neg_backoff, next_hello, next_hb, freeze_until;
    uint8_t  consec_ok, fail_streak, ok_since_p;
    uint8_t  pend_active, pend_cand, pend_role_a, pend_committed, pend_inst_set;
    uint32_t pend_deadline, pend_instant;
    uint8_t  val_active, val_ok, val_fails, val_done;
    uint32_t val_t0;
    uint8_t  g_me_set, g_peer_set;
    float    g_me, g_peer;
    float    snr[LEGUA_SNR_WIN];
    uint8_t  snr_n, snr_pos;
    uint32_t rb_times[LEGUA_RB_RING];
    uint8_t  rb_n;
    uint8_t  bad_set[LEGUA_MAX_MODES];
    uint32_t bad_until[LEGUA_MAX_MODES];
    float    speed, peer_speed;
    legua_stats st;
} legua_endpoint;

/* Retorna 0 ou <0 se a configuração for inválida. Gera a ação RX inicial. */
int  legua_init(legua_endpoint *ep, const legua_config *cfg, const legua_env *env, uint32_t now_ms,
                legua_actions *acts);
void legua_on_app(legua_endpoint *ep, const uint8_t *payload, size_t len, uint32_t now_ms,
                  legua_actions *acts);
void legua_on_rx(legua_endpoint *ep, const uint8_t *raw, size_t len, const legua_rxinfo *rx,
                 uint32_t now_ms, legua_actions *acts);
/* mode_id: modo em que o quadro foi transmitido (um DATA enviado antes de uma troca de modo não arma prazo). */
void legua_on_tx_done(legua_endpoint *ep, const uint8_t *raw, size_t len, uint8_t mode_id, uint32_t now_ms,
                      legua_actions *acts);
void legua_on_timer(legua_endpoint *ep, uint32_t now_ms, legua_actions *acts);
/* Velocidade GNSS em m/s (perfil móvel). */
void legua_set_speed(legua_endpoint *ep, float speed_mps);
/* Próximo instante em que on_timer deve ser chamado; devolve 0 se nada está agendado. */
int  legua_next_deadline(const legua_endpoint *ep, uint32_t *at);

#ifdef __cplusplus
}
#endif
#endif
