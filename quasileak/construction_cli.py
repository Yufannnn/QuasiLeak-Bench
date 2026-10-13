"""Command-line entry points for the inputs and the three construction stages."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .config import judge_panels, load_config, load_env, model_roles
from .io import read_jsonl, write_jsonl
from .llm.client import LLMClient
from .pipeline.cue_mining import assigned_pairs, mine_cues
from .pipeline.document_writing import write_documents
from .pipeline.group_construction import construct_groups
from .pipeline.inputs import assign, census, score_pairs
from .schemas import validate_documents, validate_grouped, validate_inputs, validate_mined


def add_input_commands(commands):
    for command, help_text in (
        ("census", "screen profiles with the census judges"),
        ("assign", "score profile-context compatibility and assign contexts to profiles"),
    ):
        parser = commands.add_parser(command, help=help_text)
        parser.add_argument("--profiles", required=True, type=Path)
        if command == "assign":
            parser.add_argument("--contexts", required=True, type=Path)
            parser.add_argument("--config", type=Path)
        parser.add_argument("--models", required=True, type=Path)
        parser.add_argument("--env-file", type=Path)
        parser.add_argument("--output", required=True, type=Path)


def run_inputs(args):
    load_env(args.env_file)
    panels = judge_panels(args.models)
    key, base_url = os.environ.get("LLM_API_KEY", ""), os.environ.get("LLM_BASE_URL")
    profiles = read_jsonl(args.profiles)
    if args.command == "census":
        judges = [LLMClient(key, m, base_url) for m in panels["census_judges"]]
        write_jsonl(args.output, census(profiles, judges))
        return 0
    config = load_config(args.config)
    contexts = read_jsonl(args.contexts)
    judges = [LLMClient(key, m, base_url) for m in panels["compatibility_judges"]]
    scores = score_pairs(profiles, contexts, judges)
    rows = assign(scores, [p["profile_id"] for p in profiles], [c["context_id"] for c in contexts],
                  config.contexts_per_profile, config.context_slack)
    for row in rows:
        row["score"] = round(scores[row["profile_id"], row["context_id"]], 2)
    write_jsonl(args.output, rows)
    return 0


def add_commands(commands):
    add_input_commands(commands)
    for command, help_text in (
        ("construct", "run all three construction stages"),
        ("mine-cues", "generate candidate cue pools"),
        ("build-groups", "probe candidates and construct evidence groups"),
        ("write-documents", "write documents from accepted plans"),
        ("validate", "validate construction JSONL without API calls"),
    ):
        parser = commands.add_parser(command, help=help_text)
        parser.add_argument("--config", type=Path)
        if command in ("construct", "mine-cues"):
            parser.add_argument("--profiles", required=True, type=Path)
            parser.add_argument("--contexts", required=True, type=Path)
            parser.add_argument(
                "--assignments",
                type=Path,
                help="JSONL of {profile_id, context_id} pairs to build; default is every combination",
            )
        else:
            parser.add_argument("--input", required=True, type=Path)
        if command != "validate":
            parser.add_argument("--output", required=True, type=Path)
            parser.add_argument("--models", type=Path)
            parser.add_argument("--env-file", type=Path)
            parser.add_argument("--overwrite", action="store_true")
        if command in ("construct", "build-groups", "validate"):
            parser.add_argument(
                "--previous",
                type=Path,
                action="append",
                default=[],
                help="group_construction JSONL from earlier batches, for corpus reuse limits",
            )
        if command == "validate":
            parser.add_argument("--plans", type=Path, help="group_construction JSONL for exact writing-plan comparison")


def validate_records(rows, config, plans=None, previous=()):
    if not rows:
        raise ValueError("Input is empty")
    stage = rows[0].get("stage")
    if previous and not (stage == "group_construction" or (stage == "document_writing" and plans is not None)):
        raise ValueError("--previous applies to group_construction input, or to documents checked with --plans")
    if stage == "cue_mining":
        validate_mined(rows)
    elif stage == "group_construction":
        validate_grouped([*previous, *rows], config)
    elif stage == "document_writing":
        if plans is not None:
            validate_grouped([*previous, *plans], config)
        validate_documents(rows, plans)
    else:
        raise ValueError("Unknown construction stage")
    return {"stage": stage, "records": len(rows), "valid": True}


def run(args):
    if args.command in ("census", "assign"):
        return run_inputs(args)
    config = load_config(args.config)
    command = args.command
    if command == "validate":
        previous = [row for path in args.previous for row in read_jsonl(path)]
        plans = read_jsonl(args.plans) if args.plans else None
        result = validate_records(read_jsonl(args.input), config, plans, previous)
        print(json.dumps(result))
        return 0
    if command in ("construct", "mine-cues"):
        profiles, contexts = read_jsonl(args.profiles), read_jsonl(args.contexts)
        validate_inputs(profiles, contexts)
        assignments = read_jsonl(args.assignments) if args.assignments else None
        assigned_pairs(profiles, contexts, assignments)
    else:
        records = read_jsonl(args.input)
        if command == "build-groups":
            validate_mined(records)
        else:
            validate_grouped(records, config)
    previous = [row for path in getattr(args, "previous", []) for row in read_jsonl(path)]
    if previous:
        validate_grouped(previous, config)
    output_paths = (
        [args.output / name for name in ("cue_mining.jsonl", "group_construction.jsonl", "document_writing.jsonl")]
        if command == "construct"
        else [args.output]
    )
    if not args.overwrite and any(p.exists() for p in output_paths):
        raise ValueError("Output already exists; choose a new path or pass --overwrite")
    load_env(args.env_file)
    roles = model_roles(args.models)
    clients = {
        role: LLMClient(os.environ.get("LLM_API_KEY", ""), model, os.environ.get("LLM_BASE_URL"))
        for role, model in roles.items()
    }
    if command == "construct":
        records = mine_cues(profiles, contexts, clients["proposer"], config, assignments)
        write_jsonl(output_paths[0], records)
        print(f"cue_mining: {len(records)} records", flush=True)
        records = construct_groups(records, clients["proposer"], clients["verifier"], config, previous)
        write_jsonl(output_paths[1], records)
        print(f"group_construction: {len(records)} records", flush=True)
        records = write_documents(records, clients["writer"], config)
        write_jsonl(output_paths[2], records)
        print(f"document_writing: {len(records)} records", flush=True)
    elif command == "mine-cues":
        write_jsonl(args.output, mine_cues(profiles, contexts, clients["proposer"], config, assignments))
    elif command == "build-groups":
        write_jsonl(args.output, construct_groups(records, clients["proposer"], clients["verifier"], config, previous))
    else:
        write_jsonl(args.output, write_documents(records, clients["writer"], config))
    return 0
