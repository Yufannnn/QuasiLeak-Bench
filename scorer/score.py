#!/usr/bin/env python3
"""P-GF1 scorer for QuasiLeak-Bench.

    python score.py --predictions predictions.jsonl --dataset quasileak_bench_data_full.jsonl --split test
    python score.py --predictions original.jsonl --reassigned-predictions reassigned.jsonl \
        --dataset policy_shift.jsonl.gz

Standard library only. One row per document, {"sample_id": ..., "evidence": [{"attribute": ...,
"spans": [...]}]}, where a span is verbatim text or {"start": s, "end": e}. The paper defines
the metrics; --gamma, --theta, --rho-sec, and --lambda-k set its four parameters.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from pathlib import Path

GAMMA, THETA, RHO_SEC, LAMBDA_K = 2.0, 0.75, 0.5, 1.0
MANIFEST = Path(__file__).resolve().parents[1] / "data" / "splits" / "split_manifest.json"
SPLITS = ("train", "validation", "test", "no_violation")
DSR_IOU = 0.5
TOKEN = re.compile(r"\w+(?:['\N{RIGHT SINGLE QUOTATION MARK}]\w+)*")
WHITESPACE_TOKEN = re.compile(r"\S+")
EPS = 1e-12
FACTORS = ("E_C", "E_L", "B_G", "B_A")


def locate(span, doc):
    """Character interval of a predicted span, or None when it cannot be placed."""
    if isinstance(span, dict):
        start, end = span.get("start"), span.get("end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(doc):
            return start, end
        span = span.get("text")
    if isinstance(span, str) and span.strip():
        text = span.strip()
        start = doc.find(text)
        if start >= 0:
            return start, start + len(text)
    return None


def token_set(interval, offsets):
    """Indices of the tokens a [start, end) interval overlaps."""
    if interval is None:
        return frozenset()
    start, end = interval
    return frozenset(i for i, (a, b) in enumerate(offsets) if a < end and b > start)


def iou(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def match(pred, gold, threshold=THETA):
    """Best one-to-one span matching at IoU >= threshold: most matches, then highest IoU
    sum, then lowest index pairs. Exact search over subsets of the gold spans."""
    states = {0: (0, 0.0, ())}
    for i, p in enumerate(pred):
        nxt = dict(states)
        for mask, (n, total, pairs) in states.items():
            for j, g in enumerate(gold):
                bit, v = 1 << j, iou(p, g)
                if v >= threshold and not mask & bit:
                    cand = (n + 1, total + v, pairs + ((i, j),))
                    nxt[mask | bit] = cand if mask | bit not in nxt else max_by(better, nxt[mask | bit], cand)
        states = nxt
    best = (0, 0.0, ())
    for cand in states.values():
        best = max_by(better, best, cand)
    return best[2]


def max_by(order, x, y):
    return x if order(x, y) else y


def better(x, y):
    """Span matching order on (count, IoU sum, pairs)."""
    if x[0] != y[0]:
        return x[0] > y[0]
    if not math.isclose(x[1], y[1], rel_tol=0.0, abs_tol=EPS):
        return x[1] > y[1]
    return tuple(sorted(x[2])) <= tuple(sorted(y[2]))


def group_better(x, y):
    """Group alignment order on (weight, count, pairs)."""
    if not math.isclose(x[0], y[0], rel_tol=0.0, abs_tol=EPS):
        return x[0] > y[0]
    if x[1] != y[1]:
        return x[1] > y[1]
    return tuple(sorted(x[2])) <= tuple(sorted(y[2]))


def score_document(preds, groups, hide, keep, gamma=GAMMA, theta=THETA, rho_sec=RHO_SEC):
    """preds: [{attribute, spans: [token sets]}]; groups: [{attribute, secondary, spans}]."""
    cues = [s for g in groups for s in g["spans"]]
    pair = []
    for p in preds:
        r = len(p["spans"])
        n_cue = sum(any(iou(s, c) >= theta for c in cues) for s in p["spans"])
        row = []
        for g in groups:
            m = len(match(p["spans"], g["spans"], theta))
            cell = {
                "E_C": (m / len(g["spans"])) ** gamma if g["spans"] else 0.0,
                "E_L": n_cue / r if r else 0.0,
                "B_G": m / n_cue if n_cue else 0.0,
                "B_A": 1.0 if p["attribute"] == g["attribute"] else rho_sec if p["attribute"] in g["secondary"] else 0.0,
            }
            cell["c_E"] = cell["E_C"] * cell["E_L"]
            cell["w"] = cell["c_E"] * cell["B_G"]
            cell["c_B"] = cell["w"] * cell["B_A"]
            cell["c_P"] = cell["c_B"] * (p["attribute"] in hide)
            row.append(cell)
        pair.append(row)

    # one-to-one group alignment on the structural weight w: highest total, then most pairs
    states = {0: (0.0, 0, ())}
    for i, row in enumerate(pair):
        nxt = dict(states)
        for mask, (total, n, pairs) in states.items():
            for j, cell in enumerate(row):
                bit = 1 << j
                if cell["w"] > 0.0 and not mask & bit:
                    cand = (total + cell["w"], n + 1, pairs + ((i, j),))
                    prev = nxt.get(mask | bit)
                    nxt[mask | bit] = cand if prev is None or group_better(cand, prev) else prev
        states = nxt
    aligned = (0.0, 0, ())
    for cand in states.values():
        aligned = cand if group_better(cand, aligned) else aligned
    aligned = aligned[2]

    exempt = {
        i
        for i, j in aligned
        if groups[j]["attribute"] not in hide
        and preds[i]["attribute"] in hide
        and preds[i]["attribute"] in groups[j]["secondary"]
    }
    hide_pairs = [(i, j) for i, j in aligned if groups[j]["attribute"] in hide]
    credited = {i: j for i, j in hide_pairs if pair[i][j]["c_P"] > 0.0}

    keep_cues = [s for g in groups if g["attribute"] in keep for s in g["spans"]]
    n_keep = 0
    for i, p in enumerate(preds):
        if i in exempt:
            continue
        if p["attribute"] in keep:
            n_keep += 1
            continue
        own = {a for a, _ in match(p["spans"], groups[credited[i]]["spans"], theta)} if i in credited else set()
        n_keep += any(iou(s, k) >= theta for pos, s in enumerate(p["spans"]) if pos not in own for k in keep_cues)

    out = {stage: sum(pair[i][j][stage] for i, j in hide_pairs) for stage in ("c_E", "c_B", "c_P")}
    out.update({
        "n_pred": len(preds) - len(exempt),
        "n_keep": n_keep,
        "n_hide": sum(g["attribute"] in hide for g in groups),
        "aligned": len(aligned),
        "group_aligned": {j for _, j in aligned},
        "group_credit": {j: pair[i][j]["c_P"] for i, j in hide_pairs},
    })
    for factor in FACTORS:
        out[factor] = sum(pair[i][j][factor] for i, j in aligned)
    return out


def read_jsonl(path):
    with (gzip.open if str(path).endswith(".gz") else open)(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def prf(credit, n_pred, n_gold):
    if n_pred == 0 and n_gold == 0:
        return 1.0, 1.0, 1.0
    p = credit / n_pred if n_pred else 0.0
    r = credit / n_gold if n_gold else 0.0
    return p, r, 2 * p * r / (p + r) if p + r else 0.0


def prediction_objects(row):
    objects = row.get("evidence", row.get("predictions"))
    if objects is None:
        raise ValueError(f"{row['sample_id']}: a row needs an 'evidence' list")
    if not isinstance(objects, list):
        raise ValueError(f"{row['sample_id']}: 'evidence' must be a list")
    return [o if isinstance(o, dict) else {} for o in objects]


def distractor_hits(intervals, distractors, doc):
    """Planted distractors that any predicted interval overlaps at whitespace-token IoU >= DSR_IOU."""
    offsets = [(m.start(), m.end()) for m in WHITESPACE_TOKEN.finditer(doc)]
    predicted = [token_set(x, offsets) for x in intervals]
    planted = [t for d in distractors if (t := token_set((d["start"], d["end"]), offsets))]
    return len(planted), sum(any(iou(d, p) >= DSR_IOU for p in predicted) for d in planted)


def gold_rows_for(dataset, split=None, arm=None, manifest=MANIFEST):
    """Rows of a dataset file, restricted to a named split, with a policy-shift pair
    resolved to one of its two policies."""
    rows = read_jsonl(dataset)
    if split:
        with open(manifest, encoding="utf-8") as fh:
            members = set(json.load(fh)["membership"][split])
        rows = [r for r in rows if r["sample_id"] in members]
        if len(rows) != len(members):
            raise ValueError(f"{dataset} holds {len(rows)} of the {len(members)} documents in split {split!r}")
    if rows and "policy_original" in rows[0]:
        if arm not in ("original", "reassigned"):
            raise ValueError("a policy-shift file needs --arm original or --arm reassigned")
        rows = [{**r, "policy": r[f"policy_{arm}"]} for r in rows]
    return rows


def read_predictions(predictions, gold_rows, allow_extra=False):
    pred_rows = {}
    for r in read_jsonl(predictions):
        if r["sample_id"] in pred_rows:
            raise ValueError(f"duplicate prediction row for {r['sample_id']}")
        pred_rows[r["sample_id"]] = r
    missing = [r["sample_id"] for r in gold_rows if r["sample_id"] not in pred_rows]
    extra = set(pred_rows) - {r["sample_id"] for r in gold_rows}
    if missing or (extra and not allow_extra):
        raise ValueError(f"predictions must cover every document once: {len(missing)} missing, {len(extra)} unknown")
    return pred_rows


def score(predictions, dataset, gamma=GAMMA, theta=THETA, rho_sec=RHO_SEC, lambda_k=LAMBDA_K,
          split=None, arm=None, details=None, allow_extra=False):
    gold_rows = gold_rows_for(dataset, split, arm)
    # a prediction file for the whole corpus may be scored on one of its splits
    pred_rows = read_predictions(predictions, gold_rows, allow_extra or bool(split))

    total = dict.fromkeys(("c_E", "c_B", "c_P", "n_pred", "n_keep", "n_hide", "aligned", *FACTORS), 0.0)
    cues_found = cues_hide = planted = selected = 0
    no_violation = false_alarms = 0
    for row in gold_rows:
        doc = row["document"]
        offsets = [(m.start(), m.end()) for m in TOKEN.finditer(doc)]
        hide, keep = set(row["policy"]["hide"]), set(row["policy"]["keep"])
        spans = {s["span_id"]: s for s in row["gold"]["spans"]}
        groups = [
            {
                "attribute": g["attribute"],
                "secondary": set(g["secondary_attributes"]),
                "spans": [token_set((spans[c]["start"], spans[c]["end"]), offsets) for c in g["cue_ids"]],
            }
            for g in row["gold"]["groups"]
        ]
        objects = prediction_objects(pred_rows[row["sample_id"]])
        located = [[locate(s, doc) for s in (o.get("spans") or [])] if isinstance(o.get("spans"), list) else []
                   for o in objects]
        preds = [
            {"attribute": o.get("attribute"), "spans": [token_set(x, offsets) for x in intervals]}
            for o, intervals in zip(objects, located)
        ]
        doc_score = score_document(preds, groups, hide, keep, gamma, theta, rho_sec)
        for key in total:
            total[key] += doc_score[key]
        if not doc_score["n_hide"]:
            no_violation += 1
            false_alarms += doc_score["n_pred"] > 0
        if details is not None:
            details[row["sample_id"]] = doc_score

        distinct = sorted({x for intervals in located for x in intervals if x is not None})
        hide_cues = [s for g in groups if g["attribute"] in hide for s in g["spans"]]
        cues_hide += len(hide_cues)
        cues_found += len(match([token_set(x, offsets) for x in distinct], hide_cues, theta)) if hide_cues else 0
        n_planted, n_selected = distractor_hits(distinct, row["gold"]["distractors"], doc)
        planted, selected = planted + n_planted, selected + n_selected

    p, r, f = prf(total["c_P"], total["n_pred"] + lambda_k * total["n_keep"], total["n_hide"])
    bp, br, bf = prf(total["c_B"], total["n_pred"], total["n_hide"])
    ep, er, ef = prf(total["c_E"], total["n_pred"], total["n_hide"])
    scores = {"P-GP": p, "P-GR": r, "P-GF1": f, "B-GP": bp, "B-GR": br, "B-GF1": bf,
              "E-GP": ep, "E-GR": er, "E-GF1": ef}
    for factor in FACTORS:
        scores[factor] = total[factor] / total["aligned"] if total["aligned"] else None
    scores["E_R"] = cues_found / cues_hide if cues_hide else 0.0
    scores["DSR"] = selected / planted if planted else 0.0
    # documents with no HIDE gold group that still receive a scored prediction
    scores["FAR"] = false_alarms / no_violation if no_violation else None
    out = {k: None if v is None else round(100 * v, 4) for k, v in scores.items()}
    out["N_pred"] = int(total["n_pred"])
    out["N_docs"] = len(gold_rows)
    out["N_no_violation"] = no_violation
    return out


def score_policy_shift(predictions_original, predictions_reassigned, dataset, gamma=GAMMA, theta=THETA,
                       rho_sec=RHO_SEC, lambda_k=LAMBDA_K):
    """Both arms of a policy-shift file and the paper's two policy-response measures, which
    use span-based group alignment whatever attribute a prediction names. Suppress is the
    share of groups found under the original policy that disappear once their attribute is
    no longer HIDE. Surface is the share of newly HIDE groups emitted under the reassigned
    policy. The original arm may reuse a QLB-Test prediction file; rows outside the pairs are
    ignored."""
    before, after = {}, {}
    out = {
        "original": score(predictions_original, dataset, gamma, theta, rho_sec, lambda_k,
                          arm="original", details=before, allow_extra=True),
        "reassigned": score(predictions_reassigned, dataset, gamma, theta, rho_sec, lambda_k,
                            arm="reassigned", details=after),
    }
    found = dropped = hidden = surfaced = 0
    for row in read_jsonl(dataset):
        hide_o, hide_r = set(row["policy_original"]["hide"]), set(row["policy_reassigned"]["hide"])
        old, new = before[row["sample_id"]]["group_aligned"], after[row["sample_id"]]["group_aligned"]
        for j, g in enumerate(row["gold"]["groups"]):
            if g["attribute"] in hide_o and g["attribute"] not in hide_r and j in old:
                found += 1
                dropped += j not in new
            elif g["attribute"] in hide_r and g["attribute"] not in hide_o:
                hidden += 1
                surfaced += j in new
    out["Suppress"] = round(100 * dropped / found, 4) if found else None
    out["Surface"] = round(100 * surfaced / hidden, 4) if hidden else None
    out["N_suppress"], out["N_surface"] = found, hidden
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--predictions", required=True, help="JSONL, one row per document (the original-policy arm for a policy-shift file)")
    ap.add_argument("--dataset", required=True, help="a QuasiLeak-Bench JSONL file, optionally gzipped")
    ap.add_argument("--split", choices=SPLITS, help="score only this split of the dataset file (data/splits/split_manifest.json)")
    ap.add_argument("--arm", choices=("original", "reassigned"), help="the policy to score in a policy-shift file")
    ap.add_argument("--reassigned-predictions", help="predictions under the reassigned policy; scores both arms of a policy-shift file")
    ap.add_argument("--gamma", type=float, default=GAMMA, help="completeness exponent")
    ap.add_argument("--theta", type=float, default=THETA, help="span-match IoU threshold")
    ap.add_argument("--rho-sec", type=float, default=RHO_SEC, help="credit for a verified secondary attribute")
    ap.add_argument("--lambda-k", type=float, default=LAMBDA_K, help="weight of KEEP violations")
    args = ap.parse_args()
    params = (args.gamma, args.theta, args.rho_sec, args.lambda_k)
    if args.reassigned_predictions:
        result = score_policy_shift(args.predictions, args.reassigned_predictions, args.dataset, *params)
    else:
        result = score(args.predictions, args.dataset, *params, split=args.split, arm=args.arm)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
