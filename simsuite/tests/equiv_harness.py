"""Equivalência entre `simsuite/protocol/endpoint.py` e o núcleo C (core/src/endpoint.c).

Um DES mínimo de dois nós, com canal determinístico, dirige cada ponta por um adaptador com a mesma interface:
  PyAdapter  o `Endpoint` do Python, atrás do formato de fio real (`wire.py`): os quadros viram bytes e voltam;
  CAdapter   o núcleo C, carregado como biblioteca (core/build/liblegua_shim.so) via ctypes.
O mesmo cenário roda com os quatro pares (Py-Py, C-C, Py-C, C-Py). Os rastros devem ser idênticos: mesmos
quadros byte a byte (inclui contador, MIC, potência e velocidade), mesmas trocas de modo, mesmas gravações em
NVM e mesmas estatísticas. Py-C e C-Py provam também a interoperabilidade do formato de fio.

Concessões documentadas (docs/09 §8): tempos em ms inteiros (o núcleo C usa ms); tempo no ar arredondado ao ms;
sorteios de recuo por um xorshift igual nos dois lados; o canal decide a entrega pelo modo e pela curva de PER
(sem salto de canal nem colisão de terceiros); perfil sem `fade_k`.
"""
import ctypes
import heapq
import math
import os
import random
from dataclasses import replace

from ..core.radio import p_demod, noise_dbm, CR_GAIN_DB
from ..protocol import wire
from ..protocol.endpoint import (Endpoint, Config, Frame, BASE, DATA, NEG, PEND, VALID, RECOV)
from ..protocol.modes import table, toa_us_int

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.path.join(RAIZ, "core", "build", "liblegua_shim.so")

MODES, BASE_MODE, REC_MODE = table("BR-2026")
STATE_CODE = {BASE: 0, DATA: 1, NEG: 2, PEND: 3, VALID: 4, RECOV: 5}
REASON_CODE = {"troca": 1, "falhas": 2, "silencio": 3, "silencio_rec": 4,
               "validacao_falhou": 5, "validacao_expirou": 6}
STATS = ["trocas", "rollbacks", "degradacoes", "quedas_base", "neg_ok", "neg_fail", "neg_recusa",
         "desc_silencio", "alarmes", "rejeitados", "tx_ctrl", "entregues", "gerados", "perdidos",
         "duplicados", "acked", "tx", "alarmes_mic"]       # ordem de legua_stats (core/include/legua/legua.h)
TURNAROUND_MS = 6
ACK_BYTES, CTRL_BYTES, DATA_BYTES = 14, 16, 24

LOG_CODES = {8: "modo", 9: "propose", 10: "neg_falhou", 11: "validado", 12: "commit_rx", 13: "alarme",
             14: "alarme_mic", 15: "chave", 16: "rej_chave", 17: "ctr_fim"}
LOG_REJ = {1, 2, 3, 16}


def mode_id_of(m):
    return wire.mode_id(m.sf, int(m.bw), m.cr, m.fhss)


MODE_BY_ID = {mode_id_of(m): m for m in MODES}
NAME_ID = {m.name: mode_id_of(m) for m in MODES}


class XorRng:
    """xorshift32: o mesmo gerador de core/tests/testenv.h."""

    def __init__(self, seed):
        self.s = seed or 1

    def next(self):
        x = self.s
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.s = x
        return x

    def uniform(self, a, b):
        """Como o núcleo C: ms inteiros, lo + (hi-lo) x r32 >> 32. Fatores (0,7 a 1,3) viram milésimos."""
        lo, hi = round(a * 1000), round(b * 1000)
        return (lo + (((hi - lo) * self.next()) >> 32)) / 1000.0


def ceil_ms(sec):
    return int(math.ceil(sec * 1000 - 1e-6))


# ------------------------------------------------------------------ parâmetros
_PARAM_MS = {"cooldown_up": "cooldown_up_ms", "cooldown_back": "cooldown_back_ms", "hb_interval": "hb_interval_ms",
             "t_silence": "t_silence_ms", "t_recovery": "t_recovery_ms", "t_valid": "t_valid_ms",
             "vote_timeout": "vote_timeout_ms", "instant_delay": "instant_delay_ms",
             "hello_interval": "hello_interval_ms", "neg_backoff0": "neg_backoff0_ms",
             "neg_backoff_max": "neg_backoff_max_ms", "mic_fail_window": "mic_fail_window_ms",
             "mic_fail_hold": "mic_fail_hold_ms"}
_PARAM_PLAIN = ["margin_target", "margin_up", "ladder_step", "max_budget_jump", "ema_a", "v_freeze",
                "snr_std_freeze", "fade_k", "fade_window", "n_up", "fail_streak_degrade", "retries", "k_valid", "f_valid",
                "rollback_alarm", "power_control", "mobile", "silence_descent", "validation", "mic_fail_n"]


