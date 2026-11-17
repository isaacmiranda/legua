"""Máquina de estados de referência da Légua v1 para um enlace P2P (doc 05).

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
  - o instante de troca é RELATIVO (delay_ms do COMMIT, contado do fim da transmissão do COMMIT, docs/07 §4);
  - âncora e contador gravados só depois da validação (ou no COMMIT, para ablação);
  - todo controle autenticado; quadros com MIC inválido ou contador repetido descartados;
  - alarme de rollback repetido sem queda de SNR (possível jamming);
  - limite de falhas de MIC (docs/07 §6): `mic_fail_n` quadros do par com MIC inválido em `mic_fail_window`
    congelam a negociação por `mic_fail_hold` (não propõe e vota "não"); o modo atual é mantido;
  - rotação de chave (docs/07 §6.2): aceita key_id corrente, o anterior durante a rotação e o seguinte (segue o
    par); o estado da chave vai no registro de NVM.
"""
import math
from dataclasses import dataclass, field, replace
from .modes import DATA_BYTES, ACK_BYTES, CTRL_BYTES

MIC_RING = 8        # máximo de mic_fail_n (tamanho do anel no núcleo C, LEGUA_MIC_RING)
EPS = 1e-9          # tolerância de ponto flutuante nos prazos (os instantes caem na grade de ms do núcleo C)


def _due(now, t):
    return now >= t - EPS


def _over(x, limit):
    """x > limit com a mesma tolerância (x e limit caem na grade de ms)."""
    return x > limit + EPS


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
    auth: bool = True    # MIC válido (com a chave `key` carregada no receptor)
    key: int = 0         # key_id do quadro (bits 2-3 das flags)
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
    mic_fail_n: int = 5              # falhas de MIC na janela -> congela a negociação (0 = desligado; até 8)
    mic_fail_window: float = 600.0   # s
    mic_fail_hold: float = 3600.0    # s de congelamento (renovado se as falhas continuarem)
    resync_n: int = 8                # quadros do par recusados seguidos -> pede RESYNC (0 = desligado; docs/07 §6.3)
    t_resync_min: float = 30.0       # s: recuo inicial entre pedidos e intervalo mínimo entre respostas
    t_resync_max: float = 600.0      # s: teto do recuo (dobra a cada pedido sem resposta)
    fade_k: float = 0.0              # margem de aceleração += fade_k x desvio do SNR (0 = desligado)
    fade_window: int = 30            # amostras de SNR para o desvio
    power_control: bool = True


