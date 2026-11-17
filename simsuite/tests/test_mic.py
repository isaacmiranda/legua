"""MIC v0 (AES-128-CMAC truncado a 4 B, docs/07 §6): referência Python contra FIPS-197 e RFC 4493, vetores em
sincronia com o núcleo C, e o teste C (`test_mic`) que confere os mesmos vetores."""
import os
import shutil
import subprocess
import pytest
from simsuite.protocol import mic, wire

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORE = os.path.join(RAIZ, "core")
K = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
M = bytes.fromhex("6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e51"
                  "30c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710")


def test_aes_fips197():
    ct = mic.aes128_encrypt(bytes(range(16)), bytes.fromhex("00112233445566778899aabbccddeeff"))
    assert ct.hex() == "69c4e0d86a7b0430d8cdb78070b4c55a"


@pytest.mark.parametrize("n,tag", [(0, "bb1d6929e95937287fa37d129b756746"), (16, "070a16b46b4d4144f79bdd9dd04a287c"),
                                   (40, "dfa66747de9ae63030ca32611497c827"), (64, "51f0bebf7e3b9d92fc49741779363cfe")])
def test_cmac_rfc4493(n, tag):
    assert mic.cmac(K, M[:n]).hex() == tag


def test_b0_e_tamanhos():
    b = mic.b0(1, 0x1234, 0xABCD1234, 12)
    assert b.hex() == "4c0101" "1234" "abcd1234" "0c" + "00" * 6
    # controle: B0 + 16 B = dois blocos exatos; DATA: três blocos
    assert len(b) + wire.FRAME_LEN[wire.T_COMMIT] - wire.MIC_LEN == 28
    with pytest.raises(ValueError):
        mic.b0(4, 0, 0, 0)


def test_mic_depende_de_cada_campo():
    data = bytes(range(12))
    base = mic.mic_cmac(K, 0, 7, 100, data)
    assert mic.mic_cmac(K, 1, 7, 100, data) != base
    assert mic.mic_cmac(K, 0, 8, 100, data) != base
    assert mic.mic_cmac(K, 0, 7, 100 + 0x10000, data) != base
    assert mic.mic_cmac(K, 0, 7, 100, data[:-1] + b"\x00") != base


def test_vetores_em_sincronia(tmp_path):
    novo = tmp_path / "m.txt"
    mic.main(["--vetores", str(novo)])
    with open(os.path.join(CORE, "tests", "vectors", "mic.txt")) as fh:
        assert fh.read() == novo.read_text(), "rode: make -C core vectors"


@pytest.mark.skipif(not (shutil.which("gcc") or shutil.which("cc")) or not shutil.which("make"),
                    reason="sem compilador C")
def test_mic_c_igual_python():
    r = subprocess.run(["nice", "-n", "15", "make", "-j1", "-C", CORE, "build/test_mic"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([os.path.join(CORE, "build", "test_mic"), os.path.join(CORE, "tests", "vectors", "mic.txt")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "36 vetores de quadro, ok" in r.stdout, r.stdout