def c_params(cfg):
    out = {v: round(getattr(cfg, k) * 1000) for k, v in _PARAM_MS.items()}
    out.update({k: float(getattr(cfg, k)) for k in _PARAM_PLAIN})
    out["ladder_recovery_only"] = 1 if cfg.ladder == "recuperacao" else 0
    out["persist_at_commit"] = 1 if cfg.persist_at == "commit" else 0
    return out


# ------------------------------------------------------------------ adaptador Python
def frame_to_raw(f, speed_q):
    """Frame do `Endpoint` -> bytes do formato v0 (docs/07), com as quantizações do fio."""
    t = {"HELLO": wire.T_HELLO, "DATA": wire.T_DATA, "ACK": wire.T_ACK, "PROPOSE": wire.T_PROPOSE,
         "VOTE": wire.T_VOTE, "COMMIT": wire.T_COMMIT}[f.kind]
    b = f.body
    sp = speed_q(b.get("v", 0.0))
    flags = 0
    if t == wire.T_DATA:
        flags = wire.F_ACKREQ
        dfl = (1 if b.get("val") else 0) | (2 if b.get("hb") else 0) | ((int(round(f.p_dbm)) + 9) << 2)
        body = bytes([f.seq & 0xFF, dfl, sp]) + bytes(wire.DATA_PAYLOAD)
    elif t == wire.T_ACK:
        gq = (-60.0 - b["g"]) * 2.0 + 0.5
        body = bytes([f.seq & 0xFF, 0 if gq <= 0 else (254 if gq >= 254 else int(gq))])
    elif t == wire.T_HELLO:
        body = bytes([1 if b.get("reply") else 0, sp, b["cap"] + 9, 0])
    elif t == wire.T_PROPOSE:
        body = bytes([NAME_ID[b["cand"]], sp, b["cap"] + 9, 0])
    elif t == wire.T_VOTE:
        body = bytes([NAME_ID[b["cand"]], 1 if b["yes"] else 0, sp, b["cap"] + 9])
    else:
        d = round(b["delay"] * 1000)
        body = bytes([NAME_ID[b["cand"]], d >> 8, d & 0xFF, sp])
    return wire.pack(t, f.src, f.dst, f.ctr, body, flags=flags | (f.key << 2))


def raw_to_frame(ep, raw, mode, keys=0x0F):
    """bytes -> Frame para o `Endpoint` (None se o quadro for malformado). `keys`: chaves carregadas no receptor."""
    try:
        hdr_ctr16 = int.from_bytes(raw[6:8], "big")
        ctr32 = wire.reconstruct_ctr(max(ep.peer_ctr, 0), hdr_ctr16)
        if ctr32 is None:
            # repetido ou antigo: o Endpoint o rejeita por `ctr <= peer_ctr`
            ftype = raw[0] & 0x1F
            return Frame("DATA", int.from_bytes(raw[2:4], "big"), int.from_bytes(raw[4:6], "big"), mode, 0.0,
                         ctr=-1, auth=True)
        try:
            d = wire.unpack(raw, ctr32)
            auth = True
        except ValueError as e:
            if str(e) != "mic":
                return None
            d, auth = {"type": raw[0] & 0x1F, "src": int.from_bytes(raw[2:4], "big"),
                       "dst": int.from_bytes(raw[4:6], "big"), "body": bytes(raw[8:-4])}, False
    except Exception:
        return None
    t, b = d["type"], d["body"]
    kind = {wire.T_HELLO: "HELLO", wire.T_DATA: "DATA", wire.T_ACK: "ACK", wire.T_PROPOSE: "PROPOSE",
            wire.T_VOTE: "VOTE", wire.T_COMMIT: "COMMIT"}[t]
    p = ep._cap(mode)
    body, seq = {}, 0
    if t == wire.T_DATA:
        seq = b[0]
        p = float(((b[1] >> 2) & 0x3F) - 9)
        body = {"val": bool(b[1] & 1), "hb": bool(b[1] & 2), "v": b[2] / 2.0}
    elif t == wire.T_ACK:
        seq = b[0]
        body = {} if b[1] == 0xFF else {"g": -60.0 - b[1] * 0.5}
    elif t == wire.T_HELLO:
        body = {"reply": bool(b[0] & 1), "v": b[1] / 2.0, "cap": b[2] - 9}
    elif t == wire.T_PROPOSE:
        body = {"cand": MODE_BY_ID[b[0]].name if b[0] in MODE_BY_ID else None, "v": b[1] / 2.0, "cap": b[2] - 9}
    elif t == wire.T_VOTE:
        body = {"cand": MODE_BY_ID[b[0]].name if b[0] in MODE_BY_ID else None, "yes": bool(b[1]), "v": b[2] / 2.0,
                "cap": b[3] - 9}
    else:
        body = {"cand": MODE_BY_ID[b[0]].name if b[0] in MODE_BY_ID else None,
                "delay": ((b[1] << 8) | b[2]) / 1000.0, "v": b[3] / 2.0}
    key = (raw[1] >> 2) & 3
    auth = auth and bool(keys & (1 << key))           # sem a chave no chaveiro o MIC não confere
    return Frame(kind, d["src"], d["dst"], mode, p, seq=seq, ctr=ctr32, auth=auth, nbytes=len(raw),
                 body=body, key=key)


