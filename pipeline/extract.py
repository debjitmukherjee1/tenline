"""
extract.py — derive Tenline's ten fiscal-year metrics from a company's raw
SEC EDGAR `companyfacts` payload.

Design notes:
- Each company's OWN reported fiscal-year end dates are used as the periods
  (never a calendar-quarter "frame") -- this sidesteps fiscal-year alignment
  issues for companies with non-calendar FYs (AAPL ~late Sept, MSFT ~June 30):
  whatever period a company's own 10-K calls a fiscal year is a period here
  too, regardless of which calendar month it falls in.
- Revenue defines the canonical set of (up to) ten fiscal periods for a
  company; every other metric is read at those exact periods. A metric that
  doesn't resolve at a given period is left null rather than guessed.
- A gap (e.g. gross margin for a bank or card network with no COGS concept)
  is expected, not a bug -- coverage stats should be read with that in mind.
"""
import datetime as dt

import config
import tags

DUR_TAGS = {
    "revenue": tags.REVENUE,
    "cost_of_revenue": tags.COST_OF_REVENUE,
    "gross_profit": tags.GROSS_PROFIT,
    "operating_income": tags.OPERATING_INCOME,
    "net_income": tags.NET_INCOME,
    "eps_diluted": tags.EPS_DILUTED,
    "diluted_shares": tags.DILUTED_SHARES,
    "cfo": tags.CFO,
    "capex": tags.CAPEX,
    "income_tax_expense": tags.INCOME_TAX_EXPENSE,
    "pretax_income": tags.PRETAX_INCOME,
}

INST_TAGS = {
    "equity": tags.EQUITY,
    "cash": tags.CASH,
    "lt_debt_noncurrent": tags.LT_DEBT_NONCURRENT,
    "lt_debt_current": tags.LT_DEBT_CURRENT,
    "st_borrowings": tags.ST_BORROWINGS,
}

# The ten fields actually shown per fiscal year on the company page --
# coverage is measured against these, not against every intermediate value
# extract.py resolves along the way.
OUTPUT_METRICS = (
    "revenue", "gross_margin", "operating_margin", "net_margin", "eps_diluted",
    "fcf_margin", "roe", "roic", "diluted_shares", "net_debt_to_equity",
)


def _parse(d):
    return dt.date.fromisoformat(d)


def _facts_for(companyfacts, tag_name):
    node = companyfacts.get("facts", {}).get("us-gaap", {}).get(tag_name)
    if not node:
        return []
    units = node.get("units", {})
    if not units:
        return []
    # A concept is reported in one real unit type in practice (USD,
    # USD/shares, or shares), but a handful of filers carry a stray
    # secondary unit bucket from an old tagging error (observed: Coca-Cola's
    # EarningsPerShareDiluted has a "pure"-unit bucket with 4 stray 2008-09
    # entries alongside 229 real "USD/shares" entries). Taking the largest
    # bucket rather than just the first one in insertion order avoids
    # picking the wrong (near-empty) one.
    return max(units.values(), key=len)


def _is_annual_form(entry):
    return entry.get("form", "").startswith("10-K")


def _dedupe_best(entries_by_period):
    """Within each period key, prefer form '10-K' over '10-K/A', then the
    EARLIEST 'filed' date among same-form entries -- i.e. the figure as
    originally reported in that fiscal year's own 10-K.

    This deliberately does NOT prefer the latest filing that re-discloses a
    period (e.g. as a prior-year comparative in a later 10-K). A later 10-K's
    comparative columns are often retroactively adjusted for events like
    stock splits -- and since a 10-K's income statement only reaches back
    ~2 prior years, that adjustment only reaches SOME of the ten fiscal years
    in view here, not all of them. Preferring "latest filed" was tried first
    and produced a real bug: Apple's diluted share count showed a fake ~4x
    jump between FY2017 and FY2018 that was actually the FY2020 10-K's
    split-adjusted comparative bleeding into FY2018-2020 while FY2016-2017
    (outside that filing's 3-year lookback) stayed pre-split -- a
    discontinuity from mixed adjustment, not real dilution. Taking the
    earliest-filed (as-originally-filed) value for every period keeps each
    year internally consistent with itself, at the cost of showing a real,
    visible cliff at actual stock-split dates -- which is the filed truth,
    not a data error, and is called out in the site's methodology copy."""
    best = {}
    for key, entries in entries_by_period.items():
        has_10k = [e for e in entries if e["form"] == "10-K"]
        pool = has_10k if has_10k else entries
        best[key] = sorted(pool, key=lambda e: e["filed"])[0]
    return best


