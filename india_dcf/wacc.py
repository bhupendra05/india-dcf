"""India WACC calculator — uses G-Sec risk-free rate and India ERP."""
from __future__ import annotations
from .params import IndiaWACCParams, IndiaTaxParams, SECTOR_BETA
from .financials import IndiaCompanyData


def estimate_cost_of_debt(company: IndiaCompanyData) -> float:
    """Estimate Kd from interest expense / gross debt. India floor at 7.5%."""
    total_interest = sum(y.interest_expense_cr for y in company.history if y.interest_expense_cr > 0)
    total_debt = sum(max(0, y.net_debt_cr) for y in company.history if y.net_debt_cr > 0)
    if total_interest > 0 and total_debt > 0:
        return max(0.075, min(0.16, total_interest / total_debt))
    return 0.10  # India default: 10% cost of debt


def estimate_debt_weight(company: IndiaCompanyData) -> float:
    latest = company.latest()
    if latest is None: return 0.25
    net_debt = latest.net_debt_cr
    if net_debt <= 0: return 0.0
    proxy_equity = latest.ebitda_cr * 7.0   # 7× EBITDA proxy for Indian market
    if proxy_equity <= 0: return 0.25
    return max(0.0, min(0.65, net_debt / (net_debt + proxy_equity)))


def calculate_wacc(
    company: IndiaCompanyData,
    params: IndiaWACCParams,
    tax_params: IndiaTaxParams = None,
) -> float:
    """
    India WACC = Ke × (E/V) + Kd × (1-t) × (D/V)

    Ke = G-Sec + β × India ERP
    Default Rf = 7.1% (10Y G-Sec), ERP = 7.5% (Damodaran India)
    """
    if tax_params is None:
        tax_params = IndiaTaxParams()

    # Sector-adjusted beta
    beta = params.beta
    if beta == 1.0:
        beta = SECTOR_BETA.get(company.sector, 1.0)
    ke = params.risk_free_rate + beta * params.equity_risk_premium

    kd = params.cost_of_debt if params.cost_of_debt else estimate_cost_of_debt(company)
    t = company.avg_tax_rate()
    kd_at = kd * (1 - t)

    d_weight = params.target_debt_weight if params.target_debt_weight is not None else estimate_debt_weight(company)
    e_weight = 1.0 - d_weight

    wacc = e_weight * ke + d_weight * kd_at
    return round(wacc, 6)


def wacc_components(company: IndiaCompanyData, params: IndiaWACCParams) -> dict:
    beta = SECTOR_BETA.get(company.sector, params.beta) if params.beta == 1.0 else params.beta
    ke = params.risk_free_rate + beta * params.equity_risk_premium
    kd = params.cost_of_debt or estimate_cost_of_debt(company)
    t = company.avg_tax_rate()
    d_weight = params.target_debt_weight if params.target_debt_weight is not None else estimate_debt_weight(company)
    return {
        "risk_free_rate_gsec": params.risk_free_rate,
        "india_erp": params.equity_risk_premium,
        "sector_beta": beta,
        "cost_of_equity": round(ke, 4),
        "cost_of_debt_pretax": round(kd, 4),
        "cost_of_debt_aftertax": round(kd * (1 - t), 4),
        "tax_rate": round(t, 4),
        "debt_weight": round(d_weight, 4),
        "equity_weight": round(1 - d_weight, 4),
        "wacc": calculate_wacc(company, params),
    }
