# Tenline — Executable Plan

**Name:** Tenline *("Ten years, ten lines, no narrative — just the filings.")*
**Author:** Debjit Mukherjee
**Origin:** The fundamentals pillar of the suite — Meridian covers valuation
and sentiment, MarketPulse covers markets and risk, Ledger covers track
record, Abacus is the calculator toolkit, and Tenline is a decade of
primary-source fundamentals, straight from SEC EDGAR.
**Status:** Live — full S&P 500 universe (503 companies)

---

## 0. Cost & tokens (read first)

- **$0/day to run.** Hosting is GitHub Pages; the weekly refresh runs on
  GitHub Actions (unlimited minutes for public repos); data comes from SEC
  EDGAR's free, keyless `companyfacts` XBRL API.
- **Zero Claude/Anthropic tokens in operation.** There is no LLM anywhere in
  this tool — it's XBRL facts, tag-mapping logic, and arithmetic. Nothing
  calls any AI service on a schedule.
- **Weekly, not daily.** Fundamentals only change when a company files a new
  10-K or 10-Q (quarterly at most) — a daily cron would just burn CI minutes
  re-deriving numbers that haven't changed.

---

## 1. What it is

Pick any S&P 500 company and see ten fiscal years of fundamentals as clean
charts, read directly from that company's own SEC filings:

- Revenue, with a 10-year CAGR chip
- Gross / operating / net margin
- Diluted EPS
- Free cash flow (CFO − capex) and FCF margin
- ROE and ROIC
- Diluted share count (buybacks/dilution visible)
- Net debt / equity

A **"Decade at a glance"** header on every company page: 10-yr revenue CAGR,
median net margin, total share-count change (net buybacks vs. dilution), and
FCF conversion (median FCF / net income).

**Never fabricated or interpolated.** When a filing doesn't disclose a
concept under a tag this pipeline can confidently resolve, that cell is
`null` and renders as a visible gap with a footnote explaining why — not a
guess.

---

## 2. Why it stays free (the numbers)

| Component | Provider | Free limit | Our use |
|---|---|---|---|
| Hosting | GitHub Pages | 100 GB/mo bandwidth, unlimited static | ~4 MB of JSON |
| Weekly job | GitHub Actions | Unlimited minutes (public repos) | ~5-10 min/week |
| Fundamentals | SEC EDGAR `companyfacts` XBRL | Free, no key (descriptive User-Agent + ≤10 req/s) | 503 requests/week |
| Ticker→CIK universe | community-maintained CSV snapshot of the Wikipedia S&P 500 table | Free | fetched once, checked into the repo |

The website never calls an API at runtime — it reads pre-computed JSON.
Marginal cost per visitor is $0.

---

## 3. Architecture

```
        ┌──────────────────────────────────────────────────┐
        │  GitHub Actions (cron, weekly, free)              │
SEC ───▶│  pipeline/run_all.py                              │
EDGAR   │    for each of 503 companies:                     │
        │      fetch companyfacts (throttled ≤10 req/s,     │
        │        cached on disk -- resumable)                │
        │      resolve each metric via an ORDERED tag        │
        │        fallback list; null if nothing resolves     │
        │      derive margins, FCF, ROE, ROIC, decade stats  │
        │        writes ▼                                    │
        │  site/data/manifest.json      (company list +      │
        │                                 coverage score)     │
        │  site/data/companies/<TICKER>.json                 │
        └──────────────────────┬───────────────────────────┘
                                │ git push
                                ▼
        ┌──────────────────────────────────────────────────┐
        │  GitHub Pages (static, free)                      │
        │  search.js  → type-ahead search, keyboard nav      │
        │  company.js → Chart.js charts, decade stats,       │
        │               footnoted gaps                       │
        └──────────────────────────────────────────────────┘
```

**Split of labour:** the weekly job does the slow, networked, tag-mapping
part and freezes it to JSON. The browser does the fast part (search + charts)
with zero backend.

---

## 4. The hard part: tag mapping

Companies file the same economic concept under different XBRL tags, and the
mapping is genuinely inconsistent across filers. `pipeline/tags.py` holds an
ordered fallback list per metric; `pipeline/extract.py` walks each list in
priority order and takes the first tag that resolves a value for a given
fiscal period. A few concrete things this had to handle, found by spot-
checking derived numbers against real 10-Ks rather than trusting the
pipeline on faith:

