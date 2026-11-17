/* Contrato de porte (docs/08). O núcleo não chama nada disto: o laço do porte usa estas
 * interfaces para executar as ações que o núcleo devolve e para alimentá-lo com eventos. */
#ifndef LEGUA_PORT_H
#define LEGUA_PORT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Estado em NVM. O porte grava na ação LEGUA_ACT_PERSIST e entrega ao legua_init. */
typedef struct {
    uint32_t ctr_block;        /* bloco do contador de TX (anti-replay) */
    uint32_t peer_ctr_floor;   /* maior contador do par aceito (Fase 1: gravar em NVM) */
    uint8_t  anchor_valid;     /* âncora de modo (Fase 2) */
    uint8_t  anchor_mode_id;
    uint8_t  key_id;           /* chave de TX corrente (docs/07 §6.2) */
    uint8_t  key_prev_ok;      /* rotação em curso: ainda aceita key_id - 1 */
} legua_nvm;

typedef struct {
    uint32_t (*now_ms)(void *ctx);                    /* monotônico, 32 bits, dá a volta */
    int (*nvm_load)(void *ctx, legua_nvm *out);       /* 0 ok; <0 vazio ou corrompido */
    int (*nvm_store)(void *ctx, const legua_nvm *in); /* 0 ok; gravação atômica (A/B) */
    void *ctx;
} legua_port_ops;

#ifdef __cplusplus
}
#endif
#endif
