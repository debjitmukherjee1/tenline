"""
Tenline configuration — ten fiscal years of fundamentals per S&P 500 company,
straight from SEC EDGAR XBRL filings.

Data comes from SEC EDGAR's `companyfacts` API (free, keyless, official). In
MOCK_MODE (default when offline) the pipeline generates a deterministic
synthetic decade of financials so the whole site runs without any network
access.
"""
import os

# --- SEC EDGAR ---------------------------------------------------------------
# SEC requires a descriptive User-Agent identifying the requester (name +
# contact) on every request, and asks for a fair-use rate limit of <=10 req/s.
# Keep this to name + email only -- no more personal info than that.
SEC_USER_AGENT = "Debjit Mukherjee m.debjit2007@gmail.com"
SEC_MAX_REQ_PER_SEC = 10
SEC_REQUEST_INTERVAL = 1.0 / SEC_MAX_REQ_PER_SEC + 0.05   # small safety margin

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
EDGAR_FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik10}&type=10-K"

# SEC's bulk company_tickers.json occasionally maps a ticker to the wrong
# CIK -- verified case: "XOM" resolves there to CIK 2115436 ("ExxonMobil
# Holdings Corp", an unrelated/decoy entity), while the real Exxon Mobil
# Corp (confirmed via https://data.sec.gov/submissions/CIK0000034088.json,
# which lists tickers: ["XOM"]) is CIK 34088 and isn't listed under any
# ticker in the bulk file at all. Manual, documented corrections only --
# not a general workaround, just a fix for this one known bad row.
CIK_OVERRIDES = {
    "XOM": "0000034088",
}

# --- Universe -----------------------------------------------------------------
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
UNIVERSE_PATH = os.path.join(PIPELINE_DIR, "universe.json")
CACHE_DIR = os.path.join(PIPELINE_DIR, "cache")
TICKER_MAP_CACHE = os.path.join(CACHE_DIR, "company_tickers.json")
COMPANYFACTS_CACHE_DIR = os.path.join(CACHE_DIR, "companyfacts")

# --- Output --------------------------------------------------------------------
SITE_DATA_DIR = os.path.join(PIPELINE_DIR, "..", "site", "data")
COMPANIES_DIR = os.path.join(SITE_DATA_DIR, "companies")

# --- Coverage -----------------------------------------------------------------
MAX_FISCAL_YEARS = 10
# A metric year-cell only counts as "covered" if it resolves for at least this
# many of the MAX_FISCAL_YEARS -- used only for logging, not for the per-cell
# null policy (a null year always stays null regardless of overall coverage).
MIN_FY_DURATION_DAYS = 340   # guards against stub/transition-period filings
MAX_FY_DURATION_DAYS = 380

# --- Mode ------------------------------------------------------------------
# SEC needs no key; we go "live" whenever network is intended. Set
# TENLINE_LIVE=1 in the GitHub Action; default here is mock for safe offline
# runs.
MOCK_MODE = os.environ.get("TENLINE_LIVE") != "1"
