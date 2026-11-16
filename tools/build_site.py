#!/usr/bin/env python3
"""Gera site/data.js e site/data.json a partir de simsuite/results (quick) e simsuite/results_full (full).

Uso:  python3 tools/build_site.py [--quick simsuite/results] [--full simsuite/results_full] [--saida site/data.json]
O site distingue as duas escalas; a longa pode estar ausente ou parcial. Também embute as constantes do modelo
(para o estimador do navegador) e o orçamento de tempo. Só números de simulação: sem chaves, GNSS ou dados
pessoais. NaN/inf viram null.
"""
import argparse
import datetime
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CENARIOS = ["modos", "formal", "B2", "B3", "B4", "B5", "B6", "B7", "B9", "B10", "B11",
            "F", "F6", "F7", "P", "M", "T23", "T456", "xsim", "equiv"]


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


def ler_escala(pasta):
    """Lê uma pasta de resultados. Devolve None se não houver nenhum cenário utilizável."""
    if not pasta or not os.path.isdir(pasta):
        return None
    dados, info, faltando, escalas = {}, {}, [], set()
    for c in CENARIOS:
        p = os.path.join(pasta, c + ".json")
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
        info[c] = {"segundos": d.get("segundos")}
        if d.get("escala"):
            escalas.add(d["escala"])
    if not dados:
        return None
    return {"dados": dados, "meta": {"cenarios": info, "faltando": faltando, "completa": not faltando,
                                     "escala": sorted(escalas)[0] if escalas else None}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", "--resultados", dest="quick", default="simsuite/results")
    ap.add_argument("--full", default="simsuite/results_full")
    ap.add_argument("--saida", default="site/data.json")
    a = ap.parse_args(argv)
    from simsuite.analysis.estimator import constantes
    from simsuite.analysis.orcamento import orcamento
    escalas = {}
    for nome, pasta in (("quick", a.quick), ("full", a.full)):
        e = ler_escala(pasta)
        if e:
            escalas[nome] = e
    if "quick" not in escalas:
        print("sem resultados quick em", a.quick, file=sys.stderr)
        return 1
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                check=True).stdout.strip()
        sujo = subprocess.run(["git", "status", "--porcelain", "--", "simsuite", "core"], capture_output=True,
                              text=True, check=True).stdout.strip()
        if sujo:
            commit += "+local"   # resultados gerados com código não commitado: marca, para não enganar
    except Exception:
        commit = None
    saida = {"meta": {"gerado_em": datetime.date.today().isoformat(), "commit": commit},
             "escalas": escalas, "constantes": limpar(constantes()), "orcamento": limpar(orcamento(a.quick, a.full))}
    os.makedirs(os.path.dirname(a.saida) or ".", exist_ok=True)
    with open(a.saida, "w") as fh:
        json.dump(saida, fh, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    js = os.path.splitext(a.saida)[0] + ".js"
    with open(a.saida) as src, open(js, "w") as out:
        out.write("window.LEGUA_DATA=" + src.read() + ";\n")
    resumo = ", ".join(f"{k}: {len(v['dados'])} cenários" + ("" if v["meta"]["completa"] else " (parcial)")
                       for k, v in escalas.items())
    print(f"{a.saida}: {os.path.getsize(a.saida) / 1024:.0f} KB; {resumo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
