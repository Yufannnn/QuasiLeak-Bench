"""Prepare public GoatCounter configuration and an aggregate-only Atlas snapshot."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Analytics returned an invalid count")
    return value


def aggregate(total, home, locations):
    countries = {}
    for row in locations:
        code = str(row.get("id", "")).upper()
        visits = count(row["count"])
        if not re.fullmatch(r"[A-Z]{2}", code) or code in {"ZZ", "XX"} or not visits:
            continue
        item = countries.setdefault(code, {"code": code, "name": str(row.get("name", code)), "visits": 0})
        item["visits"] += visits
    return {"status": "ok", "provider": "goatcounter",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "pageViews": max(0, count(total["total"]) - count(total.get("total_events", 0))),
            "visitors": max(0, count(home["total"]) - count(home.get("total_events", 0))),
            "countries": len(countries), "countryVisits": sorted(countries.values(), key=lambda row: -row["visits"])}


def collect(site, token, start, prefix):
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
    paths = [prefix, prefix+"index.html", prefix+"explore.html", prefix+"evaluation.html",
             prefix+"submit.html", prefix+"run.html", prefix+"compare.html"]
    common = {"start": start+"T00:00:00Z", "end": end, "path_by_name": "true",
              "include_paths": ",".join(paths)}
    def get(endpoint, **query):
        url = "https://"+site+".goatcounter.com/api/v0/stats/"+endpoint+"?"+urlencode({**common, **query})
        request = Request(url, headers={"Authorization": "Bearer "+token, "Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
        if "error" in result or "errors" in result:
            raise ValueError("Analytics API rejected the request")
        return result
    total = get("total")
    home = get("total", include_paths=prefix+","+prefix+"index.html")
    locations = []
    offset = 0
    while True:
        result = get("locations", limit=100, offset=offset)
        rows = result["stats"]
        locations.extend(rows)
        if not result.get("more"):
            break
        if not rows:
            raise ValueError("Analytics pagination returned no rows")
        offset += len(rows)
        if offset > 500:
            raise ValueError("Unexpected number of country rows")
    return aggregate(total, home, locations)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    assets = args.directory / "assets"
    config_path = assets / "analytics-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    site = os.environ.get("QLB_GOATCOUNTER_SITE", "").strip().lower()
    if site and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", site):
        raise ValueError("QLB_GOATCOUNTER_SITE must be the account name, without a URL")
    config["site"] = site
    config_path.write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
    token = os.environ.get("GOATCOUNTER_API_TOKEN", "")
    if not site or not token:
        print("Atlas account or API token is not configured; no fabricated counts will be published.")
        return
    start = os.environ.get("QLB_ANALYTICS_START") or "2026-10-15"
    datetime.strptime(start, "%Y-%m-%d")
    snapshot = collect(site, token, start, config["productionPath"])
    (assets / "visitor-stats.json").write_text(json.dumps(snapshot, indent=2)+"\n", encoding="utf-8")
    print("Atlas aggregate snapshot prepared.")


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, ValueError, KeyError) as error:
        # Never print HTTP response bodies, tokens or request headers.
        print("Atlas refresh failed: "+type(error).__name__+". Check the account name and read-only token.", file=sys.stderr)
        sys.exit(1)
