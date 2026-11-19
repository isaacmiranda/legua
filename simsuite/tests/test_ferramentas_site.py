"""Ferramentas novas do site (citação, calculadoras, decodificador de pacotes, rastros, medições, cobertura...): lógica pura
em Node e, onde cabe, paridade com a referência Python. Pula sem node."""
import json
import os
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(RAIZ, "site")
precisa_node = pytest.mark.skipif(not shutil.which("node"), reason="sem node")


def _node(js, *args, entrada=None):
    r = subprocess.run(["node", "-e", js, SITE, *args], capture_output=True, text=True, timeout=120, input=entrada)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@precisa_node
def test_citar_bloco_comando_json_e_csv():
    o = _node(r"""
    const C = require(process.argv[1] + '/citar.js'), out = {};
    const meta = { gerado_em: '2026-11-19', commit: 'abc1234', versao_nucleo: '0.1.1', repositorio: 'https://github.com/isaacmiranda/legua' };
    const b = C.bloco({ aba: 'Campo fixo', abaId: 'campo', escala: 'full', cenarios: ['F'], meta, sementes: [1, 2, 3], url: 'https://x/#campo/full' });
    out.texto = b.texto; out.bib = b.bibtex; out.cmd = b.comando;
    out.json = JSON.parse(C.jsonDaAba({ aba: 'Campo fixo', escala: 'quick', cenarios: ['F', 'Z'], meta }, { F: { a: 1 }, G: { b: 2 } }));
    const tab = { querySelectorAll: () => [{ closest: () => ({ querySelector: () => ({ textContent: ' Meu  título ' }) }), querySelectorAll: () => [
      { children: [{ textContent: 'a' }, { textContent: 'b;c' }] }, { children: [{ textContent: '1' }, { textContent: '2' }] }] }] };
    out.csv = C.tabelasCsv(tab, 'proc')[0].csv; out.slug = C.slug('Verificação formal (P1)');
    console.log(JSON.stringify(out));
    """)
    assert "núcleo 0.1.1" in o["texto"] and "longa (full)" in o["texto"] and "commit abc1234" in o["texto"] and "sem medição em hardware" in o["texto"]
    assert "Sementes: 1, 2, 3" in o["texto"] and o["bib"].startswith("@misc{legua2026campo,") and "Miranda, Isaac" in o["bib"]
    assert "--escala full" in o["cmd"] and "--so F" in o["cmd"] and "build_site.py" in o["cmd"]
    assert o["json"]["dados"] == {"F": {"a": 1}} and o["json"]["procedencia"]["commit"] == "abc1234" and "aviso" in o["json"]["procedencia"]
    assert "# proc" in o["csv"] and '"b;c"' in o["csv"] and "# tabela: Meu título" in o["csv"] and o["slug"] == "verificacao-formal-p1"


def test_citation_cff_coerente_com_a_versao_do_nucleo():
    cff = open(os.path.join(RAIZ, "CITATION.cff"), encoding="utf-8").read()
    versao = open(os.path.join(RAIZ, "core", "VERSION")).read().strip()
    assert f'version: "{versao}"' in cff and "Apache-2.0" in cff and "medição em hardware" in cff and "@" not in cff   # sem e-mail


