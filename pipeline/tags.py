"""
tags.py — ordered us-gaap tag fallback lists per metric.

Companies file the same economic concept under different XBRL tags (e.g.
"Revenues" vs "RevenueFromContractWithCustomerExcludingAssessedTax" vs
"SalesRevenueNet" -- the last is pre-ASC606, still used by older filings or
restated comparatives). extract.py walks each list in order and takes the
first tag that resolves a value for the fiscal period in question. When none
resolve, the metric is written null -- an honest gap beats a guessed number.
"""

# Duration concepts (income statement / cash flow) -- matched by (start, end).
REVENUE = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenuesNetOfInterestExpense",  # broker-dealers / investment banks (e.g. Goldman Sachs)
]
# Tried reordering "Revenues" ahead of the ASC 606 tag to fix Berkshire
# Hathaway (whose ASC-606-scoped tag excludes insurance premiums and
# investment gains, understating true revenue by ~30%). Reverted: a
# universe-wide regression check showed it silently BREAKS other companies
# where "Revenues" is the narrower/stale figure and ASC 606 is correct
# (General Mills: ASC606 ~$19-20B matches reality, "Revenues" ~$2B does not;
# same pattern for BlackRock). No cheap, reliable way to tell which tag is
# "the complete one" per company without fact-checking each individually, so
# this stays as a known, documented limitation for insurance-heavy
# conglomerates rather than trading one class of error for a worse one.

# Some banks/consumer-finance filers never tag a single combined "total
# revenue" concept at all -- their income statement only breaks it into net
# (or gross) interest income and noninterest income as separate line items
# (e.g. Truist, Synchrony). Used as a last-resort DERIVED revenue (sum of
# these two) only when nothing in REVENUE resolves for the company at all --
# see extract.py:_derive_bank_revenue_by_period.
NET_INTEREST_INCOME = [
    "InterestIncomeExpenseNet",
]
GROSS_INTEREST_INCOME = [
    "InterestAndDividendIncomeOperating",
    "InterestIncomeOperating",
]
NONINTEREST_INCOME = [
    "NoninterestIncome",
]

COST_OF_REVENUE = [
    "CostOfGoodsAndServicesSold",
    "CostOfRevenue",
    "CostOfGoodsSold",
    "CostOfServices",
]

GROSS_PROFIT = [
    "GrossProfit",
]

OPERATING_INCOME = [
    "OperatingIncomeLoss",
]

NET_INCOME = [
    "NetIncomeLoss",
    "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
]

EPS_DILUTED = [
    "EarningsPerShareDiluted",
]

DILUTED_SHARES = [
    "WeightedAverageNumberOfDilutedSharesOutstanding",
]

CFO = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]

CAPEX = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsForCapitalImprovements",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquireMachineryAndEquipment",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
]

INCOME_TAX_EXPENSE = [
    "IncomeTaxExpenseBenefit",
]

PRETAX_INCOME = [
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomesticAndForeign",
]

# Instant concepts (balance sheet) -- matched by (end) only.
EQUITY = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]

CASH = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "CashAndCashEquivalentsAtCarryingValueIncludingDiscontinuedOperations",
]

# Total debt has no single canonical tag across filers -- it is assembled from
# whichever of these balance-sheet line items a company reports (see
# extract.py:_total_debt). Each list is itself a fallback chain for that one
# component.
LT_DEBT_NONCURRENT = [
    "LongTermDebtNoncurrent",
    "LongTermDebt",
]

LT_DEBT_CURRENT = [
    "LongTermDebtCurrent",
    "DebtCurrent",
]

ST_BORROWINGS = [
    "ShortTermBorrowings",
    "CommercialPaper",
]