class PyAdapter:
    kind = "py"

    def __init__(self, nid, peer, seed, cfg, now_ms=0, noise_rise=0.0, cap=28.0, nvm=None):
        self.id, self.peer, self.cfg, self.noise_rise, self.cap = nid, peer, cfg, noise_rise, cap
        self.rng = XorRng(seed)
        self.ep = Endpoint(nid, peer, MODES, BASE_MODE, REC_MODE, cfg, XorRng(1), noise_rise, cap)
        if nvm:
            self.ep.nvm.update(nvm)
        self.ep.rng = self.rng                         # o construtor gastou sorteios de outro gerador
        self.ep._boot(now_ms / 1000.0)
        self.ep.seq = self.rng.next() & 0xFF          # como o legua_init: início aleatório
        self._speed_q = lambda v: min(255, int(v * 2 + 0.5))
        self.keys = 0x0F                               # chaves carregadas (o MIC de teste não depende da chave)

    # -- conversões
    def _norm(self, acts):
        out = []
        for a in acts:
            k = a[0]
            if k == "tx":
                f = a[1]
                out.append(("tx", frame_to_raw(f, self._speed_q).hex(), mode_id_of(f.mode), int(round(f.p_dbm))))
            elif k == "rx":
                out.append(("rx", mode_id_of(a[1])))
            elif k == "persist":
                out.append(("persist",))
            elif k == "log":
                d = a[1]
                ev = d["ev"]
                if ev == "modo":
                    out.append(("modo", NAME_ID[d["modo"]], STATE_CODE[d["estado"]], REASON_CODE[d["motivo"]]))
                elif ev == "propose":
                    out.append(("propose", NAME_ID[d["cand"]]))
                elif ev == "validado":
                    out.append(("validado", NAME_ID[d["modo"]]))
                elif ev in ("neg_falhou", "commit_rx"):
                    out.append((ev,))
                elif ev == "alarme_rollback":
                    out.append(("alarme",))
                elif ev == "alarme_mic":
                    out.append(("alarme_mic",))
                elif ev == "chave":
                    out.append(("chave", d["key"], int(d["prev"])))
                elif ev == "rejeitado":
                    out.append(("rej",))
        return out

    # -- eventos
    def on_app(self, now_ms):
        return self._norm(self.ep.on_app(now_ms / 1000.0))

    def on_rx(self, raw, mode_id, rssi10, snr10, now_ms):
        f = raw_to_frame(self.ep, raw, MODE_BY_ID[mode_id], self.keys)
        if f is None:
            return []
        if f.kind == "ACK" and f.ctr >= 0:
            f.seq = self._seq_in_flight(f.seq)
        return self._norm(self.ep.on_rx(f, rssi10 / 10.0, snr10 / 10.0, now_ms / 1000.0))

    def on_tx_done(self, raw, mode_id, now_ms):
        # o Endpoint guarda o Frame original; reconstrói o necessário a partir dos bytes
        t = raw[0] & 0x1F
        m = MODE_BY_ID[mode_id]
        if t == wire.T_DATA:
            f = Frame("DATA", self.id, self.peer, m, 0.0, seq=self._seq_in_flight(raw[8]))
        elif t == wire.T_COMMIT:
            f = Frame("COMMIT", self.id, self.peer, m, 0.0, body={"delay": ((raw[9] << 8) | raw[10]) / 1000.0})
        else:
            f = Frame({wire.T_ACK: "ACK", wire.T_HELLO: "HELLO", wire.T_PROPOSE: "PROPOSE",
                       wire.T_VOTE: "VOTE"}[t], self.id, self.peer, m, 0.0)
        return self._norm(self.ep.on_tx_done(f, now_ms / 1000.0))

    def on_timer(self, now_ms):
        return self._norm(self.ep.on_timer(now_ms / 1000.0))

    def _seq_in_flight(self, b):
        """O Endpoint numera sem limite; o fio leva 8 bits. Recupera o número do pacote em voo."""
        o = self.ep.out
        return o["seq"] if o and (o["seq"] & 0xFF) == b else b

    def next_deadline(self):
        d = self.ep.next_deadline()
        return None if d is None else ceil_ms(d)

    def set_speed(self, v):
        self.ep.set_speed(v)

    def reboot(self, now_ms):
        acts = self._norm(self.ep.reboot(now_ms / 1000.0))
        self.ep.seq = self.rng.next() & 0xFF
        return acts

    def set_keys(self, mask):
        self.keys = mask

    def rotate(self, now_ms):
        acts = self.ep.rotate_key(now_ms / 1000.0)
        return None if acts is None else self._norm(acts)

    def snapshot(self):
        e = self.ep
        a = e.nvm["anchor"]
        return (STATE_CODE[e.state], mode_id_of(e.mode), int(e.p), NAME_ID[a.name] if a else -1,
                e.key_cur | (int(e.key_prev) << 8))

    def stats(self):
        s = self.ep.stats
        return {"trocas": s["trocas"], "rollbacks": s["rollbacks"], "degradacoes": s["degradacoes"],
                "quedas_base": s["quedas_base"], "neg_ok": s["neg_ok"], "neg_fail": s["neg_fail"],
                "neg_recusa": s["neg_recusa"], "desc_silencio": s["desc_silencio"], "alarmes": s["alarmes"],
                "rejeitados": s["rejeitados"], "tx_ctrl": s["tx_ctrl"], "entregues": s["entregues"],
                "gerados": s["gerados"], "perdidos": s["perdidos"], "alarmes_mic": s["alarmes_mic"]}


