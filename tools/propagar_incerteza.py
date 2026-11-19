"""Propaga a incerteza da calibração aos resultados da suíte (docs/09 §4).

Roda os cenários escolhidos três vezes: com a calibração nominal e com as duas variantes (`simsuite.analysis.calibracao.variantes`:
cada constante deslocada de uma incerteza no sentido que piora e no sentido que melhora o enlace). Para cada número dos
resultados grava a faixa [mínimo, máximo] entre as três rodadas, e um resumo com as maiores faixas. A faixa NÃO é um intervalo
de confiança estatístico: é a sensibilidade do resultado ao deslocamento simultâneo de todas as constantes pela incerteza que a
bancada informou (cenário de pior e de melhor caso), somada à incerteza de amostragem da própria simulação, que fica à parte.

Uso (precisa do venv):
  PYTHONPATH=. ~/.venvs/legua/bin/python tools/propagar_incerteza.py calibracao.json --escala quick --so F modos
Saída: simsuite/results[_full]/cal_<id>/incerteza/{nominal,pessimista,otimista,faixas}/ e resumo.md.
"""
import argparse
import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from simsuite.analysis import calibracao as C  # noqa: E402


def faixas(nom, pes, oti, caminho="", out=None):
    """Percorre as três estruturas em paralelo; folhas numéricas que mudam viram {"nom", "min", "max"}. Devolve a estrutura e
    acumula em `out` (caminho, nom, min, max) das folhas que mudaram."""
    if out is None:
        out = []
    if isinstance(nom, dict):
        r = {}
        for k, v in nom.items():
            r[k] = faixas(v, pes.get(k) if isinstance(pes, dict) else None, oti.get(k) if isinstance(oti, dict) else None, f"{caminho}/{k}", out)[0]
        return r, out
    if isinstance(nom, list):
        r = []
        for i, v in enumerate(nom):
            r.append(faixas(v, pes[i] if isinstance(pes, list) and i < len(pes) else None, oti[i] if isinstance(oti, list) and i < len(oti) else None, f"{caminho}[{i}]", out)[0])
        return r, out
    if isinstance(nom, (int, float)) and not isinstance(nom, bool) and isinstance(pes, (int, float)) and isinstance(oti, (int, float)):
        lo, hi = min(nom, pes, oti), max(nom, pes, oti)
        if hi - lo > 1e-12:
            out.append((caminho, nom, lo, hi))
            return {"nom": nom, "min": lo, "max": hi}, out
    return nom, out


def rodar(escala, cenarios, saida, calibracao=None):
    cmd = [sys.executable, "-m", "simsuite.run_suite", "--escala", escala, "--procs", "1", "--so", *cenarios, "--saida", saida]
    if calibracao:
        cmd += ["--calibracao", calibracao]
    env = dict(os.environ, PYTHONPATH=RAIZ)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=RAIZ)
    if r.returncode != 0:
        raise SystemExit(f"a rodada falhou ({' '.join(cmd[-4:])}):\n{r.stdout[-800:]}\n{r.stderr[-800:]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("calibracao")
    ap.add_argument("--escala", default="quick", choices=["quick", "full"])
    ap.add_argument("--so", nargs="+", required=True, help="cenários (ex.: F modos)")
    ap.add_argument("--saida", default=None, help="diretório de saída (padrão: results[_full]/cal_<id>/incerteza)")
    a = ap.parse_args(argv)
    try:
        cal, _ = C.carregar(a.calibracao)
        pes, oti = C.variantes(cal)
    except (C.CalibracaoInvalida, OSError, ValueError) as e:
        raise SystemExit(f"calibração inválida: {e}")
    if not any(float(c.get("incerteza", 0)) > 0 for c in cal["constantes"].values()):
        raise SystemExit("a calibração não traz incerteza (todas zero): não há o que propagar")
    base = a.saida or os.path.join(RAIZ, "simsuite", "results" if a.escala == "quick" else "results_full", f"cal_{cal['id']}", "incerteza")
    os.makedirs(base, exist_ok=True)
    arqs = {}
    for nome, c in (("nominal", cal), ("pessimista", pes), ("otimista", oti)):
        arqs[nome] = os.path.join(base, f"calibracao-{nome}.json")
        with open(arqs[nome], "w", encoding="utf-8") as fh:
            json.dump(c, fh, ensure_ascii=False, indent=2)
        rodar(a.escala, a.so, os.path.join(base, nome), arqs[nome])
    todas, resumo = [], {}
    os.makedirs(os.path.join(base, "faixas"), exist_ok=True)
    for cen in a.so:
        dados = {n: json.load(open(os.path.join(base, n, f"{cen}.json"), encoding="utf-8")) for n in ("nominal", "pessimista", "otimista")}
        est, mud = faixas(dados["nominal"]["resultado"], dados["pessimista"]["resultado"], dados["otimista"]["resultado"], cen)
        with open(os.path.join(base, "faixas", f"{cen}.json"), "w", encoding="utf-8") as fh:
            json.dump({"cenario": cen, "escala": a.escala, "calibracao": cal["id"], "aviso": "faixa = nominal, pessimista e otimista; não é intervalo de confiança", "resultado": est}, fh, ensure_ascii=False)
        todas += mud
        resumo[cen] = len(mud)
    todas.sort(key=lambda x: -(x[3] - x[2]))
    with open(os.path.join(base, "resumo.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# Incerteza da calibração `{cal['id']}` nos resultados (escala {a.escala})\n\n")
        fh.write("Faixa = [mínimo, máximo] entre a calibração nominal e as variantes pessimista e otimista (cada constante deslocada de uma incerteza).\n"
                 "Não é intervalo de confiança; a incerteza de amostragem da simulação fica à parte.\n\n")
        fh.write("| Número | Nominal | Mínimo | Máximo | Amplitude |\n|---|---|---|---|---|\n")
        for caminho, nom, lo, hi in todas[:30]:
            fh.write(f"| `{caminho}` | {nom:.4g} | {lo:.4g} | {hi:.4g} | {hi - lo:.4g} |\n")
        fh.write(f"\nNúmeros que mudaram: {', '.join(f'{c}: {n}' for c, n in resumo.items())}.\n")
    print(f"{len(todas)} números mudaram; resumo em {os.path.join(base, 'resumo.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
