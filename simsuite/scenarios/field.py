"""Campo fixo F1-F6 e mobilidade M1-M7 (doc 05, Fases 4 e 5), em simulação.

Comparação pareada: as mesmas sementes de canal para todas as configurações
(como o rodízio intercalado do plano), repetida em blocos (dias/sessões).
"""
import math
import numpy as np
from dataclasses import replace
from ..core.channel_static import ENVS
from ..core.links import FixedLink, MobileLink
from ..core import mobility as mob
from ..protocol.modes import table, by_name
from ..protocol.endpoint import Config
from ..protocol.variants import locked_factory
from ..analysis.stats import block_bootstrap_ci, design_effect
from .common import make_pair, summarize, r7_km


class OffsetLink:
    """Enlace fixo com ganho extra (mastro alto: +; parede/indoor: -)."""

    def __init__(self, inner, offset_db):
        self.inner, self.off = inner, offset_db

    def gain_db(self, t):
        return self.inner.gain_db(t) + self.off

    def fade(self, t=None):
        return self.inner.fade(t)

    def rx_dbm(self, t, p):
        return p + self.gain_db(t) + self.fade(t)

    def radial(self, t):
        return 0.0, 0.0

    def distance(self, t):
        return self.inner.distance(t)


def configs(mobile=False, app=20.0):
    modes, base, rec = table()
    c = {
        "Fixo SF10/125 salto (base)": dict(factory=locked_factory(base)),
        "Fixo SF7/125 salto (rápido)": dict(factory=locked_factory(by_name(modes, "SF7/125/FH"))),
        "Fixo SF12/500 digital": dict(factory=locked_factory(by_name(modes, "SF12/500"))),
        "Légua perfil fixo": dict(cfg=Config()),
    }
    if mobile:
        ts = max(30.0, 3 * app)               # silêncio proporcional ao tráfego
        c["Légua perfil móvel"] = dict(cfg=Config(mobile=True, cooldown_up=120.0, n_up=10, t_silence=ts,
                                                      t_recovery=2 * ts, fail_streak_degrade=2, t_valid=20.0))
    return c


def _run_cell(env_id, link_maker, cfg_kw, T, seeds, app=20.0, tracks=(None, None), xtal="tcxo",
              one_way=True, cap=28.0, clock_ppm=(10.0, -10.0), asym_db=None, slow=None):
    blocks, energies, lats, st_acc, dis = [], [], [], {}, []
    for s in seeds:
        link = link_maker(s)
        kw = {}
        if "factory" in cfg_kw:
            kw["endpoint_cls"] = cfg_kw["factory"]
        sim = make_pair(env_id, link, T, s * 7 + 1, cfg=cfg_kw.get("cfg"), app_interval=app,
                        tracks=tracks, xtal=xtal, cap=cap, clock_ppm=clock_ppm, **kw)
        if asym_db:
            sim.asym_db = dict(asym_db)
        if slow:                       # (sigma_db, tau_s): um processo por sentido, sementes distintas
            from ..core.des import SlowFade
            sim.slow_db = {(0, 1): SlowFade(slow[0], slow[1], 7000 + s, T + 10),
                           (1, 0): SlowFade(slow[0], slow[1], 8000 + s, T + 10)}
        if one_way:
            sim.nodes[1].app_interval = None
        sim.start()
        sim.run()
        r = summarize(sim)
        blocks.append((r["entregues"], r["gerados"]))
        if r["mj_por_pacote"]:
            energies.append(r["mj_por_pacote"])
        if r["lat_p95_s"] is not None:
            lats.append(r["lat_p95_s"])
        for k, v in r["stats"].items():
            st_acc[k] = st_acc.get(k, 0) + v
        dis.append(r["acordo"].get("desacordo_s", 0.0))
    est, lo, hi = block_bootstrap_ci(blocks)
    hours = T * len(seeds) / 3600
    return {"pdr": round(est, 4), "ic95_blocos": (round(lo, 4), round(hi, 4)),
            "efeito_desenho": round(design_effect(blocks), 2) if len(blocks) > 1 else None,
            "pacotes": int(sum(b[1] for b in blocks)), "blocos": len(blocks),
            "mj_por_pacote_mediana": round(float(np.median(energies)), 1) if energies else None,
            "lat_p95_s": round(float(np.median(lats)), 2) if lats else None,
            "trocas_por_hora": round(st_acc.get("trocas", 0) / hours, 2),
            "rollbacks_por_hora": round(st_acc.get("rollbacks", 0) / hours, 2),
            "quedas_base": st_acc.get("quedas_base", 0),
            "desacordo_s_por_hora": round(sum(dis) / hours, 1)}


