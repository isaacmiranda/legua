/* Contrato de driver de rádio (docs/08). SX1262 primeiro; SX127x só com o protocolo congelado.
 * O driver é assíncrono: tx() e rx() só iniciam; o término chega como legua_radio_event. */
#ifndef LEGUA_RADIO_H
#define LEGUA_RADIO_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { LEGUA_RE_TX_DONE, LEGUA_RE_RX_DONE, LEGUA_RE_RX_TIMEOUT, LEGUA_RE_CAD_DONE } legua_radio_event_kind;

typedef struct {
    legua_radio_event_kind kind;
    uint8_t  buf[24];
    uint8_t  len;
    int16_t  rssi_dbm10;       /* décimos de dBm */
    int16_t  snr_db10;         /* décimos de dB */
    uint8_t  cad_detected;
} legua_radio_event;

typedef struct {
    /* Configura SF/BW/CR (do byte de modo), canal e potência (dBm, já limitada pelo teto do integrador). */
    int (*configure)(void *ctx, uint8_t mode_id, uint8_t channel, int8_t power_dbm);
    int (*start_tx)(void *ctx, const uint8_t *buf, size_t len);
    int (*start_rx)(void *ctx);
    int (*start_cad)(void *ctx);
    int (*sleep)(void *ctx);
    /* Tira o próximo evento do driver; 1 = havia evento. */
    int (*poll_event)(void *ctx, legua_radio_event *ev);
    void *ctx;
} legua_radio_ops;

#ifdef __cplusplus
}
#endif
#endif
