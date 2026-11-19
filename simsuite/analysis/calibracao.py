"""Importa a `calibracao.json` que a bancada devolve (docs/09 §4) e a aplica às constantes estimadas do simulador.

Formato (versão 1). Cada constante leva o valor medido e a incerteza (mesma unidade do valor):
{
  "versao": 1, "id": "bancada-2027-01", "data": "2027-01-15", "hardware": "Heltec WiFi LoRa 32 V4",
  "firmware": "core-v0.1.0", "notas": "texto livre",
  "constantes": {
    "snr_thr":        {"valor": {"7": -7.4, "12": -19.8}, "incerteza": 0.3},    // dB por SF (só os SFs medidos)
    "per_offset_db":  {"valor": 2.4, "incerteza": 0.2},
    "per_slope_db":   {"valor": 0.6, "incerteza": 0.1},
    "cr_gain_db":     {"valor": {"4": 0.9}, "incerteza": 0.2},                  // dB por CR (1..4)
    "nf_db":          {"valor": 6.5, "incerteza": 0.3},
    "i_tx_ma":        {"valor": [[-9, 17.0], [14, 44.0], [28, 930.0]], "incerteza": 15.0},   // [dBm, mA], crescente
    "canal":          {"valor": {"rural_aberto": {"pl1km": 114.0, "n": 3.8, "sigma_static": 4.5}}, "incerteza": 2.0}
  }
}
Só as constantes presentes mudam; o resto fica como está. Nada de coordenada, chave ou dado bruto no arquivo.

Uso:
  ~/.venvs/legua/bin/python -m simsuite.analysis.calibracao calibracao.json          # valida e mostra atual -> novo
  python3 -m simsuite.run_suite --calibracao calibracao.json ...   # roda a suíte com ela (saída própria)
"""
import contextlib
import copy
import json
import sys

from ..core import channel_static, radio

VERSAO = 1
PROIBIDAS = ("lat", "lon", "alt", "gnss", "chave", "key", "senha", "segredo")   # por trecho: latitude_deg, gnss_fix...
ESCALARES = {"per_offset_db": ("PER_OFFSET_DB", 0.0, 10.0), "per_slope_db": ("PER_SLOPE_DB", 0.1, 3.0),
             "nf_db": ("NF_DB", 0.5, 15.0)}
CANAL_CAMPOS = {"pl1km": (80.0, 180.0), "n": (1.5, 6.0), "sigma_static": (0.0, 20.0)}


class CalibracaoInvalida(ValueError):
    pass