class Endpoint:
    def __init__(self, nid, peer, modes, base, rec, cfg, rng, noise_rise=0.0, cap=28.0):
        self.id, self.peer = nid, peer
        self.modes, self.base, self.rec = modes, base, rec
        self.cfg, self.rng, self.noise_rise, self.cap = cfg, rng, noise_rise, cap
        self.role_a = nid < peer
        self.nvm = {"anchor": None, "ctr_block": 0, "peer_blk": 0,   # registro em NVM (docs/07 §5)
                    "key": 0, "key_prev": False}                    # chave de TX e rotação em curso (§6.2)
        self._nv_dirty = False
        self.stats = dict(trocas=0, rollbacks=0, degradacoes=0, quedas_base=0, neg_ok=0,
                          neg_fail=0, neg_recusa=0, desc_silencio=0, alarmes=0, rejeitados=0,
                          tx_ctrl=0, entregues=0, gerados=0, perdidos=0, alarmes_mic=0, resync_pedidos=0, resync_ok=0)
        if not 0 <= cfg.mic_fail_n <= MIC_RING:
            raise ValueError(f"mic_fail_n vai de 0 a {MIC_RING}")
        if cfg.resync_n and not 0 < cfg.t_resync_min <= cfg.t_resync_max:
            raise ValueError("t_resync_min deve ser > 0 e <= t_resync_max")
        self._boot(0.0)

    # ----------------------------------------------------------------- base
    def _boot(self, now):
        a = self.nvm["anchor"]
        self.mode = a or self.base
        self.state = DATA if a else BASE
        self.prev = a or self.base          # destino de rollback
        self.p = self._cap(self.mode)
        self.peer_cap = None                 # teto de TX do par, aprendido em HELLO/PROPOSE/VOTE (docs/07 §4)
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
        self.peer_ctr = self.nvm["peer_blk"] * 64    # piso do contador do par (gravado a cada bloco de 64)
        self.rollback_times = []
        self.freeze_until = now
        self.mic_fail_times = []
        self.mic_block = now                 # até quando vota "não" por falhas de MIC
        self.rs_fails = 0                    # quadros do par recusados desde o último válido (docs/07 §6.3)
        self.rs_nonce = None                 # nonce do pedido de RESYNC pendente
        self.rs_next = now                   # instante mais cedo do próximo pedido
        self.rs_backoff = self.cfg.t_resync_min
        self.rs_rsp_next = now               # instante mais cedo da próxima resposta
        self.key_cur = self.nvm["key"]
        self.key_prev = self.nvm["key_prev"]
        self.speed = 0.0
        self.degraded = False
        self.peer_speed = 0.0
        self.rx_any, self.rx_top, self.rx_map = False, 0, 0     # janela de 32 números de sequência (docs/07)
        self.bad = {}
        self.ok_since_p = 0
        self._now = now
        self._now_hint = now

    def reboot(self, now):
        acts = [("log", {"ev": "reboot"})]
        self._boot(now)
        acts.append(("rx", self.mode))
        return acts

    def _cap(self, m):
        return min(self.cap, m.cap)

    def _bump_ctr(self):
        self.ctr += 1
        if self.ctr % 64 == 0:
            self.nvm["ctr_block"] = self.ctr // 64
            self._nv_dirty = True
        return self.ctr

    def _persist_act(self):
        self.nvm["ctr_block"] = self.ctr // 64          # o registro grava o bloco corrente (seguro: >= usado)
        self._nv_dirty = False
        a = self.nvm["anchor"]
        self.nvm["key"], self.nvm["key_prev"] = self.key_cur, self.key_prev
        return ("persist", {"anchor": a.name if a else None, "ctr_block": self.nvm["ctr_block"],
                            "peer_blk": self.nvm["peer_blk"], "key": self.key_cur, "key_prev": self.key_prev})

    def _flush(self, acts):
        """Acrescenta o registro de NVM se um contador cruzou um bloco durante o evento."""
        if self._nv_dirty:
            self._nv_dirty = False
            acts.append(self._persist_act())
        return acts

    def _seq_is_new(self, seq):
        """Janela de 32 números de sequência (igual a seq_is_new do núcleo C)."""
        seq &= 0xFF
        if not self.rx_any:
            self.rx_any, self.rx_top, self.rx_map = True, seq, 1
            return True
        d = (seq - self.rx_top) & 0xFF
        if d == 0:
            return False
        if d < 128:
            self.rx_map = 0 if d >= 32 else ((self.rx_map << d) & 0xFFFFFFFF)
            self.rx_map |= 1
            self.rx_top = seq
            return True
        d = (self.rx_top - seq) & 0xFF
        if d < 32:
            if self.rx_map & (1 << d):
                return False
            self.rx_map |= 1 << d
            return True
        self.rx_top, self.rx_map = seq, 1
        return True

    def _frame(self, kind, nbytes, mode=None, **body):
        self._bump_ctr()
        m = mode or self.mode
        body["v"] = round(self.speed, 1)        # velocidade GNSS (perfil móvel)
        if kind in ("HELLO", "PROPOSE", "VOTE"):
            body["cap"] = int(round(self.cap))  # teto de TX deste nó, em dBm (byte reservado do controle, docs/07 §4)
        return Frame(kind, self.id, self.peer, m, self._cap(m) if kind != "DATA" else self.p,
                     seq=body.pop("seq", 0), ctr=self.ctr, nbytes=nbytes, body=body, key=self.key_cur)

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

    def _peer_cap_m(self, m):
        """Potência do par para quadros de controle e ACK no modo m: o teto dele, se já o conhecemos; senão supõe o nosso."""
        return self._cap(m) if self.peer_cap is None else min(self.peer_cap, m.cap)

    def _margin(self, m, p=None):
        """Margem do pior sentido: o nosso TX com o ganho eu->par e o TX do par com o ganho par->eu (docs/07 §4).
        Sem o teto do par, supõe o mesmo teto (e vale cap + min(g), como antes). Com uma potência p em teste (controle de
        potência), o par também é limitado a p, como na conta antiga: com tetos iguais o resultado é idêntico."""
        if self.g_me is None and self.g_peer is None:
            return -99
        g_out = self.g_peer if self.g_peer is not None else self.g_me      # eu -> par
        g_in = self.g_me if self.g_me is not None else self.g_peer         # par -> eu
        mine = (self._cap(m) if p is None else p) + g_out - m.sens(self.noise_rise)
        theirs = (self._peer_cap_m(m) if p is None else min(self._peer_cap_m(m), p)) + g_in - m.sens(self.noise_rise)
        return min(mine, theirs)

    def _frozen(self):
        """Perfil móvel: congela a aceleração se algum lado se move ou o SNR oscila."""
        c = self.cfg
        return c.mobile and (max(self.speed, self.peer_speed) > c.v_freeze or self._snr_std() > c.snr_std_freeze)

    def _need_up(self, delta=0.0):
        """Margem exigida para acelerar: fixa + fade_k x variabilidade medida do SNR."""
        c = self.cfg
        extra = c.fade_k * self._snr_std(c.fade_window) if c.fade_k else 0.0
        return c.margin_up + delta + extra

    def _snr_std(self, n=10):
        h = self.snr_hist[-n:]
        if len(h) < 4:
            return 0.0
        mu = sum(h) / len(h)
        return math.sqrt(sum((x - mu) ** 2 for x in h) / len(h))

    # ----------------------------------------------------------------- eventos
    def set_speed(self, v):
        self.speed = v

    def on_app(self, now):
        return self._flush(self._on_app(now))

    def _on_app(self, now):
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
            # fila cheia: descarta o mais antigo que não esteja em voo (igual ao núcleo C)
            self.queue.pop(1 if self.out is not None and len(self.queue) > 1 else 0)
            self.stats["perdidos"] += 1
        self.queue.append((self.seq, hb))

    def on_tx_done(self, frame, now):
        return self._flush(self._on_tx_done(frame, now))

    def _on_tx_done(self, frame, now):
        if frame.kind == "DATA" and self.out and self.out["seq"] == frame.seq and frame.mode == self.mode:
            wait = frame.mode.toa_q(ACK_BYTES) + (0.45 if frame.mode.fhss else 0.05) + 0.15
            self.out["deadline"] = now + wait
        elif (frame.kind == "COMMIT" and self.pending and self.pending["role"] == "A"
              and self.pending.get("committed") and self.pending.get("instant") is None):
            self.pending["instant"] = now + frame.body["delay"]
        return []

    def on_rx(self, f, rssi, snr, now):
        return self._flush(self._on_rx(f, rssi, snr, now))

    def _on_rx(self, f, rssi, snr, now):
        self._now_hint = now
        acts = []
        if f.dst not in (self.id, -1) or f.src != self.peer:
            return acts
        if f.ctr <= self.peer_ctr:
            self.stats["rejeitados"] += 1
            return [("log", {"ev": "rejeitado", "tipo": f.kind})] + self._rs_note_fail(now)
        if not self._key_acceptable(f.key) or not f.auth:
            # key_id fora do aceito ou MIC inválido: contador na janela, conta como falha de MIC
            self.stats["rejeitados"] += 1
            return [("log", {"ev": "rejeitado", "tipo": f.kind})] + self._mic_fail(now) + self._rs_note_fail(now)
        self.peer_ctr = f.ctr
        if f.ctr // 64 > self.nvm["peer_blk"]:           # grava o piso do par a cada bloco de 64
            self.nvm["peer_blk"] = f.ctr // 64
            self._nv_dirty = True
        acts += self._key_seen(f.key)
        self.rs_fails = 0
        if f.kind == "RESYNC_RSP":           # ressincronizado: o piso do par subiu para o contador do par
            self.rs_nonce, self.rs_backoff, self.rs_next = None, self.cfg.t_resync_min, now
            self.stats["resync_ok"] += 1
            return acts + [("log", {"ev": "resync", "arg": 1})]
        if f.kind == "RESYNC":               # o par perdeu o contador: responde (no máximo uma por t_resync_min)
            if self.cfg.resync_n and _due(now, self.rs_rsp_next):
                self.rs_rsp_next = now + self.cfg.t_resync_min
                acts.append(("tx", self._frame("RESYNC_RSP", CTRL_BYTES, nonce=f.body["nonce"])))
                self.stats["tx_ctrl"] += 1
            return acts
        if "cap" in f.body:
            self.peer_cap = f.body["cap"]
        if f.mode != self.mode:
            return acts
        self.peer_heard = now
        if f.kind in ("DATA", "ACK"):
            self.next_hb = max(self.next_hb, now + self.cfg.hb_interval * (1.0 if self.state != VALID else 0.1))
        g = rssi - (f.p_dbm if f.kind == "DATA" else self._peer_cap_m(self.mode))   # só o DATA leva a potência no quadro
        self.g_me = g if self.g_me is None else (1 - self.cfg.ema_a) * self.g_me + self.cfg.ema_a * g
        self.snr_hist.append(snr)
        if f.kind != "ACK":                  # o ACK não leva a velocidade (docs/07 §4)
            self.peer_speed = f.body.get("v", 0.0)
        k = f.kind
        if k == "HELLO":
            if self.state == BASE and not self.role_a and not f.body.get("reply"):
                # descoberta bidirecional: responde a HELLO para o proponente também ouvir
                acts.append(("tx", self._frame("HELLO", CTRL_BYTES, reply=True)))
                self.stats["tx_ctrl"] += 1
            if self.state == BASE and self.role_a and self.pending is None and _due(now, self.neg_block) \
                    and _due(now, self.freeze_until) and not self._frozen():
                acts += self._propose(now, initial=True)
        elif k == "DATA":
            if self._seq_is_new(f.seq):
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
                self.pending["instant"] = now + f.body["delay"]       # relativo ao fim do COMMIT (= agora)
                acts.append(("log", {"ev": "commit_rx"}))
        return acts

    # ----------------------------------------------------------------- negociação
    def _candidate(self, initial=False):
        cur_b = self.mode.budget(self.noise_rise)
        cur_toa = self.mode.toa_us(DATA_BYTES)
        best = None
        for i, m in enumerate(self.modes):
            # só modos mais rápidos e no máximo max_budget_jump dB menos robustos (um "passo")
            if not initial and (m.toa_us(DATA_BYTES) * 10 >= cur_toa * 9 or
                                m.budget(self.noise_rise) < cur_b - self.cfg.max_budget_jump):
                continue
            if self.bad.get(m.name, -1) > self._now:
                continue
            if self._margin(m) >= self._need_up():
                best = m
                break                       # tabela ordenada do mais rápido
        return best

    def _propose(self, now, initial=False, target=None):
        self._now = now
        cand = target or self._candidate(initial)
        if cand is None or cand == self.mode:
            return []
        self.pending = {"cand": cand, "role": "A", "t0": now, "deadline": now + self.cfg.vote_timeout +
                        2 * self.mode.toa_q(CTRL_BYTES)}
        self.state = NEG if self.state != BASE else self.state
        self.stats["tx_ctrl"] += 1
        return [("tx", self._frame("PROPOSE", CTRL_BYTES, cand=cand.name)),
                ("log", {"ev": "propose", "cand": cand.name})]

    # ----------------------------------------------------------------- chaves (docs/07 §6.2)
    def _key_acceptable(self, k):
        c = self.key_cur
        return k == c or (self.key_prev and k == (c + 3) % 4) or k == (c + 1) % 4

    def _key_log(self):
        self._nv_dirty = True
        return [("log", {"ev": "chave", "key": self.key_cur, "prev": self.key_prev})]

    def _key_seen(self, k):
        """Quadro autenticado com a chave k: confirma a rotação (o par já usa a nova) ou segue o par."""
        if k == self.key_cur and self.key_prev:
            self.key_prev = False
            return self._key_log()
        if k == (self.key_cur + 1) % 4:
            self.key_cur, self.key_prev = k, False
            return self._key_log()
        return []

    def rotate_key(self, now):
        """Começa uma rotação: transmite com key_id + 1 e ainda aceita a anterior. None se já há uma em curso."""
        if self.key_prev:
            return None
        self.key_cur, self.key_prev = (self.key_cur + 1) % 4, True
        return self._flush(self._key_log())

    def _rs_note_fail(self, now):
        """Ressincronização do contador do par (docs/07 §6.3): `resync_n` quadros do par recusados seguidos, sem nenhum
        válido, pedem um RESYNC com nonce novo; recuo exponencial entre pedidos."""
        c = self.cfg
        if not c.resync_n:
            return []
        self.rs_fails = min(255, self.rs_fails + 1)
        if self.rs_fails < c.resync_n or not _due(now, self.rs_next):
            return []
        self.rs_nonce = int(round(self.rng.uniform(0.001, 4294967.295) * 1000))
        self.rs_next = now + self.rs_backoff
        self.rs_backoff = min(self.rs_backoff * 2, c.t_resync_max)
        self.stats["tx_ctrl"] += 1
        self.stats["resync_pedidos"] += 1
        return [("tx", self._frame("RESYNC", CTRL_BYTES, nonce=self.rs_nonce)), ("log", {"ev": "resync", "arg": 0})]

    def _mic_fail(self, now):
        """Limite de falhas de MIC: n falhas na janela congelam a negociação, sem mudar de modo (docs/07 §6)."""
        c = self.cfg
        if not c.mic_fail_n:
            return []
        w = [x for x in self.mic_fail_times if not _due(now - x, c.mic_fail_window)] + [now]
        self.mic_fail_times = w[-c.mic_fail_n:]
        if len(self.mic_fail_times) < c.mic_fail_n:
            return []
        self.mic_fail_times = []
        self.stats["alarmes_mic"] += 1
        self.mic_block = now + c.mic_fail_hold
        self.freeze_until = max(self.freeze_until, self.mic_block)
        return [("log", {"ev": "alarme_mic"})]

    def _on_propose(self, f, now):
        cand = next((m for m in self.modes if m.name == f.body["cand"]), None)
        ok = cand is not None and (self._margin(cand) >= self._need_up(-2.0) or self.state == BASE
                                   or self.g_me is None or cand == self.rec)
        if self._frozen() or not _due(now, self.mic_block):
            ok = False
        self.stats["tx_ctrl"] += 1
        if ok:
            self.pending = {"cand": cand, "role": "B", "committed": False,
                            "deadline": now + self.cfg.vote_timeout + 3 * self.mode.toa_q(CTRL_BYTES) +
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
        self.pending["instant"] = None          # definido em on_tx_done: fim do COMMIT + instant_delay
        self.pending["committed"] = True
        self.stats["tx_ctrl"] += 1
        return [("tx", self._frame("COMMIT", CTRL_BYTES, cand=self.pending["cand"].name,
                                   delay=self.cfg.instant_delay))]

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
            self.nvm["anchor"] = cand
            acts.append(self._persist_act())
        return acts

    def _validated(self, now):
        self.state = DATA
        self.stats["neg_ok"] += 1
        self.neg_backoff = self.cfg.neg_backoff0
        self.prev = self.mode
        acts = [("log", {"ev": "validado", "modo": self.mode.name})]
        if self.cfg.persist_at == "validation":
            self.nvm["anchor"] = self.mode
            acts.append(self._persist_act())
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
        return min(cands, key=lambda x: (x.toa_us(DATA_BYTES), -x.budget(self.noise_rise)))

    def _descend(self, now, why):
        if self.mode == self.base:
            if self.state == BASE:
                return []
            # no modo base mas ainda em DATA/RECUPERACAO (a escada desceu para o próprio base, ou a âncora é o
            # base): sem esta transição o prazo de silêncio vencia de novo no mesmo instante (laço sem avanço)
            self.stats["quedas_base"] += 1
            return self._set_mode(self.base, BASE, now, why)
        nxt = self._step_down(self.mode)
        if nxt is not None and nxt != self.mode:
            self.stats["degradacoes"] += 1
            return self._set_mode(nxt, RECOV, now, why)
        self.stats["quedas_base"] += 1
        return self._set_mode(self.base, BASE, now, why)

    def _power_trim(self):
        self.ok_since_p += 1
        if not self.cfg.power_control or self.ok_since_p < 10 or self.state != DATA:
            return []
        p2 = self.p - 2
        if p2 >= -9 and self._margin(self.mode, p2) >= self.cfg.margin_target + 2:
            self.p = p2
            self.ok_since_p = 0
        return []

    # ----------------------------------------------------------------- tempo
    def on_timer(self, now):
        return self._flush(self._on_timer(now))

    def _on_timer(self, now):
        self._now_hint = now
        acts = []
        c = self.cfg
        # ACK expirado
        if self.out and self.out["deadline"] is not None and _due(now, self.out["deadline"]):
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
        if self.out and self.out.get("resend_at") is not None and _due(now, self.out["resend_at"]):
            f = replace(self.out["frame"], p_dbm=self.p, mode=self.mode, key=self.key_cur)   # retransmissão usa a chave corrente
            f.ctr = self._bump_ctr()
            f.body = dict(f.body, val=(self.state == DATA), v=round(self.speed, 1))
            self.out = {"seq": self.out["seq"], "att": self.out["att"] + 1, "deadline": None, "frame": f}
            acts.append(("tx", f))
        # validação expirada
        if self.state == VALID and _over(now - self.val["t0"], c.t_valid):
            return acts + self._rollback(now, "validacao_expirou")
        # negociação: voto ou commit não chegou
        if self.pending:
            pd = self.pending
            if pd.get("committed") and pd.get("instant") is not None and _due(now, pd["instant"]):
                acts += self._switch(now)
            elif not pd.get("committed") and _due(now, pd["deadline"]):
                acts += self._neg_fail(now)
        # silêncio
        if c.silence_descent:
            if self.state in (DATA,) and _over(now - self.peer_heard, c.t_silence):
                self.stats["desc_silencio"] += 1
                acts += self._descend(now, "silencio")
            elif self.state == RECOV and _over(now - self.peer_heard, c.t_recovery):
                self.stats["desc_silencio"] += 1
                acts += self._descend(now, "silencio_rec")
        # base: HELLO periódico
        if self.state == BASE and self.role_a and self.pending is None and _due(now, self.neg_block) \
                and _due(now, self.freeze_until) and self.consec_ok >= 5 and self.out is None and not self._frozen():
            acts += self._propose(now, initial=True)
        if self.state == BASE and _due(now, self.next_hello) and _over(now - self.peer_heard, 3 * c.hello_interval):
            self.next_hello = now + c.hello_interval * self.rng.uniform(0.7, 1.3)
            self.stats["tx_ctrl"] += 1
            acts.append(("tx", self._frame("HELLO", CTRL_BYTES)))
        # heartbeat
        if self.state in (DATA, RECOV, VALID) and _due(now, self.next_hb) and not (self.state == VALID and not self.role_a):
            self.next_hb = now + (4.0 if self.state == VALID else c.hb_interval) * self.rng.uniform(0.75, 1.25)
            if not self.queue and self.out is None:
                self._enqueue(hb=True)
                acts += self._pump(now)
        # retorno à âncora depois de uma degradação (mais rápido que a aceleração normal)
        anc = self.nvm["anchor"]
        if (self.state == DATA and self.role_a and self.pending is None and self.out is None
                and self.degraded and anc is not None and anc != self.mode
                and self.consec_ok >= 10 and _due(now - self.entered, c.cooldown_back)
                and _due(now, self.neg_block) and _due(now, self.freeze_until) and not self._frozen()
                and self._margin(anc) >= self._need_up(-2.0) and self.bad.get(anc.name, -1) <= now):
            acts += self._propose(now, target=anc)
        # aceleração
        elif (self.state == DATA and self.role_a and self.pending is None and self.out is None
                and self.consec_ok >= c.n_up and _due(now - self.last_change, c.cooldown_up)
                and _due(now, self.neg_block) and _due(now, self.freeze_until)):
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

