"""
Temel analiz - yfinance Ticker.info üzerinden BIST hisseleri için.

Skorlama mantığı (0-100 arası):
- Her metrik kendi eşiklerine göre 0-10 puan alır
- Ortalama × 10 = toplam skor
- Metrik yoksa skora dahil edilmez (NaN)

Kullanılan metrikler:
1. F/K (trailingPE)      - düşük iyi (overpriced değil)
2. PD/DD (priceToBook)   - düşük iyi
3. ROE (returnOnEquity)  - yüksek iyi (sermaye verimliliği)
4. Borç/Özsermaye        - düşük iyi (finansal sağlık)
5. Kâr marjı             - yüksek iyi
6. Gelir büyümesi        - yüksek iyi
7. Kâr büyümesi          - yüksek iyi
8. Temettü verimi        - bonus (varsa +)
"""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
import yfinance as yf

from bist_symbols import to_yahoo


@dataclass
class Fundamentals:
    symbol: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    pb_ratio: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    profit_margin: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    dividend_yield: float | None = None
    score: float = 0.0
    breakdown: dict = field(default_factory=dict)

    @property
    def grade(self) -> str:
        if self.score >= 80:
            return "A+"
        if self.score >= 70:
            return "A"
        if self.score >= 60:
            return "B"
        if self.score >= 50:
            return "C"
        if self.score >= 40:
            return "D"
        return "F"


def _score_pe(pe: float | None) -> float | None:
    if pe is None or pe <= 0:
        return None
    if pe < 8: return 10
    if pe < 12: return 9
    if pe < 15: return 8
    if pe < 20: return 6
    if pe < 25: return 4
    if pe < 35: return 2
    return 1


def _score_pb(pb: float | None) -> float | None:
    if pb is None or pb <= 0:
        return None
    if pb < 1: return 10
    if pb < 1.5: return 9
    if pb < 2: return 7
    if pb < 3: return 5
    if pb < 5: return 3
    return 1


def _score_roe(roe: float | None) -> float | None:
    if roe is None:
        return None
    if roe >= 0.30: return 10
    if roe >= 0.20: return 9
    if roe >= 0.15: return 7
    if roe >= 0.10: return 5
    if roe >= 0.05: return 3
    if roe >= 0: return 1
    return 0


def _score_debt(de: float | None) -> float | None:
    if de is None or de < 0:
        return None
    # yfinance D/E bazen yüzde bazen oran döner — 10+ ise yüzde gibi davran
    if de > 10:
        de = de / 100
    if de < 0.3: return 10
    if de < 0.5: return 9
    if de < 1.0: return 7
    if de < 1.5: return 5
    if de < 2.0: return 3
    return 1


def _score_margin(m: float | None) -> float | None:
    if m is None:
        return None
    if m >= 0.25: return 10
    if m >= 0.15: return 8
    if m >= 0.10: return 6
    if m >= 0.05: return 4
    if m >= 0: return 2
    return 0


def _score_growth(g: float | None) -> float | None:
    if g is None:
        return None
    if g >= 0.30: return 10
    if g >= 0.20: return 8
    if g >= 0.10: return 6
    if g >= 0.05: return 4
    if g >= 0: return 2
    return 0


@lru_cache(maxsize=128)
def get_fundamentals(symbol: str) -> Fundamentals:
    """yfinance'tan temel verileri çeker ve skor hesaplar."""
    ticker = to_yahoo(symbol)
    f = Fundamentals(symbol=symbol.upper())
    try:
        info: dict[str, Any] = yf.Ticker(ticker).info or {}
    except Exception as e:
        print(f"[{symbol}] temel veri hatası: {e}")
        return f

    f.name = info.get("longName") or info.get("shortName") or symbol
    f.sector = info.get("sector", "")
    f.industry = info.get("industry", "")
    f.market_cap = info.get("marketCap")
    f.pe_ratio = info.get("trailingPE")
    f.forward_pe = info.get("forwardPE")
    f.pb_ratio = info.get("priceToBook")
    f.roe = info.get("returnOnEquity")
    f.debt_to_equity = info.get("debtToEquity")
    f.profit_margin = info.get("profitMargins")
    f.revenue_growth = info.get("revenueGrowth")
    f.earnings_growth = info.get("earningsGrowth")
    f.dividend_yield = info.get("dividendYield")

    scores = {
        "F/K": _score_pe(f.pe_ratio),
        "PD/DD": _score_pb(f.pb_ratio),
        "ROE": _score_roe(f.roe),
        "Borç/Özserm.": _score_debt(f.debt_to_equity),
        "Kâr Marjı": _score_margin(f.profit_margin),
        "Gelir Büyüme": _score_growth(f.revenue_growth),
        "Kâr Büyüme": _score_growth(f.earnings_growth),
    }
    valid = [s for s in scores.values() if s is not None]
    if valid:
        base = sum(valid) / len(valid) * 10
        # Temettü bonusu (max +5)
        if f.dividend_yield and f.dividend_yield > 0:
            bonus = min(f.dividend_yield * 100, 5)
            base = min(base + bonus, 100)
        f.score = round(base, 1)
    f.breakdown = {k: v for k, v in scores.items() if v is not None}
    return f


def format_value(v: float | None, pct: bool = False, suffix: str = "") -> str:
    if v is None:
        return "—"
    if pct:
        return f"{v * 100:.2f}%"
    if abs(v) >= 1e9:
        return f"{v / 1e9:.2f}B{suffix}"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.2f}M{suffix}"
    return f"{v:.2f}{suffix}"
