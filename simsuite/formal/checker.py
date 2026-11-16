"""Verificação exaustiva (estado explícito) do acordo de modo da AdaptLoRa v1.

Modelo abstrato, independente do código do simulador, das regras do doc 05:
  modos 0=base, 1=R (recuperação), 2=C (corrente), 3=F (candidato mais rápido);
  tempo em ticks; cada quadro enviado num tick chega no seguinte OU é perdido
  (escolha do adversário, sem restrição: perdas arbitrárias e assimétricas);
  reinício (reboot) não determinístico, limitado por nó; voto "não" não determinístico.

Propriedades verificadas:
  P1 nenhum desacordo permanente: não existe ciclo alcançável formado só por estados
     em que os dois nós estão em modos diferentes (o adversário não consegue mantê-los
     separados para sempre);
  P2 limite: maior número de ticks seguidos em desacordo (caminho mais longo no DAG);
  P3 recuperação: de todo estado alcançável existe caminho até "ambos em DATA no
     mesmo modo" (EF), isto é, com entregas a rede sempre pode voltar a operar;
  S1 estados com validação divergente (A validou F, B não) são alcançáveis? (esperado:
     sim, pelo problema dos Dois Generais; P1 garante que se resolvem).
  P4 âncora confirmada: toda âncora gravada em NVM é de um modo em que o PAR já esteve (variável fantasma
     com o histórico de modos de cada nó). É a propriedade que separa os mecanismos "gravar só depois da
     validação" e "janela de validação": sem eles um nó pode reiniciar num modo que o par nunca aceitou.
     P1 e P3 valem mesmo sem esses mecanismos (a descida por silêncio resolve), por isso não os justificam.
Ablações: sem descida por silêncio, sem validação, âncora gravada no COMMIT.
"""
import itertools
import json
import sys
from collections import deque
from dataclasses import dataclass

BASE, DATA, NEG, PEND, VALID, RECOV = range(6)
ST_NAMES = ["BASE", "DATA", "NEG", "PEND", "VALID", "RECOV"]


@dataclass(frozen=True)
class Params:
    t_sil: int = 4
    t_rec: int = 7
    t_valid: int = 5
    k_valid: int = 2
    f_valid: int = 2
    t_vote: int = 2
    t_commit: int = 3
    reboots: int = 1
    silence_descent: bool = True
    validation: bool = True
    persist_at_commit: bool = False
    allow_no_vote: bool = True
    b_never_yes: bool = False      # teto de TX assimétrico: B nunca aceita o modo mais rápido (sempre vota não)


# estado de um nó: (st, mode, prev, anchor, cand, committed, timer, sil, vcnt, fails, val_ok, rb, okcnt, wait)
# wait: ticks desde o último DATA enviado sem ACK (0 = nada pendente)
def node0():
    return (BASE, 0, 0, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0)


def faster(m):
    return {0: 2, 1: 2, 2: 3, 3: -1}[m]


