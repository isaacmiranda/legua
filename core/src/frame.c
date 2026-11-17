#include <string.h>
#include "legua/legua.h"

static const uint16_t bw_tab[3] = {125, 250, 500};

int legua_mode_pack(const legua_mode *m, uint8_t *id)
{
    unsigned bw;
    if (m->sf < 5 || m->sf > 12 || m->cr < 1 || m->cr > 4)
        return -1;
    for (bw = 0; bw < 3; bw++)
        if (bw_tab[bw] == m->bw_khz)
            break;
    if (bw == 3)
        return -1;
    *id = (uint8_t)((((unsigned)m->sf - 5u) << 5) | (bw << 3) | (((unsigned)m->cr - 1u) << 1) | (m->fhss ? 1u : 0u));
    return 0;
}

int legua_mode_unpack(uint8_t id, legua_mode *m)
{
    unsigned bw = (id >> 3) & 3u;
    if (bw > 2)
        return -1;
    m->sf = (uint8_t)(((id >> 5) & 7u) + 5u);
    m->bw_khz = bw_tab[bw];
    m->cr = (uint8_t)(((id >> 1) & 3u) + 1u);
    m->fhss = id & 1u;
    return 0;
}

int legua_frame_len(uint8_t type)
{
    switch (type) {
    case LEGUA_T_DATA: return LEGUA_LEN_DATA;
    case LEGUA_T_ACK: return LEGUA_LEN_ACK;
    case LEGUA_T_HELLO: case LEGUA_T_PROPOSE: case LEGUA_T_VOTE: case LEGUA_T_COMMIT:
        return LEGUA_LEN_CTRL;
    default: return -1;
    }
}

static void put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }
static uint16_t get16(const uint8_t *p) { return (uint16_t)((p[0] << 8) | p[1]); }

int legua_frame_encode(const legua_frame *f, uint32_t ctr32, uint8_t key_id,
                       const legua_env *env, uint8_t *out)
{
    int len = legua_frame_len(f->type);
    uint32_t mic;
    if (len < 0 || f->body_len != len - LEGUA_HDR_LEN - LEGUA_MIC_LEN || (f->flags & 0xF0u))
        return -1;
    out[0] = (uint8_t)((LEGUA_VERSION << 5) | f->type);
    out[1] = (uint8_t)((f->flags & 0x03u) | ((key_id & 3u) << 2));
    put16(out + 2, f->src);
    put16(out + 4, f->dst);
    put16(out + 6, (uint16_t)ctr32);
    memcpy(out + LEGUA_HDR_LEN, f->body, f->body_len);
    if (env->mic(env->ctx, (uint8_t)(key_id & 3u), f->src, ctr32, out, (size_t)(len - LEGUA_MIC_LEN), &mic) < 0)
        return -2;
    out[len - 4] = (uint8_t)(mic >> 24); out[len - 3] = (uint8_t)(mic >> 16);
    out[len - 2] = (uint8_t)(mic >> 8);  out[len - 1] = (uint8_t)mic;
    return len;
}

int legua_frame_decode(const uint8_t *raw, size_t len, legua_frame *f)
{
    int want;
    if (len < LEGUA_HDR_LEN + LEGUA_MIC_LEN || (raw[0] >> 5) != LEGUA_VERSION)
        return -1;
    want = legua_frame_len(raw[0] & 0x1Fu);
    if (want < 0 || (size_t)want != len || (raw[1] & 0xF0u))
        return -1;
    f->type = raw[0] & 0x1Fu;
    f->flags = raw[1];                       /* inclui o id da chave nos bits 2-3 */
    f->src = get16(raw + 2);
    f->dst = get16(raw + 4);
    f->ctr16 = get16(raw + 6);
    f->body_len = (uint8_t)(len - LEGUA_HDR_LEN - LEGUA_MIC_LEN);
    memcpy(f->body, raw + LEGUA_HDR_LEN, f->body_len);
    return 0;
}

int legua_frame_verify(const uint8_t *raw, size_t len, uint32_t ctr32, const legua_env *env)
{
    uint32_t got, want;
    if (len < LEGUA_HDR_LEN + LEGUA_MIC_LEN || (uint16_t)ctr32 != get16(raw + 6))
        return 0;
    got = ((uint32_t)raw[len - 4] << 24) | ((uint32_t)raw[len - 3] << 16) |
          ((uint32_t)raw[len - 2] << 8) | raw[len - 1];
    if (env->mic(env->ctx, (uint8_t)((raw[1] >> 2) & 3u), get16(raw + 2), ctr32, raw,
                 len - LEGUA_MIC_LEN, &want) < 0)
        return 0;
    return got == want;
}

int legua_ctr_reconstruct(uint32_t last32, uint16_t ctr16, uint32_t *out)
{
    uint16_t delta = (uint16_t)(ctr16 - (uint16_t)last32);
    if (delta == 0 || delta > 0x7FFFu)
        return 0;
    *out = last32 + delta;
    return 1;
}
