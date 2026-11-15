"""Enlaces de rádio: fixos (herdados do adaptsim) e móveis.

Enlace móvel:
  - perda de percurso do ambiente com a distância 3D instantânea;
  - estado LoS/NLoS como processo de Markov ao longo da distância percorrida;
  - sombreamento espacialmente correlacionado (Gudmundson) pela distância percorrida;
  - ganho de altura para drones (aproxima espaço livre acima de ~60 m);
  - desvanecimento de Rice independente por pacote quando há movimento;
  - velocidade e aceleração radiais para Doppler estático e dinâmico (B9, M5).
Todos os parâmetros são estimativas, a calibrar nas campanhas F e M.
"""
import math
import numpy as np
from .channel_static import ENVS, Link as StaticLink, ANT_GAIN_DBI, CABLE_LOSS_DB, pathloss

# LoS/NLoS por ambiente: comprimentos médios (m) e perda extra NLoS (dB);
# distância de decorrelação do sombreamento (m)
MOBILE_PARAMS = {
    "urbano_denso": dict(los_m=40, nlos_m=120, nlos_db=12, dcorr=20),
    "urbano_residencial": dict(los_m=80, nlos_m=100, nlos_db=9, dcorr=30),
    "industrial": dict(los_m=40, nlos_m=80, nlos_db=14, dcorr=15),
    "rural_aberto": dict(los_m=800, nlos_m=80, nlos_db=5, dcorr=100),
    "rural_vegetacao": dict(los_m=150, nlos_m=200, nlos_db=8, dcorr=60),
    "rural_serra": dict(los_m=400, nlos_m=300, nlos_db=10, dcorr=120),
}
LAMBDA = 299_792_458.0 / 915e6


class MobileLink:
    def __init__(self, env, track_a, track_b, rng, ground_h=3.0):
        self.env = env
        self.rng = rng
        mp = MOBILE_PARAMS[env_key(env)]
        ta, tb = track_a, track_b
        n = min(len(ta.t), len(tb.t))
        self.dt = ta.dt
        self.t = ta.t[:n]
        pa, pb = ta.xyz[:n], tb.xyz[:n]
        d3 = np.linalg.norm(pa - pb, axis=1)
        d3 = np.maximum(d3, 5.0)
        d2 = np.maximum(np.linalg.norm(pa[:, :2] - pb[:, :2], axis=1), 5.0)
        travel = ta.travel[:n] + tb.travel[:n]
        hmax = np.maximum(pa[:, 2], pb[:, 2])
        # perda base pelo ambiente (2D, antenas ~3 m) e correção de altura
        pl = np.array([pathloss(env, x / 1000.0) for x in d2])
        fspl = 20 * np.log10(4 * math.pi * d3 / LAMBDA)
        hg = np.clip(20 * np.log10(np.maximum(hmax, ground_h) / ground_h), 0, 40)
        pl = np.maximum(fspl + 3.0, pl - hg)
        # LoS/NLoS ao longo da distância percorrida (drone alto: quase sempre LoS)
        los = np.ones(n, bool)
        state = True
        last = 0.0
        seglen = rng.exponential(mp["los_m"])
        for i in range(n):
            if travel[i] - last > seglen:
                state = not state
                last = travel[i]
                seglen = rng.exponential(mp["los_m"] if state else mp["nlos_m"])
            los[i] = state or hmax[i] > 60
        self.los = los
        nlos_loss = np.where(los, 0.0, mp["nlos_db"] * np.clip(1 - (hmax - 3) / 60, 0, 1))
        # sombreamento correlacionado no espaço (Gudmundson)
        sig = env["sigma_static"] * 0.6
        sh = np.zeros(n)
        sh[0] = rng.normal(0, sig)
        static_part = rng.normal(0, env["sigma_static"] * 0.8)
        for i in range(1, n):
            dd = abs(travel[i] - travel[i - 1])
            rho = math.exp(-dd / mp["dcorr"])
            sh[i] = rho * sh[i - 1] + math.sqrt(1 - rho ** 2) * rng.normal(0, sig)
        self.slow = -(pl + nlos_loss + sh + static_part) + 2 * (ANT_GAIN_DBI - CABLE_LOSS_DB)
        # velocidade/aceleração radiais
        vr = np.gradient(d3, self.dt)
        self.vr = vr
        self.ar = np.gradient(vr, self.dt)
        self.moving = (ta.speed[:n] + tb.speed[:n]) > 0.3
        K = 10 ** (env["K_db"] / 10)
        self._los_a = math.sqrt(K / (K + 1))
        self._sc = math.sqrt(1 / (2 * (K + 1)))
        self.d = d3

    def _i(self, t):
        return min(len(self.t) - 1, max(0, int(t / self.dt)))

    def gain_db(self, t):
        return float(self.slow[self._i(t)])

    def fade(self, t=None):
        i = self._i(t or 0)
        k = self._los_a if self.los[i] else 0.0
        sc = self._sc if self.los[i] else math.sqrt(0.5)
        h = k + sc * (self.rng.normal() + 1j * self.rng.normal())
        return 10 * math.log10(max(abs(h) ** 2, 1e-6))

    def rx_dbm(self, t, p_tx):
        return p_tx + self.gain_db(t) + self.fade(t)

    def radial(self, t):
        i = self._i(t)
        return float(self.vr[i]), float(self.ar[i])

    def distance(self, t):
        return float(self.d[self._i(t)])


class FixedLink:
    """Adaptador do enlace fixo do adaptsim para a mesma interface."""

    def __init__(self, env, d_km, rng, T_s, static_shadow=None):
        self.inner = StaticLink(env, d_km, rng, T_s, static_shadow=static_shadow)
        self.env = env
        self.d_km = d_km

    def gain_db(self, t):
        return self.inner.gain_db(t)

    def fade(self, t=None):
        return self.inner.fade()

    def rx_dbm(self, t, p_tx):
        return p_tx + self.gain_db(t) + self.fade()

    def radial(self, t):
        return 0.0, 0.0

    def distance(self, t):
        return self.d_km * 1000.0


def env_key(env):
    for k, v in ENVS.items():
        if v is env:
            return k
    return env.get("id", "rural_aberto")
