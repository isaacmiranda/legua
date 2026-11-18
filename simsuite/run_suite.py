"""Suíte de simulação do plano de testes da Légua (doc 05).

Uso (a partir do diretório que contém 'simsuite'):
  python3 -m simsuite.run_suite                  # escala rápida, todos os cenários
  python3 -m simsuite.run_suite --escala full    # tamanhos de amostra do plano
  python3 -m simsuite.run_suite --so formal B4 M # só alguns cenários
Saídas: simsuite/results/<cenário>.json e simsuite/results/relatorio.md (+ figuras).
"""
import argparse
import json
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")

# ------------------------------------------------------------------ mapa do plano
MAPA = [
    ("Fase 0", "Textos da Anatel, OCD, UTE, LGPD, nome", "Não", "—", "Decisão jurídica e regulatória; a suíte só codifica a leitura atual em core/regulatory.py"),
    ("Fase 1", "Verificação formal (TLA+/UPPAAL/PRISM)", "Sim", "formal", "Verificador de estados explícito + cadeia de Markov em Python (sem TLC/PRISM instalados)"),
    ("Fase 2", "Simulação e validação cruzada", "Sim", "modos, todos, xsim, equiv", "DES com protocolo de dois lados + modelos de malha; núcleo C equivalente ao Python (equiv); regras do LoRaSim portadas (xsim)"),
    ("B1", "Calibração RSSI/potência por unidade", "Não", "—", "Medida física; a suíte usa 25,6 dBm medidos pela Heltec como referência"),
    ("B2", "Curvas PDR × atenuação", "Parcial", "B2", "Modelo de PER; prevê onde medir (degraus de 1 dB em torno do limiar)"),
    ("B3", "Custo do plano de controle", "Sim", "B3", "Lógica do protocolo + tempo no ar; energia depende da curva de corrente (B8)"),
    ("B4", "Injeção de falhas (≥3.000 negociações)", "Sim", "B4", "Perdas por tipo, reboots, relógio, âncora no COMMIT"),
    ("B5", "Rendezvous", "Sim", "B5", "Tempo de entrada em 'stay' × intervalo de beacon"),
    ("B6", "Reprodução de traços", "Sim", "B6", "Traço de campo simulado reproduzido no atenuador simulado"),
    ("B7", "Segurança (replay, forjado, jammer)", "Sim", "B7", "Rejeição, rollback induzido, alarme"),
    ("B8", "Energia por estado", "Parcial", "B8", "Tabela do modelo; a curva real sai do PPK2/shunt"),
    ("B9", "Deriva térmica e LDRO", "Parcial", "B9", "Tolerâncias exatas; taxas de deriva estimadas (TCXO?)"),
    ("B10", "CAD multi-SF", "Parcial", "B10", "Só tempos de CAD; detecção/falso alarme exigem hardware"),
    ("B11", "Conformidade (ocupação, canais, DEP)", "Sim", "B11", "Verificador sobre o registro de TX (o mesmo roda nos logs reais)"),
    ("F1–F5", "Campo fixo urbano/rural", "Parcial", "F", "Modelo de canal estimado; serve para dimensionar e comparar configurações"),
    ("F6", "Longa duração", "Parcial", "F6", "Trocas/hora, rollbacks e estabilidade sob variação diurna/eventos"),
    ("F7", "Sintonia da aceleração", "Sim", "F7", "Margem fixa × proporcional ao desvio do SNR em enlace marginal: estabilidade × energia"),
    ("V", "Varredura da janela de validação", "Parcial", "P4", "k, f e tempo da janela: PDR, rollbacks (inclui falsos) e desacordo em enlace marginal"),
    ("S", "Varredura da descida por silêncio", "Parcial", "P1/P3", "t_silence × intervalo da aplicação: descidas falsas, PDR e desacordo"),
    ("X", "Estresses: relógio, assimetria, teto × fade_k", "Parcial", "F7", "Erro de relógio × cristal, perda só num sentido e teto de TX × fade_k: PDR, trocas, rollbacks e desacordo"),
    ("P", "Varredura de potência de TX", "Parcial", "P", "Teto simétrico e assimétrico, controle de potência ligado/desligado: PDR e energia (corrente do PA estimada)"),
    ("M1–M7", "Mobilidade", "Parcial", "M", "Trajetórias, LoS/NLoS, Doppler; perfis fixo e móvel"),
    ("T1", "P2P contra presets", "Sim", "F (configurações)", "Mesmas sementes de canal para todas as configurações"),
    ("T2/T3", "Estrela, membro fraco", "Parcial", "T23", "Modelo de nível 2: unanimidade × divisão × relay"),
    ("T4–T6", "Malha e baselines", "Parcial", "T456", "Modelos comportamentais de Meshtastic, MeshCore, Reticulum, LoRaMesher"),
    ("Fase 7", "Pipeline de dados e dataset", "Sim", "fase7", "Mesmo analisador para logs simulados e reais (JSONL)"),
]


