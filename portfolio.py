"""Portföy takip - session state tabanlı (her kullanıcı kendi portföyü)."""

from dataclasses import dataclass, field
from typing import List
import pandas as pd

from data import fetch


@dataclass
class Position:
    symbol: str
    shares: int
    avg_price: float
    entry_date: str
    stop_loss: float | None = None
    notes: str = ""


@dataclass
class Portfolio:
    cash: float
    initial_cash: float = 0.0
    positions: List[Position] = field(default_factory=list)

    def buy(self, symbol: str, shares: int, price: float, stop_loss: float | None = None) -> None:
        cost = shares * price
        if cost > self.cash:
            raise ValueError(f"Yetersiz nakit: {cost:.2f} gerekli, {self.cash:.2f} var")
        existing = next((p for p in self.positions if p.symbol == symbol.upper()), None)
        if existing:
            total_shares = existing.shares + shares
            existing.avg_price = (existing.avg_price * existing.shares + price * shares) / total_shares
            existing.shares = total_shares
            if stop_loss is not None:
                existing.stop_loss = stop_loss
        else:
            self.positions.append(
                Position(
                    symbol=symbol.upper(),
                    shares=shares,
                    avg_price=price,
                    entry_date=pd.Timestamp.now().strftime("%Y-%m-%d"),
                    stop_loss=stop_loss,
                )
            )
        self.cash -= cost

    def sell(self, symbol: str, shares: int, price: float) -> float:
        pos = next((p for p in self.positions if p.symbol == symbol.upper()), None)
        if pos is None:
            raise ValueError(f"{symbol} pozisyonu yok")
        if shares > pos.shares:
            raise ValueError(f"Sadece {pos.shares} lot var")
        proceeds = shares * price
        pnl = (price - pos.avg_price) * shares
        pos.shares -= shares
        self.cash += proceeds
        if pos.shares == 0:
            self.positions.remove(pos)
        return pnl

    def snapshot(self) -> pd.DataFrame:
        rows = []
        for p in self.positions:
            try:
                df = fetch(p.symbol, period="5d")
                current = float(df["Close"].iloc[-1]) if not df.empty else p.avg_price
            except Exception:
                current = p.avg_price
            market_value = p.shares * current
            cost_basis = p.shares * p.avg_price
            pnl = market_value - cost_basis
            pnl_pct = (current / p.avg_price - 1) * 100 if p.avg_price > 0 else 0
            rows.append({
                "Sembol": p.symbol,
                "Lot": p.shares,
                "Ort. Maliyet": round(p.avg_price, 2),
                "Güncel Fiyat": round(current, 2),
                "Maliyet": round(cost_basis, 2),
                "Piyasa Değeri": round(market_value, 2),
                "K/Z": round(pnl, 2),
                "K/Z %": round(pnl_pct, 2),
                "Stop-Loss": p.stop_loss,
            })
        return pd.DataFrame(rows)

    def total_value(self) -> float:
        snap = self.snapshot()
        market = float(snap["Piyasa Değeri"].sum()) if not snap.empty else 0.0
        return float(self.cash + market)

    def reset(self, initial_cash: float) -> None:
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions = []


def get_portfolio(st_session_state) -> Portfolio | None:
    """Session state'ten portföyü döner, yoksa None."""
    return st_session_state.get("portfolio")


def init_portfolio(st_session_state, initial_cash: float) -> Portfolio:
    """Yeni portföy oluşturur ve session state'e koyar."""
    pf = Portfolio(cash=initial_cash, initial_cash=initial_cash, positions=[])
    st_session_state["portfolio"] = pf
    return pf
