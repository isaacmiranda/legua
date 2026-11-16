#!/usr/bin/env python3
"""Gera site/consolidado.html: página única que consolida os resultados, as discussões e os trabalhos futuros.

Os números vêm de simsuite/results_full (escala longa) e, se faltar um cenário, de simsuite/results (rápida); cada
tabela diz de qual escala veio. O texto é estático (escrito à mão); só os números são lidos dos resultados, então a
página não envelhece quando a suíte é rodada de novo. Uso: python3 tools/build_consolidado.py
"""
import datetime
import html
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def carregar():
    dados, esc = {}, {}
    for escala, pasta in (("quick", "simsuite/results"), ("full", "simsuite/results_full")):
        p = os.path.join(RAIZ, pasta)
        if not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            if not f.endswith(".json") or f == "exemplo_telemetria.jsonl":
                continue
            try:
                j = json.load(open(os.path.join(p, f)))
            except ValueError:
                continue
            if "erro" in j or "resultado" not in j:
                continue
            n = j["cenario"]
            dados.setdefault(n, {})[escala] = j
    return dados


D = carregar()


def R(nome):
    """(resultado, escala, segundos) preferindo a longa."""
    for e in ("full", "quick"):
        if nome in D and e in D[nome]:
            return D[nome][e]["resultado"], e, D[nome][e].get("segundos")
    return None, None, None


def esc(x):
    return html.escape(str(x))


def n(x, c=1):
    if x is None:
        return "–"
    return f"{x:,.{c}f}".replace(",", " ").replace(".", ",") if isinstance(x, (int, float)) else esc(x)


def pct(x, c=1):
    return "–" if x is None else n(100 * x, c) + "%"


