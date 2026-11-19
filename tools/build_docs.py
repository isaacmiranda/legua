"""Converte os documentos da especificação (docs/*.md) em site/especificacao.js, para a aba "Especificação" do site.

Conversor mínimo e seguro (sem dependências): títulos, parágrafos, listas, tabelas, blocos de código, `código`, **negrito**,
*itálico* e links. Todo texto é escapado; só as tags geradas aqui chegam ao HTML. Uso:
  ~/.venvs/legua/bin/python tools/build_docs.py
"""
import html
import json
import os
import re
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = [("07", "07-especificacao-do-pacote-v0.md", "Formato do pacote v0"), ("08", "08-interface-de-radio-e-de-porte.md", "Interface de rádio e de porte"),
        ("05", "05-viabilidade-inovacao-e-plano-de-testes.md", "Viabilidade, inovação e plano de testes"), ("06", "06-suite-de-simulacao.md", "Suíte de simulação"),
        ("09", "09-escopo-simulacao-e-repositorio-de-bancada.md", "Escopo, calibração e bancada"), ("11", "11-revisao-de-usabilidade.md", "Revisão de usabilidade do site")]


def slug(txt):
    t = unicodedata.normalize("NFD", txt).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "secao"


def inline(t):
    """Escapa e aplica código, negrito, itálico e links (só http/https e âncoras)."""
    partes = re.split(r"(`[^`]+`)", t)
    out = []
    for p in partes:
        if p.startswith("`") and p.endswith("`") and len(p) > 2:
            out.append("<code>" + html.escape(p[1:-1]) + "</code>")
            continue
        s = html.escape(p, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|#[^)\s]*)\)", lambda m: '<a href="%s" rel="noopener noreferrer">%s</a>' % (html.escape(m.group(2), quote=True), m.group(1)), s)
        out.append(s)
    return "".join(out)


def converter(md):
    """Markdown -> (html, secoes[{nivel, id, titulo}])."""
    linhas = md.split("\n")
    saida, secoes, i, usados = [], [], 0, {}
    while i < len(linhas):
        l = linhas[i]
        if l.startswith("```"):
            j = i + 1
            while j < len(linhas) and not linhas[j].startswith("```"):
                j += 1
            saida.append("<pre><code>" + html.escape("\n".join(linhas[i + 1:j])) + "</code></pre>")
            i = j + 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", l)
        if m:
            nivel, tit = len(m.group(1)), m.group(2).strip()
            base = slug(re.sub(r"[`*]", "", tit))
            usados[base] = usados.get(base, 0) + 1
            sid = base if usados[base] == 1 else "%s-%d" % (base, usados[base])
            secoes.append({"nivel": nivel, "id": sid, "titulo": re.sub(r"[`*]", "", tit)})
            saida.append('<h%d id="%s">%s</h%d>' % (nivel + 1, sid, inline(tit), nivel + 1))
            i += 1
            continue
        if l.strip().startswith("|") and i + 1 < len(linhas) and re.match(r"^\s*\|?\s*:?-{2,}", linhas[i + 1]):
            cab = [c.strip() for c in l.strip().strip("|").split("|")]
            j = i + 2
            corpo = []
            while j < len(linhas) and linhas[j].strip().startswith("|"):
                corpo.append([c.strip() for c in linhas[j].strip().strip("|").split("|")])
                j += 1
            t = "<div class=\"tbl-wrap\" style=\"overflow-x:auto\"><table><thead><tr>" + "".join("<th>%s</th>" % inline(c) for c in cab) + "</tr></thead><tbody>"
            for r in corpo:
                t += "<tr>" + "".join("<td>%s</td>" % inline(c) for c in r) + "</tr>"
            saida.append(t + "</tbody></table></div>")
            i = j
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", l):
            ordenada = bool(re.match(r"^\s*\d+\.", l))
            itens = []
            while i < len(linhas) and (re.match(r"^\s*([-*]|\d+\.)\s+", linhas[i]) or (linhas[i].startswith("  ") and linhas[i].strip() and itens)):
                if re.match(r"^\s*([-*]|\d+\.)\s+", linhas[i]):
                    itens.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", linhas[i]))
                else:
                    itens[-1] += " " + linhas[i].strip()
                i += 1
            tag = "ol" if ordenada else "ul"
            saida.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x) for x in itens), tag))
            continue
        if not l.strip():
            i += 1
            continue
        par = [l.strip()]
        i += 1
        while i < len(linhas) and linhas[i].strip() and not re.match(r"^(#{1,4}\s|```|\s*\||\s*([-*]|\d+\.)\s+)", linhas[i]):
            par.append(linhas[i].strip())
            i += 1
        saida.append("<p>%s</p>" % inline(" ".join(par)))
    return "\n".join(saida), secoes


def main():
    docs = []
    for did, nome, titulo in DOCS:
        with open(os.path.join(RAIZ, "docs", nome), encoding="utf-8") as fh:
            h, s = converter(fh.read())
        docs.append({"id": did, "arquivo": "docs/" + nome, "titulo": titulo, "html": h, "secoes": s})
    saida = os.path.join(RAIZ, "site", "especificacao.js")
    with open(saida, "w", encoding="utf-8") as fh:
        fh.write("window.LEGUA_DOCS=" + json.dumps(docs, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print("site/especificacao.js: %d KB, %d documentos" % (os.path.getsize(saida) // 1024, len(docs)))


if __name__ == "__main__":
    sys.exit(main())