class Model:
    def __init__(self, P, ghost=False):
        self.P = P
        self.ghost = ghost                  # acompanha o histórico de modos de cada nó (P4)

    def init(self):
        s = (node0(), node0(), (), ())      # nós A, B; quadros em trânsito A->B, B->A
        return s + ((1, 1),) if self.ghost else s

    # ------------------------------------------------------------- um nó, um tick
    def step_node(self, me, is_a, inbox, choice):
        """Devolve (novo estado, lista de quadros a enviar). choice: escolhas não
        determinísticas deste nó neste tick: propor?, votar não?, reiniciar?"""
        P = self.P
        st, mode, prev, anchor, cand, comm, timer, sil, vcnt, fails, val_ok, rb, okc, wait = me
        propose, vote_no, reboot = choice
        out = []
        if reboot:
            m = anchor if anchor >= 0 else 0
            return ((DATA if m > 0 else BASE), m, m, anchor, -1, 0, 0, 0, 0, 0, 0, rb + 1, 0, 0), []
        heard = False
        got_ack = False
        got_val = False
        for (k, m, extra) in inbox:
            if m != mode:
                continue
            heard = True
            if k == "DATA":
                out.append(("ACK", mode, 0))
                if extra:
                    got_val = True
            elif k == "ACK":
                got_ack = True
            elif k == "PROPOSE" and not is_a and st in (DATA, BASE, RECOV):
                if vote_no:
                    out.append(("VOTE", mode, (extra, 0)))
                else:
                    out.append(("VOTE", mode, (extra, 1)))
                    cand, comm, timer = extra, 0, 0
                    if st != BASE:
                        st = PEND
            elif k == "VOTE" and is_a and st in (NEG, BASE) and cand >= 0 and extra[0] == cand:
                if extra[1]:
                    out.append(("COMMIT", mode, cand))
                    comm, timer = 1, 0
                else:
                    cand, comm = -1, 0
                    st = DATA if st == NEG else st
            elif k == "COMMIT" and not is_a and cand >= 0 and extra == cand:
                comm, timer = 1, 0
        sil = 0 if heard else min(sil + 1, max(P.t_sil, P.t_rec) + 1)
        timeout = False
        if got_ack and wait:
            okc = min(okc + 1, 2)
            wait = 0
        elif wait:
            wait += 1
            if wait > 2:              # ACK não veio em 2 ticks
                wait, timeout = 0, True
                okc = 0
        # --- validação
        if st == VALID:
            vcnt_t = vcnt + 1
            if is_a:
                if got_ack:
                    val_ok += 1
                    fails = 0
                if timeout:
                    fails += 1
                if val_ok >= P.k_valid:
                    st, prev, val_ok, fails = DATA, mode, 0, 0
                    anchor = mode
                elif fails >= P.f_valid or vcnt_t > P.t_valid:
                    st, mode = (BASE if prev == 0 else DATA), prev
                    sil, fails, val_ok, vcnt_t = 0, 0, 0, 0
            else:
                if got_val:
                    st, prev, anchor, vcnt_t = DATA, mode, mode, 0
                elif vcnt_t > P.t_valid:
                    st, mode, sil, vcnt_t = (BASE if prev == 0 else DATA), prev, 0, 0
            vcnt = vcnt_t if st == VALID else 0
        # --- pendências de negociação
        if cand >= 0:
            if comm:
                timer += 1
                if timer >= (2 if is_a else 1):   # instante combinado: mesmo tick nos dois lados
                    prev = mode if st != BASE else 0
                    mode, cand, comm, timer, sil = cand, -1, 0, 0, 0
                    if P.validation:
                        st, vcnt, fails, val_ok = VALID, 0, 0, 0
                    else:
                        st = DATA
                        prev = mode
                    if P.persist_at_commit or not P.validation:
                        anchor = mode
            else:
                timer += 1
                lim = P.t_vote if is_a else P.t_commit
                if timer > lim:
                    cand, timer = -1, 0
                    if st in (NEG, PEND):
                        st = DATA
        # --- descida por silêncio
        if P.silence_descent:
            if st in (DATA, NEG, PEND) and sil >= P.t_sil and mode > 0:
                if mode >= 2:
                    st, mode, sil = RECOV, 1, 0
                else:
                    st, mode, sil = BASE, 0, 0
                cand, comm, timer = -1, 0, 0
            elif st == RECOV and sil >= P.t_rec:
                st, mode, sil = BASE, 0, 0
        if st == RECOV and got_ack:
            st = DATA
        if st == RECOV and heard and not is_a:
            st = DATA
        # --- envio de A: proposta (escolha) ou dados
        if is_a and not any(o[0] in ("COMMIT",) for o in out):
            if propose and st in (DATA, BASE) and cand < 0 and faster(mode) > 0 and (st == DATA or sil == 0) \
                    and okc >= (1 if st == DATA else 0):
                cand, comm, timer = faster(mode), 0, 0
                if st == DATA:
                    st = NEG
                out.append(("PROPOSE", mode, cand))
            elif (st in (DATA, VALID, RECOV) or (st == BASE and sil == 0)) and not wait:
                out.append(("DATA", mode, 1 if st == DATA else 0))
                wait = 1
        if not is_a and st == BASE and sil > 0:
            out.append(("HELLO", mode, 0))
        if st in (VALID,) and mode != me[1]:
            wait = 0
        return (st, mode, prev, anchor, cand, comm, timer, sil, vcnt, fails, val_ok, rb, okc, wait), out[:2]

    # ------------------------------------------------------------- sucessores
    def successors(self, s):
        A, B, ab, ba = s[:4]
        P = self.P
        res = set()
        loss_ab = list(itertools.product([0, 1], repeat=len(ab)))
        loss_ba = list(itertools.product([0, 1], repeat=len(ba)))
        a_choices = [(p, 0, r) for p in (0, 1) for r in (0, 1) if not (r and A[11] >= P.reboots)]
        votos_b = (1,) if P.b_never_yes else ((0, 1) if P.allow_no_vote else (0,))
        b_choices = [(0, v, r) for v in votos_b for r in (0, 1)
                     if not (r and B[11] >= P.reboots)]
        for la in loss_ab:
            inb_b = tuple(m for m, l in zip(ab, la) if not l)
            for lb in loss_ba:
                inb_a = tuple(m for m, l in zip(ba, lb) if not l)
                for ca in a_choices:
                    nA, outA = self.step_node(A, True, inb_a, ca)
                    for cb in b_choices:
                        nB, outB = self.step_node(B, False, inb_b, cb)
                        t = (nA, nB, tuple(outA), tuple(outB))
                        if self.ghost:
                            t += ((s[4][0] | (1 << nA[1]), s[4][1] | (1 << nB[1])),)
                        res.add(t)
        return res