FIELD = {
    "F1 urbano denso": dict(env="urbano_denso", dists=[0.3, 0.6, 1.0, 1.5, 2.0, 3.0], offset=0.0),
    "F2 urbano residencial": dict(env="urbano_residencial", dists=[1.0, 2.0, 3.0, 4.0, 5.0], offset=0.0),
    "F3 indoor-outdoor": dict(env="urbano_residencial", dists=[0.2, 0.5, 1.0], offset=-15.0),
    "F4 rural aberto (mastro 8 m)": dict(env="rural_aberto", dists=[3, 8, 14, 20, 26], offset=8.5),
    "F5 rural com relevo/mata": dict(env="rural_serra", dists=[1, 2, 4, 6, 8], offset=0.0),
}


def field_campaign(escala="quick", which=None):
    T = 2 * 3600 if escala == "quick" else 6 * 3600
    seeds = [11, 12] if escala == "quick" else [11, 12, 13, 14, 15]
    out = {}
    for name, spec in FIELD.items():
        if which and not name.startswith(which):
            continue
        env = ENVS[spec["env"]]
        res = {}
        for d in spec["dists"]:
            row = {}
            for cname, ckw in configs().items():
                mk = lambda s, d=d: OffsetLink(FixedLink(env, d, np.random.default_rng(1000 + s), T + 10),
                                               spec["offset"])
                row[cname] = _run_cell(spec["env"], mk, ckw, T, seeds)
            res[f"{d} km"] = row
        out[name] = res
    return out


def f6_long_duration(escala="quick"):
    """Longa duração: 1 dia (quick) ou 7 dias (full) por semente de canal, várias sementes."""
    days = 1 if escala == "quick" else 7
    T = days * 86400
    seeds = [21, 22, 23]
    out = {}
    for name, (env_id, d, off) in {"urbano denso 1 km": ("urbano_denso", 1.0, 0.0),
                                   "rural aberto 8 km": ("rural_aberto", 8.0, 8.5)}.items():
        env = ENVS[env_id]
        row = {}
        for cname in ("Fixo SF10/125 salto (base)", "Légua perfil fixo"):
            ckw = configs()[cname]
            mk = lambda s, env=env, d=d, off=off: OffsetLink(
                FixedLink(env, d, np.random.default_rng(77 + s), T + 10), off)
            row[cname] = _run_cell(env_id, mk, ckw, T, seeds, app=60.0)
        out[name] = row
    return out


# ------------------------------------------------------------------ F7: sintonia da aceleração
F7_VARIANTES = {
    "Fixo SF10/125 salto (base)": None,
    "Légua atual (margem 8 dB)": {},
    "Légua margem 14 dB": dict(margin_up=14.0),
    "Légua fade_k 1": dict(fade_k=1.0),
    "Légua fade_k 2": dict(fade_k=2.0),
    "Légua fade_k 3": dict(fade_k=3.0),
}
F7_ENLACES = {"urbano denso 1 km": ("urbano_denso", 1.0, 0.0),
              "urbano residencial 3 km": ("urbano_residencial", 3.0, 0.0)}


def f7_tuning(escala="quick"):
    """Efeito da margem de aceleração (fixa ou proporcional à variabilidade do SNR) em enlace marginal.

    Pergunta (achado do F6): a oscilação (quedas ao base, desacordo) se reduz com margem maior? A que custo
    de energia? Mesmas sementes de canal para todas as variantes."""
    days, seeds = (1, [21, 22]) if escala == "quick" else (7, [21, 22, 23, 24, 25])
    T = days * 86400
    modes, base, rec = table()
    out = {}
    for lname, (env_id, d, off) in F7_ENLACES.items():
        env = ENVS[env_id]
        mk = lambda s, env=env, d=d, off=off: OffsetLink(
            FixedLink(env, d, np.random.default_rng(77 + s), T + 10), off)
        row = {}
        for vname, kw in F7_VARIANTES.items():
            ckw = dict(factory=locked_factory(base)) if kw is None else dict(cfg=Config(**kw))
            row[vname] = _run_cell(env_id, mk, ckw, T, seeds, app=60.0)
        out[lname] = row
    return out


