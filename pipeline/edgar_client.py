"""
edgar_client.py — throttled SEC EDGAR access: ticker->CIK mapping and
companyfacts fetch, with on-disk caching so a pipeline run is resumable
(an interrupted run only re-fetches tickers it hadn't cached yet).
"""
import json
import os
import time

import config

try:
    import requests
except ImportError:
    requests = None

_HEADERS = {"User-Agent": config.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
_last_request_ts = 0.0


def _throttle():
    """Sleeps as needed to respect SEC's <=10 req/sec fair-use guidance."""
    global _last_request_ts
    now = time.monotonic()
    wait = config.SEC_REQUEST_INTERVAL - (now - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.monotonic()


def _get(url, retries=3):
    last_err = None
    for attempt in range(retries):
        _throttle()
        try:
            r = requests.get(url, headers=_HEADERS, timeout=30)
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            time.sleep(1 * (attempt + 1))
    raise last_err


def load_ticker_map(force=False):
    """Returns {TICKER: cik10-string} built from SEC's company_tickers.json.
    Cached on disk -- this file changes rarely and a re-run should not need
    to refetch it every time."""
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    if not force and os.path.exists(config.TICKER_MAP_CACHE):
        with open(config.TICKER_MAP_CACHE) as f:
            raw = json.load(f)
    else:
        r = _get(config.TICKER_MAP_URL)
        raw = r.json()
        with open(config.TICKER_MAP_CACHE, "w") as f:
            json.dump(raw, f)

    mapping = {}
    for entry in raw.values():
        ticker = entry["ticker"].upper()
        cik10 = str(entry["cik_str"]).zfill(10)
        mapping[ticker] = cik10
    mapping.update(config.CIK_OVERRIDES)
    return mapping


def fetch_companyfacts(ticker, cik10, use_cache=True):
    """Returns the raw companyfacts JSON for a ticker, using the on-disk
    cache when present so an interrupted pipeline run can resume without
    re-hitting the network for tickers already fetched."""
    os.makedirs(config.COMPANYFACTS_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(config.COMPANYFACTS_CACHE_DIR, f"{ticker}.json")

    if use_cache and os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f)

    if config.MOCK_MODE:
        raise RuntimeError("fetch_companyfacts called live while MOCK_MODE is on")

    r = _get(config.COMPANYFACTS_URL.format(cik10=cik10))
    data = r.json()
    with open(cache_path, "w") as f:
        json.dump(data, f)
    return data
