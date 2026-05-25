"""
Módulo de indicadores financeiros (portado de finantial_ratios.js).
Todas as funções esperam números (float/int) e retornam valores numéricos.
"""

from typing import Union

Number = Union[int, float]

__all__ = [
    "current_ratio",
    "quick_ratio",
    "cash_ratio",
    "working_capital",
    "debt_to_equity",
    "debt_ratio",
    "interest_coverage",
    "dscr",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "roa",
    "roe",
    "roic",
    "asset_turnover",
    "inventory_turnover",
    "receivables_turnover",
    "payables_turnover",
    "dso",
    "dio",
    "dpo",
    "ccc",
    "free_cash_flow",
    "cash_flow_margin",
]

# ==============================
# 💧 LIQUIDEZ
# ==============================

def current_ratio(current_assets: Number, current_liabilities: Number) -> float:
    """Current Ratio (Liquidez Corrente): Current Assets / Current Liabilities"""
    return current_assets / current_liabilities


def quick_ratio(current_assets: Number, inventory: Number, current_liabilities: Number) -> float:
    """Quick Ratio (Liquidez Seca): (Current Assets - Inventory) / Current Liabilities"""
    return (current_assets - inventory) / current_liabilities


def cash_ratio(cash: Number, current_liabilities: Number) -> float:
    """Cash Ratio (Liquidez Imediata): Cash / Current Liabilities"""
    return cash / current_liabilities


def working_capital(current_assets: Number, current_liabilities: Number) -> float:
    """Working Capital (Capital de Giro): Current Assets - Current Liabilities"""
    return current_assets - current_liabilities

# ==============================
# 🏦 ENDIVIDAMENTO
# ==============================

def debt_to_equity(total_debt: Number, equity: Number) -> float:
    """Debt to Equity (D/E): Total Debt / Equity"""
    return total_debt / equity


def debt_ratio(total_debt: Number, total_assets: Number) -> float:
    """Debt Ratio: Total Debt / Total Assets"""
    return total_debt / total_assets


def interest_coverage(ebit: Number, interest_expense: Number) -> float:
    """Interest Coverage Ratio: EBIT / Interest Expense"""
    return ebit / interest_expense


def dscr(operating_income: Number, debt_service: Number) -> float:
    """Debt Service Coverage Ratio (DSCR): Operating Income / Debt Service"""
    return operating_income / debt_service

# ==============================
# 📈 RENTABILIDADE
# ==============================

def gross_margin(revenue: Number, cogs: Number) -> float:
    """Gross Margin: (Revenue - COGS) / Revenue"""
    return (revenue - cogs) / revenue


def operating_margin(operating_income: Number, revenue: Number) -> float:
    """Operating Margin: Operating Income / Revenue"""
    return operating_income / revenue


def net_margin(net_income: Number, revenue: Number) -> float:
    """Net Profit Margin: Net Income / Revenue"""
    return net_income / revenue


def roa(net_income: Number, total_assets: Number) -> float:
    """Return on Assets (ROA): Net Income / Total Assets"""
    return net_income / total_assets


def roe(net_income: Number, equity: Number) -> float:
    """Return on Equity (ROE): Net Income / Equity"""
    return net_income / equity


def roic(nopat: Number, invested_capital: Number) -> float:
    """Return on Invested Capital (ROIC): NOPAT / Invested Capital"""
    return nopat / invested_capital

# ==============================
# 🔄 EFICIÊNCIA
# ==============================

def asset_turnover(revenue: Number, total_assets: Number) -> float:
    """Asset Turnover: Revenue / Total Assets"""
    return revenue / total_assets


def inventory_turnover(cogs: Number, inventory: Number) -> float:
    """Inventory Turnover: COGS / Inventory"""
    return cogs / inventory


def receivables_turnover(revenue: Number, receivables: Number) -> float:
    """Receivables Turnover: Revenue / Accounts Receivable"""
    return revenue / receivables


def payables_turnover(cogs: Number, payables: Number) -> float:
    """Payables Turnover: COGS / Accounts Payable"""
    return cogs / payables

# ==============================
# ⏱️ CICLO DE CAIXA
# ==============================

def dso(receivables: Number, revenue: Number) -> float:
    """Days Sales Outstanding (DSO): (Accounts Receivable / Revenue) * 365"""
    return (receivables / revenue) * 365


def dio(inventory: Number, cogs: Number) -> float:
    """Days Inventory Outstanding (DIO): (Inventory / COGS) * 365"""
    return (inventory / cogs) * 365


def dpo(payables: Number, cogs: Number) -> float:
    """Days Payables Outstanding (DPO): (Accounts Payable / COGS) * 365"""
    return (payables / cogs) * 365


def ccc(dso_days: Number, dio_days: Number, dpo_days: Number) -> float:
    """Cash Conversion Cycle (CCC): DSO + DIO - DPO"""
    return dso_days + dio_days - dpo_days

# ==============================
# 💸 FLUXO DE CAIXA
# ==============================

def free_cash_flow(operating_cash_flow: Number, capex: Number) -> float:
    """Free Cash Flow (FCF): Operating Cash Flow - CAPEX"""
    return operating_cash_flow - capex


def cash_flow_margin(operating_cash_flow: Number, revenue: Number) -> float:
    """Cash Flow Margin: Operating Cash Flow / Revenue"""
    return operating_cash_flow / revenue
