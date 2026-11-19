"""Estimador analítico de enlace (referência do `site/estimator.js`).

Responde "o que esperar neste setup?" sem rodar o simulador de eventos: usa o mesmo canal (perda de
percurso, sombreamento estático e temporal, eventos de obstrução e chuva, desvanecimento de Rice), a
mesma curva de demodulação e a mesma corrente de TX da suíte, mas integra em vez de sortear (quadratura de
Gauss-Hermite, determinística). Não modela colisões entre os dois nós, CAD/LBT, salto sincronizado nem a
negociação de modo: é a camada de enlace de um modo fixo com DATA/ACK e retransmissão.

Números são estimativas de modelo com parâmetros estimados (docs/09); servem para comparar e dimensionar.
"""
import math

from ..core.channel_static import ENVS, ANT_GAIN_DBI, CABLE_LOSS_DB, EXT_TOA_S, CAPTURE_P, pathloss
from ..core.radio import (SNR_THR, CR_GAIN_DB, PER_OFFSET_DB, PER_SLOPE_DB, NF_DB, VCC, i_tx_ma,
                          toa_s, DWELL_MAX_S)

# Gauss-Hermite de 8 pontos para ∫ e^{-x²} f(x) dx
GH8_X = (0.381186990207322, 1.157193712446780, 1.981656756695843, 2.930637420257244)
GH8_W = (0.661147012558241, 0.207802325814892, 0.0170779830074135, 0.000199604072211367)
_NODES = [(-x, w) for x, w in zip(GH8_X[::-1], GH8_W[::-1])] + [(x, w) for x, w in zip(GH8_X, GH8_W)]
SQRT2, SQRTPI = math.sqrt(2.0), math.sqrt(math.pi)
# nós para uma normal padrão: z = x*sqrt(2), peso = w/sqrt(pi)
NORM = [(x * SQRT2, w / SQRTPI) for x, w in _NODES]

ACK_BYTES = 14
DATA_BYTES = 24
BACKOFF_MEDIO_S = 1.15          # retransmissão após recuo uniforme em [0,3; 2,0] s


def noise_dbm(bw_khz, rise_db=0.0):
    return -174.0 + 10 * math.log10(bw_khz * 1e3) + NF_DB + rise_db


def p_demod(snr_db, sf):
    x = (snr_db - SNR_THR[sf] - PER_OFFSET_DB) / PER_SLOPE_DB
    if x > 30:
        return 1.0
    if x < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def p_ext_ok(env, toa, load, cr):
    g = env["G_ext"] * load
    p_hit = 1 - math.exp(-g * (toa + EXT_TOA_S))
    cap = CAPTURE_P + 0.08 * (cr - 1)
    return 1 - p_hit * (1 - cap)


def _fast_fades_db(k_db):
    """Potência do desvanecimento de Rice (dB) em grade 8x8 de Gauss-Hermite, com pesos."""
    K = 10 ** (k_db / 10)
    los, sc = math.sqrt(K / (K + 1)), math.sqrt(1 / (2 * (K + 1)))
    out = []
    for a, wa in NORM:
        for b, wb in NORM:
            re, im = los + sc * a, sc * b
            out.append((10 * math.log10(max(re * re + im * im, 1e-12)), wa * wb))
    return out


def _slow_states(env):
    """Mistura de estados lentos: (perda extra dB, peso) por eventos de obstrução e chuva."""
    states = [(0.0, 1.0)]
    for rate, (lo, hi), dur in ((env["obstr_rate_h"], env["obstr_db"], env["obstr_dur_s"]),
                                (env["rain_rate_h"], env["rain_db"], env["rain_dur_s"])):
        occ = min(1.0, rate * dur / 3600.0)
        if occ <= 0:
            continue
        depth = 0.5 * (lo + hi)
        states = [(e, w * (1 - occ)) for e, w in states] + [(e + depth, w * occ) for e, w in states]
    return states


def _p_pkt(env, mode, rx_dbm, nbytes, fades, load):
    """P(pacote sai) dado o nível lento recebido: integra o desvanecimento rápido."""
    noise = noise_dbm(mode["bw"], env["noise_rise"])
    toa = toa_s(mode["sf"], mode["bw"], nbytes, mode["cr"])
    ext = p_ext_ok(env, toa, load, mode["cr"])
    cg = CR_GAIN_DB[mode["cr"]]
    return ext * sum(w * p_demod(rx_dbm + f - noise + cg, mode["sf"]) for f, w in fades)


