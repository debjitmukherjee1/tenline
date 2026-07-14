# Tenline — Ten Years of Filings, One Page

*Ten years, ten lines, no narrative — just the filings.*

Pick any S&P 500 company and see ten fiscal years of fundamentals — revenue,
margins, EPS, free cash flow, ROE/ROIC, diluted share count, and net
debt/equity — read straight from that company's own SEC EDGAR filings.
Refreshed weekly. Runs entirely on free tiers.

> The fundamentals pillar of a small suite of zero-cost finance tools:
> **Meridian** (valuation + sentiment), **MarketPulse** (markets + risk),
> **Ledger** (track record), **Abacus** (calculators), and Tenline
> (a decade of primary-source fundamentals).

**→ Full plan & methodology:** [`docs/EXECUTABLE_PLAN.md`](docs/EXECUTABLE_PLAN.md)

## Cost: $0/day, zero Claude tokens
The weekly refresh runs on **GitHub's servers** (Actions cron) and pulls from
**SEC EDGAR's `companyfacts` XBRL API** (free, keyless — just a descriptive
User-Agent and a polite ≤10 requests/sec). There is **no LLM in this tool at
all** — it's XBRL facts, tag-mapping logic, and arithmetic — so nothing calls
any AI service. Claude was only used to build it.

## How it stays free
- **Hosting:** GitHub Pages (static)
- **Weekly job:** GitHub Actions (unlimited minutes for public repos)
- **Data:** SEC EDGAR `companyfacts` XBRL — no API key, no secrets
- **Universe:** full S&P 500 (503 companies), seeded with CIK directly so
  the pipeline never depends on ticker-text matching against SEC's own
  (occasionally wrong) bulk reference file

## Run it locally (no keys needed)
```bash
# 1. generate sample data (mock mode, offline)
cd pipeline
pip install -r requirements.txt
python run_all.py
#    for real data instead:  TENLINE_LIVE=1 python run_all.py
#    or a quick subset:      TENLINE_LIVE=1 python run_all.py --tickers AAPL,MSFT

# 2. serve the site
cd ../site
python -m http.server 8000
# open http://localhost:8000
```

## Go live
1. Push this repo to GitHub (public). **No secrets to configure.**
2. Settings → Pages → deploy from `main` → `/site`.
3. `weekly-update.yml` refreshes all 503 companies every Monday (runs with `TENLINE_LIVE=1`).

## Structure
```
docs/    → the executable plan (architecture, tag-mapping methodology, bugs found/fixed)
site/    → static website (GitHub Pages root); data/ holds per-company JSON
pipeline/→ the weekly Python job (SEC EDGAR fetch + tag-mapping + derivation)
.github/ → the free cron automation
```

## Honesty over completeness
When a filing doesn't disclose a concept under a tag this pipeline can
confidently resolve, that value is `null` and renders as a visible gap with a
footnote explaining why — never a guess or an interpolation. Coverage across
the full universe is 86.4% average / 90% median; the gaps concentrate in
business types (banks, integrated energy, card networks) that structurally
don't report certain line items, not in tag-mapping failures. Full breakdown
in the executable plan.

⚠️ Personal / educational project, not investment advice, not a
SEBI-registered research or advisory service. Data is as-filed with the SEC
via EDGAR's XBRL data — always verify against the source filing (linked on
every company page) before relying on a number.