- **Stock splits.** A later 10-K's prior-year comparative columns are often
  retroactively restated for events like stock splits. Naively preferring
  "whichever filing most recently disclosed this period" pulls in a
  split-adjusted figure for the years within that filing's ~3-year lookback
  window, while earlier years (outside that window) stay unadjusted — a
  discontinuity from *mixed* adjustment, not real dilution. Verified against
  Apple's 2020 4-for-1 split: fixed by always taking the figure as
  **originally filed** in that fiscal year's own 10-K, so every year is
  internally consistent (a real, visible jump still appears exactly at the
  split date — that's the filed truth, not an error, and it's footnoted on
  the diluted-share-count chart).
- **A bad SEC reference file.** SEC's own bulk `company_tickers.json` maps
  the ticker "XOM" to an unrelated shell entity's CIK; the real Exxon Mobil
  Corp (confirmed via its own `submissions` endpoint) isn't listed under any
  ticker in that file at all. `config.CIK_OVERRIDES` documents this one
  correction; the full universe otherwise seeds CIK directly from a
  cross-checked source (see §5) rather than depending on ticker-text
  matching.
- **A stray malformed unit bucket.** Coca-Cola's `EarningsPerShareDiluted`
  carries a legacy "pure"-unit bucket with 4 junk 2008-09 entries alongside
  229 real `USD/shares` entries. Fixed generically — take the largest unit
  bucket rather than the first one in file order — so it protects every
  company against the same class of stray-tag issue, not just Coca-Cola.
- **Banks with no combined revenue tag.** Truist and Synchrony (among
  others) never tag a single "total revenue" concept — their income
  statement only breaks it into interest income and noninterest income as
  separate line items. `extract.py` derives revenue as
  `interest income + noninterest income` **only** when no single revenue tag
  resolves for the company at all, so a company is never a mix of
  tagged-some-years / derived-other-years.
- **Broker-dealers.** Goldman Sachs tags total revenue as
  `RevenuesNetOfInterestExpense`, not any of the standard ASC 606 tags —
  added to the fallback list directly.

**A fix that was tried and reverted:** Berkshire Hathaway's ASC-606-scoped
revenue tag excludes insurance premiums and investment gains/losses by
design, understating its true total revenue by roughly 30%. Reordering the
revenue tag list to prefer the broader `Revenues` concept looked safe (it's
numerically identical to the ASC 606 tag everywhere both are reported for an
ordinary operating company, verified against Apple) — but a universe-wide
regression check showed it silently breaks other companies where the
reverse is true (General Mills and BlackRock's `Revenues` tag is the
narrower/stale one; their ASC 606 figure is correct). No cheap way exists to
tell, per company, which tag is "the complete one" without fact-checking
individually — so this stays a known, disclosed limitation for
insurance-heavy conglomerates rather than trading one class of error for a
worse, silent one.

---

## 5. Universe & coverage

`pipeline/universe.json` seeds all 503 S&P 500 constituents (ticker, name,
GICS sector, CIK) from a community-maintained CSV snapshot of the
Wikipedia constituent table, cross-checked against SEC's CIK values —
seeding CIK directly here sidesteps the ticker-text matching issue described
above entirely, for every company, not just XOM.

Coverage is scored strictly: 10 metrics × up to 10 fiscal years, no
exemptions for business type. Across the full universe:

- **86.4% average coverage, 90% median.** 275/503 companies at ≥90%, 439/503
  (87%) at ≥70%.
- The shortfall concentrates in a small number of business types that
  structurally don't report certain concepts: banks and integrated-energy
  companies have no operating-income subtotal or COGS/gross-profit line;
  card networks and similar have no COGS line either. These are genuine,
  expected absences, not tag-mapping failures — each gets a specific
  footnote on the company page explaining *why*, generated from the metric
  and never hand-tuned per ticker (so it scales to all 503 without
  per-company overrides).
- **3 companies at 0% coverage** (0 fiscal years resolved): APA Corporation
  has no usable revenue tag anywhere in its structured filings (confirmed by
  exhaustive search, not a fixable mapping gap); FedEx Freight (FDXF) and
  Honeywell Aerospace (HONA) are brand-new 2025/2026 spinoffs that have only
  filed a Form 10-12B registration statement — zero 10-Ks exist yet, so
  there is nothing to show until they file one.