def _link_stats(env, mode, p_dbm, rx_static, retries, fades, states, load, data_b, ack_b):
    """Médias sobre sombreamento temporal e eventos, dado o sombreamento estático do enlace."""
    toa_d = toa_s(mode["sf"], mode["bw"], data_b, mode["cr"])
    toa_a = toa_s(mode["sf"], mode["bw"], ack_b, mode["cr"])
    deadline = toa_a + (0.45 if mode["fhss"] else 0.05) + 0.15
    r = retries
    acc = dict(entregue=0.0, confirmado=0.0, tentativas=0.0, acks=0.0, lat_num=0.0)
    for z, wt in NORM:
        for extra, we in states:
            w = wt * we
            slow = rx_static - env["sigma_t"] * z - extra
            pd = _p_pkt(env, mode, slow, data_b, fades, load)
            pa = _p_pkt(env, mode, slow, ack_b, fades, load)
            s = pd * pa
            entregue = 1 - (1 - pd) ** (r + 1)
            att = sum((1 - s) ** k for k in range(r + 1))
            acks = pd * att
            if entregue > 1e-12:
                ek = sum(k * (1 - pd) ** k * pd for k in range(r + 1)) / entregue
            else:
                ek = 0.0
            lat = toa_d + ek * (toa_d + deadline + BACKOFF_MEDIO_S)
            acc["entregue"] += w * entregue
            acc["confirmado"] += w * (1 - (1 - s) ** (r + 1))
            acc["tentativas"] += w * att
            acc["acks"] += w * acks
            acc["lat_num"] += w * entregue * lat
    e_pkt = VCC * i_tx_ma(p_dbm) * (acc["tentativas"] * toa_d + acc["acks"] * toa_a)
    return {"entregue": acc["entregue"], "confirmado": acc["confirmado"], "tentativas": acc["tentativas"],
            "energia_mj_pacote": e_pkt,
            "energia_mj_entregue": e_pkt / acc["entregue"] if acc["entregue"] > 1e-9 else None,
            "latencia_s": acc["lat_num"] / acc["entregue"] if acc["entregue"] > 1e-9 else None,
            "airtime_s_pacote": acc["tentativas"] * toa_d + acc["acks"] * toa_a}


def estimate(env_id, d_km, sf, bw, cr, p_dbm, fhss, retries=3, interval_s=60.0, offset_db=0.0,
             load=1.0, data_b=DATA_BYTES, ack_b=ACK_BYTES):
    """Estimativa para um modo fixo em um enlace. Devolve dict (ver chaves)."""
    env = ENVS[env_id]
    mode = dict(sf=sf, bw=bw, cr=cr, fhss=bool(fhss))
    fades = _fast_fades_db(env["K_db"])
    states = _slow_states(env)
    gain_med = -pathloss(env, d_km) + 2 * (ANT_GAIN_DBI - CABLE_LOSS_DB) + offset_db - 0.5 * env["diurnal_db"]
    rx_med = p_dbm + gain_med
    noise = noise_dbm(bw, env["noise_rise"])
    sens = noise + SNR_THR[sf] + PER_OFFSET_DB - CR_GAIN_DB[cr]
    toa_d = toa_s(sf, bw, data_b, cr)
    toa_a = toa_s(sf, bw, ack_b, cr)
    cenarios = []
    for sig in (-1.0, 0.0, 1.0, 2.0):          # sombreamento estático do enlace, em desvios-padrão de perda
        st = _link_stats(env, mode, p_dbm, rx_med - sig * env["sigma_static"], retries, fades, states, load,
                         data_b, ack_b)
        st["sigmas"] = sig
        cenarios.append(st)
    media = None
    acc = None
    for z, w in NORM:                            # média sobre enlaces (sombreamento estático sorteado)
        st = _link_stats(env, mode, p_dbm, rx_med - z * env["sigma_static"], retries, fades, states, load,
                         data_b, ack_b)
        if acc is None:
            acc = {k: 0.0 for k in ("entregue", "confirmado", "tentativas", "energia_mj_pacote", "airtime_s_pacote")}
        for k in acc:
            acc[k] += w * st[k]
    media = acc
    pkts_h = 3600.0 / interval_s if interval_s > 0 else 0.0
    ref = cenarios[1]
    return {
        "toa_dados_ms": 1000 * toa_d, "toa_ack_ms": 1000 * toa_a,
        "ruido_dbm": noise, "sens_dbm": sens, "rx_tipico_dbm": rx_med, "margem_db": rx_med - sens,
        "dwell_ok": (not fhss) or toa_d <= DWELL_MAX_S,
        "cenarios": cenarios, "media_enlaces": media,
        "airtime_hora_s": pkts_h * ref["airtime_s_pacote"],
        "duty_pct": 100.0 * pkts_h * ref["airtime_s_pacote"] / 3600.0,
        "energia_dia_j": 24 * pkts_h * ref["energia_mj_pacote"] / 1000.0,
    }


