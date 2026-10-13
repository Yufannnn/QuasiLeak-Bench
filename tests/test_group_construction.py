import copy
from collections import Counter

import pytest

from quasileak import confidence
from quasileak.config import ATTRIBUTES, ConstructionConfig
from quasileak.groups.curation import curate
from quasileak.groups.keys import reuse_key
from quasileak.groups.search import Group, SearchResult, search_attribute
from quasileak.pipeline.group_construction import construct_groups
from quasileak.schemas import validate_grouped

ATTR = "occupation"
BAR = confidence.reveal_bar(ATTR)


def record(pairs, pool=("a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8")):
    """A probed record with weak pool ``pool`` (strongest first) and the given pair scores."""
    candidates = [dict(cue=c, drops_at_singleton=False, alone_confidence=0.30 - i * 0.01) for i, c in enumerate(pool)]
    pair_rows = [
        dict(cue_a=a, cue_b=b, joint_confidence=s, joint_rank=1 if s >= BAR else 2) for (a, b), s in pairs.items()
    ]
    return {"diagnostics": [{"attribute": ATTR, "candidates": candidates, "pairs": pair_rows}]}


def test_groups_validate(grouped, config):
    validate_grouped(grouped, config)
    groups = [g for row in grouped for g in row["groups"]]
    assert groups and all(g["conf"] >= confidence.reveal_bar(g["attr"]) for g in groups)
    for row in grouped:
        for g in row["groups"]:
            audited = sorted(a["attribute"] for a in row["secondary_audits"] if a["group_attribute"] == g["attr"])
            assert audited == sorted(a for a in ATTRIBUTES if a != g["attr"])


def test_extension_bases():
    rec = record({("a1", "a2"): 0.40, ("a3", "a4"): 0.30, ("a5", "a6"): 0.80, ("a7", "a8"): 0.02})
    probes = []

    def probe(attr, cues):
        probes.append(tuple(cues))
        return 0.9 if cues[-1] == "a7" else 0.2

    result = search_attribute(rec, ATTR, probe, ConstructionConfig(), used={})
    trio_bases = [p[:2] for p in probes if len(p) == 3]
    assert list(dict.fromkeys(trio_bases)) == [("a1", "a2"), ("a3", "a4"), ("a5", "a6")]
    assert max(Counter(trio_bases).values()) <= 5
    assert not any(p[-1] == "a8" for p in probes if len(p) == 3)  # the sixth option is never tried
    trios = {g.cues: g.src for g in result.verified if g.k == 3}
    assert trios == {("a1", "a2", "a7"): "promising", ("a3", "a4", "a7"): "promising", ("a5", "a6", "a7"): "verified"}


def test_extension_stops_when_verified():
    probes = []

    def probe(attr, cues):
        probes.append(tuple(cues))
        return 0.9 if cues[-1] == "a4" else 0.2

    search_attribute(record({("a1", "a2"): 0.40}), ATTR, probe, ConstructionConfig(), used={})
    assert [p[-1] for p in probes if len(p) == 3] == ["a3", "a4"]


def test_quads_extend_trios():
    def probe(attr, cues):
        return 0.9 if len(cues) == 4 or cues[-1] == "a3" else 0.2

    result = search_attribute(record({("a1", "a2"): 0.40}), ATTR, probe, ConstructionConfig(), used={})
    quads = [g for g in result.verified if g.k == 4]
    assert quads and all(len(g.base) == 3 for g in quads)


def test_capped_cue_not_extended():
    probes = []
    search_attribute(
        record({("a1", "a2"): 0.40}),
        ATTR,
        lambda a, c: probes.append(c) or 0.2,
        ConstructionConfig(),
        used={reuse_key("a3"): 5},
    )
    assert probes and not any("a3" in c for c in probes)


def slots(n, conf=0.8):
    results = {}
    for i in range(n):
        cues = tuple(f"slot{i} cue{j}" for j in range(4))
        results[f"doc{i:03d}", ATTR] = SearchResult(
            verified=[
                Group(ATTR, cues[:2], conf),
                Group(ATTR, cues[:3], conf, cues[:2], conf, "verified"),
                Group(ATTR, cues, conf + (0.1 if i == 7 else 0), cues[:3], conf, "verified"),
            ]
        )
    return results


def test_curation_mix():
    selected = curate(slots(100), ConstructionConfig())
    assert Counter(g.k for g in selected.values()) == {2: 65, 3: 25, 4: 10}
    assert selected["doc007", ATTR].k == 4


def test_curation_reuse_cap():
    shared = Group(ATTR, ("tax folder", "linen invoice"), 0.9)
    selected = curate({(f"d{i}", ATTR): SearchResult(verified=[shared]) for i in range(7)}, ConstructionConfig())
    assert len(selected) == 5


def test_curation_nested_phrases():
    results = {
        ("d0", "income"): SearchResult(verified=[Group("income", ("tax folder copy", "rent split"), 0.9)]),
        ("d0", ATTR): SearchResult(verified=[Group(ATTR, ("tax folder", "linen invoice"), 0.9)]),
    }
    assert len(curate(results, ConstructionConfig())) == 1


def test_secondary_attribute(mined, model, config):
    original = model._joint

    def with_secondary(user):
        reply = original(user)
        if "- attribute: income" in user:
            reply["1"].update(reveals=True, confidence=0.95)
        return reply

    model._joint = with_secondary
    groups = [g for r in construct_groups(mined, model, model, config) for g in r["groups"]]
    assert groups and all(g["secondary_attributes"] == ["income"] for g in groups)


def test_distractors_see_final_cues(mined, model, config):
    prompts = []
    generate = model.generate

    def capture(**kwargs):
        prompts.append(kwargs)
        return generate(**kwargs)

    model.generate = capture
    rows = construct_groups(mined, model, model, config)
    distractor_prompts = [p["user"] for p in prompts if "You craft red-herring" in p["system"]]
    final = [c for r in rows for g in r["groups"] for c in g["cues"]]
    assert final and all(any(c in p for p in distractor_prompts) for c in final)
    first_distractor = next(i for i, p in enumerate(prompts) if "You craft red-herring" in p["system"])
    assert not any("RATIONAL attacker" in p["system"] for p in prompts[first_distractor:])


def test_previous_batch_reuse(mined, grouped, model, config):
    previous = []
    for i in range(5):
        row = copy.deepcopy(grouped[0])
        row["profile_id"] = f"earlier{i}"
        row["sample_id"] = f"earlier{i}--" + row["context_id"]
        previous.append(row)
    rows = construct_groups(mined, model, model, config, previous)
    spent = {c for g in grouped[0]["groups"] for c in g["cues"]}
    assert spent and not spent & {c for r in rows for g in r["groups"] for c in g["cues"]}


def test_overlapping_batches(mined, grouped, model, config):
    with pytest.raises(ValueError, match="overlap"):
        construct_groups(mined, model, model, config, grouped)


def test_error_names_record(mined, model, config):
    model._joint = lambda user: {"unexpected": {}}
    with pytest.raises(ValueError, match=r"--.* \(group search\)"):
        construct_groups(mined, model, model, config)