# ------------------------------------------------------------------ adaptador C
_lib = None


def lib():
    global _lib
    if _lib is None:
        _lib = ctypes.CDLL(LIB)
        _lib.shim_param.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_double]
        _lib.shim_set_speed.argtypes = [ctypes.c_int, ctypes.c_float]
        _lib.shim_setup.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p,
                                    ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_float]
    return _lib


REC = 32


class CAdapter:
    kind = "c"
    _next_handle = 0

    def __init__(self, nid, peer, seed, cfg, now_ms=0, noise_rise=0.0, cap=28.0, nvm=None, handle=0):
        self.L = lib()
        self.h = handle
        self.id, self.peer, self.cfg, self.seed = nid, peer, cfg, seed
        n = len(MODES)
        ids = bytes(mode_id_of(m) for m in MODES)
        caps = bytes(int(m.cap) & 0xFF for m in MODES)
        sens = (ctypes.c_float * n)(*[m.sens() for m in MODES])
        toa = (ctypes.c_uint32 * n)(*[m.toa_us(DATA_BYTES) for m in MODES])
        r = self.L.shim_setup(self.h, ids, caps, sens, toa, n, nid, peer, mode_id_of(BASE_MODE),
                              mode_id_of(REC_MODE), int(cap), ctypes.c_float(noise_rise))
        assert r == 0
        for k, v in c_params(cfg).items():
            assert self.L.shim_param(self.h, k.encode(), float(v)) == 0, k
        self.acc = {k: 0 for k in STATS}
        self.rec = {"anchor": -1, "ctr_block": 0, "peer_floor": 0, "key": 0, "key_prev": 0}
        if nvm:
            self.rec.update(nvm)
        self.out = (ctypes.c_uint8 * (REC * 16))()
        self._init(now_ms)

    def _init(self, now_ms):
        r = self.L.shim_init(self.h, self.seed, 1 if self.rec["anchor"] >= 0 else 0, max(self.rec["anchor"], 0),
                             self.rec["ctr_block"], self.rec["peer_floor"], self.rec["key"], self.rec["key_prev"],
                             now_ms, self.out)
        assert r >= 0, r
        return self._decode(r)

    def _decode(self, n):
        assert n >= 0, "estouro de ações no núcleo C"
        out = []
        for i in range(n):
            r = bytes(self.out[i * REC:(i + 1) * REC])
            k = r[0]
            if k == 0:                                         # TX
                out.append(("tx", r[4:4 + r[1]].hex(), r[2], ctypes.c_int8(r[3]).value))
            elif k == 1:                                       # RX
                out.append(("rx", r[2]))
            elif k == 2:                                       # PERSIST
                self.rec = {"anchor": r[2] if r[1] else -1, "ctr_block": int.from_bytes(r[4:8], "little"),
                            "peer_floor": int.from_bytes(r[8:12], "little"), "key": r[12], "key_prev": r[13]}
                out.append(("persist",))
            elif k == 4:                                       # LOG
                code, arg = r[1], int.from_bytes(r[4:8], "little")
                if code in LOG_REJ:
                    out.append(("rej",))
                elif code == 8:
                    out.append(("modo", arg & 0xFF, (arg >> 8) & 0xFF, (arg >> 16) & 0xFF))
                elif code == 9:
                    out.append(("propose", arg))
                elif code == 11:
                    out.append(("validado", arg))
                elif code == 10:
                    out.append(("neg_falhou",))
                elif code == 12:
                    out.append(("commit_rx",))
                elif code == 13:
                    out.append(("alarme",))
                elif code == 14:
                    out.append(("alarme_mic",))
                elif code == 15:
                    out.append(("chave", arg & 0xFF, (arg >> 8) & 1))
                elif code == 17:
                    out.append(("ctr_fim",))
        return out

    def on_app(self, now_ms):
        return self._decode(self.L.shim_on_app(self.h, now_ms, self.out))

    def on_rx(self, raw, mode_id, rssi10, snr10, now_ms):
        return self._decode(self.L.shim_on_rx(self.h, raw, len(raw), rssi10, snr10, now_ms, self.out))

    def on_tx_done(self, raw, mode_id, now_ms):
        return self._decode(self.L.shim_on_tx_done(self.h, raw, len(raw), mode_id, now_ms, self.out))

    def on_timer(self, now_ms):
        return self._decode(self.L.shim_on_timer(self.h, now_ms, self.out))

    def next_deadline(self):
        at = ctypes.c_uint32()
        return at.value if self.L.shim_next_deadline(self.h, ctypes.byref(at)) else None

    def set_speed(self, v):
        self.L.shim_set_speed(self.h, v)

    def _stats_now(self):
        n = self.L.shim_nstats()
        buf = (ctypes.c_uint32 * n)()
        self.L.shim_stats(self.h, buf)
        return dict(zip(STATS, list(buf)))

    def reboot(self, now_ms):
        cur = self._stats_now()
        for k in STATS:
            self.acc[k] += cur[k]
        self.seed = 0                                  # mantém o PRNG, como o adaptador Python
        return self._init(now_ms)

    def set_keys(self, mask):
        self.L.shim_set_keys(self.h, mask)

    def rotate(self, now_ms):
        r = self.L.shim_key_rotate(self.h, now_ms, self.out)
        return None if r == -3 else self._decode(r)

    def snapshot(self):
        return (self.L.shim_state(self.h), self.L.shim_mode_id(self.h), self.L.shim_power(self.h),
                self.L.shim_anchor_id(self.h), self.L.shim_key(self.h))

    def stats(self):
        cur = self._stats_now()
        return {k: self.acc[k] + cur[k] for k in STATS[:14] + ["alarmes_mic"]}