def job(name, escala, outdir=RES):
    t0 = time.time()
    cal = os.environ.get("LEGUA_CALIBRACAO_JSON")        # já validada no main; o arquivo não é relido (docs/09 §4)
    if cal:                                  # constantes medidas; vale só neste processo
        from .analysis.calibracao import aplicar
        with aplicar(json.loads(cal)):
            return _job(name, escala, outdir, t0)
    return _job(name, escala, outdir, t0)


def _job(name, escala, outdir, t0):
    try:
        if name == "modos":
            from .protocol.modes import table, DATA_BYTES, ACK_BYTES, CTRL_BYTES
            ms, base, rec = table()
            r = {"modos": [{"modo": m.name, "enquadramento": m.frame, "teto_dbm": m.cap,
                            "toa_dados_ms": round(1000 * m.toa(DATA_BYTES), 1),
                            "orcamento_db": round(m.budget(), 1)} for m in ms],
                 "base": base.name, "recuperacao": rec.name,
                 "toa_base_ctrl_ms": round(1000 * base.toa(CTRL_BYTES), 1),
                 "toa_base_dados_ms": round(1000 * base.toa(DATA_BYTES), 1)}
        elif name == "amostras":
            from .analysis.stats import sample_size_table
            r = {"tabela": sample_size_table()}
        elif name == "formal":
            from .formal.checker import ablations, negotiation_round
            r = {"ablacoes": ablations(),
                 "rodada_markov": [negotiation_round(p) for p in (0.0, 0.05, 0.1, 0.2, 0.3)]}
        elif name in ("B2", "B3", "B4", "B5", "B7", "B8", "B9", "B10", "B11"):
            from .scenarios import bench as B
            fn = {"B2": B.b2_pdr_vs_attenuation, "B3": B.b3_control_cost, "B4": B.b4_fault_injection,
                  "B5": B.b5_rendezvous, "B7": B.b7_security, "B8": B.b8_energy_table, "B9": B.b9_drift,
                  "B10": B.b10_cad_timing, "B11": B.b11_compliance}[name]
            r = fn(escala)
        elif name == "B6":
            r = b6_trace_replay(escala)
        elif name == "F7":
            from .scenarios.field import f7_tuning
            r = f7_tuning(escala)
        elif name.startswith("F") and name not in ("F6", "F7"):
            from .scenarios.field import field_campaign
            r = field_campaign(escala, which=name.split(":")[1] if ":" in name else None)
        elif name == "P":
            from .scenarios.power import power_sweep
            r = power_sweep(escala)
        elif name == "V":
            from .scenarios.sweeps import validacao_sweep
            r = validacao_sweep(escala)
        elif name == "S":
            from .scenarios.sweeps import silencio_sweep
            r = silencio_sweep(escala)
        elif name == "X":
            from .scenarios.sweeps import estresse_sweep
            r = estresse_sweep(escala)
        elif name == "F6":
            from .scenarios.field import f6_long_duration
            r = f6_long_duration(escala)
        elif name.startswith("M"):
            from .scenarios.field import mobility_campaign, doppler_check
            r = mobility_campaign(escala, which=name.split(":")[1] if ":" in name else None)
            r["_doppler"] = doppler_check()
        elif name == "T23":
            from .scenarios.topology import star
            r = star(escala)
        elif name == "T456":
            from .scenarios.topology import mesh
            r = mesh(escala)
        elif name == "fase7":
            r = fase7_demo(outdir)
        elif name == "xsim":
            from .analysis.lorasim import comparar
            from .analysis import meshtasticator
            r = comparar(rapido=(escala != "full"))
            r["meshtasticator"] = meshtasticator.comparar(rapido=(escala != "full"))
            from .analysis import lorasim_original
            r["lorasim_original"] = lorasim_original.comparar(rapido=(escala != "full"))
        elif name == "equiv":
            from .tests.equiv_harness import resumo
            r = resumo(150 if escala == "full" else 30)
        else:
            raise KeyError(name)
        r = {"cenario": name, "escala": escala, "segundos": round(time.time() - t0, 1), "resultado": r}
        if os.environ.get("LEGUA_CALIBRACAO_JSON"):       # resultado com constantes medidas: rotula (docs/09 §4)
            r["calibracao"] = json.loads(os.environ["LEGUA_CALIBRACAO_JSON"])["id"]
    except Exception as e:  # noqa
        r = {"cenario": name, "erro": repr(e), "trace": traceback.format_exc()}
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, f"{name.replace(':', '_')}.json"), "w") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else str(o))
    return name, r


