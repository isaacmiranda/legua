"""Estatística do plano de testes (doc 05): ICs, tamanhos de amostra, blocos."""
import math
import numpy as np
from scipy import stats


def wilson(k, n, conf=0.95):
    if n == 0:
        return (float("nan"), float("nan"))
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def clopper_pearson(k, n, conf=0.95):
    a = 1 - conf
    lo = 0.0 if k == 0 else stats.beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - a / 2, k + 1, n - k)
    return (float(lo), float(hi))


def n_for_halfwidth(p, h, conf=0.95):
    z = stats.norm.ppf(0.5 + conf / 2)
    return math.ceil(z * z * p * (1 - p) / (h * h))


def n_two_proportions(p1, p2, alpha=0.05, power=0.8):
    za = stats.norm.ppf(1 - alpha / 2)
    zb = stats.norm.ppf(power)
    return math.ceil((za + zb) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p1 - p2) ** 2)


def rule_of_three(n):
    """Limite superior aproximado (95%) para 0 eventos em n tentativas."""
    return 3.0 / n


def block_bootstrap_ci(blocks, conf=0.95, B=2000, rng=None):
    """blocks: lista de (k, n) por bloco (sessão/dia). IC do PDR agregado reamostrando blocos."""
    rng = rng or np.random.default_rng(0)
    ks = np.array([b[0] for b in blocks], float)
    ns = np.array([b[1] for b in blocks], float)
    m = len(blocks)
    if m == 0 or ns.sum() == 0:
        return (float("nan"), float("nan"), float("nan"))
    est = ks.sum() / ns.sum()
    idx = rng.integers(0, m, (B, m))
    boots = ks[idx].sum(1) / np.maximum(ns[idx].sum(1), 1)
    a = (1 - conf) / 2
    return (float(est), float(np.quantile(boots, a)), float(np.quantile(boots, 1 - a)))


def design_effect(blocks):
    """Efeito de desenho (inflação da variância por correlação dentro do bloco)."""
    ks = np.array([b[0] for b in blocks], float)
    ns = np.array([b[1] for b in blocks], float)
    if len(blocks) < 2 or ns.sum() == 0:
        return float("nan")
    p = ks.sum() / ns.sum()
    var_naive = p * (1 - p) / ns.sum()
    pb = ks / np.maximum(ns, 1)
    var_block = np.var(pb, ddof=1) / len(blocks)
    return float(var_block / var_naive) if var_naive > 0 else float("nan")


def sample_size_table():
    rows = [
        ("PDR≈0,90, IC95% ±2 pp", n_for_halfwidth(0.9, 0.02)),
        ("PDR≈0,99, IC95% ±0,5 pp", n_for_halfwidth(0.99, 0.005)),
        ("0,90 contra 0,95, α=0,05, poder 80% (por braço)", n_two_proportions(0.90, 0.95)),
        ("desacordo permanente < 0,1% (regra de três)", math.ceil(3 / 0.001)),
    ]
    return rows