def _proibidas(x, caminho=""):
    if isinstance(x, dict):
        for k, v in x.items():
            if any(w in str(k).lower() for w in PROIBIDAS):
                raise CalibracaoInvalida(f"campo não permitido (dado sensível) em {caminho}/{k}")
            _proibidas(v, f"{caminho}/{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _proibidas(v, f"{caminho}[{i}]")


def _num(v, nome, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not (lo <= v <= hi):
        raise CalibracaoInvalida(f"{nome}: {v!r} fora de [{lo}, {hi}]")
    return float(v)


def validar(cal):
    """Levanta CalibracaoInvalida se o arquivo não serve; devolve o dicionário de constantes normalizado."""
    if not isinstance(cal, dict) or cal.get("versao") != VERSAO:
        raise CalibracaoInvalida(f"versao deve ser {VERSAO}")
    if not isinstance(cal.get("id"), str) or not cal["id"].strip() or not all(c.isascii() and (c.isalnum() or c in "-_.") for c in cal["id"]) or cal["id"].strip(".") == "":
        raise CalibracaoInvalida("id obrigatório (letras, números, - _ .)")
    _proibidas(cal)
    cs = cal.get("constantes")
    if not isinstance(cs, dict) or not cs:
        raise CalibracaoInvalida("constantes vazio")
    out = {}
    for nome, item in cs.items():
        if not isinstance(item, dict) or "valor" not in item or "incerteza" not in item:
            raise CalibracaoInvalida(f"{nome}: precisa de valor e incerteza")
        unc = _num(item["incerteza"], f"{nome}.incerteza", 0.0, 1e4)
        v = item["valor"]
        if nome in ESCALARES:
            _, lo, hi = ESCALARES[nome]
            out[nome] = (_num(v, nome, lo, hi), unc)
        elif nome in ("snr_thr", "cr_gain_db"):
            if not isinstance(v, dict) or not v:
                raise CalibracaoInvalida(f"{nome}: valor deve ser um objeto")
            chaves, lo, hi = ((range(5, 13), -40.0, 0.0) if nome == "snr_thr" else (range(1, 5), 0.0, 3.0))
            d = {}
            for k, x in v.items():
                if not (str(k).isascii() and str(k).isdigit()) or int(k) not in chaves:
                    raise CalibracaoInvalida(f"{nome}: chave {k!r} inválida")
                d[int(k)] = _num(x, f"{nome}[{k}]", lo, hi)
            out[nome] = (d, unc)
        elif nome == "i_tx_ma":
            if not isinstance(v, list) or len(v) < 2:
                raise CalibracaoInvalida("i_tx_ma: lista de pelo menos 2 pares [dBm, mA]")
            pts = [(_num(p[0], "i_tx_ma.dBm", -20.0, 30.0), _num(p[1], "i_tx_ma.mA", 1.0, 2000.0))
                   for p in v if isinstance(p, list) and len(p) == 2]
            if len(pts) != len(v) or any(b[0] <= a[0] for a, b in zip(pts, pts[1:])):
                raise CalibracaoInvalida("i_tx_ma: pares [dBm, mA] com dBm estritamente crescente")
            out[nome] = (pts, unc)
        elif nome == "canal":
            if not isinstance(v, dict) or not v:
                raise CalibracaoInvalida("canal: valor deve ser um objeto por ambiente")
            d = {}
            for env, campos in v.items():
                if env not in channel_static.ENVS:
                    raise CalibracaoInvalida(f"canal: ambiente {env!r} desconhecido")
                if not isinstance(campos, dict) or not campos or set(campos) - set(CANAL_CAMPOS):
                    raise CalibracaoInvalida(f"canal.{env}: campos permitidos {sorted(CANAL_CAMPOS)}")
                d[env] = {c: _num(x, f"canal.{env}.{c}", *CANAL_CAMPOS[c]) for c, x in campos.items()}
            out[nome] = (d, unc)
        else:
            raise CalibracaoInvalida(f"constante desconhecida: {nome}")
    return out


def carregar(caminho):
    with open(caminho, encoding="utf-8") as fh:
        cal = json.load(fh)
    return cal, validar(cal)


def descrever(cal, cs=None):
    """Linhas (constante, atual, novo, incerteza) para conferir antes de aplicar."""
    cs = cs or validar(cal)
    linhas = []
    for nome, (v, unc) in cs.items():
        if nome in ESCALARES:
            linhas.append((nome, getattr(radio, ESCALARES[nome][0]), v, unc))
        elif nome in ("snr_thr", "cr_gain_db"):
            atual = radio.SNR_THR if nome == "snr_thr" else radio.CR_GAIN_DB
            linhas += [(f"{nome}[{k}]", atual[k], x, unc) for k, x in sorted(v.items())]
        elif nome == "i_tx_ma":
            linhas += [(f"i_tx_ma[{p:g} dBm]", round(radio.i_tx_ma(p), 1), mA, unc) for p, mA in v]
        else:
            for env, campos in v.items():
                linhas += [(f"canal.{env}.{c}", channel_static.ENVS[env][c], x, unc) for c, x in campos.items()]
    return linhas


# Sentido em que cada constante PIORA o enlace (+1: valor maior é pior; -1: valor menor é pior; 0: não decide o enlace).
SENTIDO_PIOR = {"snr_thr": +1, "per_offset_db": +1, "nf_db": +1, "cr_gain_db": -1, "per_slope_db": 0, "i_tx_ma": 0}
CANAL_PIOR = {"pl1km": +1, "n": +1, "sigma_static": 0}


def _desloca(v, delta):
    if isinstance(v, dict):
        return {k: _desloca(x, delta) for k, x in v.items()}
    if isinstance(v, (int, float)):
        return v + delta
    return v


def variantes(cal):
    """Duas cópias da calibração que carregam a incerteza para o resultado: `pessimista` (cada constante deslocada de uma
    incerteza no sentido que piora o enlace) e `otimista` (no sentido oposto). Constantes que não decidem o enlace
    (inclinação da curva, corrente de TX) e a variação entre locais (sigma) ficam como estão. Os valores deslocados são
    limitados às faixas aceitas por `validar`. Devolve (pessimista, otimista); levanta CalibracaoInvalida se `cal` for inválida."""
    validar(cal)
    out = []
    for nome, sinal in (("pessimista", +1), ("otimista", -1)):
        c = copy.deepcopy(cal)
        c["id"] = f"{cal['id']}-{nome}"
        c["notas"] = f"Variante {nome} da calibração {cal['id']}: cada constante deslocada de uma incerteza no sentido que " + \
            ("piora" if sinal > 0 else "melhora") + " o enlace. " + str(cal.get("notas", ""))
        for k, ent in c["constantes"].items():
            inc = float(ent.get("incerteza", 0.0))
            if k == "canal":
                for amb, campos in ent["valor"].items():
                    for campo, v in list(campos.items()):
                        d = sinal * CANAL_PIOR.get(campo, 0) * inc
                        lo, hi = CANAL_CAMPOS[campo]
                        campos[campo] = min(hi, max(lo, v + d))
            else:
                d = sinal * SENTIDO_PIOR.get(k, 0) * inc
                if k in ESCALARES:
                    lo, hi = ESCALARES[k][1], ESCALARES[k][2]
                    ent["valor"] = min(hi, max(lo, ent["valor"] + d))
                elif d and k in ("snr_thr", "cr_gain_db"):
                    lo, hi = (-40.0, 0.0) if k == "snr_thr" else (0.0, 3.0)
                    ent["valor"] = {c: min(hi, max(lo, x + d)) for c, x in ent["valor"].items()}
                elif d:
                    ent["valor"] = _desloca(ent["valor"], d)
        out.append(c)
    validar(out[0]); validar(out[1])
    return out[0], out[1]


def _modulos_simsuite():
    return [m for n, m in list(sys.modules.items()) if n.startswith("simsuite") and m is not None]


@contextlib.contextmanager
def aplicar(cal):
    """Troca as constantes por valores medidos enquanto o bloco roda e restaura no fim. Os escalares que outros módulos
    importaram por valor (estimador, modos) também são trocados."""
    cs = validar(cal)
    desfazer = []

    def trocar_escalar(attr, novo):
        antigo = getattr(radio, attr)
        for m in _modulos_simsuite():
            if getattr(m, attr, None) == antigo and hasattr(m, attr):
                desfazer.append((m, attr, antigo))
                setattr(m, attr, novo)

    def trocar_dict(d, novos):
        for k, x in novos.items():
            desfazer.append((d, k, d[k]))
            d[k] = x

    try:
        for nome, (v, _unc) in cs.items():
            if nome in ESCALARES:
                trocar_escalar(ESCALARES[nome][0], v)
            elif nome == "snr_thr":
                trocar_dict(radio.SNR_THR, v)
            elif nome == "cr_gain_db":
                trocar_dict(radio.CR_GAIN_DB, v)
            elif nome == "i_tx_ma":
                desfazer.append((radio, "_I_TX_TABLE", radio._I_TX_TABLE))
                radio._I_TX_TABLE = [tuple(p) for p in v]
            elif nome == "canal":
                for env, campos in v.items():
                    trocar_dict(channel_static.ENVS[env], campos)
        radio._TOA_CACHE.clear()
        yield cs
    finally:
        for alvo, chave, antigo in reversed(desfazer):
            if isinstance(alvo, dict):
                alvo[chave] = antigo
            else:
                setattr(alvo, chave, antigo)


def main(argv=None):
    if not argv and len(sys.argv) != 2:
        print(__doc__)
        return 2
    caminho = (argv or sys.argv[1:])[0]
    try:
        cal, cs = carregar(caminho)
    except (CalibracaoInvalida, OSError, json.JSONDecodeError) as e:
        print("calibração inválida:", e)
        return 1
    print(f"calibração {cal['id']} ({cal.get('data', 's/ data')}, {cal.get('hardware', 's/ hardware')}, "
          f"{cal.get('firmware', 's/ firmware')})")
    for nome, atual, novo, unc in descrever(cal, cs):
        print(f"  {nome:28s} {atual!s:>10} -> {novo!s:>10}   ± {unc:g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
