# Evaluation prompts

`zero_shot_messages.json` and `few_shot_messages.json` are the evaluation requests for the
first document of `quasileak_bench_data_full.jsonl`. `render.py` fills them for any row:

```bash
python prompts/render.py --dataset data/quasileak_bench_data_full.jsonl --shots 3 --output requests.jsonl
```

The reply `{"evidence": [...]}` plus `sample_id` is a row for `scorer/score.py`.