def range_km(env_id, sf, bw, cr, p_dbm, fhss, target=0.90, sigmas=0.0, **kw):
    """Maior distância com entrega confirmada >= target para o enlace com sombreamento `sigmas` (bissecção)."""
    lo, hi = 0.02, 400.0
    def ok(d):
        e = estimate_one(env_id, d, sf, bw, cr, p_dbm, fhss, sigmas, **kw)
        return e["confirmado"] >= target
    if not ok(lo):
        return None
    if ok(hi):
        return hi
    for _ in range(40):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo


def estimate_one(env_id, d_km, sf, bw, cr, p_dbm, fhss, sigmas=0.0, retries=3, offset_db=0.0, load=1.0,
                 data_b=DATA_BYTES, ack_b=ACK_BYTES):
    env = ENVS[env_id]
    mode = dict(sf=sf, bw=bw, cr=cr, fhss=bool(fhss))
    rx = p_dbm - pathloss(env, d_km) + 2 * (ANT_GAIN_DBI - CABLE_LOSS_DB) + offset_db - 0.5 * env["diurnal_db"]
    return _link_stats(env, mode, p_dbm, rx - sigmas * env["sigma_static"], retries, _fast_fades_db(env["K_db"]),
                       _slow_states(env), load, data_b, ack_b)


def mode_list():
    """Modos de dados da tabela BR-2026 (mesma regra de simsuite.protocol.modes.table)."""
    out = []
    for sf in (7, 8, 9, 10):
        for cr in (1, 4):
            if toa_s(sf, 125, DATA_BYTES, cr) <= DWELL_MAX_S:
                out.append(dict(sf=sf, bw=125, cr=cr, fhss=True))
    for sf in (7, 8, 9, 10, 11):
        if toa_s(sf, 250, DATA_BYTES, 1) <= DWELL_MAX_S:
            out.append(dict(sf=sf, bw=250, cr=1, fhss=True))
    for sf in range(7, 13):
        out.append(dict(sf=sf, bw=500, cr=1, fhss=False))
    return out


def rank_modes(env_id, d_km, p_dbm, target=0.95, sigmas=0.0, **kw):
    """Modos que atingem `target` de entrega confirmada, do menor ao maior custo de energia por pacote entregue."""
    rows = []
    for m in mode_list():
        st = estimate_one(env_id, d_km, m["sf"], m["bw"], m["cr"], p_dbm, m["fhss"], sigmas, **kw)
        rows.append(dict(m, confirmado=st["confirmado"], energia_mj_entregue=st["energia_mj_entregue"],
                         latencia_s=st["latencia_s"], ok=st["confirmado"] >= target))
    good = sorted([r for r in rows if r["ok"] and r["energia_mj_entregue"] is not None],
                  key=lambda r: r["energia_mj_entregue"])
    return good, rows


def _regulatorio_br():
    """Perfil BR-2026 (nao_verificado: fonte secundária) para as calculadoras do site."""
    from ..core import regulatory as R
    b = R.BR2026
    return {"perfil": b.name, "situacao": "nao_verificado", "faixas_hz": [list(x) for x in b.bands], "p_max_dbm": b.p_max_dbm,
            "p_reduzida_dbm": b.p_reduced_dbm, "antena_max_dbi": b.antenna_max_dbi, "bw_digital_min_khz": b.digital_min_bw_khz,
            "salto": [{"bw_min_khz": h.min_bw_khz, "bw_max_khz": h.max_bw_khz, "canais_min": h.min_channels, "janela_s": h.window_s, "dwell_s": h.dwell_s} for h in b.hop_classes]}


def constantes():
    """Constantes do modelo para o site (fonte única: o JS não duplica parâmetros)."""
    from ..core.radio import _I_TX_TABLE
    return {
        "envs": {k: {kk: (list(v) if isinstance(v, tuple) else v) for kk, v in e.items()} for k, e in ENVS.items()},
        "ant_gain_dbi": ANT_GAIN_DBI, "cable_loss_db": CABLE_LOSS_DB, "ext_toa_s": EXT_TOA_S, "capture_p": CAPTURE_P,
        "snr_thr": {str(k): v for k, v in SNR_THR.items()}, "cr_gain_db": {str(k): v for k, v in CR_GAIN_DB.items()},
        "per_offset_db": PER_OFFSET_DB, "per_slope_db": PER_SLOPE_DB, "nf_db": NF_DB, "vcc": VCC,
        "i_tx_table": [list(p) for p in _I_TX_TABLE], "dwell_max_s": DWELL_MAX_S, "i_rx_ma": 4.6, "regulatorio": _regulatorio_br(),
        "data_bytes": DATA_BYTES, "ack_bytes": ACK_BYTES, "backoff_medio_s": BACKOFF_MEDIO_S,
        "gh8_x": list(GH8_X), "gh8_w": list(GH8_W),
    }
