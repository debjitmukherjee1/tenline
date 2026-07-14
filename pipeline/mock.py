"""
mock.py — deterministic synthetic decade of fundamentals so the pipeline (and
site) run fully offline, with no SEC network access.

Generates the final per-year schema directly (rather than a fake raw
companyfacts payload run back through extract.py) since the only thing that
needs to be exercised offline is the site/data contract, not the XBRL parser.
"""
import random
from datetime import date


def mock_years(ticker, n=10, end_year=2025):
    rng = random.Random(ticker)
    revenue = rng.uniform(8e9, 4e11)
    growth = rng.uniform(0.03, 0.18)
    gross_m = rng.uniform(0.25, 0.65)
    op_m = gross_m - rng.uniform(0.08, 0.20)
    net_m = op_m - rng.uniform(0.02, 0.08)
    shares = rng.uniform(3e8, 1.6e10)
    share_drift = rng.uniform(-0.03, 0.01)  # negative = buybacks
    equity = revenue * rng.uniform(0.6, 1.8)
    debt = equity * rng.uniform(0.1, 0.9)
    cash = equity * rng.uniform(0.05, 0.3)

    years = []
    for i in range(n):
        fy = end_year - (n - 1 - i)
        rev = revenue * ((1 + growth) ** i)
        net_income = rev * max(0.01, net_m + rng.uniform(-0.01, 0.01))
        fcf = rev * max(0.0, net_m + rng.uniform(-0.03, 0.05))
        eq = equity * ((1 + rng.uniform(0.02, 0.10)) ** i)
        sh = shares * ((1 + share_drift) ** i)
        d = debt * ((1 + rng.uniform(-0.02, 0.05)) ** i)
        c = cash * ((1 + rng.uniform(-0.05, 0.08)) ** i)
        net_debt = d - c
        years.append({
            "fy": str(fy),
            "period_start": date(fy - 1, 1, 2).isoformat(),
            "period_end": date(fy, 12, 31).isoformat(),
            "revenue": round(rev, 2),
            "net_income": round(net_income, 2),
            "gross_margin": round(gross_m + rng.uniform(-0.01, 0.01), 4),
            "operating_margin": round(op_m + rng.uniform(-0.01, 0.01), 4),
            "net_margin": round(net_income / rev, 4),
            "eps_diluted": round(net_income / sh, 2),
            "fcf": round(fcf, 2),
            "fcf_margin": round(fcf / rev, 4),
            "roe": round(net_income / eq, 4),
            "roic": round((net_income * 1.1) / (d + eq - c), 4) if (d + eq - c) > 0 else None,
            "diluted_shares": round(sh, 0),
            "net_debt_to_equity": round(net_debt / eq, 4),
        })
    return years
