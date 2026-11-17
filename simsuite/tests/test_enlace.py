"""Testador de enlaces: valores físicos conhecidos, identidade de composição com o estimador e paridade
Python x JavaScript (site/propagacao.js, terreno.js, enlace.js)."""
import json
import math
import os
import shutil
import subprocess

import pytest

from simsuite.analysis import enlace as L
from simsuite.analysis import estimator as E

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _plano(D, alt=100.0, n=101):
    return [D * i / (n - 1) for i in range(n)], [alt] * n


def _morro(D, base, alt, pos, larg, n=201):
    d = [D * i / (n - 1) for i in range(n)]
    return d, [base + alt * math.exp(-((x - pos * D) ** 2) / (2 * max(larg, 0.01) ** 2)) for x in d]


def test_valores_fisicos_conhecidos():
    assert L.fspl(1.0) == pytest.approx(91.676, abs=0.01)
    assert L.fspl(10.0) - L.fspl(1.0) == pytest.approx(20.0, abs=1e-9)
    assert L.J(0.0) == pytest.approx(6.03, abs=0.01)
    assert abs(L.J(-0.78)) < 0.01 and L.J(-2.0) == 0.0
    assert L.fresnel_r(0.5, 0.5) == pytest.approx(9.05, abs=0.01)
    assert L.fresnel_r(5, 5) == pytest.approx(28.62, abs=0.02)
    assert L.bulge(5, 5, 4 / 3) == pytest.approx(1.47, abs=0.01)


def test_terreno_plano_nao_difrata_e_morro_obstrui():
    d, h = _plano(10.0)
    p = L.analisar_perfil(d, h, 10, 10, 4 / 3)
    assert p["perda_difracao_db"] == 0.0 and not p["obstruido"] and 0 < p["folga_min_razao"] < 0.6
    d, h = _morro(10.0, 100, 60, 0.5, 1.0)
    m = L.analisar_perfil(d, h, 10, 10, 4 / 3)
    assert m["obstruido"] and m["perda_difracao_db"] > 10 and abs(m["d_obst_km"] - 5.0) < 0.6
    d2, h2 = _morro(10.0, 100, 60, 0.5, 1.0)
    alto = L.analisar_perfil(d2, h2, 90, 90, 4 / 3)         # mastros altos reduzem a obstrução
    assert alto["perda_difracao_db"] < m["perda_difracao_db"]


def test_composicao_com_o_estimador_sem_contar_duas_vezes():
    """Terreno plano e curto, antenas padrão (2,15 dBi, 0,5 dB): o estimador recebe offset 0 e a potência recebida
    é a do espaço livre."""
    d, h = _plano(2.0, n=21)
    r = L.analisar(d, h, 3, 3, 4 / 3, 20.0, 2.15, 2.15, 0.5, 0.5, 0.0, "rural_aberto", 10, 125, 1, True)
    assert r["offset_db"] == pytest.approx(0.0, abs=1e-12)
    assert r["estimativa"]["rx_tipico_dbm"] == pytest.approx(r["rx_dbm"], abs=1e-9)
    assert r["rx_dbm"] == pytest.approx(20.0 + 2 * 1.65 - L.fspl(2.0), abs=1e-9)
    # ganho extra e perda extra entram como diferença, uma vez só
    r2 = L.analisar(d, h, 3, 3, 4 / 3, 20.0, 5.15, 2.15, 0.5, 0.5, 4.0, "rural_aberto", 10, 125, 1, True)
    assert r2["estimativa"]["rx_tipico_dbm"] == pytest.approx(r["rx_dbm"] + 3.0 - 4.0, abs=1e-9)


def test_ambiente_temporario_nao_vaza():
    from simsuite.core.channel_static import ENVS
    antes = set(ENVS)
    with L.ambiente_enlace("urbano_denso") as k:
        assert ENVS[k]["n"] == 2.0 and ENVS[k]["sigma_static"] == ENVS["urbano_denso"]["sigma_static"]
    assert set(ENVS) == antes and ENVS["urbano_denso"]["n"] == 4.0


CASOS = [
    dict(nome="plano", perfil=("plano", 10.0, 100.0), hTx=10, hRx=10, k=4 / 3, p=20.0, env="rural_aberto"),
    dict(nome="morro", perfil=("morro", 10.0, 100.0, 60.0, 0.5, 1.0), hTx=10, hRx=10, k=4 / 3, p=28.0, env="rural_serra"),
    dict(nome="morro_baixo", perfil=("morro", 6.0, 40.0, 15.0, 0.3, 0.4), hTx=5, hRx=3, k=1.0, p=14.0, env="urbano_residencial"),
    dict(nome="longo", perfil=("plano", 25.0, 5.0), hTx=30, hRx=30, k=4 / 3, p=28.0, env="rural_aberto"),
]


def _perfil(c):
    if c["perfil"][0] == "plano":
        return _plano(c["perfil"][1], c["perfil"][2])
    return _morro(*c["perfil"][1:3], c["perfil"][3], c["perfil"][4], c["perfil"][5])


