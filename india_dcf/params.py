"""
India-specific DCF parameters — calibrated for Indian capital markets.

Key differences from US/global models:
- Risk-free rate = 10Y G-Sec yield (~7.1%) not US Treasury
- ERP = India-specific equity risk premium (7.5%) — higher country risk
- Corporate tax = 22% + 10% surcharge + 4% cess = 25.168% effective
- MAT = 15% of book profit (minimum alternate tax)
- Working capital days = 60–90 days (vs 30–45 US)
- Inflation = 5–6% (affects terminal growth rate floor)
- Revenue in ₹ Crore, fiscal year = April–March
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class IndiaTaxParams:
    """India corporate tax structure (FY2024 onwards)."""
    base_rate: float = 0.22          # New regime: 22% for domestic cos (Sec 115BAA)
    surcharge: float = 0.10          # 10% surcharge on tax
    cess: float = 0.04               # 4% health & education cess
    mat_rate: float = 0.15           # MAT at 15% of book profit
    mat_surcharge: float = 0.10
    mat_cess: float = 0.04

    @property
    def effective_rate(self) -> float:
        """25.168% effective for most large cos."""
        base = self.base_rate * (1 + self.surcharge) * (1 + self.cess)
        return round(base, 6)

    @property
    def mat_effective_rate(self) -> float:
        base = self.mat_rate * (1 + self.mat_surcharge) * (1 + self.mat_cess)
        return round(base, 6)


@dataclass
class IndiaWACCParams:
    """India-calibrated WACC inputs."""
    risk_free_rate: float = 0.071       # 10Y G-Sec yield (India, ~2025)
    equity_risk_premium: float = 0.075  # Damodaran India ERP (higher than US due to country risk)
    country_risk_premium: float = 0.0   # Already baked into ERP above
    beta: float = 1.0
    cost_of_debt: Optional[float] = None     # if None, estimated
    target_debt_weight: Optional[float] = None

    @property
    def cost_of_equity(self) -> float:
        return self.risk_free_rate + self.beta * self.equity_risk_premium


@dataclass
class IndiaWorkingCapitalNorms:
    """
    Indian industry working capital norms (days of revenue).
    Much higher than Western markets due to longer payment cycles.
    """
    receivable_days: float = 75.0   # Trade receivables / Revenue × 365
    inventory_days: float = 45.0    # Inventory / Revenue × 365
    payable_days: float = 45.0      # Trade payables / Revenue × 365

    @property
    def nwc_days(self) -> float:
        return self.receivable_days + self.inventory_days - self.payable_days

    @property
    def nwc_pct_revenue(self) -> float:
        return self.nwc_days / 365.0


# Sector-specific parameters for Indian market
SECTOR_PARAMS = {
    "IT Services": IndiaWorkingCapitalNorms(receivable_days=90, inventory_days=0, payable_days=30),
    "FMCG": IndiaWorkingCapitalNorms(receivable_days=30, inventory_days=60, payable_days=45),
    "Pharma": IndiaWorkingCapitalNorms(receivable_days=90, inventory_days=90, payable_days=60),
    "Banking": IndiaWorkingCapitalNorms(receivable_days=0, inventory_days=0, payable_days=0),
    "Auto": IndiaWorkingCapitalNorms(receivable_days=30, inventory_days=45, payable_days=60),
    "Infra": IndiaWorkingCapitalNorms(receivable_days=120, inventory_days=60, payable_days=60),
    "Real Estate": IndiaWorkingCapitalNorms(receivable_days=60, inventory_days=365, payable_days=90),
    "Default": IndiaWorkingCapitalNorms(),
}

SECTOR_BETA = {
    "IT Services": 0.85,
    "FMCG": 0.65,
    "Pharma": 0.80,
    "Banking": 1.20,
    "NBFC": 1.30,
    "Auto": 1.10,
    "Metals": 1.40,
    "Real Estate": 1.50,
    "Infra": 0.90,
    "Energy": 0.95,
    "Default": 1.00,
}
