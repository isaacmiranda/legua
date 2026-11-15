"""Máquina de estados de referência da AdaptLoRa v1 para um enlace P2P (doc 05).

Pura: não conhece rádio nem relógio. Recebe eventos (on_rx, on_app, on_timer,
on_tx_done, reboot) e devolve ações:
  ("tx", Frame)        transmitir no modo indicado no quadro
  ("rx", Mode)         configurar recepção
  ("persist", dict)    gravar âncora + contador em NVM
  ("log", dict)        evento de telemetria
Regras da v1:
  - controle in-band no modo atual; descoberta e recuperação final no modo base;
  - só a ACELERAÇÃO é negociada (PROPOSE -> VOTE -> COMMIT, um único candidato,
    troca em instante combinado, janela de validação bidirecional);
  - DEGRADAÇÃO unilateral por escada pré-acordada: potência máxima -> modo de
    recuperação R -> modo base; o receptor desce por silêncio;
  - âncora e contador gravados só depois da validação (ou no COMMIT, para ablação);
  - todo controle autenticado; quadros com MIC inválido ou contador repetido descartados;
  - alarme de rollback repetido sem queda de SNR (possível jamming).
"""
import math
from dataclasses import dataclass, field, replace
from .modes import DATA_BYTES, ACK_BYTES, CTRL_BYTES

BASE, DATA, NEG, PEND, VALID, RECOV = "BASE", "DATA", "NEGOCIANDO", "AGUARDA_COMMIT", "VALIDANDO", "RECUPERACAO"


@dataclass
class Frame:
    kind: str            # HELLO, DATA, ACK, PROPOSE, VOTE, COMMIT
    src: int
    dst: int
    mode: object         # Mode em que vai ao ar
    p_dbm: float
    seq: int = 0
    ctr: int = 0         # contador anti-replay
    auth: bool = True    # MIC válido
    nbytes: int = DATA_BYTES
    body: dict = field(default_factory=dict)


@dataclass
class Config:
    margin_target: float = 5.0       # margem para potência mínima
    margin_up: float = 8.0           # margem exigida para acelerar (histerese)
    n_up: int = 20                   # sucessos seguidos antes de propor
    cooldown_up: float = 600.0       # s entre mudanças (perfil fixo)
    cooldown_back: float = 120.0     # s em R antes de propor a volta à âncora
    ladder: str = "degraus"          # "degraus" (+ladder_step dB por degrau) | "recuperacao" (só R)
    ladder_step: float = 6.0
    max_budget_jump: float = 6.0     # dB de robustez cedidos por aceleração
    fail_streak_degrade: int = 3     # tentativas falhas seguidas -> degradar
    retries: int = 3
    hb_interval: float = 60.0        # heartbeat só após 60 s sem tráfego
    t_silence: float = 90.0          # sem ouvir o par -> descer um degrau
    t_recovery: float = 180.0        # tempo mínimo em R antes de cair para o base
    t_valid: float = 45.0
    k_valid: int = 3
    f_valid: int = 3
    vote_timeout: float = 4.0
    instant_delay: float = 2.5
    hello_interval: float = 10.0
    neg_backoff0: float = 60.0
    neg_backoff_max: float = 960.0
    ema_a: float = 0.3
    persist_at: str = "validation"   # "validation" (correto) | "commit" (ablação)
    silence_descent: bool = True     # ablação: sem descida por silêncio
    validation: bool = True          # ablação: sem janela de validação
    mobile: bool = False             # perfil móvel
    v_freeze: float = 2.0            # m/s: congela aceleração acima disso
    snr_std_freeze: float = 3.0      # dB
    rollback_alarm: int = 3          # rollbacks/h sem queda de SNR -> alarme
    power_control: bool = True


