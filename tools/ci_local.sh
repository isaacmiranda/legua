#!/usr/bin/env bash
# CI local leve (4 GB de RAM, HDD): 1 job, baixa prioridade. Uso: tools/ci_local.sh [--suite]
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$HOME/.venvs/legua/bin/python}"
LOW="nice -n 15 ionice -c 2 -n 7"
echo "== núcleo C (make -j1 test) =="
$LOW make -j1 -C core test
echo "== pytest =="
PYTHONPATH=. $LOW "$PY" -m pytest -q simsuite/tests
if [ "${1:-}" = "--suite" ]; then
  echo "== suíte rápida (~3 min) =="
  PYTHONPATH=. $LOW "$PY" -m simsuite.run_suite --escala quick
fi
