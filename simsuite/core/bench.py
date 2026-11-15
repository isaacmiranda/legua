"""Bancada conduzida simulada: enlace por cabo com atenuador programável (B2-B7)."""
import math
from ..core.channel_static import ANT_GAIN_DBI


class AttenLink:
    """Ganho = -(perda fixa + atenuador(t)) com pequeno ruído de medida.

    program: função t -> atenuação (dB). Sem desvanecimento (cabo), mas com uma
    variação residual de 0,3 dB (conectores, temperatura)."""

    def __init__(self, program, rng, fixed_db=40.0, resid_db=0.3):
        self.program = program
        self.rng = rng
        self.fixed = fixed_db
        self.resid = resid_db

    def gain_db(self, t):
        return -(self.fixed + self.program(t))

    def fade(self, t=None):
        return self.rng.normal(0, self.resid)

    def rx_dbm(self, t, p_tx):
        return p_tx + self.gain_db(t) + self.fade()

    def radial(self, t):
        return 0.0, 0.0

    def distance(self, t):
        return 0.0


def constant(db):
    return lambda t: db


def steps(levels, dwell_s):
    def f(t):
        i = min(len(levels) - 1, int(t // dwell_s))
        return levels[i]
    return f


def sawtooth(lo, hi, period_s):
    def f(t):
        x = (t % period_s) / period_s
        return lo + (hi - lo) * (2 * x if x < 0.5 else 2 - 2 * x)
    return f


def from_trace(times, gains_db, p_ref=0.0):
    """Reproduz um traço de ganho de campo (dB) como atenuação."""
    import numpy as np
    times = np.asarray(times)
    gains = np.asarray(gains_db)

    def f(t):
        i = min(len(times) - 1, max(0, int(np.searchsorted(times, t))))
        return -gains[i] - 40.0
    return f
