"""MIC do pacote v0: AES-128-CMAC truncado a 32 bits (docs/07 §6). Referência executável.

Python puro, sem dependência, para gerar vetores e conferir o núcleo C (`core/src/mic_cmac.c`). É lento (milhares
de quadros por segundo); a suíte de simulação continua usando o MIC de teste de `wire.py`, que não muda o
comportamento do protocolo. Não usar em produto: não é de tempo constante.

Entrada do CMAC = bloco B0 (16 B) || cabeçalho || corpo, com
    B0 = 0x4C 'L' | 0x01 (função: MIC v0) | key_id | src (2, BE) | ctr32 (4, BE) | len(cabeçalho+corpo) | 6 x 0x00
MIC = os 4 primeiros bytes da etiqueta, lidos em big-endian (é a ordem em que vão no quadro).

Uso:  python3 -m simsuite.protocol.mic --vetores core/tests/vectors/mic.txt
"""
import argparse
import sys

B0_DOMAIN = 0x4C       # 'L'
B0_FUNC_MIC = 0x01     # 0x02 fica reservado para uma cifra futura (CTR com a mesma chave exige B0 diferente)

_SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16")


def _xtime(b):
    return ((b << 1) ^ 0x1B) & 0xFF if b & 0x80 else b << 1


def _expand(key):
    if len(key) != 16:
        raise ValueError("chave AES-128 tem 16 B")
    w = [list(key[i:i + 4]) for i in range(0, 16, 4)]
    rcon = 1
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[b] for b in t]
            t[0] ^= rcon
            rcon = _xtime(rcon)
        w.append([a ^ b for a, b in zip(w[i - 4], t)])
    return [sum(w[4 * r:4 * r + 4], []) for r in range(11)]


def aes128_encrypt(key, block):
    rk = _expand(key)
    s = [a ^ b for a, b in zip(block, rk[0])]
    for r in range(1, 11):
        s = [_SBOX[b] for b in s]
        s = [s[(i + 4 * (i % 4)) % 16] for i in range(16)]          # ShiftRows (coluna-maior)
        if r != 10:
            m = []
            for c in range(4):
                a = s[4 * c:4 * c + 4]
                x = a[0] ^ a[1] ^ a[2] ^ a[3]
                m += [a[i] ^ x ^ _xtime(a[i] ^ a[(i + 1) % 4]) for i in range(4)]
            s = m
        s = [a ^ b for a, b in zip(s, rk[r])]
    return bytes(s)


def _dbl(b):
    n = int.from_bytes(b, "big") << 1
    if n >> 128:
        n = (n ^ 0x87) & ((1 << 128) - 1)
    return n.to_bytes(16, "big")


def cmac(key, msg):
    """AES-CMAC (NIST SP 800-38B, RFC 4493), etiqueta completa de 16 B."""
    k1 = _dbl(aes128_encrypt(key, bytes(16)))
    k2 = _dbl(k1)
    n = max(1, (len(msg) + 15) // 16)
    last = msg[16 * (n - 1):]
    if len(last) == 16:
        last = bytes(a ^ b for a, b in zip(last, k1))
    else:
        last = bytes(a ^ b for a, b in zip(last + b"\x80" + bytes(15 - len(last)), k2))
    x = bytes(16)
    for i in range(n - 1):
        x = aes128_encrypt(key, bytes(a ^ b for a, b in zip(x, msg[16 * i:16 * i + 16])))
    return aes128_encrypt(key, bytes(a ^ b for a, b in zip(x, last)))


def b0(key_id, src, ctr32, data_len):
    if not (0 <= key_id <= 3 and 0 <= src <= 0xFFFF and 0 <= ctr32 <= 0xFFFFFFFF and 0 <= data_len <= 255):
        raise ValueError("campo do B0 fora da faixa")
    return bytes([B0_DOMAIN, B0_FUNC_MIC, key_id]) + src.to_bytes(2, "big") + ctr32.to_bytes(4, "big") \
        + bytes([data_len]) + bytes(6)


def mic_cmac(key, key_id, src, ctr32, data):
    """MIC de 32 bits do quadro (cabeçalho + corpo em `data`), como inteiro."""
    return int.from_bytes(cmac(key, b0(key_id, src, ctr32, len(data)) + bytes(data))[:4], "big")


def _vetores():
    """Quadros reais dos vetores do codec, reassinados com CMAC (chave de teste 00..0f e uma segunda chave)."""
    from . import wire
    keys = {0: wire.TEST_KEY, 1: bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")}
    out = []
    for ctr, raw, extra in wire._vetores():
        key_id = (raw[1] >> 2) & 3
        data = raw[:-wire.MIC_LEN]
        src = int.from_bytes(raw[2:4], "big")
        m = mic_cmac(keys[key_id], key_id, src, ctr, data + extra)
        out.append((key_id, ctr, data + m.to_bytes(4, "big"), extra))
    return keys, out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vetores", required=True, help="arquivo de saída")
    a = ap.parse_args(argv)
    keys, vec = _vetores()
    with open(a.vetores, "w") as fh:
        fh.write("# vetores do MIC v0 (AES-128-CMAC truncado a 4 B; gerado por simsuite.protocol.mic)\n")
        fh.write("# K <key_id> <chave>  |  <key_id> <ctr32> <quadro com MIC> [<dado extra>]\n")
        for kid, k in sorted(keys.items()):
            fh.write(f"K {kid} {k.hex()}\n")
        for kid, ctr, raw, extra in vec:
            fh.write(f"{kid} {ctr} {raw.hex()}" + (f" {extra.hex()}" if extra else "") + "\n")
    print(f"{len(vec)} vetores em {a.vetores}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
