# Data

```bash
python -m zipfile -e data/quasileak_bench_data.zip data/
```

| file | |
|---|---|
| `quasileak_bench_data_full.jsonl` | 5,000 documents, 500 profiles, 20 contexts, 9,099 groups, 23,041 cues, 12,237 distractors |
| `quasileak_bench_data_1k.jsonl` | 1,000-document subset of the same rows |
| `metadata/` | counts, distributions, thresholds, and file hashes |
| `DATASHEET.md` | datasheet |

## Fields

| field | |
|---|---|
| `sample_id` | document id |
| `document` | message text |
| `profile` | the sender's eight attribute values and `profile_id` |
| `context` | `context_id`, `name`, `recipient`, `purpose`, `description`, `length` (words) |
| `policy` | `hide`, `keep`, `neutral`: a partition of the eight attributes |
| `gold.groups[]` | `group_id`, `attribute`, `cue_ids` (2 to 4), `secondary_attributes`, `distance` (`NEAR`, `MEDIUM`, `FAR`), `verification` |
| `gold.spans[]` | cues: `span_id`, `group_id`, `text`, `start`, `end` |
| `gold.distractors[]` | `distractor_id`, `text`, `start`, `end` |

Offsets are half-open code-point indices into `document`. `verification` holds the
verifier's confidence and lift over chance, with a rationale, for each cue alone (all weak,
lift below 0.45) and for the group (all revealing, lift at least 0.50).
`docs/GLOSSARY.md` maps the words used in rationales to the paper's terms.

## License

CC BY-NC-SA 4.0 (`LICENSE`). 300 profiles (`synthpai_` ids) are adapted from SynthPAI
(Yukhymenko et al., 2024), released under the same license.
