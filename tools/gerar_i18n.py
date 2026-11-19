"""Dicionário de tradução PT-BR -> inglês do site (site/i18n_en.js), a partir de tools/i18n/en.tsv.

O TSV tem uma linha por texto: <chave em português com números trocados por #>\\t<tradução, com os # na mesma ordem>. Atributos
(title, aria-label, placeholder, alt) usam o prefixo `@atributo:` na chave e no valor. Os textos novos aparecem quando se roda
`tools/extrair_textos.js`; texto sem tradução continua em português (o site mostra um aviso no modo inglês).

Uso:
  ~/.venvs/legua/bin/python tools/gerar_i18n.py                 # regenera site/i18n_en.js e confere os marcadores
  ~/.venvs/legua/bin/python tools/gerar_i18n.py --importar a.txt b.txt   # (uma vez) importa linhas "indice|inglês" usando tools/i18n/chaves.json
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(RAIZ, "tools", "i18n", "en.tsv")
CHAVES = os.path.join(RAIZ, "tools", "i18n", "chaves.json")
SAIDA = os.path.join(RAIZ, "site", "i18n_en.js")


def ler_tsv():
    d = {}
    with open(TSV, encoding="utf-8") as fh:
        for n, l in enumerate(fh, 1):
            l = l.rstrip("\n")
            if not l or l.startswith("##"):
                continue
            k, _, v = l.partition("\t")
            if not v:
                raise SystemExit(f"{TSV}:{n}: linha sem tradução")
            d[k] = v
    return d


def conferir(d):
    erros = []
    for k, v in d.items():
        if k.count("#") != v.count("#"):
            erros.append(f"marcadores # diferentes: {k!r} ({k.count('#')}) -> {v!r} ({v.count('#')})")
        if k.startswith("@") != v.startswith("@"):
            erros.append(f"prefixo de atributo diferente: {k!r} -> {v!r}")
        if k.startswith("@") and k.split(":", 1)[0] != v.split(":", 1)[0]:
            erros.append(f"atributo diferente: {k!r} -> {v!r}")
    return erros


def importar(arquivos, chaves_json=CHAVES):
    chaves = json.load(open(chaves_json, encoding="utf-8"))
    d = ler_tsv() if os.path.exists(TSV) else {}
    for a in arquivos:
        for l in open(a, encoding="utf-8").read().split("\n"):
            if not l.strip():
                continue
            i, _, v = l.partition("|")
            k = chaves[int(i)]
            if k.startswith("@") and not v.startswith("@"):
                v = k.split(":", 1)[0] + ":" + v
            d[k] = v
    with open(TSV, "w", encoding="utf-8") as fh:
        fh.write("## PT-BR (números = #)\\tEN. Gerado por tools/gerar_i18n.py; edite aqui e rode o script.\n")
        for k in sorted(d):
            fh.write(f"{k}\t{d[k]}\n")
    return d


def gerar(d):
    with open(SAIDA, "w", encoding="utf-8") as fh:
        fh.write("window.LEGUA_EN=" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"site/i18n_en.js: {os.path.getsize(SAIDA) // 1024} KB, {len(d)} textos")


def main(argv):
    if argv[:1] == ["--importar"]:
        d = importar(argv[1:])
    elif argv[:1] == ["--importar2"]:                      # segunda lista de chaves (tools/i18n/chaves2.json)
        d = importar(argv[1:], os.path.join(RAIZ, "tools", "i18n", "chaves2.json"))
    else:
        d = ler_tsv()
    erros = conferir(d)
    for e in erros[:30]:
        print("ERRO:", e)
    if erros:
        print(f"{len(erros)} problema(s)")
        return 1
    gerar(d)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