@precisa_node
def test_calculadoras_paridade_com_o_python():
    from simsuite.analysis import estimator as E
    from simsuite.core import radio, regulatory as R
    K = E.constantes()
    casos = [(sf, bw, pl, cr, pre, crc, ex) for sf in (5, 6, 7, 9, 12) for bw in (125, 250, 500) for pl in (1, 14, 24, 51) for cr in (1, 4)
             for pre in (8, 12) for crc in (True, False) for ex in (True, False)]
    js = r"""
    const C = require(process.argv[1] + '/calculadoras.js'), E = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    const out = { toa: E.casos.map(c => C.toaS(c[0], c[1], c[2], c[3], c[4], c[5], c[6])),
      sens: [7, 10, 12].map(sf => C.sensibilidadeDbm(E.K, sf, 125, 1)), itx: [-9, 14, 21, 28].map(p => C.iTxMa(E.K, p)),
      plano: [125, 250, 500].map(bw => C.planoCanais(E.K.regulatorio.faixas_hz, bw).length),
      salto: C.regraSalto(E.K.regulatorio, 125, 40, 2.15), salto2: C.regraSalto(E.K.regulatorio, 125, 20, 8.15), digital: C.regraSalto(E.K.regulatorio, 500, 20, 2.15),
      ciclo: C.cicloUtil(0.4, 36), minimo: C.intervaloMinimoS(0.4, 0.01), bat: C.bateria(E.K, { capMah: 1000, pDbm: 14, toaS: 0.4, pph: 60, rxPorPacoteS: 1, sonoUa: 20 }) };
    console.log(JSON.stringify(out));
    """
    o = _node(js, entrada=json.dumps({"casos": casos, "K": K}))
    for c, t in zip(casos, o["toa"]):
        assert t == pytest.approx(radio.toa_s(c[0], c[1], c[2], c[3], c[4], c[5], c[6]), rel=1e-12), c
    for sf, s in zip((7, 10, 12), o["sens"]):
        assert s == pytest.approx(radio.noise_dbm(125) + radio.SNR_THR[sf] - radio.CR_GAIN_DB[1], abs=1e-9)
    assert o["itx"][0] == pytest.approx(18.0) and o["itx"][1] == pytest.approx(45.0) and o["itx"][3] == pytest.approx(950.0)
    assert o["plano"] == [len(R.channel_plan(R.BR2026, bw)) for bw in (125, 250, 500)]
    assert o["salto"]["ok"] and o["salto"]["tetoDbm"] == pytest.approx(R.BR2026.hop_cap_dbm(40, 2.15, 125), abs=1e-9)
    assert not o["salto2"]["ok"] and o["salto2"]["tetoDbm"] == pytest.approx(R.BR2026.hop_cap_dbm(20, 8.15, 125), abs=1e-9)
    assert o["digital"]["classe"]["canais_min"] == 17 and o["ciclo"] == pytest.approx(0.004) and o["minimo"] == pytest.approx(40.0)
    b = o["bat"]
    assert b["ativoTx"] == pytest.approx(0.4 * 60 / 3600) and 90 < b["dias"] < 120 and b["energiaPacoteMj"] == pytest.approx(45.0 * 3.3 * 0.4)


@precisa_node
def test_decodificador_de_pacotes_igual_ao_wire_py_nos_vetores():
    from simsuite.protocol import wire
    vet = [dict(ctr=ctr, raw=raw.hex(), extra=extra.hex(), esperado=dict(type=wire.unpack(raw, wire.rsp_ctr32(raw) if raw[0] & 31 == 8 else ctr, extra=extra)["type"],
           src=int.from_bytes(raw[2:4], "big"), dst=int.from_bytes(raw[4:6], "big"), flags=raw[1])) for ctr, raw, extra in wire._vetores()]
    o = _node(r"""
    const P = require(process.argv[1] + '/pacote.js'), V = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    console.log(JSON.stringify(V.map(v => { const r = P.decodificar(v.raw, { ctr32: v.ctr, extraHex: v.extra }); return r.erro ? { erro: r.erro } :
      { tipo: r.tipo, src: r.cabecalho[3].valor, dst: r.cabecalho[4].valor, flags: parseInt(r.cabecalho[2].valor, 16), ok: r.mic.confere_com_mic_de_teste, n: r.corpo.length }; })));
    """, entrada=json.dumps(vet))
    assert len(o) == len(vet) == 48
    for v, r in zip(vet, o):
        e = v["esperado"]
        assert "erro" not in r, (v, r)
        assert (r["tipo"], r["src"], r["dst"], r["flags"]) == (e["type"], e["src"], e["dst"], e["flags"]) and r["ok"] is True and r["n"] >= 1, v


