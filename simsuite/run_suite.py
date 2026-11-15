"""Suíte de simulação do plano de testes da AdaptLoRa (doc 05).

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
    ("Fase 2", "Simulação e validação cruzada", "Sim", "modos, todos", "DES com protocolo de dois lados + modelos de malha"),
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
    ("M1–M7", "Mobilidade", "Parcial", "M", "Trajetórias, LoS/NLoS, Doppler; perfis fixo e móvel"),
    ("T1", "P2P contra presets", "Sim", "F (configurações)", "Mesmas sementes de canal para todas as configurações"),
    ("T2/T3", "Estrela, membro fraco", "Parcial", "T23", "Modelo de nível 2: unanimidade × divisão × relay"),
    ("T4–T6", "Malha e baselines", "Parcial", "T456", "Modelos comportamentais de Meshtastic, MeshCore, Reticulum, LoRaMesher"),
    ("Fase 7", "Pipeline de dados e dataset", "Sim", "fase7", "Mesmo analisador para logs simulados e reais (JSONL)"),
]


def job(name, escala, outdir=RES):
    t0 = time.time()
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
        else:
            raise KeyError(name)
        r = {"cenario": name, "escala": escala, "segundos": round(time.time() - t0, 1), "resultado": r}
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
       "F", "F6", "F7", "M", "T23", "T456", "fase7"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escala", default="quick", choices=["quick", "full"])
    ap.add_argument("--so", nargs="*", default=None)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--saida", default=None, help="diretório de saída (padrão: results/ no quick, results_full/ no full)")
    a = ap.parse_args()
    names = a.so or ALL
    outdir = a.saida or os.path.join(HERE, "results" if a.escala == "quick" else "results_full")
    t0 = time.time()
    results = {}
    with ProcessPoolExecutor(max_workers=a.procs) as ex:
        for name, r in ex.map(job, names, [a.escala] * len(names), [outdir] * len(names)):
            results[name] = r
            print(f"{name:8s} {'ERRO' if 'erro' in r else 'ok'}  {r.get('segundos', '')} s", flush=True)
    from .analysis.report import write_report
    write_report(outdir, MAPA, a.escala)
    print("relatório:", os.path.join(outdir, "relatorio.md"), round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
