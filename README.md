<p align="center"><img src="docs/banner.png" alt="QuasiLeak-Bench" width="100%"></p>

# QuasiLeak-Bench

QuasiLeak-Bench is a benchmark for policy-conditioned quasi-evidence group recovery. Messages
often contain cues that are weak alone but together reveal a private attribute of the sender,
and we call such a set of cues a quasi-evidence group. The benchmark pairs 5,000 messages with
the sender's profile and a disclosure policy that marks each attribute HIDE, KEEP, or NEUTRAL.
A detector returns the groups that reveal a HIDE attribute, each as two to four verbatim spans
bound to that attribute, and is scored on complete group recovery, attribute binding, and
policy compliance.

The ground truth is built in reverse. Weak cues are selected first and composed into groups
verified to reveal their attribute jointly, the message is written around them, and automated
quality control follows.

This repository holds the data, scorer, evaluation prompts, construction pipeline, and
fine-tuning recipe for *QuasiLeak-Bench: Evaluating LLM-Based Privacy Detectors on
Policy-Conditioned Quasi-Evidence Group Recovery*.

## Quickstart

```bash
pip install -e ".[dev]"
python -m zipfile -e data/quasileak_bench_data.zip data/
python scorer/score.py --predictions examples/predictions_1k.jsonl --dataset data/quasileak_bench_data_1k.jsonl
pytest
```

`examples/predictions_1k.jsonl` is a synthetic detector built from the 1K gold with misses,
partial groups, and binding and policy errors. It scores P-GF1 60.0 (N_pred 665).

## Contents

| path | |
|---|---|
| `data/` | the benchmark (5,000 documents) and a 1,000-document subset; see `data/README.md` |
| `scorer/` | the P-GF1 scorer; see `scorer/README.md` |
| `prompts/` | the detector prompts and `render.py`, which fills them for any row |
| `quasileak/` | the construction pipeline and its prompts |
| `configs/` | construction parameters and model roles |
| `training/` | the fine-tuning recipe and the profile split |
| `docs/GLOSSARY.md` | construction terms in prompts and rationales |

## Evaluation

```bash
python prompts/render.py --dataset data/quasileak_bench_data_full.jsonl --shots 3 --output requests.jsonl
python scorer/score.py --predictions predictions.jsonl --dataset data/quasileak_bench_data_full.jsonl
```

A prediction row is `{"sample_id": ..., "evidence": [...]}` with `evidence` taken from the
model's reply.

## Construction

```bash
quasileak census --profiles profiles.jsonl --models configs/models.example.yaml --env-file .env --output census.jsonl
quasileak assign --profiles profiles.jsonl --contexts contexts.jsonl --models configs/models.example.yaml --env-file .env --output assignments.jsonl
quasileak construct \
    --profiles examples/profiles.example.jsonl \
    --contexts examples/contexts.example.jsonl \
    --config configs/construction.yaml \
    --models configs/models.example.yaml \
    --env-file .env \
    --output outputs/example
```

`census` screens profiles with two judges, and `assign` scores every profile-context pair
with three judges and solves the assignment (`pip install -e ".[assign]"`); pass its output to
`construct --assignments`. `mine-cues`, `build-groups`, `write-documents`, and `validate` run
single stages. `construct` writes candidate documents, and the quality-check prompts in
`quasileak/prompts/quality_check.py` screen them before release. The endpoint is any
OpenAI-compatible API (`.env.example`).

## License

Code: MIT. Data: CC BY-NC-SA 4.0 (`data/LICENSE`).
