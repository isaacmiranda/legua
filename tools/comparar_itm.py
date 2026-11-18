"""Compara a difração do testador de enlaces com o ITM (Longley-Rice) da NTIA e grava os vetores de referência.

Uso (o ITM fica fora do repositório; a licença da NTIA é de domínio público nos EUA, mas não copiamos o código):
  git clone --depth 1 https://github.com/NTIA/itm.git ~/.cache/ext/itm
  mkdir -p /tmp/itmrun && cp -r ~/.cache/ext/itm/src ~/.cache/ext/itm/include /tmp/itmrun && cp tools/itm_drv.cpp /tmp/itmrun
  (cd /tmp/itmrun && sed -i 's#\\\\#/#g' src/*.cpp include/*.h && g++ -O1 -std=c++11 '-D__declspec(x)=' -I include -o drv itm_drv.cpp src/*.cpp)
  PYTHONPATH=. ~/.venvs/legua/bin/python tools/comparar_itm.py --driver /tmp/itmrun/drv
Grava simsuite/tests/vetores_itm.json (perfis + perda do ITM), que o teste usa sem precisar do ITM.
ITM: modo P2P, clima continental temperado, N0 = 301, polarização vertical, solo médio (eps 15, sigma 0,005 S/m), 915 MHz,
tempo, localização e situação a 50 % (mediana). A perda do ITM inclui o espaço livre; a do testador é FSPL + difração."""
import argparse
import json
import math
import os
import random
import subprocess

from simsuite.analysis import enlace as L

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "simsuite", "tests", "vetores_itm.json")
PARAMS = dict(f_mhz=915.0, climate=5, N0=301.0, pol=1, eps=15.0, sigma=0.005, mdvar=0, time=50.0, loc=50.0, sit=50.0)


def _grade(D, n=101):
    return [D * i / (n - 1) for i in range(n)]


def perfis():
    """Perfis sintéticos (d em km, h em m): plano, morros gaussianos e senoidais, dois morros, terreno rugoso."""
    out = []
    for D in (2.0, 5.0, 10.0, 20.0):
        d = _grade(D)
        out.append((f"plano_{D:g}km", d, [100.0] * len(d), 10.0, 10.0))
        out.append((f"plano_{D:g}km_mastro3m", d, [100.0] * len(d), 3.0, 3.0))
        for alt in (10, 30, 60, 120, 250):
            w = 0.06 * D
            out.append((f"gume_{D:g}km_{alt}m", d, [100.0 + alt * math.exp(-((x - D / 2) ** 2) / (2 * w * w)) for x in d], 10.0, 10.0))
        for alt in (30, 100):
            out.append((f"suave_{D:g}km_{alt}m", d, [100.0 + alt * math.sin(math.pi * x / D) ** 2 for x in d], 10.0, 10.0))
        out.append((f"dois_morros_{D:g}km", d, [100.0 + 60 * math.exp(-((x - D / 3) ** 2) / (2 * (0.05 * D) ** 2)) + 80 * math.exp(-((x - 2 * D / 3) ** 2) / (2 * (0.05 * D) ** 2)) for x in d], 10.0, 10.0))
        rnd = random.Random(int(D * 10))
        fase = [rnd.uniform(0, 6.28) for _ in range(4)]
        out.append((f"rugoso_{D:g}km", d, [100.0 + sum(25.0 / (k + 1) * math.sin(2 * math.pi * (k + 1) * 1.7 * x / D + fase[k]) for k in range(4)) for x in d], 10.0, 10.0))
    return out


def itm(driver, casos):
    entrada = []
    for nome, d, h, ht, hr in casos:
        n = len(d)
        entrada.append("%g %g %g %d %g %d %g %g %d %g %g %g %d %.6f %s" % (ht, hr, PARAMS["f_mhz"], PARAMS["climate"], PARAMS["N0"], PARAMS["pol"],
                       PARAMS["eps"], PARAMS["sigma"], PARAMS["mdvar"], PARAMS["time"], PARAMS["loc"], PARAMS["sit"], n, d[-1] * 1000 / (n - 1),
                       " ".join("%.3f" % x for x in h)))
    r = subprocess.run([driver], input="\n".join(entrada) + "\n", capture_output=True, text=True, timeout=120)
    linhas = r.stdout.split("\n")
    return [(int(x.split()[0]), float(x.split()[1]), int(x.split()[2])) for x in linhas if x.strip()]


def nossa(d, h, ht, hr):
    j = L.analisar_perfil(d, h, ht, hr, 4 / 3)["perda_difracao_db"]
    p = L.bullington_p526(d, h, ht, hr, 4 / 3)["perda_db"]
    return L.fspl(d[-1]) + j, L.fspl(d[-1]) + p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver", required=True)
    a = ap.parse_args()
    casos = perfis()
    res = itm(a.driver, casos)
    assert len(res) == len(casos), "o driver devolveu %d resultados para %d casos" % (len(res), len(casos))
    vet, linhas = [], []
    for (nome, d, h, ht, hr), (rc, A, w) in zip(casos, res):
        vet.append(dict(nome=nome, d_km=d, h_m=h, h_tx=ht, h_rx=hr, itm_perda_db=A, itm_rc=rc, itm_avisos=w))
        j, p = nossa(d, h, ht, hr)
        linhas.append((nome, A, j, p))
    with open(SAIDA, "w") as fh:
        json.dump(dict(fonte="NTIA ITM (github.com/NTIA/itm), modo P2P TLS", params=PARAMS, casos=vet), fh, separators=(",", ":"))
    def resumo(rot, k):
        e = [l[k] - l[1] for l in linhas]
        m = sum(e) / len(e)
        print(f"{rot:34s} erro médio {m:+6.1f} dB · desvio {math.sqrt(sum((x - m) ** 2 for x in e) / len(e)):4.1f} dB · pior subestima {min(e):+6.1f} · pior superestima {max(e):+6.1f}")
    print(f"{len(linhas)} perfis; erro = testador - ITM (negativo = testador otimista)")
    resumo("gume único (J), como era", 2)
    resumo("P.526-16 §4.5.1 (eq. 57)", 3)
    for l in linhas:
        print(f"  {l[0]:26s} ITM {l[1]:6.1f}  J {l[2]:6.1f} ({l[2]-l[1]:+5.1f})  P.526 {l[3]:6.1f} ({l[3]-l[1]:+5.1f})")


if __name__ == "__main__":
    main()