# ------------------------------------------------------------------ DES mínimo
class Channel:
    """Canal determinístico: ganho por enlace em função do tempo e curva de PER do simulador."""

    def __init__(self, gain_fn, seed=12345, windows=(), drop_fn=None):
        self.gain_fn = gain_fn              # (t_ms) -> ganho em dB (negativo), simétrico
        self.rng = XorRng(seed)
        self.windows = list(windows)        # janelas [t0, t1) em que tudo é perdido (jamming)
        self.drop_fn = drop_fn              # (t_ms, mode_id) -> True perde o quadro (falha injetada)

    def u(self):
        return self.rng.next() / 4294967296.0


class Run:
    def __init__(self, kinds, cfgs, channel, T_ms, app_ms=(30000, 41000), nvm_cap=28.0, noise_rise=0.0,
                 reboots=(), speeds=(), inject=(), seeds=(1001, 2002), keys=(), rotations=()):
        self.ch = channel
        self.T = T_ms
        self.q = []
        self.cnt = 0
        self.now = 0
        self.trace = []
        self.nodes = {}
        for i, (kind, cfg) in enumerate(zip(kinds, cfgs)):
            nid, peer = (1, 2) if i == 0 else (2, 1)
            cls = PyAdapter if kind == "py" else CAdapter
            kw = {"handle": i} if kind == "c" else {}
            ad = cls(nid, peer, seeds[i], cfg, 0, noise_rise, nvm_cap[i] if isinstance(nvm_cap, (tuple, list)) else nvm_cap, **kw)
            self.nodes[nid] = {"ad": ad, "txq": [], "busy": 0, "rx_mode": ad.snapshot()[1],
                               "wakes": set(), "app_rng": XorRng(777 + nid), "app_ms": app_ms, "last_rx": None,
                               "epoch": 0, "ctr_sent": 0}
        self.active = []
        self.reboots, self.speeds, self.inject = list(reboots), list(speeds), list(inject)
        self.keys, self.rotations = list(keys), list(rotations)   # (t, nid, máscara) e (t, nid)
        self.drops = 0

    # -- infraestrutura
    def at(self, t, kind, *args):
        self.cnt += 1
        heapq.heappush(self.q, (t, self.cnt, kind, args))

    def log(self, nid, call, acts):
        ad = self.nodes[nid]["ad"]
        self.trace.append((self.now, nid, call, tuple(acts), ad.snapshot()))

    def apply(self, nid, call, acts):
        self.log(nid, call, acts)
        n = self.nodes[nid]
        for a in acts:
            if a[0] == "tx":
                n["txq"].append(a)
                if n["busy"] <= self.now and len(n["txq"]) == 1:
                    self._start(nid)
            elif a[0] == "rx":
                n["rx_mode"] = a[1]
                # o TX em curso termina em `busy`; com busy == now o tx_end ainda está na fila de eventos (mesmo ms)
                keep = n["txq"][:1] if n["busy"] >= self.now else []
                n["txq"] = keep + [f for f in n["txq"][len(keep):] if f[2] == a[1]]

    def _toa_ms(self, tx):
        m = MODE_BY_ID[tx[2]]
        return (toa_us_int(m.sf, int(m.bw), len(tx[1]) // 2, m.cr) + 999) // 1000

    def _start(self, nid):
        n = self.nodes[nid]
        if not n["txq"]:
            return
        tx = n["txq"][0]
        t0 = max(self.now, n["busy"]) + TURNAROUND_MS
        n["busy"] = t0 + self._toa_ms(tx)
        self.at(t0, "tx_begin", nid, tx, n["epoch"])

    def _tx_begin(self, nid, tx, epoch):
        if epoch != self.nodes[nid]["epoch"]:
            return                                          # o nó reiniciou: a transmissão não acontece
        air = self._toa_ms(tx)
        rec = {"src": nid, "t0": self.now, "t1": self.now + air, "tx": tx}
        self.active.append(rec)
        self.at(self.now + air, "tx_end", nid, rec, self.nodes[nid]["epoch"])

    def _tx_end(self, nid, rec, epoch):
        n = self.nodes[nid]
        if epoch != n["epoch"]:
            return
        tx = n["txq"].pop(0)
        raw = bytes.fromhex(tx[1])
        n["ctr_sent"] = wire.reconstruct_ctr(n["ctr_sent"], int.from_bytes(raw[6:8], "big")) or n["ctr_sent"]
        self.apply(nid, "tx_done", n["ad"].on_tx_done(raw, tx[2], self.now))
        rid = 2 if nid == 1 else 1
        self._receive(rid, nid, rec, raw)
        self.active = [a for a in self.active if a["t1"] > self.now - 5000]
        if n["txq"]:
            self._start(nid)
        self._wake(nid)

    def _receive(self, rid, sid, rec, raw):
        rn = self.nodes[rid]
        tx = rec["tx"]
        mode = MODE_BY_ID[tx[2]]
        if rn["rx_mode"] != tx[2]:
            return
        if any(a["src"] == rid and a["t0"] < rec["t1"] and a["t1"] > rec["t0"] for a in self.active):
            return
        if any(t0 <= rec["t0"] < t1 for t0, t1 in self.ch.windows) or \
                (self.ch.drop_fn and self.ch.drop_fn(rec["t0"], tx[2])):
            self.drops += 1
            return
        gain = self.ch.gain_fn(rec["t0"])
        jit = (self.ch.u() - 0.5) * 2.0                   # ±1 dB
        rssi = gain + tx[3] + jit
        snr = rssi - noise_dbm(mode.bw, 0.0)
        p_ok = p_demod(snr + CR_GAIN_DB[mode.cr], mode.sf)
        if self.ch.u() >= p_ok:
            self.drops += 1
            return
        r10, s10 = round(rssi * 10), round(snr * 10)
        rn["last_rx"] = (raw, tx[2], r10, s10, self.nodes[sid]["ctr_sent"])
        self.apply(rid, "rx", rn["ad"].on_rx(raw, tx[2], r10, s10, self.now))
        self._wake(rid)

    def _wake(self, nid):
        n = self.nodes[nid]
        d = n["ad"].next_deadline()
        if d is None or d >= self.T:
            return
        d = max(d, self.now + 5)
        if d in n["wakes"]:
            return
        n["wakes"].add(d)
        self.at(d, "timer", nid, d)

    def _timer(self, nid, d):
        n = self.nodes[nid]
        n["wakes"].discard(d)
        self.apply(nid, "timer", n["ad"].on_timer(self.now))
        self._wake(nid)

    def _app(self, nid):
        n = self.nodes[nid]
        self.apply(nid, "app", n["ad"].on_app(self.now))
        self._wake(nid)
        lo, hi = n["app_ms"]
        nxt = self.now + lo + (n["app_rng"].next() % (hi - lo))
        if nxt < self.T:
            self.at(nxt, "app", nid)

    def _reboot(self, nid):
        n = self.nodes[nid]
        n["txq"] = []
        n["wakes"] = set()
        n["epoch"] += 1
        n["busy"] = self.now
        self.active = [a for a in self.active if a["src"] != nid or a["t1"] <= self.now]
        acts = n["ad"].reboot(self.now)
        n["rx_mode"] = next((a[1] for a in acts if a[0] == "rx"), n["rx_mode"])
        self.apply(nid, "reboot", acts)
        self._wake(nid)

    def _inject(self, nid, how):
        """Replay ou cópia forjada (MIC inválido) do último quadro recebido pelo nó."""
        n = self.nodes[nid]
        if not n["last_rx"]:
            return
        raw, mid, r10, s10, ctr32 = n["last_rx"]
        if mid != n["rx_mode"]:
            return                                          # o rádio só demodula no modo configurado
        if how == "forjado":
            b = bytearray(raw)
            b[-1] ^= 0x01                                   # MIC adulterado
            b[7] = (b[7] + 1) & 0xFF                        # contador à frente
            raw = bytes(b)
        elif how == "chave_antiga":
            # quem tem a chave anterior à do receptor monta um quadro autêntico com ela (contador à frente):
            # aceito só durante a rotação; depois que a chave é aposentada, recusado (docs/07 §6.2)
            k = ((n["ad"].snapshot()[4] & 3) + 3) % 4
            b = bytearray(raw[:-4])
            b[1] = (b[1] & ~0x0C) | (k << 2)
            c = ctr32 + 1
            b[6:8] = (c & 0xFFFF).to_bytes(2, "big")
            raw = bytes(b) + wire.test_mic(wire.TEST_KEY, int.from_bytes(b[2:4], "big"), c, bytes(b)).to_bytes(4, "big")
        self.apply(nid, "inject_" + how, n["ad"].on_rx(raw, mid, r10, s10, self.now))
        self._wake(nid)

    def run(self):
        for nid, n in self.nodes.items():
            self._wake(nid)
            self.at(1000 + (nid * 7919) % 5000, "app", nid)
        for t, nid in self.reboots:
            self.at(t, "reboot", nid)
        for t, nid, v in self.speeds:
            self.at(t, "speed", nid, v)
        for t, nid, how in self.inject:
            self.at(t, "inject", nid, how)
        for t, nid, mask in self.keys:
            self.at(t, "keys", nid, mask)
        for t, nid in self.rotations:
            self.at(t, "rotate", nid)
        while self.q and self.q[0][0] <= self.T:
            t, _, kind, args = heapq.heappop(self.q)
            self.now = t
            if kind == "tx_begin":
                self._tx_begin(*args)
            elif kind == "tx_end":
                self._tx_end(*args)
            elif kind == "timer":
                self._timer(*args)
            elif kind == "app":
                self._app(*args)
            elif kind == "reboot":
                self._reboot(*args)
            elif kind == "speed":
                self.nodes[args[0]]["ad"].set_speed(args[1])
            elif kind == "inject":
                self._inject(*args)
            elif kind == "keys":
                self.nodes[args[0]]["ad"].set_keys(args[1])
            elif kind == "rotate":
                nid = args[0]
                acts = self.nodes[nid]["ad"].rotate(self.now)
                self.apply(nid, "rotate", acts if acts is not None else [("recusada",)])
                self._wake(nid)
        return {"trace": self.trace,
                "stats": {nid: n["ad"].stats() for nid, n in self.nodes.items()},
                "final": {nid: n["ad"].snapshot() for nid, n in self.nodes.items()}}


def canon(trace):
    """Forma canônica para comparar: por chamada, TX na ordem; as demais ações ordenadas."""
    out = []
    for t, nid, call, acts, snap in trace:
        txs = tuple(a for a in acts if a[0] == "tx")
        rest = tuple(sorted(a for a in acts if a[0] != "tx"))
        out.append((t, nid, call, txs, rest, snap))
    return out


def first_diff(a, b):
    ca, cb = canon(a["trace"]), canon(b["trace"])
    for i, (x, y) in enumerate(zip(ca, cb)):
        if x != y:
            return i, x, y
    if len(ca) != len(cb):
        return min(len(ca), len(cb)), None, None
    return None


# ------------------------------------------------------------------ cenários
PARES = (("py", "py"), ("c", "c"), ("py", "c"), ("c", "py"))


def _eventos_de_chave(r, T):
    """Rotações de chave em instantes sorteados; às vezes uma ponta só recebe a chave nova depois (quadros recusados,
    falhas de MIC) e há quadros autênticos montados com a chave anterior (aceitos só durante a rotação)."""
    rot = sorted((r.randint(200_000, T - 200_000), r.choice([1, 2])) for _ in range(r.randint(1, 3)))
    keys = []
    if r.random() < 0.5:                       # um nó começa só com a chave 0 e recebe as demais mais tarde
        nid = 3 - rot[0][1]                    # o que não inicia: quem não tem a chave de TX não roda (erro do integrador)
        t_load = r.randint(rot[0][0] - 100_000, T - 100_000)
        keys = [(0, nid, 0x01), (t_load, nid, 0x0F)]
        rot = [(t, rot[0][1] if t < t_load else n) for t, n in rot]
    inj = [(r.randint(250_000, T - 100_000), r.choice([1, 2]), "chave_antiga") for _ in range(r.randint(1, 4))]
    return {"keys": keys, "rotations": rot, "inject_extra": inj}


def cenario_aleatorio(seed):
    """Cenário reprodutível: variante do protocolo, trajetória de ganho, apagões, reinícios, replays, velocidades."""
    import random
    r = random.Random(seed)
    base = dict(cooldown_up=r.choice([20.0, 30.0, 120.0]), n_up=r.choice([3, 5, 20]),
                neg_backoff0=r.choice([10.0, 60.0]), neg_backoff_max=r.choice([60.0, 240.0]),
                cooldown_back=r.choice([20.0, 120.0]))
    var = r.choice(["normal", "normal", "commit", "semvalid", "recup", "mobile", "semsil", "passo", "fade", "mic",
                    "chave"])
    if var == "commit":
        base["persist_at"] = "commit"
    elif var == "semvalid":
        base["validation"] = False
    elif var == "recup":
        base["ladder"] = "recuperacao"
    elif var == "mobile":
        base["mobile"] = True
    elif var == "semsil":
        base["silence_descent"] = False
    elif var == "fade":
        base.update(fade_k=r.choice([1.0, 3.0]), fade_window=r.choice([10, 30]))
    elif var == "mic":                   # limite de falhas de MIC baixo, para disparar com poucas injeções
        base.update(mic_fail_n=r.choice([1, 2]), mic_fail_window=r.choice([300.0, 900.0]),
                    mic_fail_hold=r.choice([120.0, 600.0]))
    elif var == "passo":
        base.update(ladder_step=3.0, margin_up=6.0, max_budget_jump=9.0)
    T = r.choice([2_400_000, 3_600_000])
    steps, t = [(0, r.uniform(-150, -128))], 0
    while t < T:
        t += r.randint(120_000, 900_000)
        steps.append((t, r.choice([r.uniform(-165, -128), r.uniform(-195, -185), r.uniform(-150, -130)])))

    def gain(tm, steps=steps):
        g = steps[0][1]
        for t0, v in steps:
            if t0 <= tm:
                g = v
        return g
    wins = []
    if r.random() < 0.4:
        for _ in range(r.randint(1, 6)):
            t0 = r.randint(100_000, T - 100_000)
            wins.append((t0, t0 + r.randint(5_000, 60_000)))
    return dict(
        cfg=Config(**base), gain=gain, T=T, windows=wins, variante=var,
        reboots=[(r.randint(200_000, T - 200_000), r.choice([1, 2])) for _ in range(r.choice([0, 0, 1, 3]))],
        inject=[(r.randint(300_000, T - 100_000), r.choice([1, 2]), r.choice(["replay", "forjado"]))
                for _ in range(r.choice([0, 0, 2]) if var != "mic" else r.choice([4, 8]))],
        speeds=([(r.randint(100_000, T - 100_000), r.choice([1, 2]), r.choice([0.0, 0.5, 1.5, 3.0, 10.5]))
                 for _ in range(4)] if var == "mobile" else []),
        noise_rise=r.choice([0.0, 0.0, 6.0]), cap=_tetos(seed),
        **(_eventos_de_chave(r, T) if var == "chave" else {}),
        app_ms=r.choice([(5_000, 15_000), (30_000, 41_000), (60_000, 90_000)]), chan_seed=seed + 5)


def _tetos(seed):
    """Teto de TX de cada nó. Gerador próprio: não mexe nos sorteios do resto do cenário. Metade das sementes tem
    tetos diferentes (docs/07 §4: o teto do par viaja nos controles)."""
    rc = random.Random(seed * 7919 + 13)
    return rc.choice([(28.0, 28.0), (28.0, 28.0), (22.0, 22.0), (28.0, 14.0), (14.0, 28.0), (28.0, 8.0), (2.0, 28.0), (22.0, 10.0)])


def rodar(sc, kinds):
    ch = Channel(sc["gain"], seed=sc["chan_seed"], windows=sc.get("windows", ()), drop_fn=sc.get("drop_fn"))
    return Run(kinds, (sc["cfg"], sc["cfg"]), ch, sc["T"], app_ms=sc.get("app_ms", (30_000, 41_000)),
               noise_rise=sc.get("noise_rise", 0.0), nvm_cap=sc.get("cap", 28.0), reboots=sc.get("reboots", ()),
               speeds=sc.get("speeds", ()), inject=list(sc.get("inject", ())) + list(sc.get("inject_extra", ())),
               keys=sc.get("keys", ()),
               rotations=sc.get("rotations", ())).run()


def comparar(sc):
    """Roda os quatro pares; devolve (resultado do Py-Py, lista de divergências)."""
    res = {k: rodar(sc, k) for k in PARES}
    base = res[("py", "py")]
    div = []
    for k, v in res.items():
        d = first_diff(base, v)
        if d:
            div.append((k, d))
        elif base["stats"] != v["stats"] or base["final"] != v["final"]:
            div.append((k, ("stats", base["stats"], v["stats"])))
    return base, div


def ensure_built():
    """Compila a biblioteca de teste do núcleo C se ainda não existe (make com 1 job, baixa prioridade)."""
    import subprocess
    if not os.path.exists(LIB):
        r = subprocess.run(["nice", "-n", "15", "make", "-j1", "-C", os.path.join(RAIZ, "core"),
                            "build/liblegua_shim.so"], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError("não compilou o núcleo C: " + r.stderr[-400:])


def resumo(n_seeds, first=1000):
    """Cenário `equiv` da suíte: compara os quatro pares em `n_seeds` cenários aleatórios e soma o que foi exercitado."""
    ensure_built()
    ag, var, eventos, div = {}, {}, 0, []
    for seed in range(first, first + n_seeds):
        sc = cenario_aleatorio(seed)
        base, d = comparar(sc)
        var[sc["variante"]] = var.get(sc["variante"], 0) + 1
        eventos += len(base["trace"])
        for nid in (1, 2):
            for k, v in base["stats"][nid].items():
                ag[k] = ag.get(k, 0) + v
        if d:
            div.append({"semente": seed, "variante": sc["variante"], "par": "-".join(d[0][0]),
                        "detalhe": str(d[0][1])[:300]})
    return {"cenarios": n_seeds, "pares": ["Py-Py", "C-C", "Py-C", "C-Py"], "divergencias": len(div),
            "detalhes_divergencias": div[:5], "eventos_comparados": eventos, "variantes": var, "exercitado": ag,
            "sementes": [first, first + n_seeds - 1]}
