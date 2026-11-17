"""Varreduras de mecanismo (cenários V e S).

V: janela de validação. `k_valid` ACKs confirmam o modo novo, `f_valid` falhas desfazem (rollback), `t_valid` é o
tempo da janela. O P4 (docs/06) mostra que a validação é o que sustenta a âncora tardia; aqui se mede o custo:
PDR, rollbacks por hora (falsos ou não) e desacordo, em enlaces marginais onde o ACK se perde de verdade.

S: descida por silêncio. `t_silence` é quanto o nó espera sem ouvir o par antes de descer um degrau; o intervalo
da aplicação (`app`) decide se esse silêncio é real ou só falta de tráfego (o heartbeat só sai após 60 s).

Mesmas sementes de canal em todas as células; só a configuração muda.
"""
import numpy as np
from ..core.channel_static import ENVS
from ..core.links import FixedLink
from ..protocol.endpoint import Config
from .field import _run_cell

ENV = "urbano_residencial"
DISTS = [2.0, 3.0]


def _grade(escala):
    T = 2 * 3600 if escala == "quick" else 6 * 3600
    seeds = [11, 12] if escala == "quick" else [11, 12, 13, 14, 15]
    return T, seeds


def _cell(d, cfg, T, seeds, app=20.0):
    env = ENVS[ENV]
    mk = lambda s, d=d: FixedLink(env, d, np.random.default_rng(1000 + s), T + 10)
    return _run_cell(ENV, mk, dict(cfg=cfg), T, seeds, app=app)


def validacao_sweep(escala="quick"):
    T, seeds = _grade(escala)
    ks, fs, tvs = [1, 2, 3, 5], [1, 3, 5], [15.0, 45.0, 90.0]
    out = {"ambiente": ENV, "dists_km": DISTS, "k_valid": ks, "f_valid": fs, "t_valid_s": tvs, "T_h": T / 3600,
           "sementes": seeds, "k_f": {}, "t_valid": {}}
    for d in DISTS:
        key = f"{d} km"
        out["k_f"][key] = {f"k{k}/f{f}": _cell(d, Config(k_valid=k, f_valid=f), T, seeds) for k in ks for f in fs}
        out["t_valid"][key] = {f"{t:g} s": _cell(d, Config(t_valid=t), T, seeds) for t in tvs}
    out["nota"] = ("Padrão: k=3, f=3, janela 45 s. Rótulo kK/fF = ACKs para confirmar / falhas para desfazer. "
                   "rollbacks_por_hora conta também os falsos (o modo era bom, mas ACKs se perderam).")
    return out


def silencio_sweep(escala="quick"):
    T, seeds = _grade(escala)
    tss, apps = [30.0, 60.0, 90.0, 180.0, 300.0], [5.0, 20.0, 60.0, 300.0]
    out = {"ambiente": ENV, "dists_km": DISTS, "t_silence_s": tss, "app_s": apps, "T_h": T / 3600,
           "sementes": seeds, "celulas": {}}
    for d in DISTS:
        out["celulas"][f"{d} km"] = {
            f"ts{t:g}": {f"app{a:g}": _cell(d, Config(t_silence=t), T, seeds, app=a) for a in apps} for t in tss}
    out["nota"] = ("Padrão: t_silence = 90 s. app = intervalo entre pacotes da aplicação; com app maior que "
                   "t_silence o silêncio é normal e só o heartbeat (60 s) evita descidas falsas.")
    return out


def estresse_sweep(escala="quick"):
    """Cenário X: três estresses que a calibração real vai exercitar primeiro.

    relogio: erro de relógio dos dois nós (ppm, sinais opostos) × cristal (tcxo ou xtal comum). O instante combinado
      da troca depende de relógios que andam separados.
    assimetria: perda extra só no sentido B->A (dB), com A->B intacto. A margem vale o pior sentido?
    teto_fade: teto de TX simétrico × `fade_k` (margem extra pela variabilidade do SNR).
    Mesmas sementes de canal em todas as células; a coluna `0 dB`/`0 ppm`/`fade_k 0` é a referência."""
    T, seeds = _grade(escala)
    d = 2.0
    out = {"ambiente": ENV, "dist_km": d, "T_h": T / 3600, "sementes": seeds, "relogio": {}, "assimetria": {},
           "teto_fade": {}}
    ppms = [(0.0, 0.0), (10.0, -10.0), (50.0, -50.0), (100.0, -100.0)]
    for xt in ("tcxo", "xtal"):
        for a, b in ppms:
            out["relogio"][f"{xt}/{abs(a):g} ppm"] = _cell_x(d, Config(), T, seeds, xtal=xt, clock_ppm=(a, b))
    for a, b in (ppms[0], ppms[-1]):                      # cristal comum com TX a 14 dBm: sem deriva térmica no modelo
        out["relogio"][f"xtal 14 dBm/{abs(a):g} ppm"] = _cell_x(d, Config(), T, seeds, xtal="xtal", clock_ppm=(a, b),
                                                              cap=(14.0, 14.0))
    for db in (0.0, 3.0, 6.0, 9.0, 12.0):
        out["assimetria"][f"{db:g} dB"] = _cell_x(d, Config(), T, seeds, asym_db={(1, 0): db})
    for cap in (20.0, 24.0, 28.0):
        out["teto_fade"][f"{cap:g} dBm"] = {f"fade_k {k:g}": _cell_x(d, Config(fade_k=k), T, seeds, cap=(cap, cap))
                                            for k in (0.0, 1.0, 2.0)}
    out["nota"] = ("relogio: erro ppm dos nós A e B em sinais opostos (rótulo = módulo). assimetria: perda extra só "
                   "de B para A. teto_fade: teto de TX × fade_k. Referência = primeira coluna de cada grupo. "
                   "No modelo, o cristal comum (xtal) a 28 dBm perde tudo por deriva térmica no pacote (ver B9): falha do "
                   "modelo de cristal, não do protocolo; a 14 dBm a deriva some. Parâmetros do canal e do cristal "
                   "estimados (docs/09 §4).")
    return out


def _cell_x(d, cfg, T, seeds, **kw):
    env = ENVS[ENV]
    mk = lambda s, d=d: FixedLink(env, d, np.random.default_rng(1000 + s), T + 10)
    return _run_cell(ENV, mk, dict(cfg=cfg), T, seeds, app=20.0, **kw)
