# QuasiLeak-Bench CLI

Install from a checkout (Python 3.10 or newer):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
quasileak --help
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
`qlb` is a shorter alias for `quasileak`. To install directly from GitHub instead:

```bash
python -m pip install "git+https://github.com/Yufannnn/QuasiLeak-Bench.git"
```

The installed wheel includes the released scorer, split manifest, prediction schema,
and official prompt templates. The dataset is downloaded separately from the
[repository](https://github.com/Yufannnn/QuasiLeak-Bench/tree/main/data) or
[Hugging Face](https://huggingface.co/datasets/HenryZYF/QuasiLeak-Bench).
No PyPI release is required for either installation method.

## Offline terminal demo

From the repository root, after installation:

```bash
bash scripts/demo_cli.sh
```

This prints the benchmark header, dataset views, and score table without model calls.
The script extracts only the demo dataset into `outputs/cli-demo/`. The equivalent
individual commands are:

```bash
python -m zipfile -e data/quasileak_bench_data.zip data/
quasileak banner
quasileak datasets list
quasileak score --predictions examples/predictions_1k.jsonl \
  --dataset data/quasileak_bench_data_1k.jsonl \
  --name "Example detector (synthetic)" --output outputs/example-score.json
```

The final table is ready for a terminal screenshot. Its expected P-GF1 is **60.0163**,
with **1,000 documents** and **665 predicted groups**. These are synthetic example
predictions supplied with the release, not a newly evaluated model or a paper baseline.
The legacy 1K subset overlaps Train and Test and is for a quick check; use `--split test`
on the Full dataset for held-out evaluation.

The example passes the format and coverage checks but deliberately includes misses,
partial groups, and binding and policy errors. Passing `quasileak check` establishes
well-formed predictions, not their accuracy. `score` retains the scorer's original
penalties and does not silently filter or repair predictions.

## Commands

| Command | Purpose |
| --- | --- |
| `datasets list [--json]` | Show the released views and split sizes |
| `render` | Render the exact official 0-shot or 3-shot prompts |
| `run` | Run a detector on those prompts through a chat-completions API |
| `check` | Check prediction schema, IDs, coverage, and span locations |
| `score` | Run the unchanged released evaluator |
| `report` | Display saved scores as a table, JSON, or CSV |
| `compare` | Compare scores under matching evaluation conditions |
| `schema` | Print the released prediction schema |
| `diagnose` | Check bundled resources and print the scorer checksum |

Use `quasileak COMMAND --help` for flags. Construction commands such as `census`,
`assign`, `construct`, and `validate` keep their existing meaning.

## Render the official prompts

```bash
quasileak render --dataset data/quasileak_bench_data_full.jsonl \
  --split test --shots 3 --output outputs/test-requests.jsonl
```

Each request has `sample_id` and `messages`. Rendering preserves the full author
profile and the HIDE/KEEP/NEUTRAL policy. Gold annotations are not sent to the detector.
The official few-shot examples are preserved as separate chat messages.

## Run a detector

Set `LLM_API_KEY` and `LLM_BASE_URL` in your environment or an ignored `.env` file.
The base URL is the API prefix before `/chat/completions` (include `/v1` if your
provider requires it). Select a model supported by your endpoint:

```bash
quasileak run --dataset data/quasileak_bench_data_full.jsonl --split test \
  --model YOUR_MODEL --shots 3 --env-file .env --output outputs/model-predictions.jsonl
```

This command makes API calls and may incur provider charges. It runs sequentially,
prints progress, and saves each completed prediction immediately. Pass `--base-url`
to override `LLM_BASE_URL`, or `--api-key-env NAME` to read a different key variable.
No credentials are written to result metadata.

Run the same command with `--resume` after an interruption:

```bash
quasileak run --dataset data/quasileak_bench_data_full.jsonl --split test \
  --model YOUR_MODEL --shots 3 --env-file .env --output outputs/model-predictions.jsonl --resume
```

Resume checks the exact rendered prompts, dataset, model, endpoint, and generation
settings before skipping completed IDs. The output's `.run.json` records these
settings, and `.responses.jsonl` stores the raw model replies. An invalid JSON reply
stops the run with the raw reply preserved; resume retries that document. Invalid
groups or spans inside a prediction object remain available for the official
scorer's penalties.

The default output budget is 4,096 tokens; use `--max-tokens` to change it. Generation
settings are recorded for reproducibility, not asserted to reproduce a paper baseline.

## Check and score predictions

```bash
quasileak check --predictions outputs/model-predictions.jsonl \
  --dataset data/quasileak_bench_data_full.jsonl --split test
quasileak score --predictions outputs/model-predictions.jsonl \
  --dataset data/quasileak_bench_data_full.jsonl --split test \
  --name "My detector" --output outputs/model-score.json
quasileak report outputs/model-score.json --format csv --output outputs/model-score.csv
```

Files may be JSONL or gzipped JSONL. Predicted spans use verbatim strings (first
occurrence) or half-open character intervals, exactly as in the released scorer.
Use `quasileak score --json` for machine-readable stdout. The saved JSON contains
`metrics` and evaluation hashes, the selected split/arm, and metric parameters.
All metrics use the original scorer's definitions and defaults.

`check` is a submission diagnostic, not a prerequisite for scoring. The official
scorer continues to penalize malformed groups rather than repairing them.

## Policy-shift evaluation

Use `--arm original` or `--arm reassigned` with `render`, `run`, `check`, or `score`
on a policy-shift dataset. To score both arms and compute Suppress and Surface:

```bash
quasileak score --dataset data/splits/policy_shift.jsonl.gz \
  --predictions outputs/original.jsonl --reassigned-predictions outputs/reassigned.jsonl \
  --name "My detector" --output outputs/policy-score.json
quasileak report outputs/policy-score.json
```

The original arm can reuse a Test prediction file when it covers the study's IDs,
as supported by the released scorer. Do not combine paired scoring with `--arm`
or `--split`.

## Compare runs

```bash
quasileak compare outputs/baseline-score.json outputs/model-score.json
quasileak compare outputs/baseline-score.json outputs/model-score.json \
  --baseline outputs/baseline-score.json --format csv --output outputs/comparison.csv
```

The first file is the default baseline. P-GF1 deltas are percentage points.
Comparisons require identical evaluation metadata; they do not claim statistical
significance. Legacy raw scorer JSON can be displayed with `report`, but must be
regenerated through `quasileak score` to include the metadata required by `compare`.

## Development checks

```bash
python -m pip install -e ".[dev]" build
python -m pytest -q
python -m build
```

Builds bundle the canonical evaluator resources byte for byte. The original
`scorer/score.py` and corpus checksums remain unchanged.

## Terminal appearance

Interactive terminals use a large, full-name QuasiLeak-Bench block wordmark with a
cyan-to-blue-to-purple gradient, boxed tables, and a P-GF1 score card. The wordmark
adapts to the terminal width. Run `quasileak banner` to show the header on
its own, or `bash scripts/demo_cli.sh` for the synthetic example workflow.
The layout adapts to terminal width. Use `quasileak --plain datasets list` to
disable decoration, or set `NO_COLOR=1` to remove colours. Redirected output,
JSON, CSV, and saved score/report files remain plain; scores are unchanged.

The README includes a vector terminal preview generated from the actual CLI,
released scorer, and bundled example predictions. Regenerate it after a layout change:

```bash
python scripts/render_cli_preview.py
```
