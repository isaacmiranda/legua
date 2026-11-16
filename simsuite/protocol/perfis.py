"""Perfis nomeados do protocolo (resultado da sintonia F7, docs/06 §F7).

Cada perfil é um `Config` (o núcleo C tem os mesmos em `legua_params_profile`; o teste de equivalência confere).
A escolha é um compromisso entre energia e estabilidade, não uma melhoria sem custo:

  padrao     margem de aceleração fixa de 8 dB; o que menos gasta energia; oscila mais em enlaces urbanos
  estavel    exige 8 dB + 3 desvios do SNR medido (`fade_k` = 3): menos quedas ao modo base e menos tempo de
             desacordo entre as pontas, ao custo de energia (o enlace acelera menos)
  cauteloso  margem fixa de 14 dB: só acelera com folga grande; simples, sem estatística

Os números de cada perfil por cenário estão na aba "Sintonia (F7)" do site e em docs/06.
"""
from .endpoint import Config

PERFIS = {
    "padrao": Config(),
    "estavel": Config(fade_k=3.0),
    "cauteloso": Config(margin_up=14.0),
}
# índice do perfil no núcleo C (enum legua_profile)
PERFIL_C = {"padrao": 0, "estavel": 1, "cauteloso": 2}


def perfil(nome):
    """Devolve uma cópia do `Config` do perfil (levanta KeyError se o nome não existe)."""
    from dataclasses import replace
    return replace(PERFIS[nome])
