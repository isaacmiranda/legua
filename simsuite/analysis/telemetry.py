"""Pipeline de análise da telemetria JSONL (Fase 7).

O mesmo código processa os registros gerados pelo simulador e os que a biblioteca
vai gravar no hardware (um arquivo por nó, ou um arquivo único), desde que sigam o
esquema abaixo. Campos por evento:
  comuns:  v (versão), t (s, relógio GNSS/PPS), node, ev
  tx:      tipo (DATA/ACK/HELLO/PROPOSE/VOTE/COMMIT), seq, modo, sf, bw, cr, pwr, ch, nb, fh, estado
  rx:      tipo, src, seq, modo, rssi, snr
  modo:    modo, estado, motivo        (mudança de modo/estado)
  propose, validado, neg_falhou, alarme_rollback, reboot, persist, rejeitado
  (no hardware: + lat, lon, alt, vel, temp, fw)
"""
import json
import glob
from collections import defaultdict
import numpy as np
from ..core.radio import toa_s, i_tx_ma, VCC
from ..core.regulatory import check_compliance, BR2026
from .stats import block_bootstrap_ci, wilson


def load(paths):
    recs = []
    for p in (glob.glob(paths) if isinstance(paths, str) else paths):
        with open(p) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    recs.sort(key=lambda r: r["t"])
    return recs


def analyze(recs, block_s=3600.0):
    tx_data = {}
    rx_data = set()
    blocks = defaultdict(lambda: [0, 0])
    energy = defaultdict(float)
    txlog = []
    mode_time = defaultdict(lambda: defaultdict(float))
    last_mode = {}
    events = defaultdict(int)
    t_end = recs[-1]["t"] if recs else 0.0
    for r in recs:
        ev = r["ev"]
        if ev == "tx":
            dur = toa_s(r["sf"], r["bw"], r.get("nb", 24), r.get("cr", 1))
            energy[r["node"]] += VCC * i_tx_ma(r["pwr"]) * dur
            txlog.append({"t": r["t"], "dur": dur, "bw": r["bw"], "freq": (r.get("fh"), r["bw"], r["ch"]),
                          "p_dbm": r["pwr"], "fhss": bool(r.get("fh")), "n_hop": 35 if r.get("fh") else 0,
                          "node": r["node"]})
            if r["tipo"] == "DATA" and not r.get("hb"):
                k = (r["node"], r["seq"])
                if k not in tx_data:
                    tx_data[k] = r["t"]
        elif ev == "rx":
            if r["tipo"] == "DATA":
                rx_data.add((r["src"], r["seq"]))
        elif ev == "modo":
            n = r["node"]
            if n in last_mode:
                m0, t0 = last_mode[n]
                mode_time[n][m0] += r["t"] - t0
            last_mode[n] = (r["modo"], r["t"])
        else:
            events[ev] += 1
    for n, (m0, t0) in last_mode.items():
        mode_time[n][m0] += t_end - t0
    for k, t0 in tx_data.items():
        b = int(t0 // block_s)
        blocks[b][1] += 1
        blocks[b][0] += k in rx_data
    bl = [tuple(v) for _, v in sorted(blocks.items())]
    k = sum(b[0] for b in bl)
    n = sum(b[1] for b in bl)
    est, lo, hi = block_bootstrap_ci(bl) if bl else (float("nan"),) * 3
    comp = check_compliance(txlog, BR2026)
    return {"pacotes": n, "entregues": k, "pdr": est, "ic95_blocos": (lo, hi), "ic95_wilson_ingenuo": wilson(k, n),
            "energia_tx_mj_por_no": dict(energy), "tempo_em_modo_s": {n: dict(v) for n, v in mode_time.items()},
            "eventos": dict(events), "conformidade_br2026": comp["conforme"],
            "violacoes": comp["violacoes"], "pior_ocupacao_s": comp["pior_ocupacao_s"]}
