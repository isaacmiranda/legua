"""Montagem de enlaces P2P com a Légua de referência ou baselines."""
import os
import numpy as np
from ..core.channel_static import ENVS
from ..core.links import FixedLink, MobileLink
from ..core.des import Sim, Node, AgreementTracker
from ..protocol.modes import table
from ..protocol.endpoint import Endpoint, Config

R7 = {}

# Varredura de potência (run_suite --teto): limita o teto de TX de TODOS os nós de qualquer cenário. Vem do ambiente para
# valer também nos processos filhos. Nunca aumenta um teto que o cenário já fixou mais baixo (a bancada usa 0 e 10 dBm).
TETO_MAX = float(os.environ["LEGUA_TETO_MAX"]) if os.environ.get("LEGUA_TETO_MAX") else None


def teto(c):
    """Teto efetivo de TX em dBm para o valor pedido pelo cenário."""
    return c if TETO_MAX is None else min(c, TETO_MAX)


def r7_km(env):
    from ..core.channel_static import range_km, ANT_GAIN_DBI, CABLE_LOSS_DB
    from ..core.radio import noise_dbm, SNR_THR, PER_OFFSET_DB
    sens = noise_dbm(125, env["noise_rise"]) + SNR_THR[7] + PER_OFFSET_DB
    return range_km(env, 22 + 2 * (ANT_GAIN_DBI - CABLE_LOSS_DB) - sens)


def make_pair(env_id, link, T, seed, cfg=None, profile="BR-2026", cap=28.0, app_interval=60.0,
              tracks=(None, None), log_path=None, xtal="tcxo", clock_ppm=(10.0, -10.0), ext_scale=1.0,
              endpoint_cls=Endpoint):
    env = ENVS[env_id]
    rng = np.random.default_rng(seed)
    modes, base, rec = table(profile)
    cfg = cfg or Config()
    sim = Sim(env, rng, T, {(0, 1): link}, log_path=log_path, ext_scale=ext_scale)
    eps = []
    caps = cap if isinstance(cap, (tuple, list)) else (cap, cap)       # teto de TX por nó (assimétrico se for par)
    caps = tuple(teto(c) for c in caps)
    for nid, peer in ((0, 1), (1, 0)):
        ep = endpoint_cls(nid, peer, modes, base, rec, cfg, rng, env["noise_rise"], caps[nid])
        n = Node(nid, ep, track=tracks[nid], clock_ppm=clock_ppm[nid], xtal=xtal, app_interval=app_interval)
        sim.add(n)
        eps.append(ep)
    sim.tracker = AgreementTracker(0, 1)
    return sim


def summarize(sim):
    e0, e1 = sim.nodes[0].ep, sim.nodes[1].ep
    gen = e0.stats["gerados"] + e1.stats["gerados"]
    dl = len(sim.deliveries)
    lat = [t1 - t0 for (_, _, t0, t1) in sim.deliveries if t0 is not None]
    energy = sim.nodes[0].energy_tx + sim.nodes[1].energy_tx
    st = {k: e0.stats[k] + e1.stats[k] for k in e0.stats}
    ag = sim.tracker.finish(sim.T) if sim.tracker else {}
    modes = {}
    return dict(gerados=gen, entregues=dl, pdr=dl / gen if gen else 0.0,
                energia_mj=energy, mj_por_pacote=energy / dl if dl else None,
                airtime_s=sim.nodes[0].airtime + sim.nodes[1].airtime,
                lat_med_s=float(np.median(lat)) if lat else None,
                lat_p95_s=float(np.percentile(lat, 95)) if lat else None,
                acordo=ag, stats=st, perdas=dict(sim.reason),
                modo_final=(e0.mode.name, e1.mode.name))