@precisa_node
def test_gerador_de_pacotes_igual_ao_wire_py_e_erros_claros():
    from simsuite.protocol import wire
    o = _node(r"""
    const P = require(process.argv[1] + '/pacote.js');
    const g = P.montar({ tipo: 2, src: 1, dst: 2, ctr32: 70000, flags: 1, corpo: [5, 0x24, 4, 1, 2, 3, 4, 5, 6, 7, 8, 9] });
    const rsp = P.montar({ tipo: 8, src: 3, dst: 4, ctr32: 0x1FFFE, corpo: [0, 1, 0xFF, 0xFE], extraHex: '01020304' });
    const d = P.decodificar(g.hex, { ctr32: 70000 });
    console.log(JSON.stringify({ g: g.hex, rsp: rsp.hex, mic_ok: d.mic.confere_com_mic_de_teste, corpo: d.corpo.map(c => c.campo + '=' + c.valor),
      erros: [P.decodificar('', {}).erro, P.decodificar('abc', {}).erro, P.decodificar('0102', {}).erro, P.decodificar('ff' + '00'.repeat(15), {}).erro, P.decodificar('02' + '00'.repeat(15), {}).erro,
        P.montar({ tipo: 2, corpo: [1] }).erro, P.montar({ tipo: 9 }).erro], adv: P.decodificar('02' + 'f0' + '00'.repeat(22), {}).avisos }));
    """)
    py = wire.pack(wire.T_DATA, 1, 2, 70000, bytes([5, 0x24, 4, 1, 2, 3, 4, 5, 6, 7, 8, 9]), flags=1)
    assert o["g"] == py.hex() and o["mic_ok"] is True
    assert o["rsp"] == wire.pack(wire.T_RESYNC_RSP, 3, 4, 0x1FFFE, bytes([0, 1, 0xFF, 0xFE]), extra=bytes([1, 2, 3, 4])).hex()
    assert o["corpo"][0] == "seq=5" and "payload (9 B)=010203040506070809" in o["corpo"]
    assert "hexadecimal" in o["erros"][0] and "ímpar" in o["erros"][1] and "curto" in o["erros"][2] and "versão" in o["erros"][3] and "bytes" in o["erros"][4]
    assert "leva 12 bytes" in o["erros"][5] and "inválido" in o["erros"][6] and any("reservados" in a for a in o["adv"])


def _medicoes_sinteticas(seed=3):
    import math
    import random
    r = random.Random(seed)
    csv = ["distancia_km;rssi_dbm;potencia_dbm"]
    pts = []
    for d in (0.2, 0.3, 0.5, 0.8, 1.2, 1.8, 2.5, 3.5, 5.0, 7.0) * 3:
        pl = 112.0 + 10 * 3.6 * math.log10(d) + r.gauss(0, 3.0)
        rssi = 14 + 0.0 - pl
        rssi = round(rssi, 2); pts.append((d, rssi)); csv.append(f"{d};{rssi:.2f};14")
    return "\n".join(csv), pts


@precisa_node
def test_ajuste_de_percurso_igual_ao_numpy_e_calibracao_valida_no_importador(tmp_path):
    import numpy as np
    from simsuite.analysis import calibracao as CAL
    csv, pts = _medicoes_sinteticas()
    o = _node(r"""
    const M = require(process.argv[1] + '/medicoes.js'), csv = require('fs').readFileSync(0, 'utf8');
    const l = M.lerCsv(csv), a = M.ajustePercurso(l.linhas, { p: 14, ganhos: 0 });
    const cal = M.gerarCalibracao({ id: 'teste-medido', data: '2026-11-19', hardware: 'x', firmware: 'core-v0.1.1', ambiente: 'rural_aberto', percurso: a, limiar: { porSf: {} }, perOffsetDb: 2.5 });
    console.log(JSON.stringify({ n: l.linhas.length, a: { pl1km: a.pl1km, n: a.n, sigma: a.sigma, se_n: a.se_n, r2: a.r2 }, cal: cal.obj, avisos: a.avisos }));
    """, entrada=csv)
    x = np.array([10 * np.log10(d) for d, _ in pts])
    y = np.array([14 - r for _, r in pts])
    n_np, pl_np = np.polyfit(x, y, 1)
    assert o["n"] == 30 and o["a"]["n"] == pytest.approx(n_np, abs=1e-9) and o["a"]["pl1km"] == pytest.approx(pl_np, abs=1e-9)
    res = y - (pl_np + n_np * x)
    assert o["a"]["sigma"] == pytest.approx(np.sqrt(np.sum(res ** 2) / 28), abs=1e-9)
    assert 3.2 < o["a"]["n"] < 4.0 and 109 < o["a"]["pl1km"] < 115 and o["a"]["r2"] > 0.9
    cal = o["cal"]
    CAL.validar(cal)                                                  # o importador do simulador aceita o arquivo gerado no navegador
    assert any("de n =" in cal["notas"] or "erro-padrão de n" in cal["notas"] for _ in [0]) and "coordenadas" in cal["notas"]
    assert cal["constantes"]["canal"]["valor"]["rural_aberto"]["n"] == pytest.approx(n_np, abs=0.006)


