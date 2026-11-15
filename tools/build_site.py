#!/usr/bin/env python3
"""Gera site/data.json a partir de simsuite/results/*.json (para o GitHub Pages).

Uso:  python3 tools/build_site.py [--resultados simsuite/results] [--saida site/data.json]
Só lê números de simulação (sem chaves, sem GNSS, sem dados pessoais). NaN/inf viram null.
"""
import argparse
import datetime
import json
import math
import os
import subprocess
import sys

CENARIOS = ["modos", "formal", "B2", "B3", "B4", "B5", "B6", "B7", "B9", "B10", "B11",
            "F", "F6", "F7", "M", "T23", "T456"]


def limpar(x):
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return None
        return float(f"{x:.5g}")
    if isinstance(x, dict):
        return {k: limpar(v) for k, v in x.items()}
    if isinstance(x, list):
        return [limpar(v) for v in x]
    return x


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--resultados", default="simsuite/results")
    ap.add_argument("--saida", default="site/data.json")
    a = ap.parse_args(argv)
    dados, escalas, faltando = {}, {}, []
    for c in CENARIOS:
        p = os.path.join(a.resultados, c + ".json")
        if not os.path.exists(p):
            faltando.append(c)
            continue
        d = json.load(open(p))
        if "erro" in d:
            faltando.append(c + " (erro)")
            continue
        r = d["resultado"]
        if c == "B9":                       # só o que o site usa; as 216 linhas ficam fora
            r = {"falhas_com_ldro_auto": r["falhas_com_ldro_auto"], "nota": r["nota"]}
        dados[c] = limpar(r)
        escalas[c] = d.get("escala")
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                check=True).stdout.strip()
    except Exception:
        commit = None
    meta = {"gerado_em": datetime.date.today().isoformat(), "commit": commit,
            "escalas": sorted({e for e in escalas.values() if e}), "faltando": faltando}
    os.makedirs(os.path.dirname(a.saida) or ".", exist_ok=True)
    with open(a.saida, "w") as fh:
        json.dump({"meta": meta, "dados": dados}, fh, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    # data.js permite abrir o site por file:// e no Pages sem fetch
    js = os.path.splitext(a.saida)[0] + ".js"
    with open(a.saida) as src, open(js, "w") as out:
        out.write("window.LEGUA_DATA=" + src.read() + ";\n")
    print(f"{a.saida}: {os.path.getsize(a.saida) / 1024:.0f} KB, escala {meta['escalas']}, faltando {faltando or 'nada'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