# ------------------------------------------------------------------ mobilidade
def _tracks(kind, T, rng):
    """Devolve (env_id, track_fixo, track_móvel, descrição)."""
    if kind == "M1 pedestre urbano":
        pts = [(400, 0), (1400, 300), (1800, 1200), (900, 1600), (300, 900)]
        return "urbano_residencial", mob.static(0, 0, 6, T), mob.waypoints(pts, 1.4, z=1.3, T=T, rng=rng), "5 km/h"
    if kind == "M1 pedestre rural":
        pts = [(1000, 0), (4000, 500), (6000, 2500), (3000, 4000)]
        return "rural_aberto", mob.static(0, 0, 8, T), mob.waypoints(pts, 1.4, z=1.3, T=T, rng=rng), "5 km/h"
    if kind == "M2 bicicleta urbana":
        pts = [(300, 0), (2000, 400), (2600, 2000), (800, 2400), (200, 1200)]
        return "urbano_residencial", mob.static(0, 0, 6, T), mob.waypoints(pts, 5.0, z=1.2, T=T, rng=rng), "18 km/h"
    if kind == "M3 carro urbano NLoS":
        pts = [(200, 0), (1200, 300), (1500, 1100), (600, 1500), (100, 800)]
        return "urbano_denso", mob.static(0, 0, 6, T), mob.waypoints(pts, 11.0, z=1.7, T=T, rng=rng), "40 km/h"
    if kind == "M4 carro rodovia":
        return "rural_aberto", mob.static(0, 0, 8, T), mob.straight((-12000, 600), (12000, 600), 28.0, z=1.7,
                                                                      T=T, rng=rng), "100 km/h"
    if kind == "M5 passagem cruzada":
        a = mob.straight((-6000, 0), (6000, 0), 20.0, z=1.7, T=T, rng=rng)
        b = mob.straight((6000, 30), (-6000, 30), 20.0, z=1.7, T=T, rng=rng)
        return "rural_aberto", a, b, "2 x 72 km/h"
    if kind.startswith("M6 drone"):
        alt = float(kind.split()[-1].replace("m", ""))
        env = "urbano_residencial" if "urbano" in kind else "rural_aberto"
        r = 1500 if env == "urbano_residencial" else 6000
        return env, mob.static(0, 0, 6, T), mob.drone_orbit(0, 0, r, alt, 10.0, T=T), f"10 m/s a {alt:.0f} m"
    if kind == "M7 gado":
        return "rural_vegetacao", mob.static(0, 0, 8, T, dt=5.0), mob.cattle(2500, 0, 1500, T=T, dt=5.0, rng=rng), "pastejo"
    raise KeyError(kind)


MOB_KINDS = ["M1 pedestre urbano", "M1 pedestre rural", "M2 bicicleta urbana", "M3 carro urbano NLoS",
             "M4 carro rodovia", "M5 passagem cruzada", "M6 drone urbano 30m", "M6 drone urbano 120m",
             "M6 drone rural 60m", "M7 gado"]


def mobility_campaign(escala="quick", which=None):
    out = {}
    for kind in MOB_KINDS:
        if which and not kind.startswith(which):
            continue
        cattle = kind.startswith("M7")
        T = (86400 if escala == "full" else 6 * 3600) if cattle else (3600 if escala == "quick" else 3 * 3600)
        app = 60.0 if cattle else 2.0
        seeds = [31, 32] if escala == "quick" else [31, 32, 33]
        row = {}
        for cname, ckw in configs(mobile=True, app=app).items():
            def mk(s, kind=kind, T=T):
                rng = np.random.default_rng(500 + s)
                env_id, ta, tb, _ = _tracks(kind, T + 60, rng)
                return MobileLink(ENVS[env_id], ta, tb, np.random.default_rng(900 + s))
            env_id, ta, tb, desc = _tracks(kind, T + 60, np.random.default_rng(1))
            row[cname] = _run_cell(env_id, mk, ckw, T, seeds, app=app, tracks=(ta, tb))
        out[kind] = {"ambiente": env_id, "velocidade": desc, "configs": row}
    return out


def doppler_check():
    """Doppler estático e dinâmico do M5 em relação às tolerâncias (alimenta B9)."""
    from ..core.radio import doppler_hz, drift_tolerance_hz, static_offset_tolerance_hz
    env_id, a, b, _ = _tracks("M5 passagem cruzada", 600, np.random.default_rng(0))
    lk = MobileLink(ENVS[env_id], a, b, np.random.default_rng(1))
    vr = np.abs(lk.vr)
    ar = np.abs(lk.ar)
    lam = 299_792_458.0 / 915e6
    return {"doppler_max_hz": round(float(doppler_hz(vr.max())), 1),
            "variacao_max_hz_s": round(float(ar.max() / lam), 1),
            "tolerancia_estatica_125k_hz": static_offset_tolerance_hz(125),
            "tolerancia_dinamica_sf12_500_hz": round(drift_tolerance_hz(12, 500), 1),
            "tolerancia_dinamica_sf10_125_hz": round(drift_tolerance_hz(10, 125), 1)}
