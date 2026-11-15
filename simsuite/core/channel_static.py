"""Ambientes e modelo de canal a 915 MHz.

Perda de percurso: PL(d) = PL_1km + 10 n log10(d_km)  (forma Hata / dois raios)
Sombreamento: componente estática por enlace (local) + processo AR(1) temporal.
Eventos: obstruções (veículos, contêineres), chuva e ciclo diurno de umidade.
Desvanecimento rápido: Rice com fator K, sorteado a cada transmissão.
Interferência externa: ALOHA de fundo com taxa G (pacotes/s no canal) e captura.

Os parâmetros são estimativas de ordem de grandeza calibradas por:
- Hata (cidade pequena/média) ajustado para antenas a ~3 m;
- Facina et al. (SBrT 2021): ~8 km com SF7/20 dBm em visada, 915 MHz;
- Ferreira et al. (SBrT 2019) e Oliveira et al. (SBrT 2023): vegetação e umidade.
Não substituem campanha de campo.
"""
import math
import numpy as np

ENVS = {
    "urbano_denso": dict(
        label="Urbano denso", grupo="urbano",
        desc="Centro com prédios altos, antenas a ~3 m, tráfego de veículos",
        pl1km=142.0, n=4.0, sigma_static=8.0, sigma_t=3.0, tau_s=300.0,
        K_db=3.0, noise_rise=6.0, G_ext=0.30,
        obstr_rate_h=2.0, obstr_db=(6, 15), obstr_dur_s=300,
        diurnal_db=1.0, rain_rate_h=0.0, rain_db=(0, 0), rain_dur_s=0),
    "urbano_residencial": dict(
        label="Urbano residencial", grupo="urbano",
        desc="Casas de 1 a 3 pavimentos, arborização de rua",
        pl1km=133.0, n=3.7, sigma_static=7.0, sigma_t=2.0, tau_s=600.0,
        K_db=5.0, noise_rise=3.0, G_ext=0.15,
        obstr_rate_h=1.0, obstr_db=(4, 10), obstr_dur_s=600,
        diurnal_db=1.5, rain_rate_h=0.04, rain_db=(1, 3), rain_dur_s=5400),
    "industrial": dict(
        label="Industrial / portuário", grupo="urbano",
        desc="Galpões metálicos, contêineres, motores e inversores",
        pl1km=138.0, n=3.8, sigma_static=10.0, sigma_t=3.5, tau_s=180.0,
        K_db=2.0, noise_rise=8.0, G_ext=0.10,
        obstr_rate_h=0.5, obstr_db=(10, 20), obstr_dur_s=1200,
        diurnal_db=0.5, rain_rate_h=0.0, rain_db=(0, 0), rain_dur_s=0),
    "rural_aberto": dict(
        label="Rural aberto", grupo="rural",
        desc="Pastagem ou sertão plano, visada parcial, mastros de ~3 m",
        pl1km=112.0, n=4.0, sigma_static=4.0, sigma_t=1.0, tau_s=1800.0,
        K_db=10.0, noise_rise=0.0, G_ext=0.01,
        obstr_rate_h=0.0, obstr_db=(0, 0), obstr_dur_s=0,
        diurnal_db=1.5, rain_rate_h=0.04, rain_db=(1, 3), rain_dur_s=5400),
    "rural_vegetacao": dict(
        label="Rural com vegetação", grupo="rural",
        desc="Mata, caatinga densa ou pomar; perda varia com umidade e chuva",
        pl1km=128.0, n=4.2, sigma_static=6.0, sigma_t=2.0, tau_s=900.0,
        K_db=6.0, noise_rise=0.0, G_ext=0.01,
        obstr_rate_h=0.0, obstr_db=(0, 0), obstr_dur_s=0,
        diurnal_db=4.0, rain_rate_h=0.08, rain_db=(3, 8), rain_dur_s=7200),
    "rural_serra": dict(
        label="Rural serrano", grupo="rural",
        desc="Relevo ondulado; alguns enlaces em sombra de morro",
        pl1km=118.0, n=4.0, sigma_static=12.0, sigma_t=1.5, tau_s=1800.0,
        K_db=8.0, noise_rise=0.0, G_ext=0.005,
        obstr_rate_h=0.0, obstr_db=(0, 0), obstr_dur_s=0,
        diurnal_db=2.0, rain_rate_h=0.04, rain_db=(2, 5), rain_dur_s=5400),
}