def agree(s):
    return s[0][1] == s[1][1]


def operating(s):
    return agree(s) and s[0][0] == DATA and s[1][0] == DATA


def explore(P, limit=3_000_000, ghost=False):
    M = Model(P, ghost)
    s0 = M.init()
    idx = {s0: 0}
    states = [s0]
    edges = [None]
    q = deque([0])
    while q:
        i = q.popleft()
        succ = []
        for t in M.successors(states[i]):
            j = idx.get(t)
            if j is None:
                j = len(states)
                idx[t] = j
                states.append(t)
                edges.append(None)
                q.append(j)
                if len(states) > limit:
                    raise RuntimeError("espaço de estados excedeu o limite")
            succ.append(j)
        edges[i] = succ
    return states, edges


def p4_violation(states):
    """Primeiro estado em que um nó tem âncora de um modo em que o par nunca esteve (ou None)."""
    for s in states:
        (A, B), (sa, sb) = s[:2], s[4]
        for x, seen_peer in ((A, sb), (B, sa)):
            if x[3] > 0 and not (seen_peer >> x[3]) & 1:
                return s
    return None


def analyze(P):
    states, edges = explore(P, ghost=True)
    n = len(states)
    dis = [not agree(s) for s in states]
    # P1: ciclo no subgrafo de desacordo (Tarjan iterativo simplificado via DFS de cores)
    color = [0] * n
    cycle_witness = None
    longest = [0] * n
    sys.setrecursionlimit(1_000_000)
    order = []
    for root in range(n):
        if not dis[root] or color[root]:
            continue
        stack = [(root, iter(edges[root]))]
        color[root] = 1
        while stack:
            v, it = stack[-1]
            adv = False
            for w in it:
                if not dis[w]:
                    continue
                if color[w] == 1:
                    cycle_witness = (v, w)
                    break
                if color[w] == 0:
                    color[w] = 1
                    stack.append((w, iter(edges[w])))
                    adv = True
                    break
            if cycle_witness:
                break
            if not adv:
                color[v] = 2
                order.append(v)
                stack.pop()
        if cycle_witness:
            break
    p1 = cycle_witness is None
    bound = None
    if p1:
        for v in order:          # ordem pós-fixada: sucessores antes
            best = 0
            for w in edges[v]:
                if dis[w]:
                    best = max(best, longest[w] + 1)
            longest[v] = best
        bound = max((longest[v] + 1 for v in range(n) if dis[v]), default=0)
    # P3: EF operando (busca reversa)
    rev = [[] for _ in range(n)]
    for v, ws in enumerate(edges):
        for w in ws:
            rev[w].append(v)
    good = [operating(s) for s in states]
    q = deque(i for i in range(n) if good[i])
    can = good[:]
    while q:
        w = q.popleft()
        for v in rev[w]:
            if not can[v]:
                can[v] = True
                q.append(v)
    p3 = all(can)
    s1 = any(s[0][0] == DATA and s[1][0] == DATA and s[0][3] != s[1][3] and s[0][3] >= 0 and s[1][3] >= 0
             for s in states)
    s_dis_valid = any(not agree(s) and s[0][0] == DATA and s[1][0] == DATA for s in states)
    v4 = p4_violation(states)
    out = {"estados": n, "P1_sem_desacordo_permanente": p1, "P2_maior_desacordo_ticks": bound,
           "P3_recuperacao_sempre_possivel": p3,
           "S1_ancoras_divergentes_alcancaveis": s1,
           "desacordo_com_ambos_em_DATA_alcancavel": s_dis_valid,
           "P4_ancora_confirmada_pelo_par": v4 is None}
    if v4 is not None:
        out["contraexemplo_P4"] = fmt(v4)
    if cycle_witness:
        v, w = cycle_witness
        out["contraexemplo"] = {"de": fmt(states[v]), "para": fmt(states[w])}
    return out


def fmt(s):
    A, B, ab, ba = s[:4]
    f = lambda x: {"estado": ST_NAMES[x[0]], "modo": x[1], "ancora": x[3], "silencio": x[7]}
    return {"A": f(A), "B": f(B), "A->B": [m[0] for m in ab], "B->A": [m[0] for m in ba]}