def b6_trace_replay(escala):
    """Traço de um enlace móvel simulado (M1 rural) reproduzido no atenuador simulado."""
    import numpy as np
    from .core.channel_static import ENVS
    from .core.links import MobileLink
    from .core.bench import AttenLink
    from .scenarios.field import _tracks
    from .scenarios.common import make_pair, summarize
    T = 3600.0
    env_id, ta, tb, _ = _tracks("M1 pedestre urbano", T + 60, np.random.default_rng(1))
    lk = MobileLink(ENVS[env_id], ta, tb, np.random.default_rng(2))
    gains = lk.slow.copy()
    times = lk.t.copy()

    def prog(t):
        i = min(len(times) - 1, int(t / lk.dt))
        return -gains[i] - 40.0
    out = {}
    for nome, link in (("campo (simulado)", lk), ("bancada (traço reproduzido)", AttenLink(prog, np.random.default_rng(3)))):
        sim = make_pair(env_id, link, T, 9, app_interval=2.0, ext_scale=1.0 if "campo" in nome else 0.0)
        sim.nodes[1].app_interval = None
        sim.start()
        sim.run()
        s = summarize(sim)
        out[nome] = {"pdr": round(s["pdr"], 4), "trocas": s["stats"]["trocas"], "rollbacks": s["stats"]["rollbacks"],
                     "quedas_base": s["stats"]["quedas_base"], "mj_por_pacote": round(s["mj_por_pacote"] or 0, 1)}
    out["nota"] = ("A bancada reproduz só o ganho lento (sem desvanecimento rápido nem interferência); a diferença "
                   "entre as duas linhas é o que um atenuador programável não captura.")
    return out


def fase7_demo(outdir=RES):
    import numpy as np
    from .core.channel_static import ENVS
    from .core.links import FixedLink
    from .scenarios.common import make_pair, summarize
    from .analysis.telemetry import load, analyze
    path = os.path.join(outdir, "exemplo_telemetria.jsonl")
    os.makedirs(outdir, exist_ok=True)
    env = ENVS["urbano_residencial"]
    sim = make_pair("urbano_residencial", FixedLink(env, 1.2, np.random.default_rng(3), 6 * 3600),
                    6 * 3600, 5, log_path=path, app_interval=30.0)
    sim.start()
    sim.run()
    s = summarize(sim)
    a = analyze(load(path))
    return {"simulador": {"pdr": s["pdr"], "pacotes": s["gerados"]},
            "pipeline_sobre_o_log": {k: a[k] for k in ("pacotes", "entregues", "pdr", "ic95_blocos",
                                                       "ic95_wilson_ingenuo", "conformidade_br2026",
                                                       "pior_ocupacao_s", "tempo_em_modo_s")},
            "arquivo": os.path.basename(path)}


ALL = ["modos", "amostras", "formal", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", "B11",
       "F", "F6", "F7", "P", "V", "S", "X", "M", "T23", "T456", "fase7", "xsim", "equiv"]


