"""Perfis regulatórios executáveis e verificador de conformidade (cenário B11).

Perfil BR-2026 (leitura do projeto, a confirmar com OCD; ver doc 05):
  Faixas: 902-907,5 MHz e 915-928 MHz (907,5-915 excluída).
  Salto (Ato 14.448, 10.2.5, cópia secundária):
    20 dB BW < 250 kHz : >= 35 canais, <= 0,4 s por canal a cada 14 s
    20 dB BW >= 250 kHz: >= 17 canais, <= 0,4 s por canal a cada 7 s
    1 W de pico só com >= 35 canais; senão 0,25 W.
  Modulação digital (10.3): 6 dB BW >= 500 kHz, 1 W, DEP <= 8 dBm/3 kHz.
  Antena > 6 dBi: reduz a potência dB a dB (10.5).
  10.2.8.1: proibido coordenar conjuntos de salto entre transmissores distintos.
"""
import math
import random
from dataclasses import dataclass, field

BANDS_BR = [(902.0e6, 907.5e6), (915.0e6, 928.0e6)]


@dataclass
class HopClass:
    min_bw_khz: float
    max_bw_khz: float
    min_channels: int
    window_s: float
    dwell_s: float = 0.4


@dataclass
class Profile:
    name: str
    bands: list
    hop_classes: list            # lista de HopClass
    digital_min_bw_khz: float = 500.0
    p_max_dbm: float = 30.0      # 1 W conduzido
    p_reduced_dbm: float = 24.0  # 0,25 W com menos canais
    psd_dbm_3khz: float = 8.0
    antenna_max_dbi: float = 6.0
    verified: bool = False
    notes: str = ""

    def hop_class(self, bw_khz):
        for hc in self.hop_classes:
            if hc.min_bw_khz <= bw_khz < hc.max_bw_khz:
                return hc
        return None

    def digital_cap_dbm(self, bw_khz, ant_dbi=2.15):
        """Teto como modulação digital (só BW >= 500 kHz)."""
        if bw_khz < self.digital_min_bw_khz:
            return None
        psd = self.psd_dbm_3khz + 10 * math.log10(bw_khz / 3.0)
        return min(self.p_max_dbm, psd) - max(0.0, ant_dbi - self.antenna_max_dbi)

    def hop_cap_dbm(self, n_channels, ant_dbi=2.15, bw_khz=125):
        hc = self.hop_class(bw_khz)
        p = self.p_max_dbm if (hc and n_channels >= 35) else self.p_reduced_dbm
        return p - max(0.0, ant_dbi - self.antenna_max_dbi)


BR2026 = Profile(
    name="BR-2026",
    bands=BANDS_BR,
    hop_classes=[HopClass(0, 250, 35, 14.0), HopClass(250, 501, 17, 7.0)],
    notes="Ato 14.448 (10.2.5, 10.3, 10.5, 10.2.8.1) + Ato 14.158/4.746; fonte secundária; confirmar com OCD",
)

NO_RULE = Profile(name="sem-regra", bands=[(902.0e6, 928.0e6)], hop_classes=[],
                  p_max_dbm=28.0, notes="teto técnico do hardware")


def channel_plan(profile, bw_khz, guard_khz=None):
    """Lista de frequências centrais (Hz) que cabem nas faixas do perfil."""
    step = (bw_khz + (guard_khz if guard_khz is not None else 0.6 * bw_khz)) * 1e3
    half = bw_khz * 1e3 / 2
    out = []
    for lo, hi in profile.bands:
        f = lo + half
        while f + half <= hi:
            out.append(f)
            f += step
    return out


class HopSequence:
    """Sequência de salto derivada da chave e do identificador do enlace.

    Saltos por fatia de tempo de 0,4 s; cada canal é visitado uma vez por ciclo de
    N fatias, logo a ocupação de qualquer canal é <= 0,4 s a cada N x 0,4 s.
    Sequências de enlaces distintos são independentes (não coordenadas: 10.2.8.1)."""

    def __init__(self, key, n_channels, slot_s=0.4, plan_size=None):
        self.n = n_channels
        self.slot = slot_s
        rng = random.Random(f"hop:{key}")
        pool = list(range(plan_size or n_channels))
        rng.shuffle(pool)
        self.seq = pool[:n_channels]
        self.key = key

    def slot_index(self, t):
        return int(math.floor(t / self.slot))

    def channel(self, t):
        return self.seq[self.slot_index(t) % self.n]

    def slot_end(self, t):
        return (self.slot_index(t) + 1) * self.slot

    GUARD_S = 0.015   # guarda contra deriva de relógio entre os nós

    def fit_start(self, t, toa):
        """Início mais cedo >= t em que o pacote cabe na fatia, com guarda nas bordas."""
        g = self.GUARD_S
        start = self.slot_index(t) * self.slot
        if t < start + g:
            t = start + g
        if self.slot_end(t) - g - t >= toa:
            return t
        return self.slot_end(t) + g


# ---------------------------------------------------------------- verificação
def check_compliance(tx_log, profile, horizon=None):
    """Verifica um registro de transmissões contra o perfil.

    tx_log: lista de dicts {t, dur, bw, freq (Hz ou índice de canal), p_dbm, fhss(bool),
            n_hop (canais da sequência), node}
    Devolve dict com violações por regra e estatísticas de ocupação.
    """
    viol = {"dwell_pacote": 0, "ocupacao_janela": 0, "canais_insuficientes": 0,
            "potencia": 0, "fora_da_faixa": 0, "digital_bw": 0}
    worst_occ = {}
    by_node_ch = {}
    for r in tx_log:
        bw = r["bw"]
        if r.get("fhss"):
            hc = profile.hop_class(bw)
            if hc is None:
                viol["digital_bw"] += 1
                continue
            if r["dur"] > hc.dwell_s + 1e-9:
                viol["dwell_pacote"] += 1
            if r.get("n_hop", 0) < hc.min_channels:
                viol["canais_insuficientes"] += 1
            cap = profile.hop_cap_dbm(r.get("n_hop", 0), bw_khz=bw)
            if r["p_dbm"] > cap + 1e-6:
                viol["potencia"] += 1
            by_node_ch.setdefault((r["node"], r["freq"], hc.window_s), []).append((r["t"], r["dur"]))
        else:
            cap = profile.digital_cap_dbm(bw)
            if cap is None:
                # canal fixo estreito: só baixa potência
                if r["p_dbm"] > r.get("low_power_cap", -3.0) + 1e-6:
                    viol["potencia"] += 1
            elif r["p_dbm"] > cap + 1e-6:
                viol["potencia"] += 1
        f = r.get("freq_hz")
        if f is not None and not any(lo <= f <= hi for lo, hi in profile.bands):
            viol["fora_da_faixa"] += 1
    # ocupação por canal em janela deslizante
    for (node, ch, win), evs in by_node_ch.items():
        evs.sort()
        j = 0
        acc = 0.0
        worst = 0.0
        for i, (t, d) in enumerate(evs):
            acc += d
            while evs[j][0] < t + d - win:
                acc -= evs[j][1]
                j += 1
            worst = max(worst, acc)
        worst_occ[(node, ch)] = worst
        if worst > 0.4 + 1e-6:
            viol["ocupacao_janela"] += 1
    return {"violacoes": viol, "total_tx": len(tx_log),
            "pior_ocupacao_s": max(worst_occ.values()) if worst_occ else 0.0,
            "canais_usados": len({k[1] for k in worst_occ}),
            "conforme": all(v == 0 for v in viol.values())}
