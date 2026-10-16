"""Public evaluation commands. All scores come from the unchanged release scorer."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.util
from importlib.metadata import version
import io
import json
import math
from pathlib import Path
import sys

METRICS = ("P-GF1", "P-GP", "P-GR", "E-GF1", "DSR", "FAR", "N_docs", "N_pred")
SPLITS = ("train", "validation", "test", "subset_non_revealing")
PARAMETERS = {"gamma": 2.0, "theta": 0.75, "rho_sec": 0.5, "lambda_k": 1.0}


def resource_root():
    package = Path(__file__).resolve().parent
    for candidate in (package / "_bundled", package.parent):
        if (candidate / "scorer/score.py").is_file():
            return candidate
    raise RuntimeError("Evaluator resources are missing; reinstall quasileak-bench")


@lru_cache(maxsize=None)
def released_module(name):
    path = resource_root() / {"scorer": "scorer/score.py", "renderer": "prompts/render.py"}[name]
    spec = importlib.util.spec_from_file_location("_qlb_released_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def selected_rows(args):
    rows = released_module("scorer").gold_rows_for(args.dataset, args.split, args.arm)
    if not rows:
        raise ValueError("The selected dataset is empty")
    ids = [r["sample_id"] for r in rows]
    if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("Dataset sample IDs must be unique nonempty strings")
    return rows


def output_text(text, path=None):
    if path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")


def output_json(value, path=None):
    output_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", path)


def table(headers, rows):
    def display(value):
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.4f}"
        return str(value)
    body = [[display(value) for value in row] for row in rows]
    widths = [max(len(header), *(len(row[i]) for row in body)) for i, header in enumerate(headers)]
    def line(row):
        return "  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip()
    return "\n".join([line(headers), line(["─" * w for w in widths]), *(line(row) for row in body)]) + "\n"


def dataset_arguments(parser):
    parser.add_argument("--dataset", type=Path, required=True, help="Released JSONL dataset, optionally .gz")
    parser.add_argument("--split", choices=SPLITS, help="Restrict to the official split")
    parser.add_argument("--arm", choices=("original", "reassigned"), help="Policy-shift arm")


def add_commands(commands):
    datasets = commands.add_parser("datasets", help="Inspect the released benchmark views")
    sub = datasets.add_subparsers(dest="dataset_command", required=True)
    listing = sub.add_parser("list", help="List views, counts, and intended use")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(handler=list_datasets)

    render = commands.add_parser("render", help="Render the official prompts with full profiles and policies")
    dataset_arguments(render)
    render.add_argument("--shots", type=int, choices=(0, 3), default=3)
    render.add_argument("--output", type=Path, required=True)
    render.set_defaults(handler=render_prompts)

    score = commands.add_parser("score", help="Score predictions with the released P-GF1 evaluator")
    dataset_arguments(score)
    score.add_argument("--predictions", type=Path, required=True)
    score.add_argument("--reassigned-predictions", type=Path, help="Score both policy-shift arms")
    score.add_argument("--name", help="Run label for reports")
    score.add_argument("--output", type=Path, help="Save metrics and comparison metadata as JSON")
    score.add_argument("--json", action="store_true", help="Print the saved JSON format")
    for name, default in PARAMETERS.items():
        score.add_argument("--" + name.replace("_", "-"), type=float, default=default)
    score.set_defaults(handler=score_predictions)

    check = commands.add_parser("check", help="Check prediction format, document IDs, coverage, and span locations")
    dataset_arguments(check)
    check.add_argument("--predictions", type=Path, required=True)
    check.set_defaults(handler=check_predictions)

    for command, help_text in (("report", "Display saved scores"), ("compare", "Compare runs with matching evaluation metadata")):
        parser = commands.add_parser(command, help=help_text)
        parser.add_argument("scores", nargs="+", type=Path)
        parser.add_argument("--format", choices=("table", "json", "csv"), default="table")
        parser.add_argument("--output", type=Path)
        if command == "compare":
            parser.add_argument("--baseline", type=Path, help="Baseline score file (default: first input)")
        parser.set_defaults(handler=compare_scores if command == "compare" else report_scores)

    schema = commands.add_parser("schema", help="Print the released prediction JSON schema")
    schema.set_defaults(handler=lambda args: output_json(json.loads(
        (resource_root() / "scorer/prediction_schema.json").read_text(encoding="utf-8"))))
    diagnose = commands.add_parser("diagnose", help="Check the installed evaluator and prompt resources")
    diagnose.set_defaults(handler=diagnose_install)

    from .evaluation_run import add_run_command
    add_run_command(commands)


def list_datasets(args):
    manifest = json.loads((resource_root() / "data/splits/split_manifest.json").read_text(encoding="utf-8"))
    membership = manifest["membership"]
    views = [
        {"view": "QLB-Test", "documents": len(membership["test"]), "selection": "--split test", "use": "Held-out evaluation"},
        {"view": "QLB-Full", "documents": manifest["files"]["full/full"]["rows"], "selection": "Full dataset", "use": "Prompted evaluation; includes Train/Test"},
        {"view": "QLB-SNR", "documents": len(membership["subset_non_revealing"]), "selection": "--split subset_non_revealing", "use": "Subset non-revealing groups"},
        {"view": "QLB-PS", "documents": len(membership["policy_shift"]), "selection": "Policy-shift file + --arm", "use": "Paired policy evaluation"},
        {"view": "Train", "documents": len(membership["train"]), "selection": "--split train", "use": "Training only"},
        {"view": "Validation", "documents": len(membership["validation"]), "selection": "--split validation", "use": "Model selection"},
    ]
    if args.json:
        output_json(views)
    else:
        print("QuasiLeak-Bench | Dataset views\n")
        print(table(("View", "Documents", "Selection", "Use"), [[v[k] for k in ("view", "documents", "selection", "use")] for v in views]))
        print("Splits are by profile. QLB-Full contains Test; do not train on Test documents.")


def render_prompts(args):
    rows = selected_rows(args)
    render = released_module("renderer").render
    if args.output.resolve() == args.dataset.resolve():
        raise ValueError("Output must differ from the dataset")
    output_text("".join(json.dumps({"sample_id": row["sample_id"], "messages": render(row, args.shots)},
                                   ensure_ascii=False) + "\n" for row in rows), args.output)
    print(f"Rendered {len(rows):,} official {args.shots}-shot prompts → {args.output}")


def evaluation_metadata(args, rows, parameters):
    return {
        "dataset_sha256": digest(args.dataset),
        "sample_ids_sha256": json_digest(sorted(row["sample_id"] for row in rows)),
        "scorer_sha256": digest(resource_root() / "scorer/score.py"),
        "manifest_sha256": digest(resource_root() / "data/splits/split_manifest.json") if args.split else None,
        "split": args.split,
        "arm": args.arm,
        "parameters": parameters,
    }


def score_predictions(args):
    scorer = released_module("scorer")
    params = {key: getattr(args, key) for key in PARAMETERS}
    if any(not math.isfinite(value) for value in params.values()):
        raise ValueError("Metric parameters must be finite")
    if params["gamma"] <= 0 or not 0 < params["theta"] <= 1 or not 0 <= params["rho_sec"] <= 1 or params["lambda_k"] < 0:
        raise ValueError("Require gamma > 0, 0 < theta <= 1, 0 <= rho-sec <= 1, lambda-k >= 0")
    if args.output and args.output.resolve() in {path.resolve() for path in (
        args.dataset, args.predictions, args.reassigned_predictions) if path}:
        raise ValueError("Output must differ from all inputs")
    if args.reassigned_predictions:
        if args.arm or args.split:
            raise ValueError("--reassigned-predictions cannot be combined with --arm or --split")
        rows = scorer.gold_rows_for(args.dataset, arm="original")
        if not rows or any("policy_original" not in row for row in rows):
            raise ValueError("Paired evaluation requires a policy-shift dataset")
        metrics = scorer.score_policy_shift(args.predictions, args.reassigned_predictions, args.dataset, **params)
    else:
        rows = selected_rows(args)
        metrics = scorer.score(args.predictions, args.dataset, split=args.split, arm=args.arm, **params)
    snapshot = {
        "format": "quasileak-score-v1",
        "name": args.name or args.predictions.stem,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation": evaluation_metadata(args, rows, params),
        "metrics": metrics,
    }
    if args.reassigned_predictions:
        snapshot["evaluation"]["arm"] = "paired"
    if args.output:
        output_json(snapshot, args.output)
    if args.json:
        output_json(snapshot)
    else:
        print("QuasiLeak-Bench | Evaluation\n")
        print(format_report([snapshot]))
        print("Scores are percentages; N_docs and N_pred are counts.")
        if args.output:
            print(f"Saved scores and evaluation metadata → {args.output}")


def check_predictions(args):
    from jsonschema import Draft202012Validator
    scorer = released_module("scorer")
    gold = selected_rows(args)
    predictions = scorer.read_predictions(args.predictions, gold, allow_extra=bool(args.split))
    all_ids = {row["sample_id"] for row in scorer.read_jsonl(args.dataset)}
    unknown = set(predictions) - all_ids
    if unknown:
        raise ValueError(f"Predictions contain {len(unknown)} unknown document IDs")
    schema = json.loads((resource_root() / "scorer/prediction_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    invalid = []
    groups = 0
    for row in gold:
        pred = predictions[row["sample_id"]]
        errors = list(validator.iter_errors(pred))
        if errors:
            invalid.append(f"{row['sample_id']}: {errors[0].message}")
            continue
        for group in scorer.prediction_objects(pred):
            groups += 1
            for span in group["spans"]:
                if scorer.locate(span, row["document"]) is None:
                    invalid.append(f"{row['sample_id']}: span cannot be located in the document")
    if invalid:
        raise ValueError(f"{len(invalid)} prediction issue(s); " + "; ".join(invalid[:5]))
    print(f"PASS | {len(gold):,} documents, {groups:,} predicted groups; format, IDs, coverage, and spans checked.")
    if len(predictions) > len(gold):
        print(f"{len(predictions) - len(gold):,} valid dataset IDs outside the selected split were ignored.")


def load_snapshot(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a score JSON object")
    if data.get("format") == "quasileak-score-v1":
        if not isinstance(data.get("name"), str) or not isinstance(data.get("metrics"), dict):
            raise ValueError(f"{path}: invalid score snapshot")
        return data
    # Legacy score.py output can be displayed, but lacks comparison metadata.
    if "P-GF1" in data or {"original", "reassigned"} <= data.keys():
        return {"name": Path(path).stem, "metrics": data}
    raise ValueError(f"{path}: unrecognized score file")


def metric_rows(snapshots):
    rows = []
    for snapshot in snapshots:
        metrics = snapshot["metrics"]
        arms = ("original", "reassigned") if "original" in metrics else (None,)
        for arm in arms:
            scores = metrics[arm] if arm else metrics
            label = snapshot["name"] + (f" / {arm}" if arm else "")
            rows.append({"Run": label, **{key: scores.get(key) for key in METRICS}})
    return rows


def format_report(snapshots):
    rows = metric_rows(snapshots)
    return table(("Run", *METRICS), [[row[key] for key in ("Run", *METRICS)] for row in rows])


def write_report(args, snapshots, rows, headers):
    inputs = [*args.scores]
    if getattr(args, "baseline", None):
        inputs.append(args.baseline)
    if args.output and args.output.resolve() in {path.resolve() for path in inputs}:
        raise ValueError("Report output must differ from score inputs")
    if args.format == "json":
        output_json({"runs": snapshots, "rows": rows}, args.output)
    elif args.format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        output_text(buffer.getvalue(), args.output)
    else:
        output_text(table(headers, [[r.get(key) for key in headers] for r in rows]), args.output)


def report_scores(args):
    snapshots = [load_snapshot(path) for path in args.scores]
    rows = metric_rows(snapshots)
    write_report(args, snapshots, rows, ("Run", *METRICS))
    if args.format == "table" and not args.output:
        for snapshot in snapshots:
            metrics = snapshot["metrics"]
            if "original" in metrics:
                print(f"{snapshot['name']}: Suppress={metrics.get('Suppress')}%, Surface={metrics.get('Surface')}%")


def compare_scores(args):
    snapshots = [load_snapshot(path) for path in args.scores]
    baseline = load_snapshot(args.baseline) if args.baseline else snapshots[0]
    context = baseline.get("evaluation")
    if not context:
        raise ValueError("Comparison requires score snapshots from 'quasileak score', including evaluation metadata")
    for snapshot in snapshots:
        if snapshot.get("evaluation") != context:
            raise ValueError("Cannot compare runs: dataset, sample IDs, split, policy arm, scorer, or metric parameters differ")
    baseline_rows = metric_rows([baseline])
    rows = metric_rows(snapshots)
    for index, row in enumerate(rows):
        value = baseline_rows[index % len(baseline_rows)]["P-GF1"]
        row["Δ P-GF1"] = None if value is None or row["P-GF1"] is None else row["P-GF1"] - value
    write_report(args, snapshots, rows, ("Run", "P-GF1", "Δ P-GF1", *METRICS[1:]))
    if args.format == "table" and not args.output:
        print(f"Baseline: {baseline['name']}. Deltas are percentage points; no significance test is implied.")


def diagnose_install(args):
    root = resource_root()
    released_module("scorer")
    released_module("renderer").load_template(0)
    released_module("renderer").load_template(3)
    print(f"QuasiLeak-Bench {version('quasileak-bench')} | Python {sys.version.split()[0]}")
    print(f"Evaluator resources: {root}")
    print(f"Scorer SHA-256: {digest(root / 'scorer/score.py')}")
    json.loads((root / "data/splits/split_manifest.json").read_text(encoding="utf-8"))
    json.loads((root / "scorer/prediction_schema.json").read_text(encoding="utf-8"))
    print("PASS | scorer, split manifest, prediction schema, and 0/3-shot prompts available.")
