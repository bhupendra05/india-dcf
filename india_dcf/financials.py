"""India company financials — INR Crore denominated."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class IndiaAnnualData:
    fiscal_year: str        # "FY2023", "FY2022"
    revenue_cr: float
    ebitda_cr: float
    ebit_cr: float
    pat_cr: float
    depreciation_cr: float
    capex_cr: float
    interest_expense_cr: float
    tax_cr: float
    net_debt_cr: float
    shares_outstanding_cr: float   # in Crore shares
    nwc_cr: float = 0.0           # Net Working Capital

    @property
    def ebitda_margin(self): return self.ebitda_cr / self.revenue_cr if self.revenue_cr else None
    @property
    def ebit_margin(self): return self.ebit_cr / self.revenue_cr if self.revenue_cr else None
    @property
    def pat_margin(self): return self.pat_cr / self.revenue_cr if self.revenue_cr else None
    @property
    def effective_tax_rate(self):
        pretax = self.pat_cr + self.tax_cr
        if pretax <= 0: return 0.25
        return max(0, min(0.45, self.tax_cr / pretax))
    @property
    def capex_pct(self): return self.capex_cr / self.revenue_cr if self.revenue_cr else 0.05
    @property
    def da_pct(self): return self.depreciation_cr / self.revenue_cr if self.revenue_cr else 0.04


@dataclass
class IndiaCompanyData:
    symbol: str
    company_name: str
    sector: str = "Default"
    history: List[IndiaAnnualData] = field(default_factory=list)

    def latest(self) -> Optional[IndiaAnnualData]:
        return self.history[-1] if self.history else None

    def avg_revenue_growth(self) -> float:
        if len(self.history) < 2: return 0.12  # India default higher than US
        rates = []
        for i in range(1, len(self.history)):
            prev, curr = self.history[i-1].revenue_cr, self.history[i].revenue_cr
            if prev > 0: rates.append((curr - prev) / prev)
        return sum(rates) / len(rates) if rates else 0.12

    def avg_ebitda_margin(self) -> float:
        ms = [y.ebitda_margin for y in self.history if y.ebitda_margin]
        return sum(ms) / len(ms) if ms else 0.20

    def avg_capex_pct(self) -> float:
        ps = [y.capex_pct for y in self.history if y.revenue_cr > 0]
        return sum(ps) / len(ps) if ps else 0.05

    def avg_da_pct(self) -> float:
        ps = [y.da_pct for y in self.history if y.revenue_cr > 0]
        return sum(ps) / len(ps) if ps else 0.04

    def avg_tax_rate(self) -> float:
        rates = [y.effective_tax_rate for y in self.history]
        valid = [r for r in rates if 0.10 < r < 0.40]
        return sum(valid) / len(valid) if valid else 0.2517  # India effective rate