@pytest.mark.skipif(not shutil.which("node"), reason="sem node")
def test_paridade_python_javascript(tmp_path):
    js = r"""
    const fs = require('fs'), path = process.argv[2];
    const K = JSON.parse(fs.readFileSync(0, 'utf8'));
    global.LeguaEstimator = require(path + '/estimator.js');
    global.LeguaPropagacao = require(path + '/propagacao.js');
    const T = require(path + '/terreno.js'), N = require(path + '/enlace.js').make(K);
    const casos = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
    console.log(JSON.stringify(casos.map(c => {
      const pf = c.perfil[0] === 'plano' ? T.plano(c.perfil[1], c.perfil[2]) : T.morro(c.perfil[1], c.perfil[2], c.perfil[3], c.perfil[4], c.perfil[5]);
      const r = N.analisar({ perfil: pf, hTx: c.hTx, hRx: c.hRx, k: c.k, p_dbm: c.p, gTx: 2.15, gRx: 2.15, lTx: 0.5, lRx: 0.5, extra_db: c.extra || 0,
        env: c.env, sf: 10, bw: 125, cr: 1, fhss: true, retries: 3, interval_s: 60, load: 1, alvo: 0.95, sig: 0 });
      return { perfil: r.perfil, perda: r.perda, rx: r.rx_dbm, rx_est: r.rx_estimador_dbm, offset: r.offset_db, margem: r.estimativa.margem_db,
        conf: r.estimativa.cenarios[1].confirmado, bom: r.melhor ? [r.melhor.sf, r.melhor.bw, r.melhor.cr] : null };
    })));
    """
    f = tmp_path / "run.js"
    f.write_text(js)
    inp = tmp_path / "casos.json"
    inp.write_text(json.dumps(CASOS))
    r = subprocess.run(["node", str(f), os.path.join(RAIZ, "site"), str(inp)], input=json.dumps(E.constantes()),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    for c, s in zip(CASOS, json.loads(r.stdout)):
        d, h = _perfil(c)
        py = L.analisar(d, h, c["hTx"], c["hRx"], c["k"], c["p"], 2.15, 2.15, 0.5, 0.5, c.get("extra", 0.0), c["env"], 10, 125, 1, True)
        pf = py["perfil"]
        assert s["perfil"]["perda_difracao_db"] == pytest.approx(pf["perda_difracao_db"], abs=1e-9), c["nome"]
        assert s["perfil"]["folga_min_razao"] == pytest.approx(pf["folga_min_razao"], abs=1e-9), c["nome"]
        assert s["perda"]["total_db"] == pytest.approx(py["perda_total_db"], abs=1e-9), c["nome"]
        assert s["rx"] == pytest.approx(py["rx_dbm"], abs=1e-9) and s["rx_est"] == pytest.approx(py["rx_dbm"], abs=1e-9)
        assert s["offset"] == pytest.approx(py["offset_db"], abs=1e-9)
        assert s["margem"] == pytest.approx(py["estimativa"]["margem_db"], abs=1e-9)
        assert s["conf"] == pytest.approx(py["estimativa"]["cenarios"][1]["confirmado"], rel=1e-9, abs=1e-12)


@pytest.mark.skipif(not shutil.which("node"), reason="sem node")
def test_leitura_de_csv_do_terreno():
    js = r"""
    const T = require(process.argv[1] + '/terreno.js');
    const casos = {
      duas: T.lerCsv('distancia_km;altitude_m\n0;100\n0,5;112\n1;130', 0),
      ponto: T.lerCsv('0.0,100\n0.5,112\n1.0,130', 0),
      uma: T.lerCsv('100\n110\n120\n130', 3),
      sem_dist: T.lerCsv('100\n110', 0),
      desordem: T.lerCsv('0;100\n2;110\n1;120', 0),
      alt: T.lerCsv('0;100\n1;99999', 0),
      texto: T.lerCsv('0;100\n1;abc', 0),
      desloc: T.lerCsv('5;100\n6;110', 0),
    };
    console.log(JSON.stringify(casos));
    """
    r = subprocess.run(["node", "-e", js, os.path.join(RAIZ, "site")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout)
    assert c["duas"]["perfil"]["d"] == [0, 0.5, 1] and c["duas"]["perfil"]["h"] == [100, 112, 130]
    assert c["ponto"]["perfil"]["d"] == [0, 0.5, 1]
    assert c["uma"]["perfil"]["d"] == [0, 1, 2, 3]
    assert c["desloc"]["perfil"]["d"] == [0, 1]                  # a origem é normalizada para 0
    for k in ("sem_dist", "desordem", "alt", "texto"):
        assert "erro" in c[k], k


@pytest.mark.skipif(not shutil.which("node"), reason="sem node")
def test_leitura_de_hgt_e_perfil_entre_pontos():
    """Grade SRTM3 sintética (plano inclinado leste-oeste + um vazio): elevação bilinear, perfil, tiles ausentes."""
    js = r"""
    const T = require(process.argv[1] + '/terreno.js');
    const n = 1201, buf = new ArrayBuffer(n * n * 2), dv = new DataView(buf);
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) dv.setInt16(2 * (r * n + c), 100 + Math.round(c / 4), false);   // sobe 300 m para leste
    dv.setInt16(2 * (600 * n + 600), -32768, false);                                                                     // um vazio
    const g = T.lerHgt(buf, 'S23W046.hgt');
    const out = { g: g.erro || [g.grade.lat0, g.grade.lon0, g.grade.n] };
    out.centro = T.elevacao([g.grade], -22.5, -45.5).v;
    out.oeste = T.elevacao([g.grade], -22.5, -46.0).v;
    out.leste = T.elevacao([g.grade], -22.5, -45.0).v;
    out.fora = T.elevacao([g.grade], -21.5, -45.5);
    const p = T.perfilEntre([g.grade], { lat: -22.5, lon: -45.9 }, { lat: -22.5, lon: -45.1 }, 30);
    out.n = p.perfil.d.length; out.D = p.D_km; out.h0 = p.perfil.h[0]; out.h1 = p.perfil.h[p.perfil.h.length - 1];
    out.mono = p.perfil.h.every((v, i, a) => i === 0 || v >= a[i - 1] - 1e-9);
    out.sem_grade = T.perfilEntre([g.grade], { lat: -22.5, lon: -45.9 }, { lat: -22.5, lon: -44.95 }, 30).erro;
    out.nome_ruim = T.lerHgt(buf, 'foo.hgt').erro;
    out.tamanho_ruim = T.lerHgt(new ArrayBuffer(1000), 'S23W046.hgt').erro;
    out.polar = T.perfilEntre([g.grade], { lat: 70, lon: 0 }, { lat: 70, lon: 0.5 }, 30).erro;
    out.curto = T.perfilEntre([g.grade], { lat: -22.5, lon: -45.5 }, { lat: -22.5, lon: -45.5 }, 30).erro;
    out.hav = T.haversineKm(0, 0, 0, 1);
    console.log(JSON.stringify(out));
    """
    r = subprocess.run(["node", "-e", js, os.path.join(RAIZ, "site")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout)
    assert o["g"] == [-23, -46, 1201]
    assert o["oeste"] == pytest.approx(100.0) and o["leste"] == pytest.approx(400.0)
    assert o["centro"] == pytest.approx(250.0, abs=1.0)
    assert o["fora"]["ok"] is False and o["fora"]["falta"] == "S22W046"
    assert 80 < o["D"] < 85
    assert o["h1"] > o["h0"] and o["mono"]
    assert "falta a grade S23W045.hgt" in o["sem_grade"]
    assert "nome do arquivo" in o["nome_ruim"] and "tamanho" in o["tamanho_ruim"]
    assert "60" in o["polar"] and "0,02" in o["curto"]
    assert o["hav"] == pytest.approx(111.19, abs=0.05)


@pytest.mark.skipif(not shutil.which("node") or not shutil.which("gcc"), reason="sem node ou gcc")
def test_trecho_c_gerado_compila_e_usa_o_enum_certo(tmp_path):
    from simsuite.protocol.perfis import PERFIL_C
    js = r"""
    const G = require(process.argv[1] + '/perfil_c.js');
    const out = {};
    for (const n of Object.keys(G.PERFIS)) for (const cap of [-20, 0, 14.4, 28, 40]) out[n + '|' + cap] = G.gerar({ perfil: n, cap_dbm: cap, ruido_db: 6 });
    console.log(JSON.stringify(out));
    """
    r = subprocess.run(["node", "-e", js, os.path.join(RAIZ, "site")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    gerado = json.loads(r.stdout)
    enum = {0: "LEGUA_PROFILE_DEFAULT", 1: "LEGUA_PROFILE_STABLE", 2: "LEGUA_PROFILE_CAUTIOUS"}
    for chave, texto in gerado.items():
        nome, cap = chave.split("|")
        assert enum[PERFIL_C[nome]] in texto
        esperado = max(-9, min(28, round(float(cap))))
        assert "cfg->cap_dbm = %d;" % esperado in texto
        c = tmp_path / "t.c"
        c.write_text(texto + "\nint main(void) { legua_config c; return meu_enlace_config(&c, 1, 2); }\n")
        cc = subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-fsyntax-only", "-I", os.path.join(RAIZ, "core", "include"),
                             "-I", os.path.join(RAIZ, "core"), str(c)], capture_output=True, text=True)
        assert cc.returncode == 0, (chave, cc.stderr)
    with pytest.raises(Exception):
        subprocess.run(["node", "-e", "require(process.argv[1]+'/perfil_c.js').gerar({perfil:'x'})", os.path.join(RAIZ, "site")], check=True, capture_output=True)
