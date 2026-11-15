"""Tabela de modos por perfil regulatório (decisões 1, 4, 5, 6 do doc 05).

Cada modo carrega o enquadramento (salto, digital, baixa potência), o teto de
potência, a classe de salto e o custo de tempo no ar para o quadro de dados.
"""
import math
from dataclasses import dataclass
from ..core.radio import toa_s, noise_dbm, SNR_THR, PER_OFFSET_DB, CR_GAIN_DB, i_tx_ma
from ..core.regulatory import BR2026, NO_RULE

# Tamanhos do formato v0 (docs/07; simsuite/protocol/wire.py): cabeçalho 8 + corpo + MIC 4.
DATA_BYTES = 24      # corpo 12 (parede de 24 B no SF10/125)
ACK_BYTES = 14       # corpo 2 (seq + ganho); era 12 antes da especificação v0
CTRL_BYTES = 20      # corpo 8, com bytes reservados (candidato a compactar)
HW_MAX_DBM = 28.0    # Heltec V4 (FEM); medido 25,6 dBm para 27 configurados [SEC]


@dataclass(frozen=True)
class Mode:
    name: str
    sf: int
    bw: float
    cr: int
    fhss: bool
    cap: float
    frame: str
    n_hop: int = 0

    def sens(self, noise_rise=0.0):
        return noise_dbm(self.bw, noise_rise) + SNR_THR[self.sf] + PER_OFFSET_DB - CR_GAIN_DB[self.cr]

    def toa(self, nbytes):
        return toa_s(self.sf, self.bw, nbytes, self.cr)

    def budget(self, noise_rise=0.0):
        return self.cap - self.sens(noise_rise)

    def energy_mj(self, p_dbm, nbytes=DATA_BYTES):
        return 3.3 * i_tx_ma(p_dbm) * self.toa(nbytes)


def _m(sf, bw, cr, fhss, cap, frame, n_hop=0):
    crs = "" if cr == 1 else f"/CR4{cr + 4}"
    return Mode(f"SF{sf}/{int(bw)}{crs}{'/FH' if fhss else ''}", sf, bw, cr, fhss, cap, frame, n_hop)


def table(profile_name="BR-2026"):
    """Devolve (modos de dados, modo base, modo de recuperação)."""
    if profile_name == "BR-2026":
        modes = []
        for sf in (7, 8, 9, 10):
            for cr in (1, 4):
                m = _m(sf, 125, cr, True, HW_MAX_DBM, "salto", 35)
                if m.toa(DATA_BYTES) <= 0.4:
                    modes.append(m)
        for sf in (7, 8, 9, 10, 11):
            m = _m(sf, 250, 1, True, HW_MAX_DBM, "salto", 35)
            if m.toa(DATA_BYTES) <= 0.4:
                modes.append(m)
        cap500 = min(HW_MAX_DBM, BR2026.digital_cap_dbm(500))
        for sf in range(7, 13):
            modes.append(_m(sf, 500, 1, False, cap500, "digital"))
        base = _m(10, 125, 1, True, HW_MAX_DBM, "salto", 35)
        rec = _m(11, 250, 1, True, HW_MAX_DBM, "salto", 35)
    else:  # sem regra: teto técnico, inclui SF11/12 em 125 kHz
        modes = [_m(sf, bw, 1, False, HW_MAX_DBM, "sem regra")
                 for bw in (125, 250, 500) for sf in range(7, 13)]
        base = _m(12, 125, 1, False, HW_MAX_DBM, "sem regra")
        rec = _m(11, 125, 1, False, HW_MAX_DBM, "sem regra")
    # ordena do mais rápido (menor tempo no ar) ao mais lento
    modes.sort(key=lambda m: (m.toa(DATA_BYTES), -m.budget()))
    return modes, base, rec


def by_name(modes, name):
    for m in modes:
        if m.name == name:
            return m
    raise KeyError(name)