@precisa_node
def test_limiar_de_snr_recupera_o_centro_e_recusa_localizacao_e_dados_ruins():
    import math
    import random
    r = random.Random(5)
    linhas = ["snr_db;pdr;sf"]
    for snr in [x * 0.5 for x in range(-50, -6)]:                    # SF10: centro verdadeiro em -12,5 dB
        p = 1 / (1 + math.exp(-(snr + 12.5) / 0.6))
        linhas.append(f"{snr};{min(1, max(0, p + r.gauss(0, 0.03))):.3f};10")
    linhas_ruins = ["snr_db;pdr;sf", "-10;0.5;10", "-12;0.6;10"]
    o = _node(r"""
    const M = require(process.argv[1] + '/medicoes.js'), V = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    const l = M.lerCsv(V.ok.join('\n')), a = M.ajusteLimiar(l.linhas), pouco = M.ajusteLimiar(M.lerCsv(V.ruins.join('\n')).linhas);
    console.log(JSON.stringify({ c: a.porSf[10].c, s: a.porSf[10].s, se: a.porSf[10].se_c, erros_pouco: pouco.erros,
      gps: M.lerCsv('distancia_km;rssi_dbm;lat;lon\n1;-90;-3.7;-38.5').erro, gnss: M.lerCsv('d_km,rssi,gnss_fix\n1,-90,3').erro, sem_d: M.lerCsv('rssi_dbm\n-90').erro,
      vazio: M.lerCsv('').erro, curto: M.ajustePercurso([{ d: 1, rssi: -90 }, { d: 2, rssi: -95 }], { p: 14, ganhos: 0 }).erro, igual: M.ajustePercurso([{ d: 1, rssi: -90 }, { d: 1, rssi: -91 }, { d: 1, rssi: -92 }], { p: 14, ganhos: 0 }).erro,
      pct: M.lerCsv('distancia_km;pdr\n1;85\n2;50').linhas.map(x => x.pdr), virgula: M.lerCsv('distancia_km;rssi_dbm\n1,5;-90,5').linhas[0] }));
    """, entrada=json.dumps({"ok": linhas, "ruins": linhas_ruins}))
    assert o["c"] == pytest.approx(-12.5, abs=0.4) and o["s"] == pytest.approx(0.6, abs=0.3) and 0 < o["se"] < 0.5
    assert "SF10" in o["erros_pouco"][0] and "ao menos 6" in o["erros_pouco"][0]
    assert "localização" in o["gps"] and "localização" in o["gnss"] and "distância" in o["sem_d"] and "cole um CSV" in o["vazio"]
    assert "3 medições" in o["curto"] and "mesma distância" in o["igual"]
    assert o["pct"] == [0.85, 0.5] and o["virgula"]["d"] == 1.5 and o["virgula"]["rssi"] == -90.5


