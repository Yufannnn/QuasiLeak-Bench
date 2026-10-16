<p align="center"><img src="docs/banner.png" alt="QuasiLeak-Bench" width="100%"></p>

# QuasiLeak-Bench

[Paper](https://arxiv.org/abs/2610.21333) · [Dataset](https://huggingface.co/datasets/HenryZYF/QuasiLeak-Bench) · [Leaderboard](https://yufannnn.github.io/QuasiLeak-Bench/)

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

## Benchmark views

| view | documents | use |
|---|---:|---|
| QLB-Test | 1,000 | the headline set for prompted and fine-tuned systems |
| QLB-Full | 5,000 | prompted systems, as in the paper's main comparison |
| QLB-SNR | 1,618 | Subset Non-Revealing: Full documents in which no smaller subset of any HIDE group reveals its attribute |
| QLB-PS | 500 pairs | the paper's policy study: documents under their released and a reassigned policy |
| Train / Validation | 3,500 / 500 | fine-tuning and model selection |

The split is by profile (350 / 50 / 100 profiles, `training/split.json`), so no Test profile
appears in Train or Validation. Test lies inside Full, so no system may train on a Test
document. `data/splits/` holds the membership of each view and the paired policy-shift file.
The 1,000-document subset in the data zip overlaps Train and Test, so it serves only as a quick
check.
The same views load from the Hugging Face dataset as the configurations `qlb`, `full`,
`subset_non_revealing`, and `policy_shift`.


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
python scorer/score.py --predictions predictions.jsonl --dataset data/quasileak_bench_data_full.jsonl --split test
python scorer/score.py --predictions predictions.jsonl --reassigned-predictions reassigned.jsonl \
    --dataset data/splits/policy_shift.jsonl.gz
```

A prediction row is `{"sample_id": ..., "evidence": [...]}` with `evidence` taken from the
model's reply. Scores include the false-alarm rate on documents with no HIDE group.
QLB-PS scores one run under each document's released policy and one under the reassigned
policy; `scorer/README.md` lists every output.

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

## Citation

```bibtex
@article{zhu2026quasileak,
  title   = {QuasiLeak-Bench: Evaluating LLM-Based Privacy Detectors on
             Policy-Conditioned Quasi-Evidence Group Recovery},
  author  = {Zhu, Yufan and Jiang, Yangfan and Fei, Yang and Hou, Shizheng and
             Mohapatra, Shubhankar and Xiao, Xiaokui},
  journal = {arXiv preprint arXiv:2610.21333},
  year    = {2026}
}
```

## License

Code: MIT. Data: CC BY-NC-SA 4.0 (`data/LICENSE`).
