# Tenline — data sources

- **Ticker → CIK map:** https://www.sec.gov/files/company_tickers.json
  (free, no key; cached at `pipeline/cache/company_tickers.json`)
- **Company fundamentals (XBRL):** https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
  (free, no key; requires a descriptive `User-Agent` header and a fair-use
  rate limit of <=10 requests/sec — see `pipeline/config.py`)
- **EDGAR filings page (linked per company):** https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=##########&type=10-K

Verified live July 2026. No secrets, no API keys, nothing beyond a
descriptive User-Agent (name + email).