@precisa_node
def test_sensibilidade_tornado_monte_carlo_e_determinismo():
    from simsuite.analysis import estimator as E
    o = _node(r"""
    global.LeguaEstimator = require(process.argv[1] + '/estimator.js');
    const S = require(process.argv[1] + '/sensibilidade.js'), K = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    const base = { env: 'rural_aberto', d_km: 3, sf: 10, bw: 125, cr: 1, p_dbm: 20, fhss: true, retries: 3, interval_s: 60, load: 1 };
    const t = S.tornado(K, base, 'margem'), t2 = S.tornado(K, base, 'confirmado');
    const a = S.monteCarlo(K, base, { pl1km: 3, n: 0.3, snr_thr: 1 }, 120, 0.95, 7), b = S.monteCarlo(K, base, { pl1km: 3, n: 0.3, snr_thr: 1 }, 120, 0.95, 7), c = S.monteCarlo(K, base, {}, 20, 0.95, 7);
    console.log(JSON.stringify({ t: t.linhas.map(l => [l.id, l.baixo, l.alto, l.amplitude]), base: t.base, t2: t2.linhas.slice(0, 3).map(l => l.id), a, igual: JSON.stringify(a) === JSON.stringify(b), c }));
    """, entrada=json.dumps(E.constantes()))
    linhas = {l[0]: l for l in o["t"]}
    assert len(linhas) == 11 and o["t"][0][3] >= o["t"][-1][3]                          # ordenado por amplitude
    assert linhas["p_dbm"][3] == pytest.approx(6.0, abs=1e-6)                           # ±3 dB de potência = 6 dB de margem
    assert linhas["offset_db"][3] == pytest.approx(12.0, abs=1e-6) and linhas["nf_db"][3] == pytest.approx(3.0, abs=1e-6)
    assert linhas["pl1km"][3] == pytest.approx(8.0, abs=1e-6)                           # ±4 dB na perda = 8 dB
    assert o["igual"] is True                                                           # mesma semente, mesmo resultado
    assert o["a"]["margem"]["p5"] < o["a"]["margem"]["p50"] < o["a"]["margem"]["p95"] and 0 <= o["a"]["probAtingeAlvo"] <= 1
    assert o["c"]["margem"]["p5"] == o["c"]["margem"]["p95"] == pytest.approx(o["base"], abs=1e-9)   # sem incerteza, sem espalhamento


def _rastro_exemplo():
    ev = [
        {"v": 1, "t": 0.0, "node": 1, "ev": "modo", "modo": "SF10/125/FH", "estado": "BASE", "motivo": "boot"},
        {"v": 1, "t": 0.0, "node": 2, "ev": "modo", "modo": "SF10/125/FH", "estado": "BASE", "motivo": "boot", "lat": -3.7, "lon": -38.5, "alt": 20},
        {"v": 1, "t": 5.0, "node": 1, "ev": "tx", "tipo": "DATA", "seq": 1, "modo": "SF10/125/FH", "pwr": 14},
        {"v": 1, "t": 5.4, "node": 2, "ev": "rx", "tipo": "DATA", "src": 1, "seq": 1, "rssi": -101.0, "snr": -5.0, "gps_fix": 3},
        {"v": 1, "t": 60.0, "node": 1, "ev": "propose", "modo": "SF9/125/FH"},
        {"v": 1, "t": 70.0, "node": 1, "ev": "modo", "modo": "SF9/125/FH", "estado": "VALIDANDO", "motivo": "commit"},
        {"v": 1, "t": 70.0, "node": 2, "ev": "modo", "modo": "SF9/125/FH", "estado": "VALIDANDO", "motivo": "commit"},
        {"v": 1, "t": 200.0, "node": 1, "ev": "alarme_rollback"},
        {"v": 1, "t": 200.0, "node": 1, "ev": "modo", "modo": "SF10/125/FH", "estado": "BASE", "motivo": "rollback"},
        {"v": 1, "t": 300.0, "node": 2, "ev": "reboot"},
        {"v": 1, "t": 310.0, "node": 2, "ev": "rejeitado", "tipo": "DATA"},
        {"v": 1, "t": 320.0, "node": 2, "ev": "resync", "arg": 0},
    ]
    return ev, "\n".join(json.dumps(e) for e in ev) + "\nlixo\n{\"t\": 1}\n"


