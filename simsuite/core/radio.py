"""Modelo de rádio LoRa (SX1262 / Heltec WiFi LoRa 32 V4) da suíte de simulação.

Tudo aqui é determinístico; a aleatoriedade fica em channel.py.
Valores marcados como APROX devem ser substituídos por medições de bancada (E16).
"""
import math

# Limiar de SNR de demodulação por SF (datasheet Semtech, dB)
SNR_THR = {5: -2.5, 6: -5.0, 7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}

# Ganho de sensibilidade por taxa de código (CR 4/5..4/8). APROX: o datasheet não
# muda a sensibilidade com o CR; medições indicam ~1 dB entre 4/5 e 4/8.
CR_GAIN_DB = {1: 0.0, 2: 0.3, 3: 0.6, 4: 1.0}

# Margem prática: a falha ocorre 2-4 dB acima do limite teórico
# (Hernandez Ortiz et al., 2026, SX1262 com atenuadores). Centro da curva em +2,5 dB.
PER_OFFSET_DB = 2.5
PER_SLOPE_DB = 0.6

NF_DB = 6.0          # figura de ruído do receptor
VCC = 3.3            # V
I_RX_MA = 4.6        # SX1262 RX, DC-DC (datasheet)

# Corrente de TX do SX1262 (PA HP) por potência. APROX: interpolação de valores
# típicos do datasheet; a curva real da Heltec V4 precisa ser medida.
_I_TX_TABLE = [(-9, 18.0), (0, 24.0), (10, 38.0), (14, 45.0), (17, 90.0),
               (20, 102.0), (22, 118.0), (25, 600.0), (28, 950.0)]
# Acima de 22 dBm: Heltec V4 com FEM GC1109; pico de placa próximo de 1 A a 27 dBm
# configurados (teste publicado pela Heltec) [SEC]. Medir na bancada (B8).

DWELL_MAX_S = 0.4    # salto em frequência: ocupação máx. por canal (perfil BR, não verificado)


def i_tx_ma(p_dbm):
    t = _I_TX_TABLE
    if p_dbm <= t[0][0]:
        return t[0][1]
    for (p0, i0), (p1, i1) in zip(t, t[1:]):
        if p_dbm <= p1:
            return i0 + (i1 - i0) * (p_dbm - p0) / (p1 - p0)
    return t[-1][1]


_TOA_CACHE = {}


def toa_s(sf, bw_khz, payload_b, cr=1, preamble=8, crc=True, explicit=True):
    """Tempo no ar (AN1200.13 da Semtech; SF5/SF6 conforme o datasheet do SX126x)."""
    key = (sf, bw_khz, payload_b, cr, preamble)
    if key in _TOA_CACHE:
        return _TOA_CACHE[key]
    tsym = (2 ** sf) / (bw_khz * 1e3)
    de = 1 if tsym > 0.016 else 0
    ih = 0 if explicit else 1
    if sf >= 7:
        num = 8 * payload_b - 4 * sf + 28 + 16 * (1 if crc else 0) - 20 * ih
        nsym = 8 + max(math.ceil(num / (4 * (sf - 2 * de))) * (cr + 4), 0)
        t = (preamble + 4.25) * tsym + nsym * tsym
    else:
        num = 8 * payload_b + 16 * (1 if crc else 0) - 4 * sf + 20 * (1 - ih)
        nsym = 8 + max(math.ceil(num / (4 * sf)) * (cr + 4), 0)
        t = (preamble + 6.25) * tsym + nsym * tsym
    _TOA_CACHE[key] = t
    return t


def noise_dbm(bw_khz, noise_rise_db=0.0):
    return -174.0 + 10 * math.log10(bw_khz * 1e3) + NF_DB + noise_rise_db


def p_demod(snr_db, sf):
    """Probabilidade de demodular um pacote dado o SNR (curva logística)."""
    x = (snr_db - SNR_THR[sf] - PER_OFFSET_DB) / PER_SLOPE_DB
    if x > 30:
        return 1.0
    if x < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


class Mode:
    """Modo de rádio (SF, BW, CR). cap = potência máxima permitida a este modo
    pelo enquadramento em uso (dBm); fhss = sujeito à ocupação máxima por canal."""
    __slots__ = ("sf", "bw", "cr", "name", "fhss", "cap", "frame")

    def __init__(self, sf, bw, fhss=None, cr=1, cap=99.0, frame=""):
        self.sf, self.bw, self.cr = sf, bw, cr
        # BW 500 kHz -> enquadramento de banda larga (canal fixo); demais -> salto
        self.fhss = (bw < 500) if fhss is None else fhss
        self.cap = cap
        self.frame = frame
        bws = ("%g" % bw).replace(".", ",")
        self.name = f"SF{sf}/BW{bws}" + (f"/CR4{cr + 4}" if cr > 1 else "")

    def sens(self, noise_rise=0.0):
        """Potência mínima recebida para o centro da curva de PER (dBm)."""
        return (noise_dbm(self.bw, noise_rise) + SNR_THR[self.sf] + PER_OFFSET_DB
                - CR_GAIN_DB[self.cr])

    def toa(self, payload_b):
        return toa_s(self.sf, self.bw, payload_b, self.cr)

    def __repr__(self):
        return self.name


def fragments(mode, payload_b, overhead_b, frag_hdr_b=2, dwell_rule=True):
    """Divide o payload até cada fragmento caber na ocupação máxima por canal.
    Devolve (n_frag, bytes_por_fragmento_no_ar)."""
    n = 1
    while True:
        per = math.ceil(payload_b / n) + overhead_b + (frag_hdr_b if n > 1 else 0)
        if not (dwell_rule and mode.fhss) or mode.toa(per) <= DWELL_MAX_S or n >= 8:
            return n, per
        n += 1


# ---------------------------------------------------------------- frequência
F_CARRIER_HZ = 915e6
C_LIGHT = 299_792_458.0


def tsym_s(sf, bw_khz):
    return (2 ** sf) / (bw_khz * 1e3)


def ldro_on(sf, bw_khz):
    """LDRO automático e não desligável quando o símbolo passa de 16 ms (decisão 15)."""
    return tsym_s(sf, bw_khz) >= 0.016


def static_offset_tolerance_hz(bw_khz):
    """Desvio estático tolerado: +-25% da BW (Semtech; Ullah et al. 2024)."""
    return 0.25 * bw_khz * 1e3


def drift_tolerance_hz(sf, bw_khz):
    """Variação de frequência tolerada dentro do pacote: F = L*BW/(3*2^SF),
    L = 16 com LDRO, 1 sem (Ullah et al., IEEE OJ-COMS 2024)."""
    L = 16 if ldro_on(sf, bw_khz) else 1
    return L * bw_khz * 1e3 / (3 * 2 ** sf)


def doppler_hz(radial_speed_ms):
    return radial_speed_ms * F_CARRIER_HZ / C_LIGHT
