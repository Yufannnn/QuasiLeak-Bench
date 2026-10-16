"""Daily totals are aggregate-only, bounded, and quietly empty on failure."""
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

spec = importlib.util.spec_from_file_location("qlb_prepare_atlas", Path(__file__).resolve().parents[1] / "website-tools/prepare_atlas.py")
atlas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)
NOW = datetime(2026, 10, 16, 6, 23, tzinfo=timezone.utc)


def test_unconfigured_activity_is_empty(monkeypatch):
    monkeypatch.delenv("QLB_GOATCOUNTER_SITE", raising=False)
    monkeypatch.delenv("GOATCOUNTER_API_TOKEN", raising=False)
    monkeypatch.setattr(atlas, "urlopen", lambda *a, **k: pytest.fail("No unauthenticated provider request"))
    assert atlas.activity_snapshot("/QuasiLeak-Bench/", NOW) == {"daily": [], "generated_at": NOW.isoformat()}


def test_goatcounter_total_daily_buckets(monkeypatch):
    monkeypatch.setenv("QLB_GOATCOUNTER_SITE", "quasileak-bench")
    monkeypatch.setenv("GOATCOUNTER_API_TOKEN", "read-only-test-token")
    def response(request, timeout):
        url = urlsplit(request.full_url)
        assert url.path == "/api/v0/stats/total"
        query = parse_qs(url.query)
        assert query["end"] == ["2026-10-16T06:00:00+00:00"]
        assert query["path_by_name"] == ["true"]
        assert "/QuasiLeak-Bench/" in query["include_paths"][0]
        return io.StringIO(json.dumps({"stats": [{"day": "2026-10-16", "daily": 12, "hourly": [1]*12}],
                                     "paths": ["never publish"], "referrers": ["never publish"]}))
    monkeypatch.setattr(atlas, "urlopen", response)
    result = atlas.activity_snapshot("/QuasiLeak-Bench/", NOW)
    assert len(result["daily"]) == 84
    assert result["daily"][-1] == {"day": "2026-10-16", "views": 12}
    assert all(set(row) == {"day", "views"} for row in result["daily"])
    assert set(result) == {"daily", "generated_at"}


@pytest.mark.parametrize("payload", [{"error": "private upstream error"}, {"stats": [{"day": "bad", "daily": 1}]},
    {"stats": [{"day": "2026-10-16", "daily": -1}]},
    {"stats": [{"day": "2026-10-16", "daily": 1}]*2}, {"stats": None}])
def test_failed_or_invalid_daily_fetch_is_empty(monkeypatch, payload):
    monkeypatch.setenv("QLB_GOATCOUNTER_SITE", "quasileak-bench")
    monkeypatch.setenv("GOATCOUNTER_API_TOKEN", "read-only-test-token")
    monkeypatch.setattr(atlas, "urlopen", lambda *a, **k: io.StringIO(json.dumps(payload)))
    assert atlas.activity_snapshot("/QuasiLeak-Bench/", NOW)["daily"] == []


def test_cloudflare_atlas_is_preserved_when_activity_is_unconfigured(monkeypatch, tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "analytics-config.json").write_text(json.dumps({"provider":"cloudflare",
        "endpoint":"https://qlb-visitor-atlas.encformer-visitors.workers.dev", "productionPath":"/QuasiLeak-Bench/"}))
    monkeypatch.setattr(atlas.sys, "argv", ["prepare_atlas", "--directory", str(tmp_path)])
    monkeypatch.setattr(atlas, "refresh_release_counters", lambda *args: None)
    monkeypatch.delenv("QLB_GOATCOUNTER_SITE", raising=False)
    monkeypatch.delenv("GOATCOUNTER_API_TOKEN", raising=False)
    monkeypatch.setattr(atlas, "public_json", lambda url: {"status":"ok", "provider":"cloudflare", "pageViews":5,
        "countries":1, "countryVisits":[{"code":"SG", "visits":5}]})
    atlas.main()
    result = json.loads((assets / "visitor-stats.json").read_text())
    assert result["pageViews"] == 5
    assert result["countryVisits"] == [{"code":"SG", "visits":5}]
    assert result["daily"] == []
    assert "generated_at" in result


def test_cloudflare_daily_counts_are_not_replaced_by_goatcounter(monkeypatch, tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "analytics-config.json").write_text(json.dumps({"provider":"cloudflare",
        "endpoint":"https://qlb-visitor-atlas.encformer-visitors.workers.dev", "productionPath":"/QuasiLeak-Bench/"}))
    monkeypatch.setattr(atlas.sys, "argv", ["prepare_atlas", "--directory", str(tmp_path)])
    monkeypatch.setattr(atlas, "refresh_release_counters", lambda *args: None)
    monkeypatch.setattr(atlas, "activity_snapshot", lambda *args: pytest.fail("Cloudflare must not depend on GoatCounter"))
    monkeypatch.setattr(atlas, "public_json", lambda url: {"status":"ok", "provider":"cloudflare", "pageViews":6,
        "daily":[{"day":"2026-10-16", "views":6}], "generatedAt":"2026-10-16T06:23:00Z"})
    atlas.main()
    result = json.loads((assets / "visitor-stats.json").read_text())
    assert result["daily"] == [{"day":"2026-10-16", "views":6}]
    assert result["generated_at"] == "2026-10-16T06:23:00Z"
