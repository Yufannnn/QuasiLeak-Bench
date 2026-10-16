#!/usr/bin/env bash
# Offline demo using the release's synthetic example detector; no model calls.
set -euo pipefail
demo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$demo_root"
if [[ -x .venv/bin/quasileak ]]; then
  demo_python=.venv/bin/python
  demo_cli=.venv/bin/quasileak
elif command -v quasileak >/dev/null 2>&1; then
  demo_python=python3
  demo_cli=quasileak
else
  echo 'Install first: python3 -m venv .venv && .venv/bin/python -m pip install .'
  exit 1
fi
mkdir -p outputs/cli-demo
if [[ ! -f outputs/cli-demo/quasileak_bench_data_1k.jsonl ]]; then
  "$demo_python" - <<'PY'
from zipfile import ZipFile
with ZipFile("data/quasileak_bench_data.zip") as archive:
    archive.extract("quasileak_bench_data_1k.jsonl", "outputs/cli-demo")
PY
fi
"$demo_cli" banner
echo
"$demo_cli" datasets list
echo
"$demo_cli" check --dataset outputs/cli-demo/quasileak_bench_data_1k.jsonl \
  --predictions examples/predictions_1k.jsonl
echo
"$demo_cli" score --dataset outputs/cli-demo/quasileak_bench_data_1k.jsonl \
  --predictions examples/predictions_1k.jsonl --name 'Example detector (synthetic)' \
  --output outputs/cli-demo/example-score.json
