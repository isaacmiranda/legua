#!/usr/bin/env bash
# Varredura de potência: roda os cenários que dependem do teto de TX com o teto limitado a cada valor (o de 28 dBm é a
# rodada normal). Um processo por vez, baixa prioridade. Uso: tools/varredura_teto.sh quick|full [tetos...]
set -u
esc="${1:-quick}"; shift || true
tetos=("$@"); [ ${#tetos[@]} -eq 0 ] && tetos=(8 14 20)
cd "$(dirname "$0")/.."
for t in "${tetos[@]}"; do
  echo "== teto $t dBm ($esc) =="
  PYTHONPATH=. nice -n 15 ionice -c 2 -n 7 ~/.venvs/legua/bin/python -m simsuite.run_suite \
    --escala "$esc" --procs 1 --teto "$t" --limite-horas 3 || echo "falhou: teto $t"
done
echo "exit 0"
