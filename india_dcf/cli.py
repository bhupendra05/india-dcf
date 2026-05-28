"""CLI for india-dcf."""
from __future__ import annotations
import sys
import click
from .params import IndiaWACCParams, IndiaTaxParams, SECTOR_BETA
from .wacc import calculate_wacc, wacc_components
from .dcf import IndiaDCFAssumptions, run_india_dcf
from .fetch import fetch_india_financials

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    console = Console()
    _RICH = True
except ImportError:
    console = None
    _RICH = False


def _cr(v): return f"₹{v:,.0f} Cr" if v is not None else "N/A"
def _pct(v): return f"{v*100:.1f}%" if v is not None else "N/A"


@click.group()
def cli():
    """india-dcf — India-calibrated DCF valuation (G-Sec risk-free, India ERP, correct tax)."""


@cli.command("value")
@click.argument("symbol")
@click.option("--sector", default="Default", help="Sector for beta/WC norms")
@click.option("--wacc", "wacc_override", default=None, type=float, help="Override WACC (e.g. 0.12)")
@click.option("--beta", default=None, type=float, help="Override beta")
@click.option("--growth", default=None, type=float, help="Revenue growth override")
@click.option("--terminal-growth", default=0.055, help="Terminal growth (default: 5.5% for India)")
@click.option("--exit-multiple", default=10.0)
@click.option("--years", default=5)
def value_cmd(symbol, sector, wacc_override, beta, growth, terminal_growth, exit_multiple, years):
    """Run India DCF for SYMBOL (NSE ticker).

    Example: india-dcf value INFY --sector "IT Services"
    """
    if console: console.print(f"[dim]Fetching financials for {symbol.upper()}...[/]")
    try:
        company = fetch_india_financials(symbol, sector=sector)
    except Exception as e:
        click.echo(f"Error: {e}", err=True); sys.exit(1)

    wacc_params = IndiaWACCParams(beta=beta or SECTOR_BETA.get(sector, 1.0))
    wacc = wacc_override or calculate_wacc(company, wacc_params)

    asmp = IndiaDCFAssumptions(
        projection_years=years,
        revenue_growth_rates=[growth] * years if growth else None,
        terminal_growth_rate=terminal_growth,
        exit_ebitda_multiple=exit_multiple,
    )

    result = run_india_dcf(company, asmp, wacc)

    if not _RICH:
        print(f"WACC: {_pct(wacc)}  |  Implied Price (blended): ₹{result.implied_price_blended:,.2f}")
        return

    comps = wacc_components(company, wacc_params)
    console.print(Panel(
        f"[bold cyan]{company.company_name}[/] ({company.symbol}) · {company.sector}\n"
        f"Base Year: {result.base_year}  ·  Revenue: {_cr(result.base_revenue_cr)}\n"
        f"WACC: [bold yellow]{_pct(result.wacc)}[/]  ·  Tax Rate: {_pct(result.tax_rate)}\n"
        f"Risk-Free (G-Sec): {_pct(comps['risk_free_rate_gsec'])}  ·  India ERP: {_pct(comps['india_erp'])}  ·  Beta: {comps['sector_beta']:.2f}",
        title="[bold]India DCF Valuation (₹ Crore)[/]", border_style="blue",
    ))

    t = Table(title="Projections", box=box.SIMPLE_HEAVY)
    t.add_column("Period", style="bold")
    t.add_column("Revenue", justify="right")
    t.add_column("Growth", justify="right")
    t.add_column("EBITDA", justify="right")
    t.add_column("UFCF", justify="right")
    t.add_column("PV of UFCF", justify="right")
    for p in result.projections:
        t.add_row(p.year_label, _cr(p.revenue_cr), _pct(p.revenue_growth),
                  _cr(p.ebitda_cr), _cr(p.ufcf_cr), _cr(p.pv_ufcf_cr))
    console.print(t)

    t2 = Table(title="Valuation", box=box.SIMPLE_HEAVY, show_lines=True)
    t2.add_column("Metric", style="bold")
    t2.add_column("Gordon Growth", justify="right")
    t2.add_column("Exit Multiple", justify="right")
    t2.add_column("Blended", justify="right", style="bold yellow")
    t2.add_row("PV of FCFs", _cr(result.sum_pv_ufcf_cr), _cr(result.sum_pv_ufcf_cr), _cr(result.sum_pv_ufcf_cr))
    t2.add_row("PV of Terminal Value", _cr(result.pv_tv_gordon_cr), _cr(result.pv_tv_exit_cr), "")
    t2.add_row("Enterprise Value", _cr(result.ev_gordon_cr), _cr(result.ev_exit_cr), _cr(result.ev_blended_cr))
    t2.add_row("(−) Net Debt", _cr(result.net_debt_cr), "", "")
    t2.add_row("[bold]Implied Price (₹)[/]",
               f"[green]₹{result.implied_price_gordon:,.2f}[/]",
               f"[green]₹{result.implied_price_exit:,.2f}[/]",
               f"[bold green]₹{result.implied_price_blended:,.2f}[/]")
    console.print(t2)


@cli.command("sectors")
def sectors_cmd():
    """List available sectors and their default beta."""
    click.echo("\nSector           Beta")
    click.echo("-" * 25)
    for s, b in SECTOR_BETA.items():
        click.echo(f"  {s:<20} {b:.2f}")


def main():
    cli()