def _duration_facts_by_period(companyfacts, tag_list):
    """Merged {(start,end): value} across the tag fallback list, in priority
    order -- an earlier tag's period coverage is never overwritten by a
    later fallback tag. Returns (values, sources) where sources maps the
    same keys to which tag resolved them (for coverage/debug logging)."""
    result, sources = {}, {}
    for tag_name in tag_list:
        raw = [e for e in _facts_for(companyfacts, tag_name) if _is_annual_form(e) and "start" in e]
        by_period = {}
        for e in raw:
            span = (_parse(e["end"]) - _parse(e["start"])).days
            if not (config.MIN_FY_DURATION_DAYS <= span <= config.MAX_FY_DURATION_DAYS):
                continue
            by_period.setdefault((e["start"], e["end"]), []).append(e)
        for key, e in _dedupe_best(by_period).items():
            if key not in result:
                result[key] = e["val"]
                sources[key] = tag_name
    return result, sources


def _instant_facts_by_end(companyfacts, tag_list):
    """Merged {end: value} across the tag fallback list, in priority order."""
    result, sources = {}, {}
    for tag_name in tag_list:
        raw = [e for e in _facts_for(companyfacts, tag_name) if _is_annual_form(e) and "start" not in e]
        by_end = {}
        for e in raw:
            by_end.setdefault(e["end"], []).append(e)
        for end, e in _dedupe_best(by_end).items():
            if end not in result:
                result[end] = e["val"]
                sources[end] = tag_name
    return result, sources


def _derive_bank_revenue_by_period(companyfacts):
    """{(start,end): net/gross interest income + noninterest income} -- for
    filers with no single combined revenue tag anywhere in REVENUE (common
    for banks/consumer-finance companies: Truist and Synchrony, for example,
    tag interest income and noninterest income as separate line items with
    no combined total). Prefers net interest income (after interest
    expense) over gross when both are available, since net is the standard
    "total revenue" analog in bank income-statement presentation."""
    net_ii, _ = _duration_facts_by_period(companyfacts, tags.NET_INTEREST_INCOME)
    interest_income = net_ii if net_ii else _duration_facts_by_period(companyfacts, tags.GROSS_INTEREST_INCOME)[0]
    noninterest, _ = _duration_facts_by_period(companyfacts, tags.NONINTEREST_INCOME)
    return {p: interest_income[p] + noninterest[p] for p in set(interest_income) & set(noninterest)}


def _canonical_periods(rev_by_period):
    """Latest MAX_FISCAL_YEARS distinct fiscal periods, newest first."""
    return sorted(rev_by_period.keys(), key=lambda k: k[1], reverse=True)[: config.MAX_FISCAL_YEARS]


# Tried using each fact's own SEC-assigned 'fy' field as the label instead
# of the period-end's calendar year, on the theory that it's the filing's
# own authoritative label. Reverted: that field actually reflects which
# FILING contains the disclosure (its DocumentFiscalYearFocus), not the
# fiscal year of the specific period being disclosed -- a company's first
# filing under a new revenue tag shows 2-3 prior years as comparatives that
# all inherit that ONE filing's fy value, which produced duplicate/wrong
# labels (verified against Apple's real FY2016-2018: all collapsed onto
# 2018/2019). The calendar-year-of-period-end heuristic below tested correct
# against both Apple and Walmart's actual reported fiscal-year labels.


def _total_debt(period_end, inst_values):
    """Assembled from whichever balance-sheet debt components resolve; a
    missing component is treated as 0 IF at least one component resolved for
    this period (a company legitimately reporting zero short-term borrowings
    looks identical, in this data, to one that simply files a different tag
    -- a known approximation, documented in docs/EXECUTABLE_PLAN.md). If NONE
    of the components resolve, total debt (and net debt/equity) is null."""
    parts = [
        inst_values["lt_debt_noncurrent"].get(period_end),
        inst_values["lt_debt_current"].get(period_end),
        inst_values["st_borrowings"].get(period_end),
    ]
    parts = [p for p in parts if p is not None]
    return sum(parts) if parts else None


