"""
Backtest motoru - gerçekçi varsayımlarla:
- Komisyon: %0.2 (BIST ortalaması, BSMV dahil)
- Slippage: %0.1 (emir kayması)
- Tek pozisyon: aynı anda sadece bir hissede olur
- Pozisyon büyüklüğü: sermayenin %2'si riske atılır (ATR tabanlı sizing)
"""

from dataclasses import dataclass, field
from typing import List
import pandas as pd


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None
    shares: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    initial_capital: float = 0.0
    final_capital: float = 0.0

    @property
    def total_return_pct(self) -> float:
        if self.initial_capital == 0:
            return 0.0
        return (self.final_capital / self.initial_capital - 1) * 100

    @property
    def num_trades(self) -> int:
        return len([t for t in self.trades if t.exit_date is not None])

    @property
    def win_rate(self) -> float:
        closed = [t for t in self.trades if t.exit_date is not None]
        if not closed:
            return 0.0
        wins = sum(1 for t in closed if t.pnl > 0)
        return wins / len(closed) * 100

    @property
    def max_drawdown_pct(self) -> float:
        if len(self.equity_curve) == 0:
            return 0.0
        running_max = self.equity_curve.cummax()
        dd = (self.equity_curve - running_max) / running_max
        return float(dd.min() * 100)

    @property
    def profit_factor(self) -> float:
        closed = [t for t in self.trades if t.exit_date is not None]
        gross_profit = sum(t.pnl for t in closed if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in closed if t.pnl < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 880_000.0,
    commission: float = 0.002,
    slippage: float = 0.001,
    risk_per_trade: float = 0.02,
) -> BacktestResult:
    """
    df: generate_signals ile üretilmiş dataframe (buy_signal, sell_signal, stop_distance içermeli)
    """
    result = BacktestResult(initial_capital=initial_capital)
    capital = initial_capital
    position: Trade | None = None
    stop_price: float | None = None
    target_price: float | None = None
    equity = []

    def close_position(pos, exit_px, date, reason):
        nonlocal capital
        proceeds = pos.shares * exit_px * (1 - commission)
        pos.exit_date = date
        pos.exit_price = exit_px
        pos.pnl = proceeds - (pos.shares * pos.entry_price)
        pos.pnl_pct = (exit_px / pos.entry_price - 1) * 100
        pos.reason = reason
        capital += proceeds

    for date, row in df.iterrows():
        close = float(row["Close"])

        # Pozisyon varsa stop-loss / take-profit kontrolü
        if position is not None and stop_price is not None:
            if float(row["Low"]) <= stop_price:
                exit_price = stop_price * (1 - slippage)
                close_position(position, exit_price, date, "stop_loss")
                result.trades.append(position)
                position = None
                stop_price = None
                target_price = None
            elif target_price is not None and float(row["High"]) >= target_price:
                exit_price = target_price * (1 - slippage)
                close_position(position, exit_price, date, "take_profit")
                result.trades.append(position)
                position = None
                stop_price = None
                target_price = None

        # Satış sinyali
        if position is not None and bool(row.get("sell_signal", False)):
            exit_price = close * (1 - slippage)
            close_position(position, exit_price, date, "signal")
            result.trades.append(position)
            position = None
            stop_price = None
            target_price = None

        # Alım sinyali
        if position is None and bool(row.get("buy_signal", False)):
            stop_distance = float(row.get("stop_distance", 0) or 0)
            target_distance = float(row.get("target_distance", 0) or 0)
            if stop_distance > 0:
                risk_amount = capital * risk_per_trade
                shares = int(risk_amount / stop_distance)
                entry_price = close * (1 + slippage)
                cost = shares * entry_price * (1 + commission)
                if shares > 0 and cost <= capital:
                    capital -= cost
                    position = Trade(
                        entry_date=date,
                        entry_price=entry_price,
                        shares=shares,
                    )
                    stop_price = entry_price - stop_distance
                    if target_distance > 0:
                        target_price = entry_price + target_distance

        # Equity hesabı (nakit + açık pozisyon değeri)
        open_value = position.shares * close if position is not None else 0
        equity.append(capital + open_value)

    result.equity_curve = pd.Series(equity, index=df.index)
    result.final_capital = float(equity[-1]) if equity else initial_capital
    return result