---

## 6. Derivations

- **Gross / operating / net margin** = gross profit / revenue, operating
  income / revenue, net income / revenue. Gross profit falls back to
  `revenue − cost of revenue` when no direct `GrossProfit` tag exists.
- **FCF** = cash flow from operations − capex (`PaymentsToAcquire...`
  property/plant/equipment tags). **FCF margin** = FCF / revenue.
- **ROE** = net income / average stockholders' equity, where "average" is
  (this fiscal year-end + the prior fiscal year-end)/2 when a prior year is
  available in the ten-year window; the oldest year in the window falls back
  to ending equity only (no earlier balance to average against).
- **ROIC** = NOPAT / invested capital. NOPAT = operating income × (1 −
  effective tax rate), where effective tax rate = income tax expense /
  pretax income, clamped to [0, 1] to guard against one-off items pushing
  the raw ratio outside a sane range. Invested capital = total debt + equity
  − cash, **period-end** (not averaged) — a deliberate v1 simplification,
  documented here rather than silently assumed.
- **Total debt** = sum of whichever of {long-term debt (current +
  noncurrent), short-term borrowings} resolve; a missing component counts as
  zero *only if* at least one component resolved for that company (so a
  company that simply doesn't tag short-term borrowings isn't penalized),
  otherwise total debt — and everything derived from it — is null. This is a
  known approximation: **for banks, insurers, and other deposit-funded
  financials, it excludes customer deposits, trading liabilities, and
  insurance reserves**, so net debt/equity understates real leverage for
  those business types. Disclosed as a permanent footnote on that chart.
- **Net debt / equity** = (total debt − cash) / equity.
- **Decade "share-count change"** detects likely stock-split events (a
  ≥1.8x jump or ≤0.6x drop between consecutive fiscal years — consistent
  with a clean split/reverse-split ratio, not organic buyback/issuance pace)
  and rescales the *first* year's share count by the detected ratio before
  comparing to the last year, so this one headline stat isn't dominated by a
  mechanical split (verified against Apple: without this, its decade of net
  buybacks would show as +173% "dilution" purely from the 2020 4-for-1
  split; with it, −27.7%, which matches the real buyback story). Per-year
  table values are never touched by this — only the single decade summary
  stat.
- **Fiscal year alignment.** Every metric is read at each company's own
  reported (start, end) period — never a calendar-quarter "frame" — so
  companies with non-calendar fiscal years (Apple ~late September, Microsoft
  ~June 30) are handled correctly by construction, with no special-casing
  needed.

---

## 7. Build phases

- **Phase 0 — pilot:** 10-ticker pilot (the coverage names: AAPL, MSFT,
  AMZN, GOOGL, TSLA, V, KO, JPM, XOM, JNJ), spot-checked against real 10-K
  figures.
- **Phase 1 — coverage tuning:** fixed real tag-mapping bugs found during
  the spot-check (see §4); accepted remaining gaps as structural, with
  footnotes rather than fallback hacks.
- **Phase 2 — site:** search + company chart pages, old-money theme
  matching the rest of the suite.
- **Phase 3 — scale:** full 503-company live run, throttled and resumable
  via an on-disk `companyfacts` cache (an interrupted run only re-fetches
  tickers it hadn't reached yet).
- **Phase 4 — self-review:** re-derived every number after two more real
  bugs surfaced during the full-universe run (ROE average-equity direction;
  several banks with no combined revenue tag) — see §4 and §6.
- **Phase 5 — automate:** `weekly-update.yml` cron refreshes and commits.

---

## 8. Sources (verified July 2026)

- SEC EDGAR `companyfacts` XBRL API: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
- SEC ticker→CIK bulk file: https://www.sec.gov/files/company_tickers.json (has at least one known bad mapping — see §4/§5)
- SEC `submissions` API (used to verify the correction above): https://data.sec.gov/submissions/CIK##########.json
- S&P 500 constituent universe: community-maintained CSV snapshot of the Wikipedia constituent table, cross-checked against SEC CIK values
- GitHub Pages / Actions limits: https://docs.github.com/en/pages and https://docs.github.com/en/actions