# Generic, per-metric explanations shown as a footnote on the company page
# when a metric is null for EVERY fiscal year -- i.e. a structural reporting
# difference for that company, not a one-off gap. Deliberately generic
# (not hand-tuned per ticker) so it scales to the full 500-company universe
# without per-company overrides.
_STRUCTURAL_NOTES = {
    "gross_margin": "Not disclosed as a distinct line in this company's filings (no cost-of-revenue/gross-profit tag) -- common for banks, insurers, and other financials.",
    "operating_margin": "Not disclosed as a distinct line in this company's filings (no operating-income subtotal tag) -- common for banks and integrated energy companies.",
    "roic": "Requires an operating-income and effective-tax-rate breakdown not disclosed as distinct tags in this company's filings.",
    "fcf_margin": "Operating cash flow and/or capital expenditures aren't disclosed as distinct tags in this company's filings -- capex in particular is often untagged for banks, where it's immaterial.",
    "eps_diluted": "Not tagged under a standard diluted EPS concept in this company's filings -- can happen with multi-class share structures.",
    "diluted_shares": "Not tagged under a standard diluted share-count concept in this company's filings.",
    "net_debt_to_equity": "Debt components aren't disclosed as distinct tags in this company's filings.",
    "roe": "Stockholders' equity isn't disclosed as a distinct tag in this company's filings.",
    "net_margin": "Net income isn't disclosed as a distinct tag in this company's filings.",
    "revenue": "Total revenue isn't disclosed as a single distinct tag in this company's filings.",
}


def _coverage_notes(years):
    """{metric: reason} for every output metric that is null across the
    ENTIRE resolved history -- a company-wide structural gap worth
    explaining, as opposed to a one-off single-year gap (those are shown as
    a plain break in the line chart, no note needed)."""
    notes = {}
    for m in OUTPUT_METRICS:
        if years and all(y[m] is None for y in years):
            notes[m] = _STRUCTURAL_NOTES[m]
    return notes


