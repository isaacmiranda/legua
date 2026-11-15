"""Modelos de mobilidade para os cenários M1-M7 e T6.

Cada modelo devolve, numa grade de tempo, posição (x, y, z em metros), velocidade
escalar e distância percorrida. A grade é usada pelos enlaces móveis (links.py).
"""
import math
import numpy as np


class Track:
    """Trajetória amostrada a cada dt segundos."""

    def __init__(self, t, xyz, kind):
        self.t = t
        self.xyz = xyz
        self.kind = kind
        d = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(xyz[:, :2], axis=0), axis=1))]
        self.travel = d
        dt = np.diff(t, prepend=t[0] - (t[1] - t[0]))
        v = np.r_[0.0, np.linalg.norm(np.diff(xyz, axis=0), axis=1)] / np.maximum(dt, 1e-9)
        self.speed = v
        self.dt = t[1] - t[0]

    def idx(self, tq):
        return min(len(self.t) - 1, max(0, int(tq / self.dt)))

    def pos(self, tq):
        return self.xyz[self.idx(tq)]

    def speed_at(self, tq):
        return float(self.speed[self.idx(tq)])

    def travel_at(self, tq):
        return float(self.travel[self.idx(tq)])


def static(x, y, z=3.0, T=3600.0, dt=1.0):
    t = np.arange(0, T + dt, dt)
    return Track(t, np.tile([x, y, z], (len(t), 1)).astype(float), "fixo")


def waypoints(points, speed_ms, z=1.5, T=3600.0, dt=1.0, pause_s=0.0, kind="rota", rng=None,
              speed_jitter=0.15):
    """Percorre os pontos em vai-e-vem com velocidade ~speed_ms (jitter relativo)."""
    rng = rng or np.random.default_rng(0)
    pts = [np.array(p, float) for p in points]
    legs = pts + pts[-2::-1]
    t = np.arange(0, T + dt, dt)
    xyz = np.zeros((len(t), 3))
    seg, pos, pause = 0, legs[0].copy(), 0.0
    v = speed_ms
    for i in range(len(t)):
        xyz[i, :2] = pos
        xyz[i, 2] = z
        if pause > 0:
            pause -= dt
            continue
        tgt = legs[(seg + 1) % len(legs)]
        vec = tgt - pos
        dist = np.linalg.norm(vec)
        v = max(0.2, speed_ms * (1 + speed_jitter * rng.normal()))
        step = v * dt
        if dist <= step:
            pos = tgt.copy()
            seg = (seg + 1) % (len(legs) - 1 if len(legs) > 1 else 1)
            pause = pause_s
        else:
            pos = pos + vec / dist * step
    return Track(t, xyz, kind)


def straight(p0, p1, speed_ms, z=1.5, T=3600.0, dt=1.0, kind="reta", rng=None):
    return waypoints([p0, p1], speed_ms, z=z, T=T, dt=dt, kind=kind, rng=rng, speed_jitter=0.05)


def drone_orbit(cx, cy, radius, alt, speed_ms, T=3600.0, dt=1.0):
    t = np.arange(0, T + dt, dt)
    w = speed_ms / radius
    xyz = np.c_[cx + radius * np.cos(w * t), cy + radius * np.sin(w * t), np.full_like(t, alt)]
    return Track(t, xyz, "drone")


def cattle(x0, y0, paddock_m, T=86400.0, dt=5.0, rng=None):
    """Passeio aleatório correlacionado com pastejo (paradas) e limite de piquete."""
    rng = rng or np.random.default_rng(1)
    t = np.arange(0, T + dt, dt)
    xyz = np.zeros((len(t), 3))
    pos = np.array([x0, y0], float)
    hd = rng.uniform(0, 2 * math.pi)
    moving = False
    for i in range(len(t)):
        xyz[i] = [pos[0], pos[1], 1.2]
        if rng.random() < (0.02 if moving else 0.01):
            moving = not moving
        if moving:
            hd += rng.normal(0, 0.4)
            v = rng.uniform(0.3, 1.2)
            nxt = pos + v * dt * np.array([math.cos(hd), math.sin(hd)])
            if np.any(np.abs(nxt - [x0, y0]) > paddock_m / 2):
                hd += math.pi
            else:
                pos = nxt
    return Track(t, xyz, "gado")


def random_waypoint_area(L, speed_ms, z=1.5, T=3600.0, dt=1.0, rng=None, kind="rwp"):
    rng = rng or np.random.default_rng(2)
    pts = [rng.uniform(0, L, 2) for _ in range(12)]
    return waypoints(pts, speed_ms, z=z, T=T, dt=dt, rng=rng, kind=kind, pause_s=30)
