"""Cenários de bancada B2-B11 do plano de testes (doc 05, Fase 3), em simulação.

Cada função devolve um dict serializável. 'escala' controla o tamanho da amostra:
quick (minutos) ou full (tamanhos do plano: >=100 pacotes/degrau, >=3000 negociações).
"""
import math
import numpy as np
from dataclasses import replace
from ..core.channel_static import ENVS
from ..core.bench import AttenLink, constant, sawtooth
from ..core.regulatory import BR2026, check_compliance, channel_plan, HopSequence
from ..core.radio import (toa_s, i_tx_ma, VCC, I_RX_MA, drift_tolerance_hz, ldro_on, tsym_s,
                          static_offset_tolerance_hz)
from ..protocol.modes import table, by_name, DATA_BYTES, ACK_BYTES, CTRL_BYTES, HW_MAX_DBM
from ..protocol.endpoint import Config
from ..protocol.variants import locked_factory, negtest_factory
from ..analysis.stats import wilson, rule_of_three, n_for_halfwidth
from .common import make_pair, summarize

BENCH_ENV = "rural_aberto"     # sem ruído extra; G_ext zerado na bancada blindada


def _bench_pair(link, T, seed, cfg=None, factory=None, cap=0.0, app=10.0, xtal="tcxo"):
    sim = make_pair(BENCH_ENV, link, T, seed, cfg=cfg, cap=cap, app_interval=app, xtal=xtal,
                    ext_scale=0.0, **({"endpoint_cls": factory} if factory else {}))
    sim.lbt = True
    return sim


# ------------------------------------------------------------------ B2
def b2_pdr_vs_attenuation(escala="quick", seed=1):
    """Curva PDR x atenuação por modo travado; potência de bancada 0 dBm."""
    modes, base, rec = table()
    names = ["SF7/125/FH", "SF9/125/FH", "SF9/125/CR48/FH", "SF10/125/FH", "SF11/250/FH",
             "SF12/500"]
    n_pkt = 100 if escala == "quick" else 300
    out = {}
    for nm in names:
        m = by_name(modes + [base, rec], nm)
        thr = -(m.sens() - 0.0) - 40.0          # atenuação do centro da curva a 0 dBm
        curve = []
        for att in np.arange(thr - 6, thr + 5, 1.0):
            T = n_pkt * 6.0 + 60
            sim = _bench_pair(AttenLink(constant(att), np.random.default_rng(seed)), T, seed,
                              factory=locked_factory(m), cap=0.0, app=6.0)
            sim.nodes[1].app_interval = None     # só um sentido de dados
            sim.start()
            sim.run()
            s = summarize(sim)
            k, n = s["entregues"], s["gerados"]
            curve.append({"atenuacao_db": float(att + 40.0), "pdr": k / n if n else 0.0, "n": n,
                          "ic95": wilson(k, n)})
        # interpolação dos pontos de 90% e 50%
        def at(level):
            xs = [c["atenuacao_db"] for c in curve]
            ys = [c["pdr"] for c in curve]
            for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
                if y0 >= level > y1:
                    return x0 + (x1 - x0) * (y0 - level) / (y0 - y1)
            return None
        out[nm] = {"curva": curve, "perda_max_90_db": at(0.9), "perda_max_50_db": at(0.5),
                   "toa_dados_ms": round(1000 * m.toa(DATA_BYTES), 1)}
    g = out
    cr_gain = None
    if g["SF9/125/FH"]["perda_max_90_db"] and g["SF9/125/CR48/FH"]["perda_max_90_db"]:
        cr_gain = g["SF9/125/CR48/FH"]["perda_max_90_db"] - g["SF9/125/FH"]["perda_max_90_db"]
    return {"modos": out, "ganho_cr48_sf9_db": cr_gain,
            "nota": "Curva de PER é modelo (centro 2,5 dB acima do limiar do datasheet); "
                    "a bancada real substitui estes valores."}


