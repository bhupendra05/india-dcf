# india-dcf

**India-calibrated DCF valuation engine for NSE/BSE listed companies.**

Most DCF tools are built for US markets — wrong risk-free rate, wrong ERP, wrong tax structure, wrong terminal growth assumptions. `india-dcf` fixes all of that.

```bash
pip install india-dcf
india-dcf value INFY --sector "IT Services"
india-dcf value RELIANCE --sector Energy --years 7
```

## Why India needs its own DCF model

| Parameter | US (typical) | India (this library) |
|-----------|-------------|----------------------|
| Risk-free rate | 4.3% (10Y Treasury) | **7.1% (10Y G-Sec)** |
| Equity Risk Premium | 5.5% | **7.5% (Damodaran India ERP)** |
| Corporate tax rate | 21% | **25.168%** (22% + 10% surcharge + 4% cess) |
| Terminal growth | 2.5% | **5.5%** (India inflation-adjusted) |
| Working capital | 30–45 days | **60–120 days** (sector-dependent) |
| Currency | USD | **₹ Crore** |

## Installation

```bash
pip install india-dcf          # basic
pip install india-dcf[rich]    # with colourful terminal output
```

## CLI Usage

```bash
# Full DCF valuation
india-dcf value INFY
india-dcf value TCS --sector "IT Services"
india-dcf value HDFCBANK --sector Banking --wacc 0.13
india-dcf value ASIANPAINT --sector FMCG --growth 0.12 --years 7

# List available sectors with beta
india-dcf sectors
```

### Sample Output

```
╭─ India DCF Valuation (₹ Crore) ─────────────────────────────────────╮
│ Infosys Limited (INFY) · IT Services                                  │
│ Base Year: FY2024  ·  Revenue: ₹1,53,670 Cr                           │
│ WACC: 12.8%  ·  Tax Rate: 25.2%                                       │
│ Risk-Free (G-Sec): 7.1%  ·  India ERP: 7.5%  ·  Beta: 0.85           │
╰───────────────────────────────────────────────────────────────────────╯

  Period    Revenue        Growth    EBITDA      UFCF      PV of UFCF
 ─────────────────────────────────────────────────────────────────────
  FY+1      ₹1,72,117 Cr  12.0%    ₹36,145 Cr  ₹28,632 Cr  ₹25,389 Cr
  FY+2      ₹1,91,650 Cr  11.4%    ₹40,246 Cr  ₹31,895 Cr  ₹25,049 Cr
  ...
```

## Python API

```python
from india_dcf import run_india_dcf, IndiaDCFAssumptions, calculate_wacc, IndiaWACCParams
from india_dcf.fetch import fetch_india_financials

# Fetch live data
company = fetch_india_financials("INFY", sector="IT Services")

# Customize WACC
wacc_params = IndiaWACCParams(beta=0.85)
wacc = calculate_wacc(company, wacc_params)

# Run DCF
assumptions = IndiaDCFAssumptions(
    projection_years=5,
    terminal_growth_rate=0.055,   # India: 5.5% (not US 2.5%)
    exit_ebitda_multiple=18.0,
)
result = run_india_dcf(company, assumptions, wacc)

print(f"Implied Price (Blended): ₹{result.implied_price_blended:,.2f}")
print(f"Enterprise Value: ₹{result.ev_blended_cr:,.0f} Cr")
print(f"WACC: {result.wacc * 100:.1f}%")
```

### Using your own financials (no API call)

```python
from india_dcf.financials import IndiaCompanyData, IndiaAnnualData
from india_dcf import run_india_dcf, IndiaDCFAssumptions

company = IndiaCompanyData(
    symbol="PRIVATE_CO",
    company_name="My Portfolio Company",
    sector="Pharma",
    history=[
        IndiaAnnualData("FY2022", revenue_cr=800, ebitda_cr=160, ebit_cr=130,
                        pat_cr=95, depreciation_cr=30, capex_cr=40,
                        interest_expense_cr=10, tax_cr=32, net_debt_cr=100,
                        shares_outstanding_cr=50),
        IndiaAnnualData("FY2023", revenue_cr=960, ebitda_cr=202, ebit_cr=165,
                        pat_cr=122, depreciation_cr=37, capex_cr=48,
                        interest_expense_cr=9, tax_cr=41, net_debt_cr=80,
                        shares_outstanding_cr=50),
    ]
)
result = run_india_dcf(company, IndiaDCFAssumptions(), wacc=0.13)
```

## India-Specific Features

### Tax Structure
```python
from india_dcf.params import IndiaTaxParams
t = IndiaTaxParams()
print(t.effective_rate)     # 0.25168 → 25.168%
print(t.mat_effective_rate) # 0.17160 → 17.16% (MAT regime)
```

### WACC with G-Sec Risk-Free
```python
from india_dcf import IndiaWACCParams
p = IndiaWACCParams(
    risk_free_rate=0.071,        # RBI 10Y G-Sec
    equity_risk_premium=0.075,   # Damodaran India ERP
    beta=0.85,                   # IT Services levered beta
)
# Ke = 7.1% + 0.85 × 7.5% = 13.475%
```

### Sector Betas & Working Capital Norms
```
Sector          Beta   WC Days
IT Services     0.85     60
FMCG            0.65     45
Pharma          0.80    120
Banking         1.20      0
Auto            1.10     15
Metals          1.40     60
Real Estate     1.50    335
```

## Sectors

```
$ india-dcf sectors

Sector                Beta
─────────────────────────
  IT Services         0.85
  FMCG                0.65
  Pharma              0.80
  Banking             1.20
  NBFC                1.30
  Auto                1.10
  Metals              1.40
  Real Estate         1.50
  Infra               0.90
  Energy              0.95
  Default             1.00
```

## Contributing

PRs welcome. Key areas: sector parameter refinement, SEBI filing integration, sensitivity analysis (tornado charts), scenario modelling.

## License

MIT
