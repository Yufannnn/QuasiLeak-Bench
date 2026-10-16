# Data

```bash
python -m zipfile -e data/quasileak_bench_data.zip data/
```

| file | |
|---|---|
| `quasileak_bench_data_full.jsonl` | 5,000 documents, 500 profiles, 20 contexts, 9,099 groups, 23,041 cues, 12,237 distractors |
| `quasileak_bench_data_1k.jsonl` | 1,000-document subset of the same rows |
| `quasileak_bench_data_v1.0.jsonl` | v1.0.0, the corpus of the submitted paper (`CHANGELOG.md`) |
| `metadata/` | counts, distributions, thresholds, and file hashes |
| `DATASHEET.md` | datasheet |

`splits/` sits next to the zip:

| file | |
|---|---|
| `split_manifest.json` | sample ids of Train, Validation, Test, QLB-SNR, QLB-PS, and the fine-tuning study's policy pairs, with source hashes |
| `validation_report.json` | the checks the split files pass |
| `subset_non_revealing.jsonl.gz` | QLB-SNR (Subset Non-Revealing), 1,618 Full documents in which no smaller subset of any HIDE group reveals its attribute |
| `policy_shift.jsonl.gz` | QLB-PS, the paper's 500-pair policy study, each document under its released and a reassigned policy |
| `sft_policy_shift.jsonl.gz` | the fine-tuning study's 500 policy pairs, all in Test |

A policy-shift row is a dataset row with `policy_original` and `policy_reassigned` in place
of `policy`, the gold `group_id`s each policy hides (`targets_original`,
`targets_reassigned`), and the attributes whose HIDE status changes for groups in the
document (`newly_hidden`, `newly_permitted`). Each policy's targets are all verified groups
of an attribute it marks HIDE.

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
