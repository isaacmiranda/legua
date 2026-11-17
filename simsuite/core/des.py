"""Simulador de eventos discretos para enlaces P2P com a Légua de referência.

O rádio é half-duplex e só recebe no modo e na sequência de salto configurados.
Cada quadro passa por: casamento de modo e canal (relógios com deriva), Doppler
estático e dinâmico, curva de PER, colisões com captura (mesmo SF: SIR >= 6 dB;
SF diferente: SIR >= -16 dB), interferência externa ALOHA e regras de falha
injetadas. Gera telemetria no mesmo formato JSONL planejado para o hardware.
"""
import heapq
import json
import math
import itertools
from ..core.radio import (CR_GAIN_DB, noise_dbm, p_demod, i_tx_ma, VCC, I_RX_MA, static_offset_tolerance_hz,
                          drift_tolerance_hz, doppler_hz, ldro_on, tsym_s)
from ..core.channel_static import p_ext_ok
from ..core.regulatory import HopSequence
from ..protocol.modes import ACK_BYTES

LAMBDA = 299_792_458.0 / 915e6
SAME_SF_CAPTURE_DB = 6.0
DIFF_SF_ISOLATION_DB = 16.0     # Croce et al.: 8-25 dB; valor médio (APROX)
TURNAROUND_S = 0.006
FLASH_STALL_S = 0.08            # apagar setor da flash do ESP32 bloqueia a CPU (APROX)
XTAL_DRIFT_HZ_S = {"tcxo": 5.0, "xtal": 400.0}   # deriva térmica em TX longo (APROX, B9)


class Node:
    def __init__(self, nid, endpoint=None, track=None, clock_ppm=10.0, xtal="tcxo", app_interval=60.0,
                 app_jitter=0.2):
        self.id = nid
        self.ep = endpoint
        self.track = track
        self.ppm = clock_ppm
        self.clock_off = 0.0
        self.xtal = xtal
        self.rx_mode = endpoint.mode if endpoint else None
        self.busy_until = 0.0
        self.deaf_until = 0.0
        self.txq = []
        self.energy_tx = 0.0
        self.airtime = 0.0
        self.app_interval = app_interval
        self.app_jitter = app_jitter
        self.gen_time = {}

    def local(self, t):
        return t + self.clock_off + self.ppm * 1e-6 * t


