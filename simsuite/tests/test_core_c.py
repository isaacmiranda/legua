"""Referência Python x núcleo C (Fase 0): codec, tempo no ar e simulação de dois nós.
Pulado se não houver gcc/make. Roda o make com 1 job e baixa prioridade."""
import os
import shutil
import subprocess
import pytest
from simsuite.core.radio import toa_s
from simsuite.protocol import wire

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORE = os.path.join(RAIZ, "core")
precisa_cc = pytest.mark.skipif(not (shutil.which("gcc") or shutil.which("cc")) or not shutil.which("make"),
                                reason="sem compilador C")


def _make(*alvos):
    cmd = ["nice", "-n", "15", "make", "-j1", "-C", CORE, *alvos]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def test_tamanhos_do_formato():
    assert wire.FRAME_LEN[wire.T_DATA] == 24 and wire.FRAME_LEN[wire.T_ACK] == 14
    assert all(wire.FRAME_LEN[t] == 20 for t in (wire.T_HELLO, wire.T_PROPOSE, wire.T_VOTE, wire.T_COMMIT))
    assert wire.DATA_PAYLOAD == wire.BODY_LEN[wire.T_DATA] - 3
    # o DATA de 24 B é a parede do SF10/125 com salto
    assert toa_s(10, 125, wire.FRAME_LEN[wire.T_DATA]) <= 0.4


def test_modo_ida_e_volta():
    for sf in range(5, 13):
        for bw in (125, 250, 500):
            for cr in range(1, 5):
                for fh in (False, True):
                    assert wire.mode_from_id(wire.mode_id(sf, bw, cr, fh)) == (sf, bw, cr, fh)


def test_pack_unpack_e_adulteracao():
    body = bytes(range(12))
    raw = wire.pack(wire.T_DATA, 1, 2, 70000, body)
    assert len(raw) == 24
    assert wire.unpack(raw, 70000)["body"] == body
    ruim = bytearray(raw); ruim[9] ^= 1
    with pytest.raises(ValueError):
        wire.unpack(bytes(ruim), 70000)
    with pytest.raises(ValueError):
        wire.unpack(raw, 70001)                 # contador errado


def test_reconstrucao_do_contador():
    assert wire.reconstruct_ctr(100, 100) is None
    assert wire.reconstruct_ctr(100, 50) is None
    assert wire.reconstruct_ctr(0xFFFF, 3) == 0x10003
    assert wire.reconstruct_ctr(0x1FFF0, 0x0005) == 0x20005


def test_vetores_em_sincronia(tmp_path):
    novo = tmp_path / "v.txt"
    wire.main(["--vetores", str(novo)])
    with open(os.path.join(CORE, "tests", "vectors", "frames.txt")) as fh:
        assert fh.read() == novo.read_text(), "rode: make -C core vectors"


@precisa_cc
def test_toa_c_igual_python():
    r = _make("build/toa_table")
    assert r.returncode == 0, r.stderr
    saida = subprocess.run([os.path.join(CORE, "build", "toa_table")], capture_output=True, text=True).stdout
    linhas = saida.strip().splitlines()
    assert len(linhas) == 3 * 6 * 4 * 4
    for ln in linhas:
        sf, bw, cr, n, us = map(int, ln.split())
        assert abs(us - toa_s(sf, bw, n, cr) * 1e6) <= 1.0, ln


@precisa_cc
def test_nucleo_c_passa_testes():
    r = _make("test")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "codec:" in r.stdout and "sim: ok" in r.stdout