class Endpoint:
    def __init__(self, nid, peer, modes, base, rec, cfg, rng, noise_rise=0.0, cap=28.0):
        self.id, self.peer = nid, peer
        self.modes, self.base, self.rec = modes, base, rec
        self.cfg, self.rng, self.noise_rise, self.cap = cfg, rng, noise_rise, cap
        self.role_a = nid < peer
        self.nvm = {"anchor": None, "ctr_block": 0}
        self.stats = dict(trocas=0, rollbacks=0, degradacoes=0, quedas_base=0, neg_ok=0,
                          neg_fail=0, neg_recusa=0, desc_silencio=0, alarmes=0, rejeitados=0,
                          tx_ctrl=0, entregues=0, gerados=0, perdidos=0)
        self._boot(0.0)

    # ----------------------------------------------------------------- base
    def _boot(self, now):
        a = self.nvm["anchor"]
        self.mode = a or self.base
        self.state = DATA if a else BASE
        self.prev = a or self.base          # destino de rollback
        self.p = self._cap(self.mode)
        self.peer_heard = now
        self.entered = now
        self.out = None                      # pacote aguardando ACK
        self.queue = []
        self.seq = 0
        self.consec_ok = 0
        self.fail_streak = 0
        self.last_change = now
        self.neg_block = now
        self.neg_backoff = self.cfg.neg_backoff0
        self.pending = None
        self.val = None
        self.g_me = None                     # ganho estimado par->eu
        self.g_peer = None                   # ganho estimado eu->par (relatado no ACK)
        self.snr_hist = []
        self.next_hello = now + self.rng.uniform(0, self.cfg.hello_interval)
        self.next_hb = now + self.cfg.hb_interval
        self.ctr = self.nvm["ctr_block"] * 64 + 64   # salta para o próximo bloco
        self.peer_ctr = -1
        self.rollback_times = []
        self.freeze_until = now
        self.speed = 0.0
        self.degraded = False
        self.peer_speed = 0.0
        self.peer_rx_seq = set()
        self.bad = {}
        self._now = now
        self._now_hint = now

    def reboot(self, now):
        acts = [("log", {"ev": "reboot"})]
        self._boot(now)
        acts.append(("rx", self.mode))
        return acts

    def _cap(self, m):
        return min(self.cap, m.cap)

    def _frame(self, kind, nbytes, mode=None, **body):
        self.ctr += 1
        if self.ctr % 64 == 0:
            self.nvm["ctr_block"] = self.ctr // 64
        m = mode or self.mode
        body["v"] = round(self.speed, 1)        # velocidade GNSS (perfil móvel)
        return Frame(kind, self.id, self.peer, m, self._cap(m) if kind != "DATA" else self.p,
                     seq=body.pop("seq", 0), ctr=self.ctr, nbytes=nbytes, body=body)

    def _set_mode(self, mode, state, now, why):
        self.mode = mode
        self.degraded = state == RECOV or (self.degraded and state == DATA and mode != self.nvm["anchor"])
        self.state = state
        self.entered = now
        self.p = self._cap(mode)
        self.fail_streak = 0
        self.consec_ok = 0
        self.peer_heard = now
        self.out = None          # o pacote pendente continua na fila e sai no novo modo
        return [("rx", mode), ("log", {"ev": "modo", "modo": mode.name, "estado": state, "motivo": why})]

    def _g(self):
        gs = [g for g in (self.g_me, self.g_peer) if g is not None]
        return min(gs) if gs else None

    def _margin(self, m, p=None):
        g = self._g()
        if g is None:
            return -99
        return (self._cap(m) if p is None else p) + g - m.sens(self.noise_rise)

    def _min_power(self, m):
        g = self._g()
        if g is None or not self.cfg.power_control:
            return self._cap(m)
        need = self.cfg.margin_target - (g - m.sens(self.noise_rise))
        return min(self._cap(m), max(-9.0, math.ceil(need / 2) * 2))

    def _frozen(self):
        """Perfil móvel: congela a aceleração se algum lado se move ou o SNR oscila."""
        c = self.cfg
        return c.mobile and (max(self.speed, self.peer_speed) > c.v_freeze or self._snr_std() > c.snr_std_freeze)

    def _snr_std(self):
        h = self.snr_hist[-10:]
        if len(h) < 4:
            return 0.0
        mu = sum(h) / len(h)
        return math.sqrt(sum((x - mu) ** 2 for x in h) / len(h))

    # ----------------------------------------------------------------- eventos
    def set_speed(self, v):
        self.speed = v

    def on_app(self, now):
        self._now_hint = now
        self.stats["gerados"] += 1
        self._enqueue()
        return self._pump(now)

    def _pump(self, now):
        """Envia o próximo pacote se não houver um aguardando ACK."""
        if self.out is not None or self.pending is not None:
            return []
        if self.state == BASE and self.g_me is None:
            return []                        # no base, só envia dados depois de ouvir o par
        if not self.queue:
            return []
        seq, hb = self.queue[0]
        # val=True: "estou validado neste modo" (confirma a validação do par)
        f = self._frame("DATA", DATA_BYTES, seq=seq, val=(self.state == DATA), hb=hb)
        self.out = {"seq": seq, "att": 1, "deadline": None, "frame": f}
        return [("tx", f)]

    def _enqueue(self, hb=False):
        self.seq += 1
        if len(self.queue) >= 10:
            self.queue.pop(0)
            self.stats["perdidos"] += 1
        self.queue.append((self.seq, hb))

    def on_tx_done(self, frame, now):
        if frame.kind == "DATA" and self.out and self.out["seq"] == frame.seq:
            wait = frame.mode.toa(ACK_BYTES) + (0.45 if frame.mode.fhss else 0.05) + 0.15
            self.out["deadline"] = now + wait
        return []

    def on_rx(self, f, rssi, snr, now):
        self._now_hint = now
        acts = []
        if f.dst not in (self.id, -1) or f.src != self.peer:
            return acts
        if not f.auth or f.ctr <= self.peer_ctr:
            self.stats["rejeitados"] += 1
            return [("log", {"ev": "rejeitado", "tipo": f.kind})]
        self.peer_ctr = f.ctr
        if f.mode != self.mode:
            return acts
        self.peer_heard = now
        if f.kind in ("DATA", "ACK"):
            self.next_hb = max(self.next_hb, now + self.cfg.hb_interval * (1.0 if self.state != VALID else 0.1))
        g = rssi - f.p_dbm
        self.g_me = g if self.g_me is None else (1 - self.cfg.ema_a) * self.g_me + self.cfg.ema_a * g
        self.snr_hist.append(snr)
        self.peer_speed = f.body.get("v", 0.0)
        k = f.kind
        if k == "HELLO":
            if self.state == BASE and not self.role_a and not f.body.get("reply"):
                # descoberta bidirecional: responde a HELLO para o proponente também ouvir
                acts.append(("tx", self._frame("HELLO", CTRL_BYTES, reply=True)))
                self.stats["tx_ctrl"] += 1
            if self.state == BASE and self.role_a and self.pending is None and now >= self.neg_block \
                    and now >= self.freeze_until and not self._frozen():
                acts += self._propose(now, initial=True)
        elif k == "DATA":
            if f.seq not in self.peer_rx_seq:
                self.peer_rx_seq.add(f.seq)
                if not f.body.get("hb"):
                    self.stats["entregues"] += 1
            ack = self._frame("ACK", ACK_BYTES, seq=f.seq, g=g)
            acts.append(("tx", ack))
            if self.state == RECOV:
                self.consec_ok += 1
                if self.consec_ok >= 3:
                    self.state = DATA
            if self.state == VALID and not self.role_a and f.body.get("val"):
                acts += self._validated(now)
            if self.state == BASE:
                pass
        elif k == "ACK":
            if self.out and f.seq == self.out["seq"]:
                self.g_peer = f.body.get("g", self.g_peer) if self.g_peer is None else \
                    (1 - self.cfg.ema_a) * self.g_peer + self.cfg.ema_a * f.body.get("g", self.g_peer)
                if self.queue and self.queue[0][0] == f.seq:
                    self.queue.pop(0)
                self.out = None
                self.consec_ok += 1
                self.fail_streak = 0
                if self.state == VALID and self.role_a:
                    self.val["ok"] += 1
                    if self.val["ok"] >= self.cfg.k_valid and not self.val.get("done"):
                        self.val["done"] = True
                        acts += self._validated(now)
                elif self.state == RECOV and self.consec_ok >= 3:
                    self.state = DATA
                acts += self._power_trim()
                acts += self._pump(now)
        elif k == "PROPOSE":
            acts += self._on_propose(f, now)
        elif k == "VOTE":
            acts += self._on_vote(f, now)
        elif k == "COMMIT":
            if (self.pending and self.pending["role"] == "B"
                    and f.body.get("cand") == self.pending["cand"].name):
                self.pending["committed"] = True
                self.pending["instant"] = f.body["instant"]
                acts.append(("log", {"ev": "commit_rx"}))
        return acts

    # ----------------------------------------------------------------- negociação
    def _candidate(self, initial=False):
        cur_b = self.mode.budget(self.noise_rise)
        cur_toa = self.mode.toa(DATA_BYTES)
        best = None
        for i, m in enumerate(self.modes):
            # só modos mais rápidos e no máximo max_budget_jump dB menos robustos (um "passo")
            if not initial and (m.toa(DATA_BYTES) >= cur_toa * 0.9 or
                                m.budget(self.noise_rise) < cur_b - self.cfg.max_budget_jump):
                continue
            if self.bad.get(m.name, -1) > self._now:
                continue
            if self._margin(m) >= self.cfg.margin_up:
                best = m
                break                       # tabela ordenada do mais rápido
        return best

    def _propose(self, now, initial=False, target=None):
        self._now = now
        cand = target or self._candidate(initial)
        if cand is None or cand == self.mode:
            return []
        inst = now + self.cfg.instant_delay + 2 * self.mode.toa(CTRL_BYTES)
        self.pending = {"cand": cand, "role": "A", "t0": now, "deadline": now + self.cfg.vote_timeout +
                        2 * self.mode.toa(CTRL_BYTES)}
        self.state = NEG if self.state != BASE else self.state
        self.stats["tx_ctrl"] += 1
        return [("tx", self._frame("PROPOSE", CTRL_BYTES, cand=cand.name)),
                ("log", {"ev": "propose", "cand": cand.name})]

    def _on_propose(self, f, now):
        cand = next((m for m in self.modes if m.name == f.body["cand"]), None)
        ok = cand is not None and (self._margin(cand) >= self.cfg.margin_up - 2 or self.state == BASE
                                   or self.g_me is None or cand == self.rec)
        if self._frozen():
            ok = False
        self.stats["tx_ctrl"] += 1
        if ok:
            self.pending = {"cand": cand, "role": "B", "committed": False,
                            "deadline": now + self.cfg.vote_timeout + 3 * self.mode.toa(CTRL_BYTES) +
                            self.cfg.instant_delay}
            if self.state != BASE:
                self.state = PEND
        return [("tx", self._frame("VOTE", CTRL_BYTES, cand=f.body["cand"], yes=ok))]

    def _on_vote(self, f, now):
        if not (self.pending and self.pending["role"] == "A" and f.body.get("cand") == self.pending["cand"].name):
            return []
        if not f.body.get("yes"):
            self.stats["neg_recusa"] += 1
            return self._neg_fail(now)
        inst = now + self.cfg.instant_delay
        self.pending["instant"] = inst
        self.pending["committed"] = True
        self.stats["tx_ctrl"] += 1
        return [("tx", self._frame("COMMIT", CTRL_BYTES, cand=self.pending["cand"].name, instant=inst))]

    def _neg_fail(self, now):
        self.stats["neg_fail"] += 1
        self.pending = None
        if self.state in (NEG, PEND):
            self.state = DATA
        if self.state == BASE:
            self.neg_block = now + self.cfg.hello_interval
        else:
            self.neg_block = now + self.neg_backoff
            self.neg_backoff = min(self.cfg.neg_backoff_max, self.neg_backoff * 2)
        return [("log", {"ev": "neg_falhou"})]

    def _switch(self, now):
        cand = self.pending["cand"]
        self.prev = self.mode if self.state != BASE else (self.nvm["anchor"] or self.base)
        if self.state == BASE:
            self.prev = self.base
        self.pending = None
        self.stats["trocas"] += 1
        self.last_change = now
        self.val = {"ok": 0, "t0": now, "fails": 0}
        acts = self._set_mode(cand, VALID if self.cfg.validation else DATA, now, "troca")
        self.next_hb = now + self.rng.uniform(0.2, 2.0)
        self.p = self._cap(cand)
        if self.cfg.persist_at == "commit" or not self.cfg.validation:
            acts.append(("persist", {"anchor": cand.name}))
            self.nvm["anchor"] = cand
        return acts

    def _validated(self, now):
        self.state = DATA
        self.stats["neg_ok"] += 1
        self.neg_backoff = self.cfg.neg_backoff0
        self.prev = self.mode
        acts = [("log", {"ev": "validado", "modo": self.mode.name})]
        if self.cfg.persist_at == "validation":
            self.nvm["anchor"] = self.mode
            acts.append(("persist", {"anchor": self.mode.name}))
        return acts

    def _rollback(self, now, why):
        self.stats["rollbacks"] += 1
        self.rollback_times = [x for x in self.rollback_times if now - x < 3600] + [now]
        acts = []
        # alarme: rollbacks repetidos sem queda de SNR medida (possível jamming)
        if len(self.rollback_times) >= self.cfg.rollback_alarm and self._snr_std() < 2.0:
            self.stats["alarmes"] += 1
            self.freeze_until = now + 3600
            acts.append(("log", {"ev": "alarme_rollback"}))
        self.bad[self.mode.name] = now + 3 * self.neg_backoff
        tgt = self.prev if self.prev is not None else self.base
        st = BASE if tgt == self.base else DATA
        self.neg_block = now + self.neg_backoff
        self.neg_backoff = min(self.cfg.neg_backoff_max, self.neg_backoff * 2)
        return acts + self._set_mode(tgt, st, now, why)

    def _step_down(self, m):
        """Degrau pré-acordado: o modo mais rápido com pelo menos ladder_step dB a mais de
        orçamento (função determinística da tabela, igual nos dois lados)."""
        if self.cfg.ladder == "recuperacao":
            return self.rec if m != self.rec else None
        b = m.budget(self.noise_rise) + self.cfg.ladder_step
        cands = [x for x in self.modes if x.budget(self.noise_rise) >= b - 1e-9]
        if not cands:
            return None
        return min(cands, key=lambda x: (x.toa(DATA_BYTES), -x.budget(self.noise_rise)))

    def _descend(self, now, why):
        if self.mode == self.base:
            return []
        nxt = self._step_down(self.mode)
        if nxt is not None and nxt != self.mode:
            self.stats["degradacoes"] += 1
            return self._set_mode(nxt, RECOV, now, why)
        self.stats["quedas_base"] += 1
        return self._set_mode(self.base, BASE, now, why)

    def _power_trim(self):
        self.ok_since_p = getattr(self, "ok_since_p", 0) + 1
        if not self.cfg.power_control or self.ok_since_p < 10 or self.state != DATA:
            return []
        p2 = self.p - 2
        if p2 >= -9 and self._margin(self.mode, p2) >= self.cfg.margin_target + 2:
            self.p = p2
            self.ok_since_p = 0
        return []

    # ----------------------------------------------------------------- tempo
    def on_timer(self, now):
        self._now_hint = now
        acts = []
        c = self.cfg
        # ACK expirado
        if self.out and self.out["deadline"] is not None and now >= self.out["deadline"]:
            self.fail_streak += 1
            self.consec_ok = 0
            if self.state == VALID:
                self.val["fails"] += 1
            self.ok_since_p = 0
            if self.p < self._cap(self.mode):
                self.p = min(self._cap(self.mode), self.p + 6)     # potência é unilateral
            if self.out["att"] <= c.retries:
                self.out["deadline"] = None
                self.out["resend_at"] = now + self.rng.uniform(0.3, 2.0)
            else:
                self.stats["perdidos"] += 1
                if self.queue:
                    self.queue.pop(0)
                self.out = None
            if self.state == VALID and self.role_a and self.val["fails"] >= c.f_valid:
                return acts + self._rollback(now, "validacao_falhou")
            if self.state == DATA and self.fail_streak >= c.fail_streak_degrade and self.p >= self._cap(self.mode):
                return acts + self._descend(now, "falhas")
        # retransmissão após recuo aleatório
        if self.out and self.out.get("resend_at") is not None and now >= self.out["resend_at"]:
            f = replace(self.out["frame"], p_dbm=self.p, mode=self.mode)
            self.ctr += 1
            f.ctr = self.ctr
            f.body = dict(f.body, val=(self.state == DATA))
            self.out = {"seq": self.out["seq"], "att": self.out["att"] + 1, "deadline": None, "frame": f}
            acts.append(("tx", f))
        # validação expirada
        if self.state == VALID and now - self.val["t0"] > c.t_valid:
            return acts + self._rollback(now, "validacao_expirou")
        # negociação: voto ou commit não chegou
        if self.pending:
            pd = self.pending
            if pd.get("committed") and now >= pd["instant"]:
                acts += self._switch(now)
            elif not pd.get("committed") and now >= pd["deadline"]:
                acts += self._neg_fail(now)
        # silêncio
        if c.silence_descent:
            if self.state in (DATA,) and now - self.peer_heard > c.t_silence:
                self.stats["desc_silencio"] += 1
                acts += self._descend(now, "silencio")
            elif self.state == RECOV and now - self.peer_heard > c.t_recovery:
                self.stats["desc_silencio"] += 1
                acts += self._descend(now, "silencio_rec")
        # base: HELLO periódico
        if self.state == BASE and self.role_a and self.pending is None and now >= self.neg_block \
                and now >= self.freeze_until and self.consec_ok >= 5 and self.out is None and not self._frozen():
            acts += self._propose(now, initial=True)
        if self.state == BASE and now >= self.next_hello and now - self.peer_heard > 3 * c.hello_interval:
            self.next_hello = now + c.hello_interval * self.rng.uniform(0.7, 1.3)
            self.stats["tx_ctrl"] += 1
            acts.append(("tx", self._frame("HELLO", CTRL_BYTES)))
        # heartbeat
        if self.state in (DATA, RECOV, VALID) and now >= self.next_hb and not (self.state == VALID and not self.role_a):
            self.next_hb = now + (4.0 if self.state == VALID else c.hb_interval) * self.rng.uniform(0.75, 1.25)
            if not self.queue and self.out is None:
                self._enqueue(hb=True)
                acts += self._pump(now)
        # retorno à âncora depois de uma degradação (mais rápido que a aceleração normal)
        anc = self.nvm["anchor"]
        if (self.state == DATA and self.role_a and self.pending is None and self.out is None
                and self.degraded and anc is not None and anc != self.mode
                and self.consec_ok >= 10 and now - self.entered >= c.cooldown_back
                and now >= self.neg_block and now >= self.freeze_until and not self._frozen()
                and self._margin(anc) >= c.margin_up - 2 and self.bad.get(anc.name, -1) <= now):
            acts += self._propose(now, target=anc)
        # aceleração
        elif (self.state == DATA and self.role_a and self.pending is None and self.out is None
                and self.consec_ok >= c.n_up and now - self.last_change >= c.cooldown_up
                and now >= self.neg_block and now >= self.freeze_until):
            if not self._frozen():
                acts += self._propose(now)
        if self.state not in (NEG, PEND):
            acts += self._pump(now)
        return acts

    def next_deadline(self):
        ds = [max(self.next_hello, self.peer_heard + 3 * self.cfg.hello_interval) if self.state == BASE else None,
              self.next_hb if (self.state in (DATA, RECOV) or (self.state == VALID and self.role_a)) else None]
        if self.out and self.out["deadline"] is not None:
            ds.append(self.out["deadline"])
        if self.out and self.out.get("resend_at") is not None:
            ds.append(self.out["resend_at"])
        if self.pending:
            ds.append(self.pending.get("instant") if self.pending.get("committed") else self.pending["deadline"])
        if self.state == VALID:
            ds.append(self.val["t0"] + self.cfg.t_valid + 0.01)
        if self.state == DATA and self.cfg.silence_descent:
            ds.append(self.peer_heard + self.cfg.t_silence + 0.01)
        if self.state == RECOV and self.cfg.silence_descent:
            ds.append(self.peer_heard + self.cfg.t_recovery + 0.01)
        ds = [d for d in ds if d is not None]
        return min(ds) if ds else None

