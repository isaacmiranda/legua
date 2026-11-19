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
