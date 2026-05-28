"""Fetch India company financials from Yahoo Finance (.NS suffix for NSE)."""
from __future__ import annotations
import urllib.request
import urllib.parse
import json
from .financials import IndiaCompanyData, IndiaAnnualData

_BASE = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
_MODULES = "incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory,financialData,summaryDetail,assetProfile,defaultKeyStatistics"
_CRORE = 1e7
_HEADERS = {"User-Agent": "Mozilla/5.0 (india-dcf/1.0; +https://github.com/bhupendra05/india-dcf)"}


def _get(ticker: str) -> dict:
    url = _BASE.format(ticker=urllib.parse.quote(ticker)) + f"?modules={_MODULES}&lang=en"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["quoteSummary"]["result"][0]


def _v(obj: dict, *keys, default=None):
    """Safely extract nested .raw value."""
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k, {})
    return obj.get("raw", default) if isinstance(obj, dict) else default


def _to_cr(v):
    return v / _CRORE if v is not None else 0.0


def fetch_india_financials(symbol: str, sector: str = "Default") -> IndiaCompanyData:
    """
    Fetch NSE-listed company financials from Yahoo Finance.
    Tries {symbol}.NS first, then {symbol}.BO for BSE.
    Returns IndiaCompanyData with INR Crore denomination.
    """
    raw = None
    for suffix in (".NS", ".BO", ""):
        try:
            raw = _get(symbol.upper() + suffix)
            break
        except Exception:
            continue
    if raw is None:
        raise ValueError(f"Could not fetch data for {symbol}. Check ticker (e.g., 'INFY', 'TCS').")

    profile = raw.get("assetProfile", {})
    key_stats = raw.get("defaultKeyStatistics", {})
    fin_data = raw.get("financialData", {})

    company_name = profile.get("longName") or profile.get("shortName") or symbol.upper()
    detected_sector = profile.get("sector") or sector

    # Shares outstanding in Crore shares
    shares_raw = _v(key_stats, "sharesOutstanding")
    shares_cr = shares_raw / _CRORE if shares_raw else 1.0

    # Build history from annual income statement
    income_stmts = raw.get("incomeStatementHistory", {}).get("incomeStatementHistory", [])
    balance_sheets = raw.get("balanceSheetHistory", {}).get("balanceSheetStatements", [])
    cashflows = raw.get("cashflowStatementHistory", {}).get("cashflowStatements", [])

    history = []
    for i, inc in enumerate(income_stmts):
        fy_raw = inc.get("endDate", {}).get("fmt", f"FY{2024 - i}")
        fy = "FY" + fy_raw[:4] if not fy_raw.startswith("FY") else fy_raw

        revenue = _to_cr(_v(inc, "totalRevenue"))
        ebit = _to_cr(_v(inc, "ebit"))
        da = _to_cr(_v(inc, "depreciationAndAmortization"))
        interest = _to_cr(_v(inc, "interestExpense"))
        tax = _to_cr(_v(inc, "incomeTaxExpense"))
        pat = _to_cr(_v(inc, "netIncome"))
        ebitda = ebit + da if ebit and da else revenue * 0.20

        bs = balance_sheets[i] if i < len(balance_sheets) else {}
        total_debt = _to_cr(_v(bs, "totalDebt") or _v(bs, "longTermDebt"))
        cash = _to_cr(_v(bs, "cash") or _v(bs, "cashAndCashEquivalents"))
        net_debt = total_debt - cash
        receivables = _to_cr(_v(bs, "netReceivables"))
        inventory = _to_cr(_v(bs, "inventory"))
        payables = _to_cr(_v(bs, "accountsPayable"))
        nwc = receivables + inventory - payables

        cf = cashflows[i] if i < len(cashflows) else {}
        capex_raw = _v(cf, "capitalExpenditures")
        capex = abs(_to_cr(capex_raw)) if capex_raw else revenue * 0.05

        if revenue <= 0:
            continue

        history.append(IndiaAnnualData(
            fiscal_year=fy,
            revenue_cr=revenue,
            ebitda_cr=ebitda,
            ebit_cr=ebit,
            pat_cr=pat,
            depreciation_cr=da,
            capex_cr=capex,
            interest_expense_cr=interest,
            tax_cr=tax,
            net_debt_cr=net_debt,
            shares_outstanding_cr=shares_cr,
            nwc_cr=nwc,
        ))

    # Yahoo Finance returns newest first — reverse so history is oldest→newest
    history.reverse()

    if not history:
        raise ValueError(f"No usable annual financials for {symbol}. Try NSE/BSE ticker directly.")

    # Attach current shares to all years (Yahoo only gives one value)
    for yr in history:
        yr.shares_outstanding_cr = shares_cr

    return IndiaCompanyData(
        symbol=symbol.upper(),
        company_name=company_name,
        sector=sector if sector != "Default" else detected_sector,
        history=history,
    )
