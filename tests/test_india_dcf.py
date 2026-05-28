"""Tests for india-dcf."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from india_dcf.params import IndiaTaxParams, IndiaWACCParams, IndiaWorkingCapitalNorms, SECTOR_BETA, SECTOR_PARAMS
from india_dcf.financials import IndiaAnnualData, IndiaCompanyData
from india_dcf.wacc import calculate_wacc, wacc_components, estimate_cost_of_debt, estimate_debt_weight
from india_dcf.dcf import IndiaDCFAssumptions, run_india_dcf, IndiaDCFResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_annual(fy="FY2024", revenue=10000, ebitda=2000, ebit=1600, pat=1200,
                da=400, capex=500, interest=100, tax=400, net_debt=500,
                shares=400, nwc=1000):
    return IndiaAnnualData(
        fiscal_year=fy, revenue_cr=revenue, ebitda_cr=ebitda, ebit_cr=ebit,
        pat_cr=pat, depreciation_cr=da, capex_cr=capex,
        interest_expense_cr=interest, tax_cr=tax, net_debt_cr=net_debt,
        shares_outstanding_cr=shares, nwc_cr=nwc,
    )


def make_company(n_years=3, sector="IT Services") -> IndiaCompanyData:
    base_rev = 8000
    history = []
    for i in range(n_years):
        rev = base_rev * (1.15 ** i)
        history.append(make_annual(
            fy=f"FY{2022 + i}", revenue=rev, ebitda=rev * 0.20, ebit=rev * 0.16,
            pat=rev * 0.12, da=rev * 0.04, capex=rev * 0.05,
            interest=rev * 0.01, tax=rev * 0.04, net_debt=500, shares=400,
        ))
    return IndiaCompanyData(symbol="TEST", company_name="Test Co", sector=sector, history=history)


# ── Tax params ────────────────────────────────────────────────────────────────

def test_india_tax_effective_rate():
    t = IndiaTaxParams()
    assert abs(t.effective_rate - 0.25168) < 0.001

def test_india_tax_mat_rate():
    t = IndiaTaxParams()
    assert abs(t.mat_effective_rate - 0.1716) < 0.001

def test_india_tax_custom():
    t = IndiaTaxParams(base_rate=0.25, surcharge=0.0, cess=0.0)
    assert abs(t.effective_rate - 0.25) < 1e-6

def test_india_wacc_params_defaults():
    p = IndiaWACCParams()
    assert p.risk_free_rate == 0.071
    assert p.equity_risk_premium == 0.075

def test_india_wacc_cost_of_equity():
    p = IndiaWACCParams(beta=1.2)
    ke = p.cost_of_equity
    assert abs(ke - (0.071 + 1.2 * 0.075)) < 1e-6

def test_sector_beta_coverage():
    assert "IT Services" in SECTOR_BETA
    assert "Banking" in SECTOR_BETA
    assert "FMCG" in SECTOR_BETA
    assert SECTOR_BETA["FMCG"] < SECTOR_BETA["Banking"]

def test_sector_beta_defaults():
    assert "Default" in SECTOR_BETA
    assert SECTOR_BETA["Default"] == 1.0

def test_sector_params_nwc():
    it = SECTOR_PARAMS["IT Services"]
    assert it.nwc_days == 60.0  # 90 receivable + 0 inventory - 30 payable
    assert 0 < it.nwc_pct_revenue < 0.3

def test_sector_params_fmcg():
    fmcg = SECTOR_PARAMS["FMCG"]
    assert fmcg.inventory_days == 60

def test_nwc_pct_calculation():
    n = IndiaWorkingCapitalNorms(receivable_days=90, inventory_days=45, payable_days=45)
    assert abs(n.nwc_days - 90) < 1e-6
    assert abs(n.nwc_pct_revenue - 90/365) < 1e-6


# ── Financials ────────────────────────────────────────────────────────────────

def test_annual_data_margins():
    yr = make_annual(revenue=10000, ebitda=2500, ebit=2000, pat=1500)
    assert abs(yr.ebitda_margin - 0.25) < 1e-6
    assert abs(yr.ebit_margin - 0.20) < 1e-6
    assert abs(yr.pat_margin - 0.15) < 1e-6

def test_annual_data_tax_rate():
    # pat + tax = pretax; effective = tax / pretax
    yr = make_annual(pat=1200, tax=400)
    rate = yr.effective_tax_rate
    assert 0.10 < rate < 0.40

def test_annual_data_capex_pct():
    yr = make_annual(revenue=10000, capex=500)
    assert abs(yr.capex_pct - 0.05) < 1e-6

def test_annual_data_da_pct():
    yr = make_annual(revenue=10000, da=400)
    assert abs(yr.da_pct - 0.04) < 1e-6

def test_company_latest():
    co = make_company(3)
    assert co.latest().fiscal_year == "FY2024"

def test_company_avg_revenue_growth():
    co = make_company(3)
    growth = co.avg_revenue_growth()
    assert abs(growth - 0.15) < 0.01

def test_company_avg_ebitda_margin():
    co = make_company(3)
    margin = co.avg_ebitda_margin()
    assert abs(margin - 0.20) < 0.01

def test_company_avg_capex_pct():
    co = make_company(3)
    pct = co.avg_capex_pct()
    assert abs(pct - 0.05) < 0.01

def test_company_single_year_growth():
    co = make_company(1)
    assert co.avg_revenue_growth() == 0.12  # fallback

def test_company_avg_tax_rate_valid():
    co = make_company(3)
    rate = co.avg_tax_rate()
    assert 0.10 < rate < 0.40


# ── WACC ──────────────────────────────────────────────────────────────────────

def test_calculate_wacc_basic():
    co = make_company()
    p = IndiaWACCParams()
    wacc = calculate_wacc(co, p)
    assert 0.08 < wacc < 0.18

def test_wacc_uses_sector_beta():
    co = make_company(sector="FMCG")
    p = IndiaWACCParams()  # beta=1.0 → will use sector lookup
    wacc_fmcg = calculate_wacc(co, p)
    co2 = make_company(sector="Metals")
    wacc_metals = calculate_wacc(co2, p)
    assert wacc_fmcg < wacc_metals

def test_wacc_zero_debt():
    # Company with no debt should have lower WACC (no tax shield but also Ke only)
    co = make_company()
    for yr in co.history:
        yr.net_debt_cr = 0
    p = IndiaWACCParams(target_debt_weight=0.0)
    wacc = calculate_wacc(co, p)
    ke = p.risk_free_rate + SECTOR_BETA["IT Services"] * p.equity_risk_premium
    assert abs(wacc - ke) < 0.001

def test_estimate_cost_of_debt_floor():
    co = make_company()
    kd = estimate_cost_of_debt(co)
    assert kd >= 0.075  # India floor

def test_estimate_debt_weight_no_debt():
    co = make_company()
    for yr in co.history:
        yr.net_debt_cr = -1000  # net cash
    w = estimate_debt_weight(co)
    assert w == 0.0

def test_wacc_components_keys():
    co = make_company()
    p = IndiaWACCParams()
    comps = wacc_components(co, p)
    assert "risk_free_rate_gsec" in comps
    assert "india_erp" in comps
    assert "sector_beta" in comps
    assert "wacc" in comps

def test_wacc_components_gsec():
    co = make_company()
    p = IndiaWACCParams(risk_free_rate=0.071)
    comps = wacc_components(co, p)
    assert comps["risk_free_rate_gsec"] == 0.071


# ── DCF ───────────────────────────────────────────────────────────────────────

def test_run_dcf_basic():
    co = make_company()
    asmp = IndiaDCFAssumptions(projection_years=5)
    wacc = 0.12
    result = run_india_dcf(co, asmp, wacc)
    assert isinstance(result, IndiaDCFResult)
    assert result.implied_price_blended > 0

def test_dcf_projection_count():
    co = make_company()
    asmp = IndiaDCFAssumptions(projection_years=5)
    result = run_india_dcf(co, asmp, 0.12)
    assert len(result.projections) == 5

def test_dcf_10_year_projection():
    co = make_company()
    asmp = IndiaDCFAssumptions(projection_years=10)
    result = run_india_dcf(co, asmp, 0.12)
    assert len(result.projections) == 10

def test_dcf_year_labels():
    co = make_company()
    result = run_india_dcf(co, IndiaDCFAssumptions(projection_years=3), 0.12)
    labels = [p.year_label for p in result.projections]
    assert labels == ["FY+1", "FY+2", "FY+3"]

def test_dcf_terminal_growth_india():
    asmp = IndiaDCFAssumptions()
    assert asmp.terminal_growth_rate == 0.055  # India: 5.5% not US 2.5%

def test_dcf_custom_growth_rate():
    co = make_company()
    asmp = IndiaDCFAssumptions(projection_years=3, revenue_growth_rates=[0.20, 0.18, 0.15])
    result = run_india_dcf(co, asmp, 0.12)
    assert abs(result.projections[0].revenue_growth - 0.20) < 1e-6
    assert abs(result.projections[1].revenue_growth - 0.18) < 1e-6

def test_dcf_ev_structure():
    co = make_company()
    result = run_india_dcf(co, IndiaDCFAssumptions(), 0.12)
    # EV = sum_pv_ufcf + pv_tv
    assert abs(result.ev_gordon_cr - (result.sum_pv_ufcf_cr + result.pv_tv_gordon_cr)) < 1.0
    assert abs(result.ev_exit_cr - (result.sum_pv_ufcf_cr + result.pv_tv_exit_cr)) < 1.0

def test_dcf_blended_is_average():
    co = make_company()
    result = run_india_dcf(co, IndiaDCFAssumptions(), 0.12)
    blended = (result.ev_gordon_cr + result.ev_exit_cr) / 2
    assert abs(result.ev_blended_cr - blended) < 1.0

def test_dcf_equity_value():
    co = make_company()
    result = run_india_dcf(co, IndiaDCFAssumptions(), 0.12)
    eq = result.ev_blended_cr - result.net_debt_cr
    assert abs(result.equity_value_blended_cr - eq) < 1.0

def test_dcf_implied_price():
    co = make_company()
    result = run_india_dcf(co, IndiaDCFAssumptions(), 0.12)
    expected = result.equity_value_blended_cr / result.shares_outstanding_cr
    assert abs(result.implied_price_blended - expected) < 0.01

def test_dcf_high_wacc_lower_price():
    co = make_company()
    asmp = IndiaDCFAssumptions()
    r1 = run_india_dcf(co, asmp, 0.10)
    r2 = run_india_dcf(co, asmp, 0.16)
    assert r1.implied_price_blended > r2.implied_price_blended

def test_dcf_wacc_must_exceed_terminal_growth():
    co = make_company()
    asmp = IndiaDCFAssumptions(terminal_growth_rate=0.055)
    result = run_india_dcf(co, asmp, 0.055)  # wacc == g, uses fallback ×20
    assert result.implied_price_blended > 0  # shouldn't crash

def test_dcf_no_history_raises():
    co = IndiaCompanyData(symbol="EMPTY", company_name="Empty", history=[])
    with pytest.raises(ValueError, match="No financial data"):
        run_india_dcf(co, IndiaDCFAssumptions(), 0.12)

def test_dcf_growth_rate_padding():
    co = make_company()
    # Provide only 2 growth rates but projection_years=5 → should pad last rate
    asmp = IndiaDCFAssumptions(projection_years=5, revenue_growth_rates=[0.20, 0.15])
    result = run_india_dcf(co, asmp, 0.12)
    assert len(result.projections) == 5
    assert abs(result.projections[4].revenue_growth - 0.15) < 1e-6

def test_dcf_base_year_metadata():
    co = make_company(3)
    result = run_india_dcf(co, IndiaDCFAssumptions(), 0.12)
    assert result.base_year == "FY2024"
    assert result.symbol == "TEST"

def test_dcf_assumptions_custom_tax():
    co = make_company()
    asmp = IndiaDCFAssumptions(tax_rate=0.35)
    result = run_india_dcf(co, asmp, 0.12)
    assert abs(result.tax_rate - 0.35) < 1e-6
