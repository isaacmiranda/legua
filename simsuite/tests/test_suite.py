"""Testes da suíte: rodar com  python3 -m pytest -q simsuite/tests  (a partir de /home/claude)."""
import numpy as np
import pytest
from simsuite.core.radio import toa_s, drift_tolerance_hz
from simsuite.core.regulatory import BR2026, check_compliance, HopSequence, channel_plan
from simsuite.protocol.modes import table, DATA_BYTES, CTRL_BYTES
from simsuite.formal.checker import analyze, Params, negotiation_round
from simsuite.analysis.stats import n_for_halfwidth, wilson, rule_of_three
from simsuite.core.bench import AttenLink, constant
from simsuite.scenarios.common import make_pair, summarize


def test_toa_matches_spec_table():
    # tabela de RF-05d do documento 01 (ms)
    assert round(1000 * toa_s(10, 125, 16)) == 330
    assert round(1000 * toa_s(10, 125, 24)) == 371
    assert round(1000 * toa_s(10, 125, 32)) == 453
    assert round(1000 * toa_s(11, 125, 24)) == 823
    assert round(1000 * toa_s(11, 250, 24)) == 371
    assert round(1000 * toa_s(12, 500, 24)) == 330


def test_24_byte_wall():
    assert toa_s(10, 125, 24) <= 0.4 < toa_s(10, 125, 25)


def test_mode_table_respects_dwell():
    modes, base, rec = table()
    for m in modes + [base, rec]:
        if m.fhss:
            assert m.toa(DATA_BYTES) <= 0.4
            assert m.toa(CTRL_BYTES) <= 0.4
    assert not any(m.sf >= 11 and m.bw == 125 for m in modes)


def test_ldro_tolerance():
    assert round(drift_tolerance_hz(12, 125)) == 163


def test_hop_sequence_occupancy():
    hs = HopSequence("x", 35, plan_size=92)
    t, log = 0.0, []
    while t < 300:
        t = hs.fit_start(t, 0.371)
        log.append({"t": t, "dur": 0.371, "bw": 125, "freq": hs.channel(t), "p_dbm": 28, "fhss": True,
                    "n_hop": 35, "node": 0})
        t += 0.371
    rep = check_compliance(log, BR2026)
    assert rep["conforme"], rep


def test_compliance_flags_long_packet_and_power():
    bad = [{"t": 0, "dur": 0.82, "bw": 125, "freq": 1, "p_dbm": 28, "fhss": True, "n_hop": 35, "node": 0},
           {"t": 1, "dur": 0.1, "bw": 125, "freq": 2, "p_dbm": 22, "fhss": False, "n_hop": 0, "node": 0}]
    rep = check_compliance(bad, BR2026)
    assert rep["violacoes"]["dwell_pacote"] == 1 and rep["violacoes"]["potencia"] == 1


def test_channel_plan_excludes_forbidden_band():
    for f in channel_plan(BR2026, 125):
        assert not (907.5e6 < f < 915e6)


def test_formal_reference_and_ablation():
    ref = analyze(Params())
    assert ref["P1_sem_desacordo_permanente"] and ref["P3_recuperacao_sempre_possivel"]
    assert ref["P4_ancora_confirmada_pelo_par"]
    abl = analyze(Params(silence_descent=False))
    assert not abl["P1_sem_desacordo_permanente"]


def test_formal_p4_discrimina_validacao_e_ancora_tardia():
    """P1 e P3 valem sem esses mecanismos; só P4 (âncora de um modo em que o par já esteve) os separa."""
    for p in (Params(validation=False), Params(persist_at_commit=True)):
        r = analyze(p)
        assert r["P1_sem_desacordo_permanente"] and r["P3_recuperacao_sempre_possivel"]
        assert not r["P4_ancora_confirmada_pelo_par"] and "contraexemplo_P4" in r


def test_markov_no_loss_always_succeeds():
    r = negotiation_round(0.0)
    assert r["P_F"] == pytest.approx(1.0)


def test_stats():
    assert n_for_halfwidth(0.9, 0.02) == 865
    lo, hi = wilson(90, 100)
    assert lo < 0.9 < hi
    assert rule_of_three(3000) == pytest.approx(0.001)