class Sim:
    def __init__(self, env, rng, T, links, log_path=None, profile_name="BR-2026", ext_scale=1.0):
        self.env = env
        self.rng = rng
        self.T = T
        self.now = 0.0
        self.q = []
        self.cnt = itertools.count()
        self.nodes = {}
        self.links = links             # dict (a, b) com a < b
        self.active = []               # transmissões no ar
        self.hops = {}
        self.txlog = []
        self.log = open(log_path, "w") if log_path else None
        self.drop_rules = []
        self.ext_scale = ext_scale
        self.asym_db = {}              # {(src, dst): dB extras de perda só nesse sentido (enlace assimétrico)}
        self.deliveries = []           # (src, seq, t_gen, t_rx)
        self.tracker = None
        self.reason = {}
        self.lbt = True

    # ------------------------------------------------------------- infra
    def add(self, node):
        self.nodes[node.id] = node

    def link(self, a, b):
        return self.links[(a, b) if a < b else (b, a)]

    def at(self, t, fn, *args):
        heapq.heappush(self.q, (t, next(self.cnt), fn, args))

    def hopseq(self, key, mode):
        k = (key, mode.bw)
        if k not in self.hops:
            self.hops[k] = HopSequence(f"{key}:{mode.bw}", mode.n_hop or 35, plan_size=92 if mode.bw < 250 else 46)
        return self.hops[k]

    def hopkey(self, node, mode, peer):
        if node.ep is not None and mode == node.ep.base:
            return "base"
        a, b = sorted((node.id, peer))
        return f"L{a}-{b}"

    def channel(self, node, mode, peer, t_local):
        if not mode.fhss:
            a, b = sorted((node.id, peer))
            return ("fix", mode.bw, (a * 7 + b * 13) % 23)
        hs = self.hopseq(self.hopkey(node, mode, peer), mode)
        return ("hop", mode.bw, hs.channel(t_local))

    def emit(self, rec):
        if self.log:
            self.log.write(json.dumps(rec) + "\n")

    # ------------------------------------------------------------- ações
    def apply(self, node, acts):
        for a in acts:
            k = a[0]
            if k == "tx":
                self.send(node, a[1])
            elif k == "rx":
                node.rx_mode = a[1]
                # quadros ainda não iniciados em outro modo são descartados
                keep = node.txq[:1] if node.busy_until > self.now else []
                node.txq = keep + [f for f in node.txq[len(keep):] if f.mode == a[1]]
            elif k == "persist":
                node.deaf_until = max(node.deaf_until, self.now + FLASH_STALL_S)
                self.emit({"v": 1, "t": round(self.now, 3), "node": node.id, "ev": "persist", **a[1]})
            elif k == "log":
                self.emit({"v": 1, "t": round(self.now, 3), "node": node.id, **a[1]})
                if self.tracker:
                    self.tracker.on_log(node, a[1], self.now)

    def send(self, node, f):
        node.txq.append(f)
        if node.busy_until <= self.now and len(node.txq) == 1:
            self._start_next(node)

    def _start_next(self, node):
        if not node.txq:
            return
        f = node.txq[0]
        toa = f.mode.toa(f.nbytes)
        t0 = max(self.now, node.busy_until) + TURNAROUND_S
        if f.mode.fhss:
            hs = self.hopseq(self.hopkey(node, f.mode, f.dst if f.dst >= 0 else f.src), f.mode)
            tl = node.local(t0)
            t0 += hs.fit_start(tl, toa) - tl
        node.busy_until = t0 + toa
        self.at(t0, self._tx_begin, node, f, toa)

    def _tx_begin(self, node, f, toa, tries=0):
        peer = f.dst if f.dst >= 0 else f.src
        ch = self.channel(node, f.mode, peer, node.local(self.now))
        # escuta antes de transmitir (CAD): adia se houver transmissão audível no canal
        if self.lbt and tries < 4 and any(a["ch"] == ch and a["t1"] > self.now and a["src"] != node.id
                                          and self._audible(a, node) for a in self.active):
            back = self.rng.uniform(0.05, 0.6) + toa
            node.busy_until = self.now + back + toa
            if f.mode.fhss:
                hs = self.hopseq(self.hopkey(node, f.mode, peer), f.mode)
                tl = node.local(self.now + back)
                back += hs.fit_start(tl, toa) - tl
                node.busy_until = self.now + back + toa
            self.at(self.now + back, self._tx_begin, node, f, toa, tries + 1)
            return
        tx = {"src": node.id, "f": f, "t0": self.now, "t1": self.now + toa, "ch": ch, "p": f.p_dbm}
        self.active.append(tx)
        node.energy_tx += VCC * i_tx_ma(f.p_dbm) * toa
        node.airtime += toa
        self.txlog.append({"t": self.now, "dur": toa, "bw": f.mode.bw, "freq": ch, "p_dbm": f.p_dbm,
                           "fhss": f.mode.fhss, "n_hop": f.mode.n_hop, "node": node.id})
        self.emit({"v": 1, "t": round(self.now, 3), "node": node.id, "ev": "tx", "tipo": f.kind,
                   "seq": f.seq, "modo": f.mode.name, "sf": f.mode.sf, "bw": f.mode.bw, "cr": f.mode.cr,
                   "pwr": round(f.p_dbm, 1), "ch": str(ch[2]), "nb": f.nbytes, "fh": f.mode.fhss, "hb": bool(f.body.get("hb")),
                   "estado": getattr(node.ep, "state", None)})
        self.at(self.now + toa, self._tx_end, node, tx)

    def _tx_end(self, node, tx):
        f = tx["f"]
        node.txq.pop(0)
        if node.ep is not None:
            self.apply(node, node.ep.on_tx_done(f, self.now))
        for rid, rn in self.nodes.items():
            if rid == node.id:
                continue
            self._receive(rn, node, tx)
        self.active = [a for a in self.active if a["t1"] > self.now - 5.0]
        if node.txq:
            self._start_next(node)
        self.wake(node)

    def _receive(self, rn, sn, tx):
        f = tx["f"]
        if f.dst not in (rn.id, -1) and not getattr(rn, "promiscuous", False):
            return
        why = None
        if rn.rx_mode != f.mode:
            why = "modo"
        elif any(a["src"] == rn.id and a["t0"] < tx["t1"] and a["t1"] > tx["t0"] for a in self.active):
            why = "half_duplex"
        elif rn.deaf_until > tx["t0"]:
            why = "flash"
        else:
            peer = sn.id
            ch_rx = self.channel(rn, f.mode, peer, rn.local(tx["t0"]))
            if ch_rx != tx["ch"]:
                why = "canal"
        if why is None:
            lk = self.link(sn.id, rn.id)
            rssi = lk.rx_dbm(tx["t0"], f.p_dbm) - self.asym_db.get((sn.id, rn.id), 0.0)
            snr = rssi - noise_dbm(f.mode.bw, self.env["noise_rise"])
            p_ok = p_demod(snr + CR_GAIN_DB[f.mode.cr], f.mode.sf) * \
                p_ext_ok(self.env, tx["t1"] - tx["t0"], self.ext_scale, f.mode.cr)
            # Doppler e deriva
            vr, ar = lk.radial(tx["t0"])
            dur = tx["t1"] - tx["t0"]
            if abs(doppler_hz(vr)) > static_offset_tolerance_hz(f.mode.bw):
                p_ok = 0.0
                why = "doppler"
            drift = (abs(ar) / LAMBDA + XTAL_DRIFT_HZ_S[sn.xtal] * max(0, f.p_dbm - 14) / 14) * dur
            if drift > drift_tolerance_hz(f.mode.sf, f.mode.bw):
                p_ok = 0.0
                why = "deriva"
            # colisões
            for a in self.active:
                if a is tx or a["src"] == rn.id or a["ch"] != tx["ch"]:
                    continue
                if a["t0"] < tx["t1"] and a["t1"] > tx["t0"]:
                    li = self.link(a["src"], rn.id)
                    pi = li.rx_dbm(a["t0"], a["p"]) - self.asym_db.get((a["src"], rn.id), 0.0)
                    sir = rssi - pi
                    need = SAME_SF_CAPTURE_DB if a["f"].mode.sf == f.mode.sf else -DIFF_SF_ISOLATION_DB
                    if getattr(a["f"], "kind", "") == "JAM":
                        need = SAME_SF_CAPTURE_DB
                    if sir < need:
                        p_ok = 0.0
                        why = "colisao"
            for rule in self.drop_rules:
                if rule(f, sn, rn, tx["t0"]):
                    p_ok = 0.0
                    why = "injetada"
            if self.rng.random() < p_ok:
                rn.clock_off = sn.clock_off + (sn.ppm - rn.ppm) * 1e-6 * self.now  # ressincroniza
                if f.kind == "DATA" and not f.body.get("hb"):
                    k = (sn.id, f.seq)
                    if k not in rn.__dict__.setdefault("_seen", set()):
                        rn._seen.add(k)
                        self.deliveries.append((sn.id, f.seq, sn.gen_time.get(f.seq), self.now))
                self.emit({"v": 1, "t": round(self.now, 3), "node": rn.id, "ev": "rx", "tipo": f.kind,
                           "src": sn.id, "seq": f.seq, "modo": f.mode.name, "rssi": round(rssi, 1),
                           "snr": round(snr, 1)})
                if rn.ep is not None:
                    self.apply(rn, rn.ep.on_rx(f, rssi, snr, self.now))
                    self.wake(rn)
                return
            why = why or "per"
        self.reason[why] = self.reason.get(why, 0) + 1

    def _audible(self, a, node):
        try:
            lk = self.link(a["src"], node.id)
        except KeyError:
            return False
        rssi = lk.gain_db(a["t0"]) + a["p"]
        return rssi > noise_dbm(a["f"].mode.bw, self.env["noise_rise"]) + (-12.0)

    # ------------------------------------------------------------- tempo
    def wake(self, node):
        if node.ep is None:
            return
        d = node.ep.next_deadline()
        if d is None or d >= self.T:
            return
        d = max(d, self.now + 0.005)
        pend = node.__dict__.setdefault("_wakes", set())
        if any(abs(x - d) < 1e-7 for x in pend):
            return
        pend.add(d)
        self.at(d, self._timer, node, d)

    def _timer(self, node, d):
        node.__dict__.get("_wakes", set()).discard(d)
        sec = int(self.now)
        if node.__dict__.get("_tsec") == sec:
            node._tcount += 1
            if node._tcount > 500:
                self.reason["laco_timer"] = self.reason.get("laco_timer", 0) + 1
                node._tcount = 0
                self.at(self.now + 1.0, self._timer, node, self.now + 1.0)
                return
        else:
            node._tsec, node._tcount = sec, 0
        if node.ep is None:
            return
        if node.track is not None:
            node.ep.set_speed(node.track.speed_at(self.now))
        self.apply(node, node.ep.on_timer(self.now))
        self.wake(node)

    def _app(self, node):
        if node.ep is not None:
            node.gen_time[node.ep.seq + 1] = self.now
            self.apply(node, node.ep.on_app(self.now))
            self.wake(node)
        nxt = self.now + node.app_interval * (1 + node.app_jitter * (2 * self.rng.random() - 1))
        if nxt < self.T:
            self.at(nxt, self._app, node)

    def start(self):
        for n in self.nodes.values():
            if n.ep is not None:
                n.rx_mode = n.ep.mode
                self.wake(n)
                if n.app_interval:
                    self.at(self.rng.uniform(1, n.app_interval), self._app, n)

    def run(self, until=None):
        until = until or self.T
        while self.q and self.q[0][0] <= until:
            t, _, fn, args = heapq.heappop(self.q)
            self.now = t
            fn(*args)
            if self.tracker:
                self.tracker.sample(self)
        self.now = until
        if self.log:
            self.log.close()
            self.log = None


