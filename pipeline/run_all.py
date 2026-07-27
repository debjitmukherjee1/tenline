"""
run_all.py — builds site/data for Tenline.

For each company in universe.json: resolve its CIK, fetch (or reuse cached)
SEC EDGAR companyfacts, derive the last ten fiscal years of the ten output
metrics, and write:

  site/data/companies/<TICKER>.json   -> {ticker, name, sector, years[], decade, coverage}
  site/data/manifest.json             -> company list + per-ticker coverage + updated_at

Resumable: the raw companyfacts fetch is cached on disk per ticker
(pipeline/cache/companyfacts/<TICKER>.json), so an interrupted run only needs
to re-fetch tickers it hadn't reached yet -- re-running is safe and cheap.

Usage:
  python run_all.py                 (mock, offline)
  TENLINE_LIVE=1 python run_all.py  (live, SEC EDGAR)
  TENLINE_LIVE=1 python run_all.py --tickers AAPL,MSFT   (subset, for testing)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import config
import edgar_client
import extract
import mock


def _load_universe(subset=None):
    with open(config.UNIVERSE_PATH) as f:
        universe = json.load(f)
    companies = universe["companies"]
    if subset:
        wanted = {t.strip().upper() for t in subset}
        companies = [c for c in companies if c["ticker"].upper() in wanted]
    return universe.get("as_of"), companies


def _run_one_mock(ticker):
    return mock.mock_years(ticker)


def _run_one_live(ticker, cik10):
    companyfacts = edgar_client.fetch_companyfacts(ticker, cik10)
    years, coverage, decade, notes, sources, disclosure = extract.extract_company(companyfacts)
    return years, coverage, decade, notes, sources, disclosure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", help="comma-separated ticker subset, e.g. AAPL,MSFT")
    parser.add_argument("--no-cache", action="store_true", help="ignore cached companyfacts, refetch live")
    args = parser.parse_args()

    subset = args.tickers.split(",") if args.tickers else None
    as_of, companies = _load_universe(subset)

    mode = "MOCK" if config.MOCK_MODE else "LIVE"
    print(f"=== Tenline pipeline ({mode}) — {len(companies)} companies ===")
    updated = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    os.makedirs(config.COMPANIES_DIR, exist_ok=True)

    # universe.json seeds CIK directly for every S&P 500 constituent (from a
    # source that's already cross-checked against SEC, e.g. it has the
    # correct XOM CIK where SEC's own bulk company_tickers.json does not --
    # see config.CIK_OVERRIDES). The ticker->CIK bulk map is only fetched as
    # a fallback for entries that don't carry a seeded CIK (e.g. an ad-hoc
    # --tickers run against a ticker not in universe.json).
    ticker_map = {}
    if not config.MOCK_MODE and any(not c.get("cik") for c in companies):
        print("Loading ticker -> CIK map from SEC EDGAR (fallback for un-seeded tickers)...")
        ticker_map = edgar_client.load_ticker_map()

    manifest_companies = []
    all_sources = {}

    for c in companies:
        ticker, name, sector = c["ticker"], c["name"], c["sector"]
        out_path = os.path.join(config.COMPANIES_DIR, f"{ticker}.json")
        cik10 = c.get("cik") or ticker_map.get(ticker.upper())

        try:
            if config.MOCK_MODE:
                years = _run_one_mock(ticker)
                coverage = {"resolved": sum(1 for y in years for m in extract.OUTPUT_METRICS if y[m] is not None),
                            "total": len(years) * len(extract.OUTPUT_METRICS)}
                coverage["pct"] = round(coverage["resolved"] / coverage["total"], 4)
                decade = extract._decade_summary(years)
                notes, sources, disclosure = {}, {}, []
            else:
                if not cik10:
                    raise ValueError(f"no CIK found for ticker {ticker}")
                if args.no_cache:
                    cache_path = os.path.join(config.COMPANYFACTS_CACHE_DIR, f"{ticker}.json")
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                years, coverage, decade, notes, sources, disclosure = _run_one_live(ticker, cik10)
                all_sources[ticker] = sources
        except Exception as e:
            print(f"  ! {ticker}: FAILED ({e})", file=sys.stderr)
            continue

        payload = {
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "cik": cik10,
            "edgar_filings_url": config.EDGAR_FILINGS_URL.format(cik10=cik10) if cik10 else None,
            "years": years,
            "decade": decade,
            "coverage": coverage,
            "notes": notes,
            "disclosure_changes": disclosure,
            "source": "mock" if config.MOCK_MODE else "live",
            "updated_at": updated,
        }
        with open(out_path, "w") as f:
            json.dump(payload, f, separators=(",", ":"))

        manifest_companies.append({
            "ticker": ticker, "name": name, "sector": sector,
            "coverage_pct": coverage["pct"], "years_covered": len(years),
        })
        print(f"  {ticker:6s} {name:28s} coverage {coverage['pct']*100:5.1f}%  "
              f"years {len(years)}  ({coverage['resolved']}/{coverage['total']} cells)")

    manifest = {
        "updated_at": updated,
        "universe_as_of": as_of,
        "companies": sorted(manifest_companies, key=lambda c: c["ticker"]),
    }
    with open(os.path.join(config.SITE_DATA_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    n_ok = len(manifest_companies)
    print(f"\nWrote {n_ok}/{len(companies)} companies -> {os.path.normpath(config.COMPANIES_DIR)}")
    if manifest_companies:
        avg_cov = sum(c["coverage_pct"] for c in manifest_companies) / n_ok
        print(f"Average coverage: {avg_cov*100:.1f}%")

    if all_sources:
        _dump_sources_log(all_sources)


def _stringify_keys(obj):
    """json.dump can't serialize tuple dict keys (duration-period keys are
    (start, end) tuples) -- stringify them for this debug log only."""
    if isinstance(obj, dict):
        return {str(k): _stringify_keys(v) for k, v in obj.items()}
    return obj


def _dump_sources_log(all_sources):
    path = os.path.join(config.CACHE_DIR, "tag_sources.json")
    with open(path, "w") as f:
        json.dump(_stringify_keys(all_sources), f, indent=2)
    print(f"Per-ticker resolved-tag log -> {os.path.normpath(path)}")


if __name__ == "__main__":
    main()