@precisa_node
def test_rastros_resumo_igual_ao_python_e_remove_localizacao():
    from collections import Counter
    ev, texto = _rastro_exemplo()
    o = _node(r"""
    const R = require(process.argv[1] + '/rastros.js'), txt = require('fs').readFileSync(0, 'utf8');
    const l = R.ler(txt), s = R.resumo(l.recs), f = R.filtrar(l.recs, { node: 2, ev: 'modo' });
    console.log(JSON.stringify({ n: l.recs.length, avisos: l.avisos, removidos: l.removidos, cont: s.contagem, dur: s.duracao,
      n1: s.nos['1'].modos.map(m => [m.t0, m.t1, m.modo, m.estado]), rb: s.nos['1'].rollbacks, rj: s.nos['2'].rejeitados, rs: s.nos['2'].resync, marcas: s.marcas.map(m => m.tipo),
      f: f.length, jsonl: R.paraJsonl(l.recs), vazio: R.ler('lixo').erro }));
    """, entrada=texto)
    assert o["n"] == len(ev) and dict(o["cont"]) == dict(Counter(e["ev"] for e in ev)) and o["dur"] == 320.0
    assert o["removidos"] == {"lat": 1, "lon": 1, "alt": 1, "gps_fix": 1} and any("localização removidos" in a for a in o["avisos"]) and any("2 linha(s) ignorada(s)" in a for a in o["avisos"])
    assert "-3.7" not in o["jsonl"] and "-38.5" not in o["jsonl"] and "gps_fix" not in o["jsonl"] and '"lat"' not in o["jsonl"]          # localização nunca volta na exportação
    assert o["n1"] == [[0.0, 70.0, "SF10/125/FH", "BASE"], [70.0, 200.0, "SF9/125/FH", "VALIDANDO"], [200.0, 320.0, "SF10/125/FH", "BASE"]]
    assert o["rb"] == 1 and o["rj"] == 1 and o["rs"] == 1 and o["marcas"] == ["rollback", "reboot", "resync"] and o["f"] == 2 and "nenhum evento válido" in o["vazio"]


def test_conversor_de_docs_escapa_e_gera_estrutura():
    import sys
    sys.path.insert(0, os.path.join(RAIZ, "tools"))
    import build_docs as B
    h, s = B.converter("# Título <b>\n\nTexto **forte** e `a<b` com [link](https://x.y/z) e [mal](javascript:alert(1)).\n\n| A | B |\n|---|---|\n| 1 | <script> |\n\n- um\n- dois\n\n```\n<x>&\n```\n\n## Título <b>\n")
    assert "<script>" not in h and "&lt;script&gt;" in h and "<code>a&lt;b</code>" in h and "<b>forte</b>" in h
    assert 'href="https://x.y/z"' in h and "javascript:" not in h.replace("[mal](javascript:alert(1))", "") or 'href="javascript' not in h
    assert "<table>" in h and "<ul><li>um</li><li>dois</li></ul>" in h and "&lt;x&gt;&amp;" in h
    assert [x["id"] for x in s] == ["titulo-b", "titulo-b-2"]                              # ids únicos


def test_especificacao_js_esta_em_dia_com_os_docs():
    import re as _re
    js = open(os.path.join(SITE, "especificacao.js"), encoding="utf-8").read()
    docs = json.loads(js[js.index("=") + 1:js.rindex(";")])
    assert [d["id"] for d in docs] == ["07", "08", "05", "06", "09", "11"]
    for d in docs:
        fonte = open(os.path.join(RAIZ, d["arquivo"]), encoding="utf-8").read()
        n_titulos = len(_re.findall(r"^#{1,4}\s", fonte, flags=_re.M))
        assert len(d["secoes"]) == n_titulos and "<script" not in d["html"], d["id"]       # regenerar com tools/build_docs.py se falhar


def test_pwa_service_worker_lista_todos_os_arquivos_e_nao_toca_em_outras_origens():
    import re as _re
    sw = open(os.path.join(SITE, "sw.js"), encoding="utf-8").read()
    lista = _re.findall(r'"([^"]+)"', sw[sw.index("var ARQUIVOS"):sw.index("];", sw.index("var ARQUIVOS"))])
    for a in lista:
        assert a == "./" or os.path.exists(os.path.join(SITE, a)), f"sw.js lista um arquivo que não existe: {a}"
    reais = {f for f in os.listdir(SITE) if f.endswith((".js", ".html", ".css", ".webmanifest", ".svg")) and f not in ("sw.js", "data.json")}
    assert reais - set(lista) == set(), f"arquivos do site fora do cache offline: {sorted(reais - set(lista))}"
    assert "url.origin !== self.location.origin" in sw and "return;" in sw                  # outras origens (tiles) nunca passam pelo cache
    m = json.load(open(os.path.join(SITE, "manifest.webmanifest"), encoding="utf-8"))
    assert m["start_url"] and m["display"] == "standalone" and m["icons"][0]["src"] == "icone.svg" and m["lang"] == "pt-BR"
    for pagina in ("index.html", "enlace.html", "consolidado.html"):
        h = open(os.path.join(SITE, pagina), encoding="utf-8").read()
        assert 'rel="manifest"' in h and 'name="theme-color"' in h, pagina