class AgreementTracker:
    """Mede desacordo entre as duas pontas (modo diferente) e episódios."""

    def __init__(self, a, b):
        self.a, self.b = a, b
        self.last_t = 0.0
        self.dis_since = None
        self.episodes = []
        self.dis_time = 0.0
        self.commits = []
        self._prop_t = None

    def sample(self, sim):
        ea, eb = sim.nodes[self.a].ep, sim.nodes[self.b].ep
        agree = ea.mode == eb.mode
        if not agree and self.dis_since is None:
            self.dis_since = sim.now
        elif agree and self.dis_since is not None:
            if sim.now - self.dis_since > 0.5:        # ignora a troca simultânea no instante
                self.episodes.append(sim.now - self.dis_since)
            self.dis_since = None
        self.last_t = sim.now

    def on_log(self, node, rec, now):
        if rec.get("ev") == "propose":
            self._prop_t = now
        elif rec.get("ev") == "validado" and self._prop_t is not None and node.ep.role_a:
            self.commits.append(now - self._prop_t)
            self._prop_t = None

    def finish(self, T):
        open_ep = (T - self.dis_since) if self.dis_since is not None else 0.0
        return {"episodios": len(self.episodes) + (1 if open_ep else 0),
                "desacordo_s": sum(self.episodes) + open_ep,
                "max_episodio_s": max(self.episodes + [open_ep]) if (self.episodes or open_ep) else 0.0,
                "em_aberto_s": open_ep,
                "tempo_ate_validar_s": self.commits}