def _median(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    n, mid = len(vals), len(vals) // 2
    return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2


def _split_adjusted_first_shares(years):
    """Returns the first fiscal year's diluted share count, rescaled to be
    comparable with the last year's, by detecting likely stock-split events
    (a >=1.8x jump or <=0.6x drop in one year -- consistent with a clean
    split/reverse-split ratio, not organic buyback/issuance pace) between
    consecutive years and folding each detected ratio into every earlier
    year. Per-year table values are never touched by this -- it exists only
    so the single decade "share-count change" headline isn't dominated by a
    mechanical split ratio (e.g. Apple's Aug-2020 4-for-1 split, which
    otherwise makes a decade of net buybacks look like +173% dilution)."""
    shares = [y["diluted_shares"] for y in years]
    if not shares or any(s is None for s in shares):
        return None
    cum = 1.0
    for i in range(len(shares) - 1, 0, -1):
        prev = shares[i - 1]
        if not prev:
            continue
        ratio = shares[i] / prev
        if ratio >= 1.8 or ratio <= 0.6:
            cum *= ratio
    return shares[0] * cum


def _decade_summary(years):
    if len(years) < 2:
        return {"revenue_cagr": None, "median_net_margin": None,
                "share_count_change_pct": None, "fcf_conversion_median": None,
                "years_covered": len(years)}
    first, last = years[0], years[-1]
    n_years = (_parse(last["period_end"]) - _parse(first["period_end"])).days / 365.25

    revenue_cagr = None
    if first["revenue"] and last["revenue"] and first["revenue"] > 0 and n_years > 0:
        revenue_cagr = (last["revenue"] / first["revenue"]) ** (1 / n_years) - 1

    share_change = None
    first_shares_adj = _split_adjusted_first_shares(years)
    if first_shares_adj and last["diluted_shares"]:
        share_change = last["diluted_shares"] / first_shares_adj - 1

    fcf_conv = _median([
        (y["fcf"] / y["net_income"]) if (y["fcf"] is not None and y["net_income"]) else None
        for y in years
    ])
    med_net_margin = _median([y["net_margin"] for y in years])

    return {
        "revenue_cagr": round(revenue_cagr, 4) if revenue_cagr is not None else None,
        "median_net_margin": round(med_net_margin, 4) if med_net_margin is not None else None,
        "share_count_change_pct": round(share_change, 4) if share_change is not None else None,
        "fcf_conversion_median": round(fcf_conv, 4) if fcf_conv is not None else None,
        "years_covered": len(years),
    }


def extract_company(companyfacts):
    """Returns (years: list[dict] oldest-first, coverage: dict, decade: dict, sources: dict)."""
    rev_by_period, rev_sources = _duration_facts_by_period(companyfacts, tags.REVENUE)
    if not rev_by_period:
        # No single combined revenue tag resolved for ANY period -- rather
        # than leave the whole company with zero fiscal years, fall back to
        # deriving revenue from interest + noninterest income (see
        # _derive_bank_revenue_by_period). Only triggers when REVENUE found
        # nothing at all, so a company is never a mix of tagged-some-years
        # and derived-other-years, which would reintroduce the same kind of
        # inconsistency the split-adjustment fix above was written to avoid.
        derived = _derive_bank_revenue_by_period(companyfacts)
        if derived:
            rev_by_period = derived
            rev_sources = {p: "derived: interest income + noninterest income" for p in derived}
    # Oldest -> newest so the running `prior_equity` below actually refers to
    # the preceding (earlier) fiscal year as the loop advances -- iterating
    # newest-first while calling the running value "prior" was tried first
    # and was backwards: it paired each year's ROE with the FOLLOWING year's
    # equity instead of the preceding one, and "no prior year, fall back to
    # ending equity only" landed on the newest year instead of the oldest.
    periods = sorted(_canonical_periods(rev_by_period), key=lambda p: p[1])

    dur_values, dur_sources = {"revenue": rev_by_period}, {"revenue": rev_sources}
    for metric, tag_list in DUR_TAGS.items():
        if metric == "revenue":
            continue
        dur_values[metric], dur_sources[metric] = _duration_facts_by_period(companyfacts, tag_list)

    inst_values = {}
    for metric, tag_list in INST_TAGS.items():
        inst_values[metric], _ = _instant_facts_by_end(companyfacts, tag_list)

    years = []
    prior_equity = None
    for start, end in periods:
        def dv(metric):
            return dur_values[metric].get((start, end))

        def iv(metric):
            return inst_values[metric].get(end)

        revenue = dv("revenue")
        gross_profit = dv("gross_profit")
        cost_of_rev = dv("cost_of_revenue")
        if gross_profit is None and revenue is not None and cost_of_rev is not None:
            gross_profit = revenue - cost_of_rev
        operating_income = dv("operating_income")
        net_income = dv("net_income")
        eps_diluted = dv("eps_diluted")
        diluted_shares = dv("diluted_shares")
        cfo = dv("cfo")
        capex = dv("capex")
        tax_expense = dv("income_tax_expense")
        pretax_income = dv("pretax_income")

        equity = iv("equity")
        cash = iv("cash")
        total_debt = _total_debt(end, inst_values)

        gross_margin = (gross_profit / revenue) if (gross_profit is not None and revenue) else None
        operating_margin = (operating_income / revenue) if (operating_income is not None and revenue) else None
        net_margin = (net_income / revenue) if (net_income is not None and revenue) else None

        fcf = (cfo - capex) if (cfo is not None and capex is not None) else None
        fcf_margin = (fcf / revenue) if (fcf is not None and revenue) else None

        # ROE uses average equity (this FY end + prior FY end) when a prior
        # year is available in this same run; falls back to ending equity
        # for the oldest year in the window (no earlier balance to average).
        avg_equity = None
        if equity is not None:
            avg_equity = (equity + prior_equity) / 2 if prior_equity is not None else equity
        roe = (net_income / avg_equity) if (net_income is not None and avg_equity) else None

        # ROIC = NOPAT / invested capital, both period-end (not averaged --
        # keeps the invested-capital base transparent for v1). NOPAT =
        # operating income x (1 - effective tax rate); effective tax rate =
        # tax expense / pretax income, clamped to [0,1] since one-off items
        # occasionally push the raw ratio outside a sane range.
        nopat = None
        if operating_income is not None and tax_expense is not None and pretax_income:
            eff_rate = max(0.0, min(1.0, tax_expense / pretax_income))
            nopat = operating_income * (1 - eff_rate)
        invested_capital = None
        if total_debt is not None and equity is not None and cash is not None:
            invested_capital = total_debt + equity - cash
        roic = (nopat / invested_capital) if (nopat is not None and invested_capital and invested_capital > 0) else None

        net_debt = (total_debt - cash) if (total_debt is not None and cash is not None) else None
        net_debt_to_equity = (net_debt / equity) if (net_debt is not None and equity) else None

        years.append({
            "fy": str(_parse(end).year),
            "period_start": start,
            "period_end": end,
            "revenue": revenue,
            "net_income": net_income,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "net_margin": net_margin,
            "eps_diluted": eps_diluted,
            "fcf": fcf,
            "fcf_margin": fcf_margin,
            "roe": roe,
            "roic": roic,
            "diluted_shares": diluted_shares,
            "net_debt_to_equity": net_debt_to_equity,
        })
        prior_equity = equity if equity is not None else prior_equity

    # `years` was already built oldest -> newest (see the sorted `periods`
    # above), which is what charts and _decade_summary expect.

    resolved = sum(1 for y in years for m in OUTPUT_METRICS if y[m] is not None)
    coverage = {
        "resolved": resolved,
        "total": len(years) * len(OUTPUT_METRICS),
        "pct": round(resolved / (len(years) * len(OUTPUT_METRICS)), 4) if years else 0.0,
    }

    decade = _decade_summary(years)
    notes = _coverage_notes(years)
    sources = {"revenue": rev_sources, **{k: v for k, v in dur_sources.items() if k != "revenue"}}
    return years, coverage, decade, notes, sources
