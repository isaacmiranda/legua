/* Légua: núcleo C99 (Fase 0). Máquina de estados pura: recebe eventos, devolve ações.
 * Sem alocação dinâmica, sem E/S, sem biblioteca de terceiros. Formato em docs/07. */
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
#define LEGUA_LEN_CTRL     20
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
 * mic() devolve o MIC de 32 bits sobre data[0..len) (cabeçalho+corpo) para a chave key_id,
 * origem src e contador completo ctr32. Em produto: AES-CMAC/CCM truncado a 4 B. */
typedef struct {
    uint32_t (*mic)(void *ctx, uint8_t key_id, uint16_t src, uint32_t ctr32,
                    const uint8_t *data, size_t len);
    uint32_t (*rand32)(void *ctx);  /* aleatório para recuo de retransmissão */
    void *ctx;
} legua_env;

/* ---- Codec ---- */
int legua_frame_len(uint8_t type);                              /* tamanho total ou -1 */
int legua_frame_encode(const legua_frame *f, uint32_t ctr32, uint8_t key_id,
                       const legua_env *env, uint8_t *out);     /* tamanho ou <0 */
/* Decodifica e valida versão, tipo, tamanho e flags reservadas. Não confere MIC. */
int legua_frame_decode(const uint8_t *raw, size_t len, legua_frame *f);
/* Confere o MIC com o contador completo já reconstruído. 1 = válido. */
int legua_frame_verify(const uint8_t *raw, size_t len, uint32_t ctr32,
                       const legua_env *env);
/* Reconstrói ctr32 a partir de ctr16 e do último aceito. 0 se repetido ou antigo. */
int legua_ctr_reconstruct(uint32_t last32, uint16_t ctr16, uint32_t *out);

/* ---- Ações devolvidas ao laço do porte ---- */
typedef enum {
    LEGUA_ACT_TX,        /* transmitir tx.bytes[0..len) no modo atual */
    LEGUA_ACT_RX,        /* configurar recepção no modo mode_id */
    LEGUA_ACT_PERSIST,   /* gravar em NVM: ctr_block */
    LEGUA_ACT_DELIVER,   /* entregar payload recebido à aplicação */
    LEGUA_ACT_LOG        /* telemetria: code, arg */
} legua_act_kind;

enum legua_log {
    LEGUA_LOG_REJ_MIC = 1, LEGUA_LOG_REJ_REPLAY, LEGUA_LOG_REJ_FORMAT, LEGUA_LOG_DUP_DATA,
    LEGUA_LOG_RETRY, LEGUA_LOG_GIVEUP, LEGUA_LOG_QUEUE_DROP
};

typedef struct {
    legua_act_kind kind;
    union {
        struct { uint8_t bytes[LEGUA_FRAME_MAX]; uint8_t len; } tx;
        struct { uint8_t mode_id; } rx;
        struct { uint32_t ctr_block; } persist;
        struct { uint8_t seq; uint8_t payload[LEGUA_DATA_PAYLOAD]; } deliver;
        struct { uint8_t code; uint32_t arg; } log;
    } u;
} legua_action;

#define LEGUA_MAX_ACTIONS 6
typedef struct {
    legua_action a[LEGUA_MAX_ACTIONS];
    uint8_t n;
} legua_actions;

/* ---- Endpoint (enlace P2P, modo fixo: DATA/ACK com retransmissão) ---- */
#ifndef LEGUA_QUEUE_LEN
#define LEGUA_QUEUE_LEN 8
#endif
#define LEGUA_CTR_BLOCK 64u

typedef struct {
    uint16_t id, peer;
    uint8_t  mode_id;
    uint8_t  key_id;
    uint8_t  retries;               /* retransmissões após a primeira tentativa */
    uint32_t ctr_block_nvm;         /* último bloco de contador gravado em NVM (0 se novo) */
    uint32_t peer_ctr_floor;        /* maior contador do par já visto (NVM); 0 se novo */
} legua_config;

typedef struct {
    uint8_t seq;
    uint8_t payload[LEGUA_DATA_PAYLOAD];
} legua_qitem;

typedef struct {
    legua_config cfg;
    legua_mode   mode;
    const legua_env *env;
    uint32_t ctr;                   /* contador de TX */
    uint32_t peer_last;             /* último contador aceito do par */
    uint8_t  seq;                   /* último número de sequência gerado */
    legua_qitem q[LEGUA_QUEUE_LEN];
    uint8_t  q_head, q_n;
    /* pacote aguardando ACK */
    uint8_t  out_valid, out_att;
    uint8_t  out_deadline_set, out_resend_set;
    uint32_t out_deadline_ms, out_resend_ms;
    /* deduplicação de DATA recebido: janela de 32 números de sequência */
    uint8_t  rx_seq_top, rx_seq_any;
    uint32_t rx_seq_map;
    /* contadores */
    uint32_t n_delivered, n_dup, n_rej, n_lost, n_acked, n_tx;
} legua_endpoint;

/* Retorna 0 ou <0 se a configuração for inválida. */
int  legua_init(legua_endpoint *ep, const legua_config *cfg, const legua_env *env,
                legua_actions *acts);
void legua_on_app(legua_endpoint *ep, const uint8_t *payload, size_t len, uint32_t now_ms,
                  legua_actions *acts);
void legua_on_rx(legua_endpoint *ep, const uint8_t *raw, size_t len, uint32_t now_ms,
                 legua_actions *acts);
void legua_on_tx_done(legua_endpoint *ep, const uint8_t *raw, size_t len, uint32_t now_ms,
                      legua_actions *acts);
void legua_on_timer(legua_endpoint *ep, uint32_t now_ms, legua_actions *acts);
/* Próximo instante em que on_timer deve ser chamado; 0 = nada agendado. Escreve em *at. */
int  legua_next_deadline(const legua_endpoint *ep, uint32_t *at);

#ifdef __cplusplus
}
#endif
#endif
