# Scorer

```bash
python scorer/score.py --predictions predictions.jsonl --dataset data/quasileak_bench_data_full.jsonl --split test
```

Standard library only. One prediction row per document:

```json
{"sample_id": "...", "evidence": [{"attribute": "education", "spans": ["verbatim span 1", "verbatim span 2"]}]}
```

`predictions` is accepted in place of `evidence`. A span is verbatim text, located at its
first occurrence, or `{"start": s, "end": e}`. `prediction_schema.json` gives the format.

Output, 0 to 100 except `N_pred`: P-GP, P-GR, P-GF1 (headline), B-GP, B-GR, B-GF1, E-GP,
E-GR, E-GF1, the mean factors `E_C`, `E_L`, `B_G`, `B_A`, cue recall `E_R`, distractor
selection rate DSR, and `N_pred`. The paper defines each metric. FAR is the false-alarm rate,
the share of documents with no HIDE group that still receive a scored prediction, over
`N_no_hide` such documents.

`--split` scores one view of a dataset file (`train`, `validation`, `test`, `subset_non_revealing`)
using `data/splits/split_manifest.json`, ignoring prediction rows outside it. A policy-shift file is scored one policy at a time
with `--arm original` or `--arm reassigned`, or both at once:

```bash
python scorer/score.py --predictions test_predictions.jsonl --reassigned-predictions reassigned.jsonl \
    --dataset data/splits/policy_shift.jsonl.gz
```

This reports every metric for each arm and the paper's two policy-response measures.
Suppress is the share of groups found under the original policy that disappear once their
attribute is no longer HIDE, and Surface is the share of newly HIDE groups that the model
emits under the reassigned policy. Both use span-based group alignment, whatever attribute a
prediction names. The original arm may reuse a Test prediction file.

`--gamma`, `--theta`, `--rho-sec`, and `--lambda-k` set the four metric parameters. The
defaults are the paper's, 2, 0.75, 0.5, and 1.
