# Visitor Atlas on Cloudflare

The QLB website stays on GitHub Pages. Its public Atlas uses a Cloudflare Worker
and D1 database at `https://qlb-visitor-atlas.encformer-visitors.workers.dev`.
Collection starts on October 16, 2026; earlier traffic cannot be reconstructed.

The database contains only `(UTC day, public page path, country code, view count)`.
No IP addresses, user-agent strings, cookies, session IDs, or fingerprints are
stored. Do Not Track, Global Privacy Control, and common bot user agents are
excluded. Worker request logging is disabled. Country comes from Cloudflare's
network location, which can differ from a reader's location when using a VPN.

These are approximate **page views**, not unique people. The homepage counter
includes the project root and `index.html`. Unknown countries contribute views
but are excluded from the country count. The public POST endpoint checks origin
and a fixed list of public paths; origin checking is not authentication and
public counters can be manipulated.

## Free-tier deployment

Workers Free includes 100,000 requests/day. D1 Free includes 5 million rows read
and 100,000 rows written/day with 5 GB storage. Keep the account on Free; no paid
plan is required. Free quotas are shared with other projects on the account.

References: [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/).

```bash
node --test website-tools/visitor-worker/*.test.mjs
npx wrangler d1 execute qlb-visitor-atlas --remote \
  --file website-tools/visitor-worker/schema.sql --config website-tools/visitor-worker/wrangler.toml
npx wrangler deploy --config website-tools/visitor-worker/wrangler.toml
```

The existing database is configured in `wrangler.toml`; do not create or overwrite
an unrelated database. Wrangler uses the owner's local Cloudflare login. No API
secret is committed or needed by the browser.

`POST /visit` receives only a public page path. `GET /stats` returns aggregate
counts. The page refreshes the Atlas every 30 seconds while visible, on return to
the tab, and after a recorded view. Polling does not record extra visits.

`GET /release` fetches public GitHub stars/forks and Hugging Face downloads/likes.
Cloudflare caches the result for 120 seconds per edge location to reduce upstream
API traffic; no tokens are needed. The page checks every minute while visible and
on return to the tab. The displayed timestamp is the upstream fetch time, not the
time the browser read the cache. Provider-side reporting delays still apply,
particularly for Hugging Face downloads. Failures are not cached; the UI labels
fallback data as a snapshot or the last live result as delayed, never as fresh.

The six-hour Pages workflow exports static fallback snapshots using
`prepare_atlas.py`; it is no longer the primary source for either live panel.
