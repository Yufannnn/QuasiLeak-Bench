# Benchmark website and Visitor Atlas

The self-contained site is in `website/`. GitHub Pages publishes that directory at
https://yufannnn.github.io/QuasiLeak-Bench/.

## Launch after the archive is public

The repository remains private during preparation. The Benchmark website workflow
checks the files but skips the Pages upload and deployment while it is private.
Making the repository public triggers the `public` event and publishes the site.
Later website pushes, manual workflow runs, and the six-hour schedule update it.
Pages is configured to use GitHub Actions; no domain or hosting purchase is needed.
If necessary, run Actions → Benchmark website → Run workflow after changing visibility.

## Activate free visitor analytics

1. Manually create a free account at https://www.goatcounter.com/signup. Use a
   dedicated account/site for this benchmark; suggested account name: `quasileak-bench`
   if available. Set the site domain to `yufannnn.github.io`. Keep Sessions and country
   collection enabled. Do not enable raw pageview storage just for this integration.
2. In GoatCounter, create an API token with the **read statistics** permission only.
   Keep the analytics dashboard private; the public site does not require dashboard access.
3. In this GitHub repository, Settings → Secrets and variables → Actions:
   - Variable `QLB_GOATCOUNTER_SITE`: the account name only, without a URL.
   - Secret `GOATCOUNTER_API_TOKEN`: the read-only API token.
   - Optional variable `QLB_ANALYTICS_START`: first collection date (`YYYY-MM-DD`);
     defaults to `2026-10-15`.
4. Run Actions → Benchmark website → Run workflow. After public launch, tracking
   starts immediately; Atlas snapshots refresh on deployment and every six hours.

GoatCounter offers free hosting for reasonable public usage:
https://www.goatcounter.com/help/terms.
Initial signup must be performed manually under those terms. No paid service,
credit card, external server, or browser-visible API token is required.

## What is counted

Tracking runs only on the production hostname and `/QuasiLeak-Bench/` path. Local
previews do not count. Query strings, hash state, and model/prediction contents are
not sent. The script respects Do Not Track and Global Privacy Control.

The Atlas labels are **Page visits**, **Homepage visits**, and **Countries reached**.
GoatCounter session-deduplicates visits per page; these are neither every browser
reload nor a global count of distinct people. Homepage visits include the project
root and `index.html`. All API queries are limited to the seven public page paths.
Unknown countries are excluded from the country total. Country fills and hover
titles use the same aggregate snapshot; the low-resolution map omits some small
countries even when they are included in the country count.

The API token is read only inside GitHub Actions. The uploaded artifact contains
only a public account name and aggregate JSON. Until configured, the Atlas keeps
its unavailable state and displays no fabricated counts. A provider/API failure
fails the refresh rather than replacing a published snapshot with fake numbers.

## Updating the site

The authoring checkout builds it with `python tools/quasileak_site/build_site.py`.
Copy only that generated site into this repository's `website/`, excluding its
local `.gitignore`. Deployment helpers live in `website-tools/`; the workflow is
`.github/workflows/pages.yml`. Do not overwrite the dataset, scorer, or research code
when updating the website.

Reference API: https://www.goatcounter.com/help/api.
Session semantics: https://www.goatcounter.com/help/sessions.
