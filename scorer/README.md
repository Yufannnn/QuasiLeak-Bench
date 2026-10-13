# Scorer

```bash
python scorer/score.py --predictions predictions.jsonl --dataset data/quasileak_bench_data_full.jsonl
```

Standard library only. One prediction row per document:

```json
{"sample_id": "...", "evidence": [{"attribute": "education", "spans": ["verbatim span 1", "verbatim span 2"]}]}
```

`predictions` is accepted in place of `evidence`. A span is verbatim text, located at its
first occurrence, or `{"start": s, "end": e}`. `prediction_schema.json` gives the format.

Output, 0 to 100 except `N_pred`: P-GP, P-GR, P-GF1 (headline), B-GP, B-GR, B-GF1, E-GP,
E-GR, E-GF1, the mean factors `E_C`, `E_L`, `B_G`, `B_A`, cue recall `E_R`, distractor
selection rate DSR, and `N_pred`. The paper defines each metric.

`--gamma`, `--theta`, `--rho-sec`, and `--lambda-k` set the four metric parameters. The
defaults are the paper's, 2, 0.75, 0.5, and 1.
