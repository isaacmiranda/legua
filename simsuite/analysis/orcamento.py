"""Orçamento de tempo da escala `full` (e da `quick`) da suíte, a partir de medições reais.

Método: tempo(full) ≈ tempo(quick) × fator de trabalho × contenção.
- fator de trabalho: razão entre o tempo simulado e o número de sementes/amostras de cada cenário nas escalas
  full e quick (lido do código; tabela abaixo).
- contenção: os tempos do quick costumam ser medidos com vários processos disputando CPU e disco, então o
  extrapolado fica alto. A contenção é a mediana de (tempo full medido) / (tempo quick × fator) nos cenários já
  medidos em `results_full/` com `--procs 1`; o intervalo vem do mínimo e do máximo dessas razões.
Cenários sem medição full usam a contenção mediana. Estimativa, não garantia: a carga real depende da máquina.

Uso:  python3 -m simsuite.analysis.orcamento [--quick simsuite/results] [--full simsuite/results_full]
"""
import argparse
import json
import os
import statistics

# fator de trabalho full/quick e a origem no código
FATORES = {
    "modos": (1.0, "fixo"), "amostras": (1.0, "fixo"), "formal": (1.0, "independe da escala"),
    "B2": (3.0, "n_pkt 100 -> 300"), "B3": (1000 / 150, "n 150 -> 1000"), "B4": (3000 / 300, "n 300 -> 3000"),
    "B5": (2000 / 300, "n 300 -> 2000"), "B6": (1.0, "independe da escala"),
    "B7": (6.0, "T 4 h -> 24 h"), "B8": (1.0, "tabela"), "B9": (1.0, "tabela"), "B10": (1.0, "tabela"),
    "B11": (6.0, "T 2 h -> 12 h"),
    "F": (7.5, "T 2 h -> 6 h; 2 -> 5 sementes"), "F6": (7.0, "1 -> 7 dias; 3 sementes"),
    "F7": (17.5, "1 -> 7 dias; 2 -> 5 sementes"),
    "M": (5.0, "T 1 h -> 3 h (gado 6 h -> 24 h); 2 -> 3 sementes"),
    "T23": (4.0, "T 6 h -> 24 h"), "T456": (3.0, "T 2 h -> 6 h"), "fase7": (1.0, "fixo"),
    "xsim": (10.0, "3 -> 6 tamanhos de rede; 1 -> 4 h por semente"), "equiv": (5.0, "30 -> 150 cenários"),
}


def _segundos(d, nome):
    p = os.path.join(d, nome + ".json")
    if not os.path.exists(p):
        return None
    j = json.load(open(p))
    return None if "erro" in j else j.get("segundos")


def orcamento(quick_dir, full_dir):
    q = {n: _segundos(quick_dir, n) for n in FATORES}
    f = {n: _segundos(full_dir, n) for n in FATORES} if full_dir and os.path.isdir(full_dir) else {}
    razoes = {n: f[n] / (q[n] * FATORES[n][0]) for n in FATORES
              if f.get(n) and q.get(n) and q[n] >= 5.0 and FATORES[n][0] > 1}
    if razoes:
        vals = sorted(razoes.values())
        med, lo, hi = statistics.median(vals), vals[0], vals[-1]
    else:
        med, lo, hi = 1.0, 0.5, 1.0
    linhas, tot = {}, dict(central=0.0, baixo=0.0, alto=0.0)
    for n, (fator, origem) in FATORES.items():
        if q.get(n) is None:
            continue
        base = q[n] * fator
        row = {"quick_s": q[n], "fator": round(fator, 2), "origem": origem, "medido_full_s": f.get(n)}
        if f.get(n):
            row.update(central_s=f[n], baixo_s=f[n], alto_s=f[n])
        else:
            row.update(central_s=round(base * med, 1), baixo_s=round(base * lo, 1), alto_s=round(base * hi, 1))
        for k, kk in (("central", "central_s"), ("baixo", "baixo_s"), ("alto", "alto_s")):
            tot[k] += row[kk]
        linhas[n] = row
    return {"linhas": linhas, "total": {k: round(v) for k, v in tot.items()},
            "contencao": {"mediana": round(med, 2), "min": round(lo, 2), "max": round(hi, 2), "medidos": sorted(razoes)},
            "procs": 1}


def estimar_execucao(quick_dir, full_dir, nomes):
    """Estimativa (central, baixo, alto, em segundos) de uma rodada full só dos cenários `nomes`.
    Ignora tempos full já medidos dos próprios cenários (a rodada os refaz), mas usa-os para calibrar a contenção.
    Devolve None se não houver resultado quick para estimar."""
    o = orcamento(quick_dir, full_dir)
    if not o["linhas"]:
        return None
    c = o["contencao"]
    tot = dict(central=0.0, baixo=0.0, alto=0.0)
    for n in nomes:
        base = o["linhas"].get(n)
        if base is None:
            continue
        w = base["quick_s"] * base["fator"]
        tot["central"] += w * c["mediana"]
        tot["baixo"] += w * c["min"]
        tot["alto"] += w * c["max"]
    return {k: round(v) for k, v in tot.items()}


def fmt(s):
    s = int(round(s))
    h, m = divmod(s // 60, 60)
    return f"{h} h {m:02d} min" if h else (f"{m} min {s % 60:02d} s" if m else f"{s} s")


def main(argv=None):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", default=os.path.join(here, "results"))
    ap.add_argument("--full", default=os.path.join(here, "results_full"))
    a = ap.parse_args(argv)
    o = orcamento(a.quick, a.full)
    print(f"{'cenário':8s} {'quick':>7s} {'fator':>6s} {'full (central)':>15s} {'faixa':>20s}  origem")
    for n, r in sorted(o["linhas"].items(), key=lambda kv: -kv[1]["central_s"]):
        faixa = "medido" if r["medido_full_s"] else f"{fmt(r['baixo_s'])} a {fmt(r['alto_s'])}"
        print(f"{n:8s} {r['quick_s']:6.1f}s {r['fator']:6.1f} {fmt(r['central_s']):>15s} {faixa:>20s}  {r['origem']}")
    t, c = o["total"], o["contencao"]
    print(f"\nTotal sequencial (--procs 1): {fmt(t['central'])} (faixa {fmt(t['baixo'])} a {fmt(t['alto'])})")
    print(f"Contenção (medido/extrapolado): mediana {c['mediana']}, min {c['min']}, max {c['max']}; medidos: {c['medidos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
