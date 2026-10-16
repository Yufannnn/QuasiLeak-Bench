"""Sequential, resumable detector evaluation through a chat-completions endpoint."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .config import load_env
from .llm.client import RETRYABLE, message_text
from .llm.parsing import parse_object


def add_run_command(commands):
    from .evaluation_cli import dataset_arguments
    parser = commands.add_parser("run", help="Run a detector on the official prompts (makes model API calls)")
    dataset_arguments(parser)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", help="Chat API base URL, including /v1 if required; or LLM_BASE_URL")
    parser.add_argument("--api-key-env", default="LLM_API_KEY", help="Environment variable holding the API key")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--shots", type=int, choices=(0, 3), default=3)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, required=True, help="Predictions JSONL; raw replies and run metadata are saved beside it")
    parser.add_argument("--resume", action="store_true", help="Continue this exact run, skipping completed document IDs")
    parser.set_defaults(handler=run_detector)


def request_chat(base_url, api_key, payload, timeout):
    request = Request(base_url + "/chat/completions", data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.load(response)
            return message_text(result)
        except HTTPError as exc:
            if exc.code not in RETRYABLE or attempt == 2:
                raise RuntimeError(f"Model request failed with HTTP {exc.code}; completed rows are saved") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("Model request failed after three attempts; completed rows are saved") from None
        time.sleep(attempt + 1)
    raise RuntimeError("Model request failed")


def completed_ids(path, expected, checkpoint):
    from .evaluation_cli import released_module
    # Recover complete rows flushed just before a metadata checkpoint was saved.
    prefix = hashlib.sha256()
    lines = 0
    with path.open("rb") as handle:
        for line in handle:
            if lines >= checkpoint["completed"]:
                break
            prefix.update(line)
            lines += 1
    if lines != checkpoint["completed"] or prefix.hexdigest() != checkpoint["predictions_sha256"]:
        raise ValueError("Checkpointed predictions changed; refusing to resume")
    completed = set()
    for row in released_module("scorer").read_jsonl(path):
        sample_id = row["sample_id"]
        if sample_id in completed or sample_id not in expected:
            raise ValueError("Resume file contains duplicate or unknown document IDs")
        released_module("scorer").prediction_objects(row)
        completed.add(sample_id)
    return completed


def run_detector(args):
    from .evaluation_cli import digest, json_digest, released_module, selected_rows
    load_env(args.env_file)
    base_url = (args.base_url or os.environ.get("LLM_BASE_URL", "")).rstrip("/")
    url = urlsplit(base_url)
    if url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise ValueError("Set --base-url or LLM_BASE_URL to an http(s) base URL without credentials or query parameters")
    if not math.isfinite(args.temperature) or args.temperature < 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("Temperature must be finite and nonnegative; timeout must be finite and positive")
    if args.max_tokens <= 0:
        raise ValueError("--max-tokens must be positive")
    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        raise ValueError(f"Set {args.api_key_env} before running a model; no requests were sent")
    rows = selected_rows(args)
    render = released_module("renderer").render
    requests = [{"sample_id": row["sample_id"], "messages": render(row, args.shots)} for row in rows]
    # The identity binds resume to the exact prompts, policies, dataset, and model settings.
    identity = {
        "model": args.model, "base_url": base_url, "shots": args.shots,
        "temperature": args.temperature, "max_tokens": args.max_tokens,
        "dataset_sha256": digest(args.dataset), "split": args.split, "arm": args.arm,
        "requests_sha256": json_digest(requests),
    }
    metadata_path = Path(str(args.output) + ".run.json")
    raw_path = Path(str(args.output) + ".responses.jsonl")
    inputs = {args.dataset.resolve()}
    if args.env_file:
        inputs.add(args.env_file.resolve())
    if any(path.resolve() in inputs for path in (args.output, metadata_path, raw_path)):
        raise ValueError("Run output files must differ from all inputs")
    paths = (args.output, metadata_path, raw_path)
    if args.resume:
        if not args.output.exists() or not metadata_path.exists():
            raise ValueError("--resume requires existing predictions and their .run.json metadata")
        previous = json.loads(metadata_path.read_text(encoding="utf-8"))
        if previous.get("settings") != identity:
            raise ValueError("Resume settings differ: use the same dataset, prompts, split, policy arm, model, and parameters")
        completed = completed_ids(args.output, {row["sample_id"] for row in rows}, previous)
    else:
        if any(path.exists() for path in paths):
            raise ValueError("Run output already exists; use --resume or choose a new output path")
        completed = set()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.touch(exist_ok=False)
        raw_path.touch(exist_ok=False)
    prediction_hash = hashlib.sha256()
    with args.output.open("rb") as existing:
        for block in iter(lambda: existing.read(1024 * 1024), b""):
            prediction_hash.update(block)
    def save_metadata():
        snapshot = {"format": "quasileak-run-v1", "settings": identity,
                    "completed": len(completed), "predictions_sha256": prediction_hash.hexdigest()}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=metadata_path.parent,
                                         prefix=".qlb-run-", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(snapshot, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temporary, metadata_path)
        finally:
            temporary.unlink(missing_ok=True)
    save_metadata()
    print(f"QuasiLeak-Bench | {args.model} | {len(rows):,} documents | {args.shots}-shot", flush=True)
    print(f"{len(completed):,} completed; {len(rows) - len(completed):,} remaining. Calls go to {url.netloc}.", flush=True)
    with args.output.open("a", encoding="utf-8", newline="\n") as predictions, raw_path.open("a", encoding="utf-8", newline="\n") as raw:
        for request in requests:
            sample_id = request["sample_id"]
            if sample_id in completed:
                continue
            payload = {"model": args.model, "messages": request["messages"], "temperature": args.temperature,
                       "max_tokens": args.max_tokens}
            text = request_chat(base_url, api_key, payload, args.timeout)
            raw.write(json.dumps({"sample_id": sample_id, "response": text}, ensure_ascii=False) + "\n")
            raw.flush()
            try:
                reply = parse_object(text)
                row = {"sample_id": sample_id, "evidence": reply.get("evidence", reply.get("predictions"))}
                released_module("scorer").prediction_objects(row)
            except (ValueError, KeyError, TypeError):
                raise ValueError(f"{sample_id}: response is not a prediction JSON object. Raw reply saved at {raw_path}; use --resume to retry") from None
            # Keep invalid groups/spans for the official scorer's penalties rather than filtering them.
            line = json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
            predictions.write(line)
            predictions.flush()
            os.fsync(predictions.fileno())
            prediction_hash.update(line.encode("utf-8"))
            completed.add(sample_id)
            save_metadata()
            print(f"[{len(completed):,}/{len(rows):,}] {sample_id}", file=sys.stderr, flush=True)
    print(f"Saved {len(completed):,} predictions → {args.output}")
