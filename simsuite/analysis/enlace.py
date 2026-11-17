"""Testador de enlaces: referência Python de site/propagacao.js, site/terreno.js e site/enlace.js.

Espaço livre + curvatura da Terra (raio efetivo k) + difração de gume único por Bullington (J(v) da ITU-R P.526, forma
aproximada; o texto da Recomendação não foi lido) + orçamento de enlace, ligado ao estimador analítico pelo campo
`offset_db`. O ambiente escolhido entra só com a variabilidade (sigma, desvanecimento, ruído, tráfego): a perda média é o
espaço livre. Estimativa para comparar e dimensionar, não previsão de campo. O teste de paridade com o JavaScript está em
simsuite/tests/test_enlace.py."""
import contextlib
import math

from ..core.channel_static import ANT_GAIN_DBI, CABLE_LOSS_DB, ENVS
from . import estimator as E

C = 299792458.0
R_TERRA_KM = 6371.0
F_MHZ = 915.0


def lambda_m(f_mhz=F_MHZ):
    return C / (f_mhz * 1e6)


def fspl(d_km, f_mhz=F_MHZ):
    return 20 * math.log10(4 * math.pi * d_km * 1000 * f_mhz * 1e6 / C)


def fresnel_r(d1_km, d2_km, f_mhz=F_MHZ, n=1):
    return math.sqrt(n * lambda_m(f_mhz) * d1_km * 1000 * d2_km * 1000 / ((d1_km + d2_km) * 1000))


def bulge(d1_km, d2_km, k):
    return d1_km * d2_km / (2 * k * R_TERRA_KM / 1000.0)


def J(v):
    return 6.9 + 20 * math.log10(math.sqrt((v - 0.1) ** 2 + 1) + v - 0.1) if v > -0.78 else 0.0


def v_param(h, d1_km, d2_km, f_mhz=F_MHZ):
    d1, d2 = d1_km * 1000, d2_km * 1000
    return h * math.sqrt(2 * (d1 + d2) / (lambda_m(f_mhz) * d1 * d2))


def analisar_perfil(d, h, h_tx, h_rx, k, f_mhz=F_MHZ):
    """d: km crescente com d[0] = 0; h: m acima do mar; alturas das antenas em m acima do solo local."""
    n, D = len(d), d[-1]
    ht, hr = h[0] + h_tx, h[-1] + h_rx
    out = dict(D_km=D, ht_m=ht, hr_m=hr, folga_min_razao=math.inf, folga_min_i=-1, obstruido=False, v=None,
               h_obst_m=None, d_obst_km=None, perda_difracao_db=0.0)
    st = sr = -math.inf
    for i in range(1, n - 1):
        d1, d2 = d[i], D - d[i]
        los = ht + (hr - ht) * d1 / D
        ef = h[i] + bulge(d1, d2, k)
        raz = (los - ef) / fresnel_r(d1, d2, f_mhz, 1)
        if raz < out["folga_min_razao"]:
            out["folga_min_razao"], out["folga_min_i"] = raz, i
        st = max(st, (ef - ht) / d1)
        sr = max(sr, (ef - hr) / d2)
    if n < 3:
        out["folga_min_razao"] = None
        return out
    out["obstruido"] = out["folga_min_razao"] < 0
    den = st + sr
    if den > 0:
        db = (hr - ht + sr * D) / den
        hb = ht + st * db
        h_obs = hb - (ht + (hr - ht) * db / D)
        if 0 < db < D:
            out["d_obst_km"], out["h_obst_m"] = db, h_obs
            out["v"] = v_param(h_obs, db, D - db, f_mhz)
            out["perda_difracao_db"] = J(out["v"])
    return out


@contextlib.contextmanager
def ambiente_enlace(base_id):
    """Registra temporariamente um ambiente com a variabilidade de `base_id` e perda de percurso = espaço livre."""
    chave = "enlace:" + base_id
    e = dict(ENVS[base_id])
    e.update(pl1km=fspl(1.0), n=2.0, diurnal_db=0.0)
    ENVS[chave] = e
    try:
        yield chave
    finally:
        del ENVS[chave]


def offset_db(g_tx, l_tx, g_rx, l_rx, perda_dif_db, extra_db):
    """Diferença para o que o estimador já soma (2 x (ganho de antena - perda de cabo) padrão)."""
    return (g_tx - l_tx + g_rx - l_rx) - 2 * (ANT_GAIN_DBI - CABLE_LOSS_DB) - perda_dif_db - extra_db


def analisar(d, h, h_tx, h_rx, k, p_dbm, g_tx, g_rx, l_tx, l_rx, extra_db, env, sf, bw, cr, fhss, retries=3,
             interval_s=60.0, load=1.0):
    pf = analisar_perfil(d, h, h_tx, h_rx, k)
    D = pf["D_km"]
    ld = pf["perda_difracao_db"]
    perda = fspl(D) + ld + extra_db
    rx = p_dbm + (g_tx - l_tx + g_rx - l_rx) - perda
    off = offset_db(g_tx, l_tx, g_rx, l_rx, ld, extra_db)
    with ambiente_enlace(env) as chave:
        e = E.estimate(chave, D, sf, bw, cr, p_dbm, fhss, retries=retries, interval_s=interval_s, offset_db=off,
                       load=load)
    return dict(perfil=pf, perda_total_db=perda, rx_dbm=rx, offset_db=off, estimativa=e)
