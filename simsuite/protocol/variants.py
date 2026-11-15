"""Variantes do ponto final para bancada e campo.

LockedEndpoint   modo travado (RF-66): presets fixos e ensaios de curva PDR.
NegTestEndpoint  gancho de teste: o proponente alterna entre dois modos a cada
                 janela de cooldown, para gerar milhares de negociações (B3/B4).
"""
from dataclasses import replace
from .endpoint import Endpoint, Config, DATA


class LockedEndpoint(Endpoint):
    def __init__(self, nid, peer, modes, base, rec, cfg, rng, noise_rise=0.0, cap=28.0, mode=None):
        cfg = replace(cfg, n_up=10 ** 9, silence_descent=False, fail_streak_degrade=10 ** 9,
                      power_control=False)
        self._lock = mode
        super().__init__(nid, peer, modes, base, rec, cfg, rng, noise_rise, cap)

    def _boot(self, now):
        self.nvm["anchor"] = self._lock
        super()._boot(now)
        self.state = DATA


def locked_factory(mode):
    def mk(nid, peer, modes, base, rec, cfg, rng, noise_rise=0.0, cap=28.0):
        return LockedEndpoint(nid, peer, modes, base, rec, cfg, rng, noise_rise, cap, mode=mode)
    return mk


class NegTestEndpoint(Endpoint):
    """Alterna o candidato entre pair[0] e pair[1] (ambos com margem na bancada)."""

    pair = None

    def _candidate(self, initial=False):
        a, b = self.pair
        if initial:
            return a
        return b if self.mode == a else a


def negtest_factory(pair):
    def mk(nid, peer, modes, base, rec, cfg, rng, noise_rise=0.0, cap=28.0):
        e = NegTestEndpoint.__new__(NegTestEndpoint)
        e.pair = pair
        Endpoint.__init__(e, nid, peer, modes, base, rec, cfg, rng, noise_rise, cap)
        return e
    return mk
