"""Gera core/profiles/br2026.h: a tabela de modos do perfil BR-2026 (nao_verificado) para o núcleo C.

A tabela vem do simulador (`simsuite.protocol.modes.table`), então o núcleo C e o Python usam exatamente os
mesmos modos, tetos e sensibilidades. O núcleo não tem RF embutida: o integrador fornece esta tabela.
Uso: python3 tools/gen_modetab.py [--saida core/profiles/br2026.h] [--conferir]
"""
import argparse
import sys

from simsuite.protocol import wire
from simsuite.protocol.modes import table, DATA_BYTES


def mode_id(m):
    return wire.mode_id(m.sf, int(m.bw), m.cr, m.fhss)


def gerar():
    modes, base, rec = table("BR-2026")
    L = ["/* GERADO por tools/gen_modetab.py a partir de simsuite.protocol.modes.table('BR-2026'). Não editar.",
         " * Perfil BR-2026: fonte secundária, nao_verificado (docs/05). Só para comparar e dimensionar. */",
         "#ifndef LEGUA_PROFILE_BR2026_H",
         "#define LEGUA_PROFILE_BR2026_H",
         '#include "legua/legua.h"', "",
         f"#define LEGUA_BR2026_N_MODES {len(modes)}",
         f"#define LEGUA_BR2026_BASE_MODE_ID 0x{mode_id(base):02X}u   /* {base.name} */",
         f"#define LEGUA_BR2026_REC_MODE_ID  0x{mode_id(rec):02X}u   /* {rec.name} */", "",
         "/* mais rápido primeiro: {mode_id, cap_dbm, sens_dbm, toa_data_us}  // nome */",
         "static const legua_mode_entry LEGUA_BR2026_MODES[LEGUA_BR2026_N_MODES] = {"]
    for m in modes:
        assert float(m.cap).is_integer()
        L.append(f"    {{0x{mode_id(m):02X}u, {int(m.cap)}, {m.sens():.6f}f, {m.toa_us(DATA_BYTES)}u}},  // {m.name}")
    L += ["};", "", "#endif", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="core/profiles/br2026.h")
    ap.add_argument("--conferir", action="store_true", help="só confere se o arquivo está em sincronia")
    a = ap.parse_args(argv)
    txt = gerar()
    if a.conferir:
        with open(a.saida) as fh:
            return 0 if fh.read() == txt else 1
    with open(a.saida, "w") as fh:
        fh.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