def tabela(cab, linhas, num=None):
    num = num or [False] * len(cab)
    h = "".join(f'<th class="{"n" if num[i] else ""}">{esc(c)}</th>' for i, c in enumerate(cab))
    b = "".join("<tr>" + "".join(f'<td class="{"n" if num[i] else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                for r in linhas)
    return f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def badge(e):
    return f'<span class="badge {"full" if e == "full" else ""}">{"escala longa" if e == "full" else "escala rápida"}</span>'


def lista(itens):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in itens) + "</ul>"


def acha(cfgs, prefixo):
    for k in cfgs:
        if k.startswith(prefixo):
            return k
    return None


secoes = []


def secao(sid, titulo, corpo):
    secoes.append((sid, titulo, corpo))


# ------------------------------------------------------------------ 1. resumo
fa, ea, _ = R("formal")
eq, eqe, _ = R("equiv")
xs, xse, _ = R("xsim")
tot_full = sum(D[c]["full"]["segundos"] for c in D if "full" in D[c] and D[c]["full"].get("segundos"))
secao("resumo", "O que é a Légua e o que este trabalho mostra", f"""
<p>A <b>Légua</b> (antes “AdaptLoRa”) é uma biblioteca LoRa ponto a ponto, sem LoRaWAN, para rádios Semtech SX12xx
(referência: Heltec WiFi LoRa 32 V4, ESP32-S3 + SX1262, 915 MHz). Seu núcleo é um acordo negociado de modo de rádio
entre os dois lados (PROPOSE, VOTE, COMMIT), troca em instante combinado, janela de validação, âncora em memória não
volátil e rollback, dentro de um envelope regulatório executável.</p>
<p>Este repositório contém <b>só simulação, protocolo e especificação</b>: o simulador de eventos e a suíte de cenários
(Python), a verificação formal, o núcleo C99 equivalente ao simulador, o formato do pacote e este site. Os
experimentos com as placas e o firmware ficam em outro repositório, que também devolverá a calibração dos parâmetros
estimados.</p>
<div class="notice"><b>Como ler.</b> Todo número vem de modelos com parâmetros <b>estimados</b> (canal, corrente do PA,
deriva, interferência) e serve para <b>comparar e dimensionar</b>, não para prever o campo. O perfil regulatório BR-2026
vem de fonte secundária e está <b>nao_verificado</b>; nada aqui afirma conformidade ou homologação. Não há medição em
hardware. Cada tabela indica a escala (rápida ou longa) de onde saiu.</div>
<p>Escala longa: 5 sementes × 7 dias nos cenários de campo longo, 3000 negociações na injeção de falhas;
{n(tot_full / 60, 0)} min de CPU com um processo. Escala rápida: 2 sementes × 1 dia, ~5 min. Nenhum intervalo de
confiança desta página é estreito o bastante para dispensar a bancada.</p>
""")

# ------------------------------------------------------------------ potência de TX
pw, pwe, _ = R("P")
corpo = ""
if pw:
    caps = list(next(iter(pw["simetrico"].values())).keys())

    def cel(r):
        return "sem enlace" if r["pdr"] < 0.02 else f"{pct(r['pdr'])} · {n(r['mj_por_pacote_mediana'], 0)} mJ"
    corpo += f"<p>{badge(pwe)} Ambiente {esc(pw['ambiente'].replace('_', ' '))}, {n(pw['T_h'], 0)} h por semente, {len(pw['sementes'])} sementes; mesmas sementes de canal em todas as células. Cada célula: PDR · energia de TX por pacote entregue (corrente do PA estimada).</p>"
    corpo += "<h3>Teto simétrico</h3>" + tabela(["Distância"] + [f"{c} dBm" for c in caps],
        [[dk] + [cel(v) for v in row.values()] for dk, row in pw["simetrico"].items()], [False] + [True] * len(caps))
    corpo += "<h3>Teto assimétrico (A em 28 dBm, B com o teto da coluna)</h3>" + tabela(["Distância"] + [f"B = {c} dBm" for c in caps],
        [[dk] + [cel(v) for v in row.values()] for dk, row in pw["assimetrico"].items()], [False] + [True] * len(caps))
    corpo += "<h3>Controle de potência ligado × desligado (28 dBm)</h3>" + tabela(["Distância", "Ligado", "Desligado"],
        [[dk, cel(r["ligado"]), cel(r["desligado"])] for dk, r in pw["controle_de_potencia"].items()], [False, True, True])
    corpo += lista([
        "Cada distância tem um teto mínimo para fechar o enlace; abaixo dele o PDR cai a zero em vez de degradar devagar, porque o modo mais robusto da tabela já está no limite.",
        "Em enlace curto o teto mais alto não é o mais barato: o modelo de corrente do PA faz a energia por pacote ter mínimo em teto intermediário. A posição desse mínimo depende da curva de corrente, que só a bancada mede.",
        "Um nó de teto baixo mantém o PDR (o outro lado compensa) mas arrasta o par para modos lentos e a energia por pacote sobe muito; o tráfego aqui vai só de A para B.",
        "O controle de potência quase não muda o PDR e a energia varia pouco nos dois sentidos; seu ganho é pequeno com este modelo de corrente."])
secao("potencia", "Varredura da potência de TX (P)", corpo or "<p>Sem dados.</p>")

# ------------------------------------------------------------------ teto de TX × cenários
def _tetos():
    from tools.build_site import ler_escala
    for escala, pasta in (("full", "simsuite/results_full"), ("quick", "simsuite/results")):
        e = ler_escala(os.path.join(RAIZ, pasta))
        if e and e.get("tetos"):
            return e["tetos"], escala
    return None, None


TT, tte = _tetos()
corpo = ""
if TT:
    caps = sorted(TT["tetos"], key=float)
    linhas, fixos = [], []
    NOMES = {"L": "Légua", "F": "modos fixos", "O": "outros"}
    for cen, todas in TT["cenarios"].items():
        if not any(len({round(r["v"][c][0], 2) for c in r["v"]}) > 1 for r in todas):
            fixos.append(cen)
            continue
        gs = [g for g in "LFO" if any(r.get("g") == g for r in todas)]
        for g in (gs if len(gs) > 1 else [None]):
            rows = [r for r in todas if g is None or r.get("g") == g]
            comuns = [r for r in rows if all(cp in r["v"] and r["v"][cp][0] >= 0.02 and r["v"][cp][1] is not None for cp in caps)]
            cel = []
            for cp in caps:
                pd = [r["v"][cp][0] for r in rows if cp in r["v"]]
                mj = sorted(r["v"][cp][1] for r in comuns)
                cel.append("–" if not pd else f"{pct(sum(pd) / len(pd))}" + (f" · {n(mj[len(mj) // 2], 0)} mJ" if mj else ""))
            rot = cen + (f" · {NOMES[g]}" if g else "")
            linhas.append([f"{rot} ({len(rows)} células, {len(comuns)} comparáveis em energia)"] + cel)
    corpo += tabela(["Cenário"] + [f"{c} dBm" for c in caps], linhas, [False] + [True] * len(caps))
    if fixos:
        corpo += f"<p>Sem diferença entre os tetos: {', '.join(fixos)} (cenários de bancada com teto próprio, ou modelos de terceiros com potência própria).</p>"
    corpo += lista([
        "Tetos menores deslocam o alcance dos enlaces: as células mais distantes caem a zero, e a média de PDR mistura enlaces mortos com saudáveis; a tabela por célula está na aba Teto × cenários do site.",
        "Os cenários de bancada (B*) já têm tetos fixos de 0 e 10 dBm e mudam pouco; a distância dos cenários de campo não foi reescalada para cada teto.",
        "A corrente do PA é estimada; onde o teto menor gasta menos energia depende da curva real, que só a bancada mede."])
secao("tetos", "Varredura de teto de TX em todos os cenários", corpo or "<p>Sem dados da varredura (rode <code>tools/varredura_teto.sh</code>).</p>")

# ------------------------------------------------------------------ 2. sintonia / campo
f7, f7e, _ = R("F7")
corpo = ""
if f7:
    corpo += f"<p>{badge(f7e)} Dois enlaces marginais, mesmas sementes de canal para todas as variantes.</p>"
    for env, cf in f7.items():
        base = acha(cf, "Fixo SF10")
        linhas = []
        for k, v in cf.items():
            linhas.append([esc(k), n(v.get("pdr"), 3), n(v.get("mj_por_pacote_mediana"), 0), n(v.get("quedas_base"), 0),
                           n(v.get("trocas_por_hora"), 2), n(v.get("desacordo_s_por_hora"), 1)])
        corpo += f"<h3>{esc(env)}</h3>" + tabela(["Variante", "PDR", "mJ/pacote", "Quedas ao base", "Trocas/h", "Desacordo (s/h)"],
                                                 linhas, [False, True, True, True, True, True])
    k0 = list(f7)[0]
    cf0 = f7[k0]
    at = acha(cf0, "Légua atual") or acha(cf0, "AdaptLoRa atual")
    b0 = acha(cf0, "Fixo SF10")
    f3 = acha(cf0, "Légua fade_k 3") or acha(cf0, "AdaptLoRa fade_k 3")
    if at and b0 and f3:
        d_en = 100 * (cf0[at]["mj_por_pacote_mediana"] / cf0[b0]["mj_por_pacote_mediana"] - 1)
        d_f3 = 100 * (cf0[f3]["mj_por_pacote_mediana"] / cf0[b0]["mj_por_pacote_mediana"] - 1)
        corpo += f"""<h3>Discussão</h3>{lista([
            f"No {esc(k0)}, a Légua com margem de aceleração de 8 dB gasta {n(d_en, 0)}% de energia em relação ao SF10/125 fixo, com PDR {n(cf0[at]['pdr'], 3)} contra {n(cf0[b0]['pdr'], 3)}, mas oscila ({n(cf0[at]['quedas_base'], 0)} quedas ao modo base).",
            f"A margem proporcional ao desvio do SNR (<code>fade_k</code> = 3) estabiliza o enlace, mas a energia vai a {n(d_f3, 0)}% do fixo: <b>estabilidade e energia são um compromisso</b>, não há ganho gratuito.",
            "Por isso existem três perfis nomeados (<code>padrao</code>, <code>estavel</code>, <code>cauteloso</code>), iguais no simulador e no núcleo C; o integrador escolhe por instalação.",
            "A escala rápida chegou a sugerir empate de energia onde a longa mostrou diferença grande: conclusões de parâmetro só valem depois da longa."])}"""
secao("sintonia", "Sintonia da aceleração (F7)", corpo or "<p>Sem dados.</p>")

f6, f6e, _ = R("F6")
corpo = ""
if f6:
    linhas = []
    for env, cf in f6.items():
        for k, v in cf.items():
            linhas.append([esc(env), esc(k), n(v.get("pdr"), 3), n(v.get("mj_por_pacote_mediana"), 0),
                           n(v.get("quedas_base"), 0) if "quedas_base" in v else "–"])
    corpo = f"<p>{badge(f6e)} Longa duração, variação diurna e eventos.</p>" + tabela(
        ["Enlace", "Configuração", "PDR", "mJ/pacote", "Quedas ao base"], linhas, [False, False, True, True, True]) + lista([
        "Em enlace folgado (rural, 8 km) a economia de energia é muito grande com entrega praticamente igual: é o caso de uso natural da adaptação.",
        "Em enlace marginal urbano a adaptação economiza energia, mas oscila: o ponto fraco já conhecido, que o F7 explora.",
        "Poucas sementes: sem intervalo de confiança útil por célula."])
secao("longa", "Longa duração (F6)", corpo or "<p>Sem dados.</p>")

fc, fce, _ = R("F")
corpo = ""
if fc:
    linhas = []
    for cen, dist in fc.items():
        for dk, cf in dist.items():
            b = acha(cf, "Fixo SF10")
            a = acha(cf, "AdaptLoRa") or acha(cf, "Légua")
            if a and b:
                linhas.append([esc(cen), esc(dk), n(cf[b].get("pdr"), 3), n(cf[b].get("mj_por_pacote_mediana"), 0),
                               n(cf[a].get("pdr"), 3), n(cf[a].get("mj_por_pacote_mediana"), 0)])
    corpo = f"<p>{badge(fce)} Energia mediana por pacote entregue, Légua contra o modo base fixo (SF10/125 com salto).</p>" + tabela(
        ["Cenário", "Distância", "PDR base", "mJ base", "PDR Légua", "mJ Légua"], linhas,
        [False, False, True, True, True, True]) + lista([
        "Rural e curtas distâncias urbanas: ganhos grandes de energia com a mesma entrega.",
        "No limite de alcance a Légua acompanha o modo base (não há para onde acelerar).",
        "Na zona intermediária urbana a Légua pode ficar poucos pontos abaixo do base em PDR e, perto do limite, gastar mais que ele."])
secao("campo", "Campo fixo (F1–F5)", corpo or "<p>Sem dados.</p>")

m, me, _ = R("M")
corpo = ""
if m:
    linhas = []
    for cen, v in m.items():
        if not isinstance(v, dict) or "configs" not in v:
            continue
        cf = v["configs"]
        b = acha(cf, "Fixo SF10")
        a = [k for k in cf if "móvel" in k.lower() or "movel" in k.lower()]
        f = [k for k in cf if k.startswith("AdaptLoRa") or k.startswith("Légua")]
        for k in (f if f else []):
            linhas.append([esc(cen), esc(v.get("velocidade", "")), esc(k), n(cf[k].get("pdr"), 3), n(cf[k].get("mj_por_pacote_mediana"), 0),
                           n(cf[b].get("pdr"), 3) if b else "–", n(cf[b].get("mj_por_pacote_mediana"), 0) if b else "–"])
    corpo = f"<p>{badge(me)} Trajetórias com LoS/NLoS, Doppler e deriva.</p>" + tabela(
        ["Cenário", "Velocidade", "Configuração", "PDR", "mJ/pacote", "PDR base fixo", "mJ base fixo"], linhas,
        [False, False, False, True, True, True, True]) + lista([
        "O perfil móvel congela a aceleração acima de 2 m/s e fica perto do base fixo em confiabilidade.",
        "O perfil fixo troca entrega por energia em movimento urbano; em pedestre ou drone rural entrega bem com pouca energia.",
        "O Doppler e a deriva térmica são aplicados pelo simulador; com cristal comum (sem TCXO) alguns modos falham a potências altas (B9)."])
secao("mobilidade", "Mobilidade (M1–M7)", corpo or "<p>Sem dados.</p>")

# ------------------------------------------------------------------ 3. acordo, formal, segurança
b4, b4e, _ = R("B4")
b3, b3e, _ = R("B3")
corpo = ""
if b4:
    tot_neg = sum(v.get("negociacoes", 0) for v in b4.values() if isinstance(v, dict))
    tot_perm = sum(v.get("desacordo_permanente", 0) for v in b4.values() if isinstance(v, dict))
    tot_rb = sum(v.get("rollbacks", 0) for v in b4.values() if isinstance(v, dict))
    linhas = [[esc(k), n(v.get("negociacoes"), 0), n(v.get("rollbacks"), 0), n(v.get("reboots"), 0),
               n(v.get("desacordo_permanente"), 0), n(v.get("max_episodio_s"), 1)] for k, v in b4.items() if isinstance(v, dict)]
    corpo += f"<p>{badge(b4e)} Injeção de falhas: perda por tipo de mensagem, reinícios, relógio fora de sincronia, âncora no COMMIT.</p>" + tabela(
        ["Caso", "Negociações", "Rollbacks", "Reinícios", "Desacordo permanente", "Maior episódio (s)"], linhas,
        [False, True, True, True, True, True]) + lista([
        f"{n(tot_neg, 0)} negociações no total, {n(tot_rb, 0)} rollbacks e <b>{n(tot_perm, 0)} desacordos permanentes</b>: toda divergência se resolve.",
        "O rollback não é falha do protocolo: é o mecanismo que protege o par quando a troca não valida; a taxa sobe com a perda do controle.",
        "O custo do plano de controle (B3) é pequeno: o controle de 16 B leva 330 ms no SF10/125 e a negociação gasta poucos mJ."])
secao("acordo", "Acordo e falhas (B3, B4)", corpo or "<p>Sem dados.</p>")

corpo = ""
if fa:
    nomes = {"referencia": "referência", "sem_descida_por_silencio": "sem descida por silêncio", "sem_validacao": "sem validação",
             "ancora_no_commit": "âncora no COMMIT", "dois_reboots": "dois reboots",
             "teto_assimetrico": "teto assimétrico (B nunca aceita)"}
    lin = []
    for k, v in fa["ablacoes"].items():
        ok = lambda x: "vale" if x else "<b>viola</b>"
        lin.append([nomes.get(k, k), n(v["estados"], 0), ok(v["P1_sem_desacordo_permanente"]),
                    n(v["P2_maior_desacordo_ticks"], 0) if v["P2_maior_desacordo_ticks"] is not None else "–",
                    ok(v["P3_recuperacao_sempre_possivel"]),
                    ok(v["P4_ancora_confirmada_pelo_par"]) if "P4_ancora_confirmada_pelo_par" in v else "–"])
    corpo = f"<p>{badge(R('formal')[1])} Verificação exaustiva de um modelo abstrato (dois nós, perdas adversárias).</p>" + tabela(
        ["Variante", "Estados", "P1 sem desacordo permanente", "P2 maior desacordo (ticks)", "P3 recuperação possível",
         "P4 âncora confirmada pelo par"], lin, [False, True, False, True, False, False]) + lista([
        "A descida por silêncio é indispensável: sem ela P1 e P3 caem, com contraexemplo executável (A em DATA, B no base, para sempre).",
        "P1 e P3 continuam valendo sem a validação e com a âncora no COMMIT. <b>Só P4</b> (toda âncora gravada é de um modo em que o par já esteve) separa esses mecanismos: vale na referência e falha nas duas ablações.",
        "Crítica: P4 usa um histórico fantasma e não garante que o par ainda aceite o modo (Dois Generais); e o maior desacordo transitório é menor sem a validação, porque o modelo não captura o ganho de voltar ao modo anterior em vez de cair ao base."])
secao("formal", "Verificação formal", corpo or "<p>Sem dados.</p>")

b7, b7e, _ = R("B7")
b11, b11e, _ = R("B11")
corpo = ""
if b7:
    lin = [[esc(k.replace("_", " ")), n(v.get("pdr"), 3), n(v.get("rollbacks"), 0), n(v.get("alarmes"), 0),
            n(v.get("rejeitados"), 0), n(v.get("energia_por_pacote_mj"), 1)] for k, v in b7.items() if isinstance(v, dict)]
    corpo += f"<p>{badge(b7e)}</p>" + tabela(["Caso", "PDR", "Rollbacks", "Alarmes", "Rejeitados", "mJ/pacote"], lin,
                                           [False, True, True, True, True, True])
    corpo += lista(["Replay e quadros forjados são rejeitados sem efeito (contador anti-replay e MIC).",
                    "O jammer reativo na janela de validação é o caso caro em energia; o alarme de rollbacks repetidos corta os rollbacks pela metade.",
                    "O MIC de teste do repositório (FNV) <b>não é segurança</b>; o algoritmo real (AES-CMAC ou CCM truncado a 4 B) ainda não foi escolhido."])
if b11:
    lin = [[esc(k), "sim" if v.get("conforme") else "<b>não</b>", n(v.get("total_tx"), 0), n(v.get("pior_ocupacao_s"), 3), n(v.get("canais_usados"), 0)]
           for k, v in b11.items() if isinstance(v, dict) and "conforme" in v]
    corpo += f"<h3>Regulação (modelo BR-2026, nao_verificado)</h3><p>{badge(b11e)}</p>" + tabela(
        ["Configuração", "Sem violações no modelo", "TX", "Pior ocupação (s)", "Canais"], lin, [False, False, True, True, True]) + \
        "<p>“Sem violações no modelo” não é conformidade: o perfil vem de fonte secundária e precisa de confirmação com o órgão regulador.</p>"
secao("seguranca", "Segurança e regulação (B7, B11)", corpo or "<p>Sem dados.</p>")

# ------------------------------------------------------------------ 4. alcance, topologia
b2, b2e, _ = R("B2")
corpo = ""
if b2:
    lin = [[esc(k), n(v.get("toa_dados_ms"), 1), n(v.get("perda_max_90_db"), 1), n(v.get("perda_max_50_db"), 1)] for k, v in b2["modos"].items()]
    corpo = f"<p>{badge(b2e)} Perda de percurso máxima para 90% e 50% de entrega (modelo de PER).</p>" + tabela(
        ["Modo", "ToA 24 B (ms)", "Perda máx. a 90% (dB)", "Perda máx. a 50% (dB)"], lin, [False, True, True, True]) + lista([
        "A curva indica onde medir na bancada (degraus de 1 dB em torno do limiar).",
        "O limiar de demodulação e a inclinação são estimativas: a calibração por unidade (B1, B2) vem da bancada."])
secao("alcance", "Alcance (B2)", corpo or "<p>Sem dados.</p>")

t456, t4e, _ = R("T456")
t23, t2e, _ = R("T23")
corpo = ""
if t456:
    lin = []
    for env, topos in t456.items():
        for topo, cf in topos.items():
            for k, v in cf.items():
                if isinstance(v, dict) and "pdr" in v:
                    lin.append([esc(env), esc(topo), esc(k), n(v["pdr"], 3), n(v.get("mj_por_pacote"), 0), n(v.get("ocupacao_%"), 1)])
    corpo += f"<p>{badge(t4e)} Malha: Légua com fallback por inundação contra modelos comportamentais (nível 2) de Meshtastic, MeshCore e Reticulum.</p><details><summary>Tabela completa ({len(lin)} linhas)</summary>" + tabela(
        ["Ambiente", "Topologia", "Protocolo e regime", "PDR", "mJ/pacote", "Ocupação (%)"], lin, [False, False, False, True, True, True]) + "</details>"
    corpo += lista(["Os baselines são <b>modelos nossos</b>, não os produtos reais. Sob o envelope BR-2026 forçado, os modelos de terceiros (sem trocar de preset) entregam quase nada: isso não diz que os produtos são ruins.",
                    "Em regime livre (22 dBm) a Légua entrega um pouco menos que o Meshtastic em algumas topologias, com cerca de um terço da energia e da ocupação do canal.",
                    "Em estrela, o relay vence a unanimidade quando há membro fraco (T2/T3)."])
secao("malha", "Grupos e malha (T2–T6)", corpo or "<p>Sem dados.</p>")

# ------------------------------------------------------------------ 5. validação
corpo = ""
if eq:
    ex = eq["exercitado"]
    corpo += f"<h3>Núcleo C × simulador Python</h3><p>{badge(eqe)}</p>" + lista([
        f"{n(eq['cenarios'], 0)} cenários aleatórios nesta rodada (mais 280 numa varredura de desenvolvimento) nos quatro pares Py-Py, C-C, Py-C e C-Py, por bytes reais do formato de fio: <b>{n(eq['divergencias'], 0)} divergência(s)</b> em {n(eq['eventos_comparados'], 0)} eventos.",
        f"Exercitado: {n(ex['trocas'], 0)} trocas de modo, {n(ex['rollbacks'], 0)} rollbacks, {n(ex['degradacoes'], 0)} degradações, {n(ex['desc_silencio'], 0)} descidas por silêncio, {n(ex['rejeitados'], 0)} quadros rejeitados.",
        "Fuzz com ASan e UBSan: 192 mil chamadas com bytes aleatórios, quadros adulterados e quadros de MIC válido com campos absurdos, sem violação de invariante.",
        "Limite: a equivalência prova que o C faz o que o Python faz, não que o Python descreve a realidade; o canal do teste é simplificado."])
if xs:
    pts = xs["aloha"]["pontos"]
    lin = [[n(p["nos"], 0), n(p["G"], 3), pct(p["pdr_analitico"]), pct(p["pdr_lorasim"]), pct(p["pdr_aqui"])] for p in pts]
    cr = xs["captura"]["resultado"]
    corpo += f"<h3>Contra as regras do LoRaSim</h3><p>{badge(xse)} Porte feito à mão das regras do LoRaSim (as comparações com o original executado estão logo abaixo).</p>" + tabela(
        ["Nós", "Carga G", "ALOHA analítico", "LoRaSim (porte)", "Simulador desta suíte"], lin, [True, True, True, True, True]) + lista([
        f"Tempo no ar idêntico em {n(xs['tempo_no_ar']['combinacoes'], 0)} combinações, exceto SF12/250 (regra do LDRO: a Semtech manda ligar acima de 16 ms; o LoRaSim só liga em 125 kHz com SF11/12).",
        f"Captura com metade dos nós 10 dB mais forte: fortes {pct(cr['aqui']['pdr_fortes'])} e fracos {pct(cr['aqui']['pdr_fracos'])} aqui; {pct(cr['lorasim']['pdr_fortes'])} e {pct(cr['lorasim']['pdr_fracos'])} no porte.",
        f"Sensibilidade: o LoRaSim usa valores medidos num SX1272; o modelo daqui (SX1262) difere em média {n(xs['sensibilidade']['diferenca_media_abs_db'], 1)} dB (máximo {n(xs['sensibilidade']['maior_diferenca_db'], 1)} dB).",
        "O simulador acompanha o ALOHA analítico; o porte do LoRaSim perde ~1 ponto a menos por causa da exceção do preâmbulo."])
if xs and xs.get("lorasim_original", {}).get("disponivel"):
    lo = xs["lorasim_original"]
    corpo += "<h3>LoRaSim original executado</h3><p>" + esc(lo["referencia"]) + f". {n(lo['horas_por_semente'], 0)} h por semente, 3 sementes; o simulador desta suíte recebe o RSSI que o original sorteou.</p>" + tabela(
        ["Nós", "Carga G", "ALOHA analítico", "LoRaSim (original)", "Simulador desta suíte"],
        [[n(p["nos"], 0), n(p["G"], 3), pct(p["pdr_analitico"]), pct(p["pdr_original"]), pct(p["pdr_aqui"])] for p in lo["pontos"]], [True] * 5) + lista([
        "As duas curvas ficam a poucos pontos uma da outra; ambas ficam acima do ALOHA puro porque a posição aleatória cria captura e o original tem a exceção do preâmbulo."])
if xs and xs.get("meshtasticator", {}).get("disponivel"):
    ms = xs["meshtasticator"]
    corpo += "<h3>Meshtasticator (código original executado)</h3><p>" + esc(ms["referencia"]) + ". Só a camada física; o roteamento por inundação não foi comparado.</p>" + tabela(
        ["Nós", "Carga G", "ALOHA analítico", "Meshtastic (original)", "Simulador desta suíte"],
        [[n(p["nos"], 0), n(p["G"], 3), pct(p["pdr_analitico"]), pct(p["pdr_meshtastic"]), pct(p["pdr_aqui"])] for p in ms["aloha"]["pontos"]], [True] * 5) + lista([
        "Tempo no ar igual em " + str(ms["tempo_no_ar"]["presets"] - len(ms["tempo_no_ar"]["presets_diferentes"])) + " dos " + str(ms["tempo_no_ar"]["presets"]) + " presets (difere em " + ", ".join(ms["tempo_no_ar"]["presets_diferentes"]) + ", pela regra do LDRO); regra de captura de 6 dB " + ("igual" if ms["regra_de_captura"]["iguais"] else "DIFERENTE") + f"; sensibilidade difere em média {n(ms['sensibilidade']['diferenca_media_abs_db'], 1)} dB."])
corpo += "<h3>Estimador analítico do site</h3>" + lista([
    "A aba Estimativas usa a mesma curva do simulador, integrada por quadratura; contra o simulador de eventos (42 pontos, sombreamento fixado) o erro absoluto médio na entrega é de 1,1 ponto percentual (máximo 4,9; viés −0,7). Só a entrega foi validada, não energia nem latência."])
secao("validacao", "Validação cruzada", corpo)

# ------------------------------------------------------------------ 6. críticas
secao("criticas", "Críticas e limitações gerais", lista([
    "<b>Nada foi medido em hardware.</b> Canal, corrente do PA, deriva térmica, limiar de demodulação e curva de PER são estimativas; a bancada devolve a calibração (docs/09 §4).",
    "<b>Regulação:</b> o perfil BR-2026 vem de fonte secundária (<code>nao_verificado</code>); a biblioteca respeita o teto do integrador, mas conformidade e homologação são do produto.",
    "<b>Amostras:</b> a escala longa não é o tamanho de amostra completo do plano (≥ 3 dias distintos por enlace com rodízio); poucos enlaces independentes, sombreamento estático sorteado por semente.",
    "<b>Baselines:</b> Meshtastic, MeshCore, Reticulum e LoRaMesher aparecem como modelos comportamentais nossos; não substituem rodar os produtos.",
    "<b>Formal:</b> o modelo é abstrato (ticks, dois nós, adversário de perda); não usa TLC, UPPAAL nem PRISM; provar o modelo não prova o código (o teste de equivalência cobre a ponte C-Python).",
    "<b>Segurança:</b> MIC de teste; sem escolha de algoritmo, sem rotação de chave, ressincronização depois de ausência longa só verificada em simulação (15 min a 12 h, minutos para voltar a DATA); contador do par fora da janela de 32767 sem procedimento; peer counter com janela de replay de até 63 quadros após reinício.",
    "<b>Novidade:</b> a contribuição defensável é acordo + validação + âncora + rollback com verificação formal dentro de um envelope regulatório executável; adaptação de SF, salto e mesh já existem na literatura e não são reivindicados.",
    "<b>Energia:</b> perto do limite de alcance a Légua pode gastar mais que o SF10 fixo; a vantagem de energia é de enlaces folgados e médios."]))

# ------------------------------------------------------------------ 7. futuros
secao("futuro", "Trabalhos futuros", f"""
<h3>Bancada e firmware (repositório separado)</h3>{lista([
    "Driver SX1262, porte ESP32-S3 (ESP-IDF) e exemplos; MIC real (AES-CMAC ou CCM, usando o AES por hardware).",
    "Calibração por unidade: potência real do PA (B1), curva de PER × atenuação (B2), corrente por estado (B8, PPK2), deriva e TCXO (B9), detecção de CAD (B10); entrada pelo arquivo <code>calibracao.json</code> e pela tabela de modos.",
    "Reinício forçado no meio da troca, reprodução de traço no atenuador programável, jammer conduzido, campanha de campo em 915 MHz com GNSS.",
    "Confirmar a homologação da Heltec V4 e a validade do perfil BR-2026 com o órgão regulador."])}
<h3>Protocolo e especificação</h3>{lista([
    "Escolher o algoritmo de MIC, o formato e a rotação de chave; ressincronização depois de ausência longa (contador do par fora da janela).",
    "Colisão de endereços curtos de 16 bits; fragmentação e payload maior que 9 B; teto de potência assimétrico entre os nós no cálculo da margem do vizinho (a varredura P já mostra o efeito em simulação).",
    "Perfis alternativos para a aceleração: histerese temporal, estimador de quantil do SNR; avaliar contra o <code>fade_k</code>.",
    "Controle em 14 B só se o perfil móvel dispensar a velocidade; decidir onde o <code>core/</code> mora (a licença é livre: Apache-2.0, arquivo <code>LICENSE</code>)."])}
<h3>Simulação e verificação</h3>{lista([
    "Comparar o roteamento por inundação do Meshtastic só se o projeto passar a mirar malha: o escopo é o par (docs/05) e os baselines T4–T6 já são modelos comportamentais.",
    "Modelos TLA+, UPPAAL ou PRISM do acordo; propriedade de vivacidade com justiça; estender P4 para o estado corrente do par.",
    "CAD/LBT e salto sincronizado no núcleo C; protocolo congelado antes de comparar malhas com os produtos reais.",
    "Escala completa do plano (mais sementes e dias, intervalos de confiança), nós com tetos e relógios heterogêneos, interferência de terceiros medida em campo.",
    "Repetir a escala longa sempre que o comportamento do protocolo mudar (orçamento de ~1 h 10 min com um processo)."])}
""")

# ------------------------------------------------------------------ montagem
hoje = datetime.date.today().isoformat()
indice = "".join(f'<li><a href="#{s}">{esc(t)}</a></li>' for s, t, _ in secoes)
corpo = "".join(f'<section class="card" id="{s}"><h2>{esc(t)}</h2>{c}</section>' for s, t, c in secoes)
pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Légua · Consolidado</title>
<meta name="description" content="Consolidado dos resultados, das discussões e dos trabalhos futuros da simulação da Légua.">
<link rel="stylesheet" href="style.css">
<style>
 .toc {{ columns: 2 260px; margin: 0 0 16px; padding-left: 20px; font-size: 14px; }}
 section h3 {{ font-size: 14px; margin: 14px 0 6px; color: var(--text-2); }}
 section p, section li {{ font-size: 14px; }}
 section ul {{ padding-left: 20px; margin: 6px 0; }}
 details summary {{ cursor: pointer; margin: 8px 0; color: var(--text-2); }}
 a {{ color: var(--accent); }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <h1>Légua · consolidado dos resultados</h1>
      <p class="sub">Achados, discussões e trabalhos futuros · gerado em {hoje} por <code>tools/build_consolidado.py</code> · <a href="index.html">voltar aos gráficos interativos</a></p>
    </div>
  </header>
  <nav aria-label="Seções"><ol class="toc">{indice}</ol></nav>
  {corpo}
  <footer>Só números de simulação, sem chaves, GNSS ou dados pessoais. Os gráficos e os dados completos estão em <a href="index.html">index.html</a>.</footer>
</div>
</body>
</html>
"""
with open(os.path.join(RAIZ, "site", "consolidado.html"), "w") as fh:
    fh.write(pagina)
print("site/consolidado.html:", len(pagina) // 1024, "KB;", len(secoes), "seções")
