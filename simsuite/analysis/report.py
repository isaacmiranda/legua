"""Gera results/relatorio.md (e figuras) a partir dos JSON dos cenários."""
import json
import os
import glob


def _t(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def _f(x, d=2):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{d}f}".replace(".", ",")
    return str(x)


def _load(res):
    out = {}
    for p in glob.glob(os.path.join(res, "*.json")):
        with open(p) as fh:
            d = json.load(fh)
        out[d["cenario"]] = d
    return out


def write_report(res, mapa, escala):
    R = _load(res)
    L = [f"# Suíte de simulação da AdaptLoRa: resultados ({'escala rápida' if escala == 'quick' else 'escala do plano'})", "",
         "Gerado por `python3 -m simsuite.run_suite`. Todos os números saem de modelos com parâmetros estimados "
         "(canal, corrente do PA, deriva, interferência) e servem para dimensionar e comparar, não para prever "
         "valores absolutos de campo.", "", "## O que é simulável no plano de testes", "",
         _t(mapa, ["Item", "Teste", "Simulável", "Cenário", "Observação"]), ""]
    err = [k for k, v in R.items() if "erro" in v]
    if err:
        L += ["**Cenários com erro:** " + ", ".join(err), ""]

    def get(k):
        return R.get(k, {}).get("resultado")

    if get("modos"):
        m = get("modos")
        L += ["## Tabela de modos BR-2026", "",
              f"Modo base {m['base']} (controle {_f(m['toa_base_ctrl_ms'], 1)} ms, dados de 24 B {_f(m['toa_base_dados_ms'], 1)} ms); "
              f"recuperação {m['recuperacao']}.", "",
              _t([(x["modo"], x["enquadramento"], _f(x["teto_dbm"], 1), _f(x["toa_dados_ms"], 1), _f(x["orcamento_db"], 1))
                  for x in m["modos"]], ["Modo", "Enquadramento", "Teto (dBm)", "ToA 24 B (ms)", "Orçamento (dB)"]), ""]
    if get("amostras"):
        L += ["## Tamanhos de amostra", "", _t(get("amostras")["tabela"], ["Objetivo", "n mínimo"]), ""]
    if get("formal"):
        f = get("formal")
        p4 = lambda v: "–" if v.get("P4_ancora_confirmada_pelo_par") is None else (
            "sim" if v["P4_ancora_confirmada_pelo_par"] else "**NÃO**")
        rows = [(k, v["estados"], "sim" if v["P1_sem_desacordo_permanente"] else "**NÃO**",
                 v["P2_maior_desacordo_ticks"], "sim" if v["P3_recuperacao_sempre_possivel"] else "**NÃO**", p4(v))
                for k, v in f["ablacoes"].items()]
        L += ["## Fase 1: verificação formal (modelo abstrato, perdas adversárias)", "",
              _t(rows, ["Variante", "Estados", "P1 sem desacordo permanente", "P2 maior desacordo (ticks)",
                        "P3 recuperação sempre possível", "P4 âncora confirmada pelo par"]), ""]
        ce = f["ablacoes"].get("sem_descida_por_silencio", {}).get("contraexemplo")
        if ce:
            L += [f"Contraexemplo sem descida por silêncio: A em {ce['de']['A']['estado']} no modo {ce['de']['A']['modo']}, "
                  f"B em {ce['de']['B']['estado']} no modo {ce['de']['B']['modo']}; o adversário repete o ciclo para sempre.", ""]
        L += ["Rodada de aceleração C→F com perda independente por quadro (cadeia de Markov exata sobre o modelo):", "",
              _t([(_f(r["p_perda"]), _f(r["P_F"], 3), _f(r["P_volta_C"], 3), _f(r["P_degradou"], 3),
                   _f(r["P_houve_desacordo"], 3), _f(r["P_desacordo_maior_8"], 3), _f(r["ticks_esperados"], 1))
                  for r in f["rodada_markov"]],
                 ["Perda", "P(fica em F)", "P(volta a C)", "P(degrada)", "P(desacordo transitório)",
                  "P(desacordo > 8 ticks)", "Ticks até assentar"]), ""]
    if get("B2"):
        b = get("B2")
        L += ["## B2: curvas PDR × perda (modelo)", "",
              _t([(k, _f(v["perda_max_90_db"], 1), _f(v["perda_max_50_db"], 1), _f(v["toa_dados_ms"], 1))
                  for k, v in b["modos"].items()], ["Modo", "Perda máx. 90% (dB)", "Perda máx. 50% (dB)", "ToA (ms)"]),
              "", f"Ganho isolado de CR 4/8 em SF9/125: {_f(b['ganho_cr48_sf9_db'], 2)} dB (modelo; B2 mede o real).", ""]
    for k, title in (("B3", "B3: custo do plano de controle"),):
        if get(k):
            rows = [(_f(r["perda"]), r["negociacoes"], r["rollbacks"], r["falhas_de_negociacao"],
                     _f(r["tempo_ate_validar_med_s"], 1), _f(r["tempo_ate_validar_p95_s"], 1),
                     _f(r["energia_ctrl_por_neg_mj"], 2), _f(r["airtime_ctrl_por_neg_ms"], 1))
                    for r in get(k)["por_perda"]]
            L += [f"## {title}", "", _t(rows, ["Perda", "Negociações", "Rollbacks", "Falhas", "Validar (med, s)",
                                                "Validar (p95, s)", "mJ ctrl/neg (10 dBm)", "Airtime ctrl/neg (ms)"]), ""]
    if get("B4"):
        rows = [(k, v["negociacoes"], v["reboots"], v["rollbacks"], v["episodios_desacordo"], _f(v["max_episodio_s"], 1),
                 v["desacordo_permanente"], _f(v["limite_sup_95_desacordo_permanente"], 4))
                for k, v in get("B4").items()]
        L += ["## B4: injeção de falhas", "", _t(rows, ["Caso", "Negociações", "Reboots", "Rollbacks",
                                                        "Episódios de desacordo", "Maior episódio (s)",
                                                        "Desacordo permanente", "Limite sup. 95%"]), ""]
    if get("B5"):
        rows = [(k, _f(v["media_s"], 1), _f(v["p95_s"], 1), _f(v["max_s"], 1), _f(v["duty_beacon_%"], 1))
                for k, v in get("B5")["resultados"].items()]
        L += ["## B5: rendezvous de nó novo ('stay' num canal)", "",
              _t(rows, ["Caso", "Média (s)", "p95 (s)", "Máx (s)", "Ocupação do beacon (%)"]), "", get("B5")["nota"], ""]
    if get("B6"):
        b = get("B6")
        L += ["## B6: traço de campo reproduzido na bancada", "",
              _t([(k, v["pdr"], v["trocas"], v["rollbacks"], v["quedas_base"], v["mj_por_pacote"])
                  for k, v in b.items() if k != "nota"], ["Execução", "PDR", "Trocas", "Rollbacks", "Quedas ao base", "mJ/pacote"]),
              "", b["nota"], ""]
    if get("B7"):
        L += ["## B7: segurança", "", _t([(k, v["pdr"], v["rollbacks"], v["alarmes"], v["rejeitados"],
                                           v["energia_por_pacote_mj"], " / ".join(v["modo_final"]))
                                          for k, v in get("B7").items()],
                                         ["Caso", "PDR", "Rollbacks", "Alarmes", "Quadros rejeitados", "mJ/pacote",
                                          "Modo final"]), ""]
    if get("B9"):
        fl = get("B9")["falhas_com_ldro_auto"]
        L += ["## B9: deriva × tolerância", "",
              f"{len(fl)} combinações falham com LDRO automático:", "",
              _t([(r["modo"], r["cristal"], r["p_dbm"], _f(r["deriva_hz"], 1), _f(r["tolerancia_hz"], 1)) for r in fl],
                 ["Modo", "Cristal", "Potência", "Deriva (Hz)", "Tolerância (Hz)"]) if fl else "", "", get("B9")["nota"], ""]
    if get("B10"):
        L += ["## B10: tempos de CAD", "", ", ".join(f"{k}: {_f(v, 1)} ms" for k, v in get("B10")["varredura_ms"].items()),
              "", get("B10")["nota"], ""]
    if get("B11"):
        L += ["## B11: conformidade dos registros de TX", "",
              _t([(k, "sim" if v["conforme"] else "**não**", _f(v["pior_ocupacao_s"], 3),
                   ", ".join(f"{a}={b}" for a, b in v["violacoes"].items() if b)) for k, v in get("B11").items()],
                 ["Fonte", "Conforme BR-2026", "Pior ocupação por canal (s)", "Violações"]), ""]
    if get("F"):
        L += ["## F1–F5: campo fixo (configurações em rodízio, mesmas sementes de canal)", ""]
        for fname, rows in get("F").items():
            cfgs = list(next(iter(rows.values())).keys())
            tab = []
            for d, row in rows.items():
                tab.append([d] + [f"{_f(row[c]['pdr'], 3)} / {_f(row[c]['mj_por_pacote_mediana'], 0)}" for c in cfgs])
            L += [f"### {fname}", "", "PDR / mJ por pacote entregue (dois nós):", "", _t(tab, ["Distância"] + cfgs), ""]
    if get("F6"):
        L += ["## F6: longa duração", "", _t([(k, c, v["pdr"], v["trocas_por_hora"], v["rollbacks_por_hora"],
                                               v["mj_por_pacote_mediana"]) for k, row in get("F6").items()
                                              for c, v in row.items()],
                                             ["Enlace", "Configuração", "PDR", "Trocas/h", "Rollbacks/h", "mJ/pacote"]), ""]
    if get("F7"):
        L += ["## F7: sintonia da aceleração (enlace marginal)", "",
              "Variantes da margem exigida para acelerar. `fade_k` soma k × desvio do SNR (últimas 30 amostras) à margem de 8 dB.", ""]
        for enlace, row in get("F7").items():
            L += [f"### {enlace}", "", _t([(c, v["pdr"], v["mj_por_pacote_mediana"], v["trocas_por_hora"], v["rollbacks_por_hora"],
                                             v["quedas_base"], v["desacordo_s_por_hora"]) for c, v in row.items()],
                                           ["Variante", "PDR", "mJ/pacote", "Trocas/h", "Rollbacks/h", "Quedas ao base", "Desacordo (s/h)"]), ""]
    if get("P"):
        P = get("P")
        L += ["## P: varredura da potência de TX", "", P["nota"], ""]
        for chave, tit in (("simetrico", "Teto simétrico"), ("assimetrico", "Teto assimétrico (A = 28 dBm)")):
            L += [f"### {tit} (PDR / mJ por pacote)", "", _t([[dk] + [f"{_f(v['pdr'], 3)} / {_f(v['mj_por_pacote_mediana'], 0)}"
                                                                    for v in row.values()] for dk, row in P[chave].items()],
                                                              ["Distância"] + [f"{c} dBm" for c in next(iter(P[chave].values()))]), ""]
        L += ["### Controle de potência", "", _t([(dk, f"{_f(r['ligado']['pdr'], 3)} / {_f(r['ligado']['mj_por_pacote_mediana'], 0)}",
                                                  f"{_f(r['desligado']['pdr'], 3)} / {_f(r['desligado']['mj_por_pacote_mediana'], 0)}")
                                                 for dk, r in P["controle_de_potencia"].items()],
                                               ["Distância", "Ligado", "Desligado"]), ""]
    if get("M"):
        m = dict(get("M"))
        dop = m.pop("_doppler", None)
        cfgs = list(next(iter(m.values()))["configs"].keys())
        tab = [[k, v["ambiente"], v["velocidade"]] + [f"{_f(v['configs'][c]['pdr'], 3)} / {_f(v['configs'][c]['mj_por_pacote_mediana'], 0)}"
                                                       for c in cfgs] for k, v in m.items()]
        L += ["## M1–M7: mobilidade (PDR / mJ por pacote)", "", _t(tab, ["Cenário", "Ambiente", "Velocidade"] + cfgs), ""]
        if dop:
            L += [f"Doppler no M5 (2 × 72 km/h): máximo {_f(dop['doppler_max_hz'], 0)} Hz contra ±{_f(dop['tolerancia_estatica_125k_hz'], 0)} Hz "
                  f"de tolerância estática; variação de até {_f(dop['variacao_max_hz_s'], 0)} Hz/s na passagem, contra tolerância "
                  f"dinâmica de {_f(dop['tolerancia_dinamica_sf10_125_hz'], 1)} Hz por pacote no SF10/125 sem LDRO.", ""]
    if get("T23"):
        L += ["## T2/T3: estrela com membro fraco", ""]
        rows = []
        for case, v in get("T23").items():
            for pol, x in v.items():
                rows.append((case, pol, x["pdr_grupo"], x["pdr_membro_fraco"], x["mj_por_pacote"],
                             x["negociacoes_ok_%"], x["latencia_media_agenda_s"]))
        L += [_t(rows, ["Caso", "Política", "PDR grupo", "PDR fraco", "mJ/pacote", "Negociações ok (%)",
                        "Espera de agenda (s)"]), ""]
    if get("T456"):
        L += ["## T4–T6: malha e baselines (modelos comportamentais)", ""]
        for env, tv in get("T456").items():
            for tname, row in tv.items():
                L += [f"### {tname}, {env}", "",
                      _t([(k, v["pdr"], _f(v["mj_por_pacote"], 0), _f(v["airtime_por_pacote_ms"], 0),
                           _f(v["lat_p95_s"], 1), _f(v["saltos"], 1), v["ocupacao_%"]) for k, v in row.items()],
                         ["Stack (regime)", "PDR", "mJ/pacote", "Airtime/pacote (ms)", "Latência p95 (s)", "Saltos",
                          "Ocupação (%)"]), ""]
    if get("fase7"):
        f = get("fase7")
        p = f["pipeline_sobre_o_log"]
        L += ["## Fase 7: pipeline de telemetria", "",
              f"PDR no simulador {_f(f['simulador']['pdr'], 4)}; o mesmo número recalculado do log JSONL: {_f(p['pdr'], 4)} "
              f"(IC95% por blocos {_f(p['ic95_blocos'][0], 3)}–{_f(p['ic95_blocos'][1], 3)}; Wilson ingênuo "
              f"{_f(p['ic95_wilson_ingenuo'][0], 3)}–{_f(p['ic95_wilson_ingenuo'][1], 3)}). Conformidade BR-2026 pelo log: "
              f"{'sim' if p['conformidade_br2026'] else 'não'}.", ""]
    with open(os.path.join(res, "relatorio.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    _figures(res, R)


def _figures(res, R):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    b2 = R.get("B2", {}).get("resultado")
    if b2:
        fig, ax = plt.subplots(figsize=(7, 4))
        for k, v in b2["modos"].items():
            ax.plot([c["atenuacao_db"] for c in v["curva"]], [c["pdr"] for c in v["curva"]], marker="o", ms=3, label=k)
        ax.set_xlabel("Perda total (dB), 0 dBm")
        ax.set_ylabel("PDR")
        ax.grid(alpha=.3)
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(os.path.join(res, "fig_b2_pdr_atenuacao.png"), dpi=130)
        plt.close(fig)
    F = R.get("F", {}).get("resultado")
    if F:
        for fname, rows in F.items():
            fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6))
            ds = list(rows.keys())
            xs = [float(d.split()[0]) for d in ds]
            for c in next(iter(rows.values())).keys():
                a1.plot(xs, [rows[d][c]["pdr"] for d in ds], marker="o", label=c)
                a2.plot(xs, [rows[d][c]["mj_por_pacote_mediana"] or float("nan") for d in ds], marker="o", label=c)
            a1.set_ylabel("PDR")
            a2.set_ylabel("mJ por pacote entregue")
            a2.set_yscale("log")
            for a in (a1, a2):
                a.set_xlabel("km")
                a.grid(alpha=.3)
            a1.legend(fontsize=7)
            fig.suptitle(fname)
            fig.tight_layout()
            fig.savefig(os.path.join(res, f"fig_{fname.split()[0]}.png"), dpi=130)
            plt.close(fig)