ANT_GAIN_DBI = 2.15    # dipolo de meia onda
CABLE_LOSS_DB = 0.5
EXT_TOA_S = 0.10       # duração média dos pacotes de terceiros
CAPTURE_P = 0.25       # chance de sobreviver a uma colisão (efeito de captura)


def pathloss(env, d_km):
    return env["pl1km"] + 10 * env["n"] * math.log10(max(d_km, 0.02))


def range_km(env, budget_db):
    """Distância em que a perda de percurso média iguala o orçamento."""
    return 10 ** ((budget_db - env["pl1km"]) / (10 * env["n"]))


class Link:
    """Enlace entre dois nós fixos. gain_db(t) devolve o ganho lento (negativo, dB)
    sem desvanecimento rápido; rx_dbm() aplica o desvanecimento por transmissão."""

    def __init__(self, env, d_km, rng, T_s, dt=10.0, static_shadow=None):
        self.env = env
        self.rng = rng
        self.dt = dt
        n = int(T_s / dt) + 2
        e = env
        pl = pathloss(e, d_km)
        s_static = rng.normal(0, e["sigma_static"]) if static_shadow is None else static_shadow
        # AR(1)
        rho = math.exp(-dt / e["tau_s"])
        w = rng.normal(0, e["sigma_t"] * math.sqrt(1 - rho ** 2), n)
        ar = np.empty(n)
        ar[0] = rng.normal(0, e["sigma_t"])
        for i in range(1, n):
            ar[i] = rho * ar[i - 1] + w[i]
        t = np.arange(n) * dt
        extra = np.zeros(n)
        # ciclo diurno (perda maior de madrugada, umidade)
        phase = rng.uniform(0, 2 * math.pi) * 0.1
        extra += e["diurnal_db"] * 0.5 * (1 + np.cos(2 * math.pi * t / 86400 + phase))
        # eventos de obstrução e chuva (Poisson)
        for rate, (lo, hi), dur in ((e["obstr_rate_h"], e["obstr_db"], e["obstr_dur_s"]),
                                    (e["rain_rate_h"], e["rain_db"], e["rain_dur_s"])):
            if rate <= 0:
                continue
            k = rng.poisson(rate * T_s / 3600)
            for _ in range(k):
                t0 = rng.uniform(0, T_s)
                du = rng.exponential(dur)
                depth = rng.uniform(lo, hi)
                extra[(t >= t0) & (t < t0 + du)] += depth
        self.slow = -(pl + s_static + ar + extra) + 2 * (ANT_GAIN_DBI - CABLE_LOSS_DB)
        K = 10 ** (e["K_db"] / 10)
        self._los = math.sqrt(K / (K + 1))
        self._sc = math.sqrt(1 / (2 * (K + 1)))
        self._pool = self._new_pool()
        self._pi = 0
        self.d_km = d_km
        self.mean_gain = -pl + 2 * (ANT_GAIN_DBI - CABLE_LOSS_DB) - s_static

    def _new_pool(self, m=4096):
        h = self._los + self._sc * (self.rng.normal(size=m) + 1j * self.rng.normal(size=m))
        return 10 * np.log10(np.abs(h) ** 2)

    def fade(self):
        if self._pi >= len(self._pool):
            self._pool = self._new_pool()
            self._pi = 0
        v = self._pool[self._pi]
        self._pi += 1
        return v

    def gain_db(self, t):
        i = int(t / self.dt)
        if i >= len(self.slow):
            i = len(self.slow) - 1
        return self.slow[i]

    def rx_dbm(self, t, p_tx):
        return p_tx + self.gain_db(t) + self.fade()


def p_ext_ok(env, toa, load_factor=1.0, cr=1):
    """Probabilidade de não ser destruído por tráfego de terceiros (ALOHA + captura).
    CR mais forte corrige parte das colisões parciais (APROX: +8 pontos por passo)."""
    g = env["G_ext"] * load_factor
    p_hit = 1 - math.exp(-g * (toa + EXT_TOA_S))
    cap = CAPTURE_P + 0.08 * (cr - 1)
    return 1 - p_hit * (1 - cap)
