"""BIST 100 tarayıcı - kısa vadeli swing stratejisine göre fırsat bulur."""

import pandas as pd
from bist_symbols import BIST100
from data import fetch
from strategy import generate_signals, latest_signal, signal_strength
from fundamentals import get_fundamentals


def scan(
    symbols: list[str] | None = None,
    period: str = "6mo",
    include_fundamentals: bool = False,
) -> pd.DataFrame:
    symbols = symbols or BIST100
    rows = []
    for sym in symbols:
        try:
            df = fetch(sym, period=period)
            if df.empty or len(df) < 30:
                continue
            sig_df = generate_signals(df)
            last = sig_df.iloc[-1]
            signal = latest_signal(sig_df)
            strength = signal_strength(sig_df)
            price = float(last["Close"])
            atr_val = float(last["atr"]) if pd.notna(last["atr"]) else 0
            row = {
                "Sembol": sym,
                "Fiyat": round(price, 2),
                "EMA9": round(float(last["ema_fast"]), 2) if pd.notna(last["ema_fast"]) else None,
                "EMA21": round(float(last["ema_slow"]), 2) if pd.notna(last["ema_slow"]) else None,
                "RSI": round(float(last["rsi"]), 1) if pd.notna(last["rsi"]) else None,
                "Hacim x": round(float(last["vol_ratio"]), 2) if pd.notna(last["vol_ratio"]) else None,
                "Sinyal": signal,
                "Güç": round(strength, 0),
                "Stop": round(price - 1.5 * atr_val, 2) if atr_val > 0 else None,
                "Hedef": round(price + 2.5 * atr_val, 2) if atr_val > 0 else None,
            }
            if include_fundamentals:
                try:
                    f = get_fundamentals(sym)
                    row["Temel"] = round(f.score, 0)
                    row["Not"] = f.grade
                    row["Birleşik"] = round(strength * 0.5 + f.score * 0.5, 0)
                except Exception:
                    row["Temel"] = None
                    row["Not"] = "—"
                    row["Birleşik"] = round(strength, 0)
            rows.append(row)
        except Exception as e:
            print(f"[{sym}] {e}")
    return pd.DataFrame(rows)
