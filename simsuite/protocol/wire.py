"""Formato de pacote v0 da Légua (docs/07). Referência executável do codec do núcleo C.

Cabeçalho de 8 B + corpo + MIC de 4 B. Tamanhos fixos por tipo: DATA 24 B, ACK 14 B,
controle (HELLO/PROPOSE/VOTE/COMMIT) 16 B. Big-endian.

O MIC aqui é um hash com chave **só para teste** (FNV-1a de 32 bits), usado pela simulação e pelo teste de
equivalência. Não é segurança. O MIC v0 real é AES-128-CMAC truncado a 4 B (docs/07 §6, `mic.py`).

Uso:  python3 -m simsuite.protocol.wire --vetores core/tests/vectors/frames.txt
"""
import argparse
import random
import sys

VERSION = 0
HDR_LEN = 8
MIC_LEN = 4

T_HELLO, T_DATA, T_ACK, T_PROPOSE, T_VOTE, T_COMMIT = 1, 2, 3, 4, 5, 6
BODY_LEN = {T_HELLO: 4, T_DATA: 12, T_ACK: 2, T_PROPOSE: 4, T_VOTE: 4, T_COMMIT: 4}
FRAME_LEN = {t: HDR_LEN + n + MIC_LEN for t, n in BODY_LEN.items()}   # 16, 24, 14, 16, 16, 16

F_ACKREQ, F_FRAG = 0x01, 0x02          # flags (byte 1); bits 2-3 = id da chave; 4-7 reservados
DATA_PAYLOAD = 9

BROADCAST = 0xFFFF
TEST_KEY = bytes(range(16))            # SÓ para vetores de teste; nunca usar em produto

_BW_CODE = {125: 0, 250: 1, 500: 2}
_BW_FROM = {v: k for k, v in _BW_CODE.items()}


def mode_id(sf, bw_khz, cr, fhss):
    """Byte de modo: SF-5 (3 bits) | BW (2) | CR-1 (2) | FHSS (1)."""
    if not (5 <= sf <= 12 and bw_khz in _BW_CODE and 1 <= cr <= 4):
        raise ValueError("modo fora do formato")
    return ((sf - 5) << 5) | (_BW_CODE[bw_khz] << 3) | ((cr - 1) << 1) | (1 if fhss else 0)


def mode_from_id(b):
    bw = (b >> 3) & 3
    if bw not in _BW_FROM:
        raise ValueError("codigo de BW invalido")
    return ((b >> 5) & 7) + 5, _BW_FROM[bw], ((b >> 1) & 3) + 1, bool(b & 1)


def test_mic(key, src, ctr32, data):
    h = 0x811C9DC5
    for b in key + src.to_bytes(2, "big") + ctr32.to_bytes(4, "big") + data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def pack(ftype, src, dst, ctr32, body, key=TEST_KEY, flags=0):
    if len(body) != BODY_LEN[ftype]:
        raise ValueError("corpo com tamanho errado para o tipo")
    hdr = bytes([(VERSION << 5) | ftype, flags]) + src.to_bytes(2, "big") + dst.to_bytes(2, "big") \
        + (ctr32 & 0xFFFF).to_bytes(2, "big")
    data = hdr + bytes(body)
    return data + test_mic(key, src, ctr32, data).to_bytes(4, "big")


def unpack(raw, ctr32, key=TEST_KEY):
    """Devolve dict ou levanta ValueError. ctr32 é o contador completo já reconstruído."""
    if len(raw) < HDR_LEN + MIC_LEN:
        raise ValueError("curto")
    ver, ftype = raw[0] >> 5, raw[0] & 0x1F
    if ver != VERSION:
        raise ValueError("versao")
    if ftype not in FRAME_LEN or len(raw) != FRAME_LEN[ftype]:
        raise ValueError("tipo ou tamanho")
    if raw[1] & 0xF0:
        raise ValueError("flags reservadas")
    src, dst = int.from_bytes(raw[2:4], "big"), int.from_bytes(raw[4:6], "big")
    if (ctr32 & 0xFFFF) != int.from_bytes(raw[6:8], "big"):
        raise ValueError("contador inconsistente")
    if test_mic(key, src, ctr32, raw[:-4]) != int.from_bytes(raw[-4:], "big"):
        raise ValueError("mic")
    return {"type": ftype, "flags": raw[1], "src": src, "dst": dst, "ctr16": ctr32 & 0xFFFF,
            "body": bytes(raw[8:-4])}


def reconstruct_ctr(last32, ctr16):
    """Reconstrói o contador de 32 bits a partir dos 16 bits do quadro. None = repetido/antigo."""
    delta = (ctr16 - (last32 & 0xFFFF)) & 0xFFFF
    if delta == 0 or delta > 0x7FFF or last32 + delta > 0xFFFFFFFF:   # sem dar a volta nos 32 bits
        return None
    return last32 + delta


def _vetores(seed=7):
    rng = random.Random(seed)
    out = []
    for t, n in sorted(BODY_LEN.items()):
        for ctr in (1, 65, 0xFFFF, 0x10000, 0x1FFFE, 0xABCD1234):
            body = bytes(rng.randrange(256) for _ in range(n))
            if t in (T_HELLO, T_PROPOSE, T_VOTE):     # o byte antes reservado leva o teto de TX do nó (docs/07 §4)
                body = bytearray(body)
                body[3 if t == T_VOTE else 2] = rng.randrange(0, 38)
                if t != T_VOTE:
                    body[3] = 0                        # o último byte de HELLO/PROPOSE segue reservado
                body = bytes(body)
            src, dst = rng.randrange(1, 0xFFFE), rng.randrange(1, 0xFFFE)
            out.append((ctr, pack(t, src, dst, ctr, body, flags=rng.choice((0, F_ACKREQ, F_ACKREQ | 0x04)))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--vetores", required=True, help="arquivo de saída: '<ctr32> <hex>' por linha")
    a = ap.parse_args(argv)
    with open(a.vetores, "w") as fh:
        fh.write("# vetores do codec v0 (gerado por simsuite.protocol.wire; chave de teste 00..0f)\n")
        for ctr, raw in _vetores():
            fh.write(f"{ctr} {raw.hex()}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