def test_pair_converges_on_bench():
    sim = make_pair("rural_aberto", AttenLink(constant(70.0), np.random.default_rng(1)), 1800, 3,
                    cap=10.0, app_interval=10.0, ext_scale=0.0)
    sim.start()
    sim.run()
    s = summarize(sim)
    assert s["pdr"] > 0.97
    assert s["modo_final"][0] == s["modo_final"][1]
    assert s["acordo"]["em_aberto_s"] == 0.0


def test_b9_sem_linhas_duplicadas():
    from simsuite.scenarios.bench import b9_drift
    r = b9_drift()
    chaves = [(x["modo"], x["cristal"], x["p_dbm"], x["ldro"]) for x in r["linhas"]]
    assert len(chaves) == len(set(chaves))


def test_fade_k_desligado_por_padrao_e_soma_variabilidade():
    from simsuite.protocol.endpoint import Config, Endpoint
    modes, base, rec = table()
    rng = np.random.default_rng(1)
    ep = Endpoint(0, 1, modes, base, rec, Config(), rng)
    assert Config().fade_k == 0.0 and ep._need_up() == Config().margin_up
    ep2 = Endpoint(0, 1, modes, base, rec, Config(fade_k=2.0), rng)
    ep2.snr_hist = [0.0, 6.0] * 15                     # desvio = 3 dB
    assert abs(ep2._need_up() - (Config().margin_up + 6.0)) < 1e-9


def test_descida_no_modo_base_nao_trava_em_recuperacao():
    """Regressão: RECUPERACAO no próprio modo base com par em silêncio devia ir a BASE, não repetir o prazo."""
    from simsuite.protocol.endpoint import Config, Endpoint, RECOV, BASE
    modes, base, rec = table()
    ep = Endpoint(0, 1, modes, base, rec, Config(), np.random.default_rng(1))
    ep.mode, ep.state, ep.peer_heard = base, RECOV, 0.0
    ep.on_timer(1000.0)
    assert ep.state == BASE
    d = ep.next_deadline()
    assert d is None or d > 1000.0          # o próximo prazo está no futuro (antes ficava no passado)


def test_orcamento_estima_e_recusa_acima_do_limite(tmp_path):
    import json
    from simsuite.analysis.orcamento import estimar_execucao, FATORES
    q = tmp_path / "q"
    q.mkdir()
    for n in ("F7", "M"):
        (q / f"{n}.json").write_text(json.dumps({"cenario": n, "escala": "quick", "segundos": 100.0, "resultado": {}}))
    e = estimar_execucao(str(q), str(tmp_path / "inexistente"), ["F7", "M"])
    assert e["central"] == round(100 * FATORES["F7"][0] + 100 * FATORES["M"][0])     # sem calibração: contenção 1
    assert e["baixo"] <= e["central"] <= e["alto"]
    assert estimar_execucao(str(tmp_path / "vazio"), None, ["F7"]) is None


def test_run_suite_full_recusa_quando_passa_do_limite(tmp_path, monkeypatch):
    import sys
    import json
    from simsuite import run_suite
    q = tmp_path / "results"
    q.mkdir()
    (q / "F7.json").write_text(json.dumps({"cenario": "F7", "escala": "quick", "segundos": 1000.0, "resultado": {}}))
    monkeypatch.setattr(run_suite, "HERE", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["run_suite", "--escala", "full", "--so", "F7", "--limite-horas", "1"])
    with pytest.raises(SystemExit) as exc:
        run_suite.main()
    assert exc.value.code == 2          # 1000 s x 17,5 = 4,9 h > 1 h: adiada, sem rodar nada


def test_varredura_de_potencia_monotonia_basica(monkeypatch):
    """Teto maior nunca piora muito o PDR de um enlace no limite, e teto assimétrico aceita tupla em make_pair."""
    from simsuite.scenarios import power
    monkeypatch.setattr(power, "CAPS", [8.0, 28.0])
    r = power.power_sweep("quick")
    s = r["simetrico"]["3.0 km"]
    assert s["28"]["pdr"] > s["8"]["pdr"] + 0.3
    assert set(r["assimetrico"]["1.0 km"]) == {"8", "28"}