# ------------------------------------------------------------------ B3 / B4
def _neg_runs(n_target, p_loss_ctrl, p_loss_data, seed, reboot_rate_h=0.0, persist="validation",
              flash=True, clock_jump=False, T_run=1800.0, att=70.0):
    modes, base, rec = table()
    pair = (by_name(modes, "SF7/500"), by_name(modes, "SF8/500"))
    cfg = Config(cooldown_up=30.0, n_up=3, persist_at=persist, neg_backoff0=10.0, neg_backoff_max=60.0)
    agg = {"negociacoes": 0, "validadas": 0, "rollbacks": 0, "desacordos": 0, "desacordo_s": [],
           "abertos_ao_fim": 0, "tempo_validar_s": [], "energia_ctrl_mj": 0.0, "airtime_ctrl_s": 0.0,
           "falhas_neg": 0, "reboots": 0, "max_episodio_s": 0.0}
    run = 0
    rng0 = np.random.default_rng(seed)
    while agg["negociacoes"] < n_target:
        run += 1
        rs = int(rng0.integers(1 << 30))
        link = AttenLink(constant(att), np.random.default_rng(rs))
        sim = _bench_pair(link, T_run + 600, rs, cfg=cfg, factory=negtest_factory(pair), cap=10.0, app=20.0)
        rr = np.random.default_rng(rs + 1)

        def drop(f, sn, rn, t, rr=rr):
            if f.kind in ("PROPOSE", "VOTE", "COMMIT"):
                return rr.random() < p_loss_ctrl
            return rr.random() < p_loss_data
        sim.drop_rules.append(drop)
        # reinícios aleatórios (inclusive durante a validação)
        if reboot_rate_h > 0:
            t = 0.0
            while True:
                t += rr.exponential(3600.0 / reboot_rate_h)
                if t > T_run:
                    break
                node = sim.nodes[int(rr.integers(0, 2))]

                def do_reboot(node=node, sim=sim):
                    agg["reboots"] += 1
                    node.txq = node.txq[:1] if node.busy_until > sim.now else []
                    sim.apply(node, node.ep.reboot(sim.now))
                    sim.wake(node)
                sim.at(t, do_reboot)
        if clock_jump:
            def jump(sim=sim, rr=rr):
                sim.nodes[1].clock_off += rr.uniform(-0.05, 0.05)
            for k in range(int(T_run // 300)):
                sim.at(300.0 * (k + 1), jump)
        # fase quieta no fim: sem perdas, sem reboots, para medir desacordo que não se resolve
        def quiet(sim=sim):
            sim.drop_rules.clear()
        sim.at(T_run, quiet)
        sim.start()
        sim.run()
        s = summarize(sim)
        st = s["stats"]
        ag = s["acordo"]
        agg["negociacoes"] += st["trocas"]
        agg["validadas"] += st["neg_ok"] // 1
        agg["rollbacks"] += st["rollbacks"]
        agg["falhas_neg"] += st["neg_fail"]
        agg["desacordos"] += ag["episodios"]
        agg["max_episodio_s"] = max(agg["max_episodio_s"], ag["max_episodio_s"])
        agg["desacordo_s"].append(ag["desacordo_s"])
        if ag["em_aberto_s"] > 0:
            agg["abertos_ao_fim"] += 1
        agg["tempo_validar_s"] += ag["tempo_ate_validar_s"]
        ctrl_toa = pair[0].toa(CTRL_BYTES)
        agg["energia_ctrl_mj"] += st["tx_ctrl"] * VCC * i_tx_ma(10.0) * ctrl_toa
        agg["airtime_ctrl_s"] += st["tx_ctrl"] * ctrl_toa
        if run > 2000:
            break
    n = max(1, agg["negociacoes"])
    tv = agg["tempo_validar_s"]
    return {"execucoes": run, "negociacoes": agg["negociacoes"], "rollbacks": agg["rollbacks"],
            "falhas_de_negociacao": agg["falhas_neg"], "reboots": agg["reboots"],
            "episodios_desacordo": agg["desacordos"],
            "desacordo_permanente": agg["abertos_ao_fim"],
            "limite_sup_95_desacordo_permanente": rule_of_three(n) if agg["abertos_ao_fim"] == 0 else None,
            "max_episodio_s": round(agg["max_episodio_s"], 1),
            "tempo_ate_validar_med_s": round(float(np.median(tv)), 2) if tv else None,
            "tempo_ate_validar_p95_s": round(float(np.percentile(tv, 95)), 2) if tv else None,
            "energia_ctrl_por_neg_mj": round(agg["energia_ctrl_mj"] / n, 2),
            "airtime_ctrl_por_neg_ms": round(1000 * agg["airtime_ctrl_s"] / n, 1)}


def b3_control_cost(escala="quick", seed=2):
    n = 150 if escala == "quick" else 1000
    rows = []
    for p in (0.0, 0.1, 0.2, 0.3):
        r = _neg_runs(n, p, p, seed + int(100 * p))
        r["perda"] = p
        rows.append(r)
    return {"por_perda": rows, "nota": "Par na bancada (SF7/500 <-> SF8/500, 10 dBm), negociação "
                                       "forçada a cada 30 s; perda injetada em todos os quadros."}


def b4_fault_injection(escala="quick", seed=3):
    n = 300 if escala == "quick" else 3000
    cases = {
        "perdas_controle_30%": dict(p_loss_ctrl=0.3, p_loss_data=0.05),
        "perdas_+_reboots": dict(p_loss_ctrl=0.2, p_loss_data=0.1, reboot_rate_h=6.0),
        "perdas_+_reboots_+_relogio": dict(p_loss_ctrl=0.2, p_loss_data=0.1, reboot_rate_h=6.0, clock_jump=True),
        "ancora_gravada_no_commit": dict(p_loss_ctrl=0.2, p_loss_data=0.1, reboot_rate_h=6.0, persist="commit"),
    }
    out = {}
    for i, (k, kw) in enumerate(cases.items()):
        out[k] = _neg_runs(n, seed=seed + 17 * i, **kw)
    return out


# ------------------------------------------------------------------ B5
def b5_rendezvous(escala="quick", seed=4):
    """Nó novo escuta um canal fixo ('stay') da sequência de 35 canais do modo base."""
    rng = np.random.default_rng(seed)
    n = 300 if escala == "quick" else 2000
    hs = HopSequence("base:125", 35, plan_size=92)
    res = {}
    for beacon_s in (0.4, 2.0, 10.0):
        for p_loss in (0.0, 0.2):
            ts = []
            for _ in range(n):
                ch = hs.seq[int(rng.integers(0, 35))]
                t = rng.uniform(0, beacon_s)
                off = rng.uniform(0, 14.0)
                while True:
                    if hs.channel(t + off) == ch and rng.random() > p_loss:
                        break
                    t += beacon_s * rng.uniform(0.9, 1.1) if beacon_s > 0.4 else beacon_s
                    if t > 1e5:
                        break
                ts.append(t)
            ts = np.array(ts)
            res[f"beacon_{beacon_s}s_perda_{int(p_loss * 100)}%"] = {
                "media_s": round(float(ts.mean()), 1), "p95_s": round(float(np.percentile(ts, 95)), 1),
                "max_s": round(float(ts.max()), 1),
                "duty_beacon_%": round(100 * toa_s(10, 125, CTRL_BYTES) / beacon_s, 1)}
    return {"resultados": res,
            "nota": "Pior caso de 14 s (35 x 0,4 s) só vale se a rede emitir em toda fatia; com beacon "
                    "a cada B s, o tempo esperado de entrada é ~35 x B / 2 e o pior caso ~35 x B."}


# ------------------------------------------------------------------ B7
def b7_security(escala="quick", seed=5):
    modes, base, rec = table()
    T = 4 * 3600 if escala == "quick" else 24 * 3600
    out = {}
    for nome, kw in {"sem_ataque": {}, "replay_e_forjado": {"forge": True},
                     "jammer_reativo_validacao": {"jam": 0.9},
                     "jammer_sem_alarme": {"jam": 0.9, "alarm": 10 ** 9}}.items():
        cfg = Config(cooldown_up=120.0, n_up=5)
        if "alarm" in kw:
            cfg = replace(cfg, rollback_alarm=kw["alarm"])
        link = AttenLink(constant(75.0), np.random.default_rng(seed))
        sim = _bench_pair(link, T, seed, cfg=cfg, cap=10.0, app=20.0)
        rr = np.random.default_rng(seed + 9)
        if kw.get("jam"):
            def jam(f, sn, rn, t, rr=rr, p=kw["jam"]):
                return sn.ep.state == "VALIDANDO" and f.kind in ("DATA", "ACK") and rr.random() < p
            sim.drop_rules.append(jam)
        if kw.get("forge"):
            from ..protocol.endpoint import Frame
            captured = {}

            def attack(sim=sim):
                ep = sim.nodes[1].ep
                # replay: reenvia um COMMIT com contador antigo; forjado: PROPOSE sem MIC válido
                f1 = Frame("COMMIT", 0, 1, ep.mode, 10.0, ctr=1, body={"cand": "SF12/500", "instant": sim.now + 1})
                f2 = Frame("PROPOSE", 0, 1, ep.mode, 10.0, ctr=10 ** 9, auth=False, body={"cand": "SF12/500"})
                for f in (f1, f2):
                    sim.apply(sim.nodes[1], ep.on_rx(f, -80.0, 20.0, sim.now))
                sim.at(sim.now + 60.0, attack)
            sim.at(120.0, attack)
        sim.start()
        sim.run()
        s = summarize(sim)
        st = s["stats"]
        out[nome] = {"pdr": round(s["pdr"], 4), "rollbacks": st["rollbacks"], "alarmes": st["alarmes"],
                     "rejeitados": st["rejeitados"], "trocas": st["trocas"],
                     "energia_por_pacote_mj": round(s["mj_por_pacote"] or 0, 2),
                     "modo_final": s["modo_final"]}
    return out


# ------------------------------------------------------------------ B8, B9, B10 (analíticos)
def b8_energy_table(escala="quick"):
    modes, base, rec = table()
    rows = []
    for m in modes + [base]:
        for p in (0, 10, 14, 17, 22, 25, 28):
            if p > m.cap:
                continue
            rows.append({"modo": m.name, "p_dbm": p, "toa_ms": round(1000 * m.toa(DATA_BYTES), 1),
                         "mj_dados": round(m.energy_mj(p), 2),
                         "mj_dados+ack": round(m.energy_mj(p) + m.energy_mj(p, ACK_BYTES), 2)})
    states = {"TX 28 dBm (FEM)": i_tx_ma(28), "TX 22 dBm": i_tx_ma(22), "TX 14 dBm": i_tx_ma(14),
              "RX (DC-DC)": I_RX_MA, "CAD (aprox.)": 2.8, "sono profundo ESP32-S3 (aprox.)": 0.02}
    return {"por_modo": rows, "correntes_mA": states,
            "nota": "Curva de corrente aproximada; B8 na bancada substitui (PPK2 até 1 A; shunt+osciloscópio "
                    "para TX acima de ~25 dBm)."}


def b9_drift(escala="quick"):
    modes, base, rec = table()
    rows = []
    for m in modes + [base]:
        toa = m.toa(DATA_BYTES)
        for xtal, rate in (("tcxo", 5.0), ("xtal", 400.0)):
            for p in (14, 22, 28):
                drift = rate * max(0, p - 14) / 14 * toa
                for ldro in ("auto", "forcado"):
                    L = 16 if (ldro == "forcado" or ldro_on(m.sf, m.bw)) else 1
                    tol = L * m.bw * 1e3 / (3 * 2 ** m.sf)
                    rows.append({"modo": m.name, "cristal": xtal, "p_dbm": p, "ldro": ldro,
                                 "deriva_hz": round(drift, 1), "tolerancia_hz": round(tol, 1),
                                 "ok": drift <= tol})
    falhas = [r for r in rows if not r["ok"] and r["ldro"] == "auto"]
    return {"linhas": rows, "falhas_com_ldro_auto": falhas,
            "nota": "Taxas de deriva térmica estimadas (TCXO ~5 Hz/s, XTAL ~400 Hz/s em TX de alta potência); "
                    "confirmar se a Heltec V4 tem TCXO e medir FEI em B9."}


def b10_cad_timing(escala="quick"):
    rows = []
    for bw in (125, 250, 500):
        for sf in range(7, 13):
            ts = tsym_s(sf, bw)
            rows.append({"sf": sf, "bw": bw, "cad_ms": round(1000 * 2 * ts, 2)})
    scan = {f"varredura SF7-12 @{bw}": round(sum(r["cad_ms"] for r in rows if r["bw"] == bw), 1)
            for bw in (125, 250, 500)}
    return {"cad_por_modo": rows, "varredura_ms": scan,
            "nota": "Só o tempo de CAD (2 símbolos) é modelado; probabilidades de detecção e falso "
                    "alarme por SF no SX1262 não têm dado publicado e são o alvo de B10 na bancada."}


# ------------------------------------------------------------------ B11
def b11_compliance(escala="quick", seed=6):
    """Conformidade dos registros de TX gerados pelo simulador."""
    modes, base, rec = table()
    T = 2 * 3600 if escala == "quick" else 12 * 3600
    out = {}
    cases = {"AdaptLoRa (perfil BR-2026)": None,
             "Fixo SF10/125 com salto": by_name([base], base.name),
             "Fixo SF12/500 digital": by_name(modes, "SF12/500")}
    for nome, mode in cases.items():
        link = AttenLink(constant(85.0), np.random.default_rng(seed))
        sim = _bench_pair(link, T, seed, cfg=Config(), cap=28.0, app=15.0,
                          factory=locked_factory(mode) if mode else None)
        sim.start()
        sim.run()
        rep = check_compliance(sim.txlog, BR2026)
        out[nome] = rep
    # preset de malha comunitário: LongFast (SF11/250) em canal fixo a 22 dBm, quadro de 32 B
    lf = [{"t": i * 30.0, "dur": toa_s(11, 250, 32), "bw": 250, "freq": ("fix", 250, 3), "p_dbm": 22.0,
           "fhss": False, "n_hop": 0, "node": 0} for i in range(int(T / 30))]
    out["LongFast fixo 22 dBm (estilo Meshtastic)"] = check_compliance(lf, BR2026)
    lf_hop = [dict(r, fhss=True, n_hop=1) for r in lf]
    out["LongFast tratado como salto com 1 canal"] = check_compliance(lf_hop, BR2026)
    return out