if __name__ == "__main__":
    print(json.dumps(analyze(Params()), indent=1))


# ---------------------------------------------------------------- cadeia de Markov
def prob_successors(M, s, p_loss, propose=False):
    A, B, ab, ba = s[:4]
    out = {}
    for la in itertools.product([0, 1], repeat=len(ab)):
        pa = 1.0
        for l in la:
            pa *= p_loss if l else 1 - p_loss
        inb_b = tuple(m for m, l in zip(ab, la) if not l)
        for lb in itertools.product([0, 1], repeat=len(ba)):
            pb = 1.0
            for l in lb:
                pb *= p_loss if l else 1 - p_loss
            inb_a = tuple(m for m, l in zip(ba, lb) if not l)
            nA, oA = M.step_node(A, True, inb_a, (1 if propose else 0, 0, 0))
            nB, oB = M.step_node(B, False, inb_b, (0, 0, 0))
            t = (nA, nB, tuple(oA), tuple(oB))
            out[t] = out.get(t, 0.0) + pa * pb
    return out


def negotiation_round(p_loss, P=Params(), horizon=400):
    """Uma rodada de aceleração C->F a partir de enlace operando em C, com perda p por quadro.
    Devolve P(terminar em F), P(voltar a C), P(cair para R/base), P(houve desacordo),
    tempo esperado até assentar (ticks) e P(desacordo > k ticks)."""
    M = Model(P)
    # estado operando em C (modo 2), ambos validados, nada em trânsito
    nA = (DATA, 2, 2, 2, -1, 0, 0, 0, 0, 0, 0, 0, 2, 0)
    nB = (DATA, 2, 2, 2, -1, 0, 0, 0, 0, 0, 0, 0, 2, 0)
    dist = {((nA, nB, (), ()), 0, False): 1.0}     # (estado, ticks em desacordo, já houve)
    res = {"F": 0.0, "C": 0.0, "degradou": 0.0}
    dis_any = 0.0
    t_exp = 0.0
    dis_hist = {}
    first = True
    for t in range(horizon):
        nd = {}
        for (s, dcount, seen), pr in dist.items():
            for s2, q in prob_successors(M, s, p_loss, propose=first).items():
                dis = not agree(s2)
                key = (s2, dcount + (1 if dis else 0), seen or dis)
                nd[key] = nd.get(key, 0.0) + pr * q
        first = False
        dist = {}
        for (s, dcount, seen), pr in nd.items():
            A, B = s[0], s[1]
            settled = (A[0] == DATA and B[0] == DATA and A[1] == B[1] and A[4] < 0 and B[4] < 0
                       and A[3] == B[3])
            if t > 0 and (settled or (A[1] <= 1 and B[1] <= 1 and A[1] == B[1])):
                k = "F" if A[1] == 3 else ("C" if A[1] == 2 else "degradou")
                res[k] += pr
                t_exp += pr * (t + 1)
                if seen:
                    dis_any += pr
                dis_hist[dcount] = dis_hist.get(dcount, 0.0) + pr
            else:
                dist[(s, dcount, seen)] = dist.get((s, dcount, seen), 0.0) + pr
        if sum(dist.values()) < 1e-9:
            break
    tot = sum(res.values())
    tail = lambda k: sum(v for d, v in dis_hist.items() if d > k)
    return {"p_perda": p_loss, "P_F": res["F"], "P_volta_C": res["C"], "P_degradou": res["degradou"],
            "P_houve_desacordo": dis_any, "ticks_esperados": t_exp / tot if tot else None,
            "P_desacordo_maior_3": tail(3), "P_desacordo_maior_8": tail(8), "massa_resolvida": tot}


def ablations():
    cases = {
        "referencia": Params(),
        "sem_descida_por_silencio": Params(silence_descent=False),
        "sem_validacao": Params(validation=False),
        "ancora_no_commit": Params(persist_at_commit=True),
        "dois_reboots": Params(reboots=2),
        "teto_assimetrico": Params(b_never_yes=True),
    }
    out = {k: analyze(p) for k, p in cases.items()}
    out["teto_assimetrico"]["nota"] = (
        "B nunca aceita um modo mais rápido (por exemplo, o teto de potência dele não comporta o modo). P3 'falha' só "
        "porque 'operando' exige DATA e a negociação nunca é aceita: os dois ficam em acordo permanente no modo base "
        "(P2 = 0, P1 e P4 valem). É a ausência de aceleração, não perda de enlace; a segurança continua intacta.")
    return out