# cenários cujo resultado muda com o teto de TX (os demais são tabelas, verificação ou independem da potência)
CENARIOS_DE_TETO = ["B2", "B3", "B4", "B5", "B6", "B7", "B11", "F", "F6", "F7", "M", "T23", "T456", "fase7"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escala", default="quick", choices=["quick", "full"])
    ap.add_argument("--so", nargs="*", default=None)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--limite-horas", type=float, default=8.0,
                    help="na escala full, recusa rodar se a estimativa passar disso (padrão 8 h); veja --forcar")
    ap.add_argument("--forcar", action="store_true", help="ignora o limite de horas da escala full")
    ap.add_argument("--teto", type=float, default=None,
                    help="varredura de potência: limita o teto de TX de todos os nós (dBm) e grava em results[_full]/teto_<N>/; "
                         "sem --so roda os cenários que dependem do teto")
    ap.add_argument("--calibracao", default=None,
                    help="calibracao.json da bancada (docs/09 §4): roda a suíte com as constantes medidas e grava em "
                         "results[_full]/cal_<id>/ (o arquivo é copiado para lá); sem ele, os valores são os estimados")
    ap.add_argument("--saida", default=None, help="diretório de saída (padrão: results/ no quick, results_full/ no full)")
    a = ap.parse_args()
    if a.calibracao:
        from .analysis.calibracao import carregar, CalibracaoInvalida
        try:
            cal_json, _ = carregar(a.calibracao)
        except (CalibracaoInvalida, OSError, ValueError) as e:
            raise SystemExit(f"calibração inválida: {e}")
        os.environ["LEGUA_CALIBRACAO_JSON"] = json.dumps(cal_json)          # cópia validada, herdada pelos filhos (job)
    if a.teto is not None:
        os.environ["LEGUA_TETO_MAX"] = f"{a.teto:g}"           # herdado pelos processos filhos (common.TETO_MAX)
    names = a.so or (CENARIOS_DE_TETO if a.teto is not None else ALL)
    outdir = a.saida or os.path.join(HERE, "results" if a.escala == "quick" else "results_full")
    if a.teto is not None and not a.saida:
        outdir = os.path.join(outdir, f"teto_{a.teto:g}")
    if a.calibracao and not a.saida:
        outdir = os.path.join(outdir, f"cal_{cal_json['id']}")
    if a.escala == "full" and not a.forcar:
        from .analysis.orcamento import estimar_execucao, fmt
        est = estimar_execucao(os.path.join(HERE, "results"), outdir, names)
        if est is None:
            print("aviso: sem resultados quick em results/, não foi possível estimar o tempo da escala full.")
        else:
            print(f"estimativa da escala full ({len(names)} cenários, --procs 1): {fmt(est['central'])} "
                  f"(faixa {fmt(est['baixo'])} a {fmt(est['alto'])}); limite {a.limite_horas:g} h")
            if est["central"] > a.limite_horas * 3600:
                print("acima do limite: rodada adiada. Use --so para um subconjunto ou --forcar para rodar assim mesmo.")
                raise SystemExit(2)
    if a.calibracao:                 # só depois de aceita a rodada; o que vale é a cópia validada, não o arquivo
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "calibracao.json"), "w", encoding="utf-8") as fh:
            json.dump(cal_json, fh, ensure_ascii=False, indent=2)
    t0 = time.time()
    results = {}
    with ProcessPoolExecutor(max_workers=a.procs) as ex:
        for name, r in ex.map(job, names, [a.escala] * len(names), [outdir] * len(names)):
            results[name] = r
            print(f"{name:8s} {'ERRO' if 'erro' in r else 'ok'}  {r.get('segundos', '')} s", flush=True)
    from .analysis.report import write_report
    write_report(outdir, MAPA, a.escala)
    print("relatório:", os.path.join(outdir, "relatorio.md"), round(time.time() - t0), "s")
    falhas = sorted(n for n, r in results.items() if "erro" in r)
    if falhas:                      # o relatório já saiu; a saída diferente de zero impede que a CI ignore o erro
        print("cenários com erro:", ", ".join(falhas))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
