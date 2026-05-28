"""
India DCF engine — INR Crore denominated, India-specific assumptions.

UFCF = EBIT(1-t) + D&A − CapEx − ΔNWC
India-specific: higher WC days, MAT consideration, G-Sec risk-free rate.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .financials import IndiaCompanyData
from .params import IndiaWorkingCapitalNorms, SECTOR_PARAMS


@dataclass
class IndiaDCFAssumptions:
    projection_years: int = 5
    revenue_growth_rates: Optional[List[float]] = None
    ebitda_margin: Optional[float] = None
    capex_pct_revenue: Optional[float] = None
    da_pct_revenue: Optional[float] = None
    nwc_pct_revenue: Optional[float] = None   # if None, derived from sector norms
    terminal_growth_rate: float = 0.055        # India: higher (5.5%) vs US (2.5%) due to inflation
    exit_ebitda_multiple: float = 10.0
    tax_rate: Optional[float] = None
    use_mat: bool = False                       # Use MAT rate if company is MAT-paying


@dataclass
class IndiaYearProjection:
    year_label: str
    revenue_cr: float
    revenue_growth: float
    ebitda_cr: float
    ebit_cr: float
    noplat_cr: float
    depreciation_cr: float
    capex_cr: float
    delta_nwc_cr: float
    ufcf_cr: float
    pv_factor: float
    pv_ufcf_cr: float


@dataclass
class IndiaDCFResult:
    symbol: str
    company_name: str
    currency: str = "INR"
    unit: str = "Crore"
    base_revenue_cr: float = 0.0
    base_year: str = ""
    wacc: float = 0.0
    tax_rate: float = 0.0
    terminal_growth_rate: float = 0.0
    exit_multiple: float = 0.0

    projections: List[IndiaYearProjection] = field(default_factory=list)
    terminal_ebitda_cr: float = 0.0
    terminal_ufcf_cr: float = 0.0
    tv_gordon_cr: float = 0.0
    tv_exit_cr: float = 0.0
    pv_tv_gordon_cr: float = 0.0
    pv_tv_exit_cr: float = 0.0
    sum_pv_ufcf_cr: float = 0.0

    ev_gordon_cr: float = 0.0
    ev_exit_cr: float = 0.0
    ev_blended_cr: float = 0.0
    net_debt_cr: float = 0.0
    shares_outstanding_cr: float = 0.0
    equity_value_gordon_cr: float = 0.0
    equity_value_exit_cr: float = 0.0
    equity_value_blended_cr: float = 0.0
    implied_price_gordon: float = 0.0
    implied_price_exit: float = 0.0
    implied_price_blended: float = 0.0


def run_india_dcf(
    company: IndiaCompanyData,
    assumptions: IndiaDCFAssumptions,
    wacc: float,
) -> IndiaDCFResult:
    latest = company.latest()
    if latest is None:
        raise ValueError(f"No financial data for {company.symbol}")

    tax_rate = assumptions.tax_rate or company.avg_tax_rate()
    ebitda_margin = assumptions.ebitda_margin or company.avg_ebitda_margin()
    capex_pct = assumptions.capex_pct_revenue or company.avg_capex_pct()
    da_pct = assumptions.da_pct_revenue or company.avg_da_pct()

    # NWC: use sector norms if not specified
    if assumptions.nwc_pct_revenue is not None:
        nwc_pct = assumptions.nwc_pct_revenue
    else:
        norms: IndiaWorkingCapitalNorms = SECTOR_PARAMS.get(company.sector, SECTOR_PARAMS["Default"])
        nwc_pct = norms.nwc_pct_revenue

    avg_growth = company.avg_revenue_growth()
    n = assumptions.projection_years

    if assumptions.revenue_growth_rates:
        growth_rates = list(assumptions.revenue_growth_rates)
        while len(growth_rates) < n:
            growth_rates.append(growth_rates[-1])
        growth_rates = growth_rates[:n]
    else:
        # Fade from historical avg to terminal + 2% over 5 years
        start = avg_growth
        end = assumptions.terminal_growth_rate + 0.02
        growth_rates = [start + (end - start) * (i / max(n - 1, 1)) for i in range(n)]

    revenue = latest.revenue_cr
    projections = []
    sum_pv = 0.0

    for i in range(n):
        g = growth_rates[i]
        prev_rev = revenue
        revenue = revenue * (1 + g)
        delta_nwc = (revenue - prev_rev) * nwc_pct
        ebitda = revenue * ebitda_margin
        da = revenue * da_pct
        ebit = ebitda - da
        noplat = ebit * (1 - tax_rate)
        capex = revenue * capex_pct
        ufcf = noplat + da - capex - delta_nwc
        pv_f = 1.0 / (1 + wacc) ** (i + 1)
        pv_ufcf = ufcf * pv_f
        sum_pv += pv_ufcf
        projections.append(IndiaYearProjection(
            year_label=f"FY+{i+1}", revenue_cr=revenue, revenue_growth=g,
            ebitda_cr=ebitda, ebit_cr=ebit, noplat_cr=noplat,
            depreciation_cr=da, capex_cr=capex, delta_nwc_cr=delta_nwc,
            ufcf_cr=ufcf, pv_factor=pv_f, pv_ufcf_cr=pv_ufcf,
        ))

    terminal_ebitda = revenue * ebitda_margin
    terminal_ufcf = projections[-1].ufcf_cr
    g_term = assumptions.terminal_growth_rate
    pv_n = 1.0 / (1 + wacc) ** n

    tv_gordon = terminal_ufcf * (1 + g_term) / (wacc - g_term) if wacc > g_term else terminal_ufcf * 20
    tv_exit = terminal_ebitda * assumptions.exit_ebitda_multiple

    ev_gordon = sum_pv + tv_gordon * pv_n
    ev_exit = sum_pv + tv_exit * pv_n
    ev_blended = (ev_gordon + ev_exit) / 2

    nd = latest.net_debt_cr
    sh = latest.shares_outstanding_cr

    def _eq(ev): return ev - nd
    def _price(ev): return _eq(ev) / sh if sh > 0 else 0

    return IndiaDCFResult(
        symbol=company.symbol, company_name=company.company_name,
        base_revenue_cr=latest.revenue_cr, base_year=latest.fiscal_year,
        wacc=wacc, tax_rate=tax_rate, terminal_growth_rate=g_term,
        exit_multiple=assumptions.exit_ebitda_multiple,
        projections=projections,
        terminal_ebitda_cr=terminal_ebitda, terminal_ufcf_cr=terminal_ufcf,
        tv_gordon_cr=tv_gordon, tv_exit_cr=tv_exit,
        pv_tv_gordon_cr=tv_gordon * pv_n, pv_tv_exit_cr=tv_exit * pv_n,
        sum_pv_ufcf_cr=sum_pv,
        ev_gordon_cr=ev_gordon, ev_exit_cr=ev_exit, ev_blended_cr=ev_blended,
        net_debt_cr=nd, shares_outstanding_cr=sh,
        equity_value_gordon_cr=_eq(ev_gordon), equity_value_exit_cr=_eq(ev_exit),
        equity_value_blended_cr=_eq(ev_blended),
        implied_price_gordon=_price(ev_gordon), implied_price_exit=_price(ev_exit),
        implied_price_blended=_price(ev_blended),
    )
