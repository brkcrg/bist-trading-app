"""
GÜNLÜK TRADE (INTRADAY) STRATEJİSİ

Kullanılan metodlar:
1. VWAP (Volume Weighted Average Price) — profesyonel day trader benchmark'ı
2. Opening Range Breakout (ORB) — seansın ilk 30 dakikasının yüksek/alçak kırılımı
3. RSI(9) — kısa vadede momentum
4. Hacim spike — ortalamanın 2x üzerinde hacim

Kurallar (LONG):
- Fiyat VWAP'ın üzerinde (alıcı üstünlüğü)
- Opening range'in (ilk 30dk) üstünü kırdı
- RSI(9) 50-75 arası (momentum var, aşırı alım değil)
- Hacim spike onayı

Stop-loss: Giriş - 1 × ATR (intraday için çok sıkı)
Hedef 1: Giriş + 1 × ATR (kısmi kâr al)
Hedef 2: Giriş + 2 × ATR (trailing stop ile)

UYARI: Day trading istatistiksel olarak profesyonel trader'ların bile
çoğunun kaybettiği en zor trading stilidir. BIST'te işlem saatleri 10:00-18:00.
Komisyonlar kısa vadede kârı ciddi oranda yer.
"""

import pandas as pd
from indicators import ema, rsi, atr, sma, session_vwap


def opening_range(df: pd.DataFrame, minutes: int = 30) -> pd.DataFrame:
    """
    Her gün için ilk N dakikanın high/low'unu hesaplar.
    Bu range'in üstünü kırarsa LONG, altını kırarsa SHORT sinyali.
    """
    out = df.copy()
    out["or_high"] = None
    out["or_low"] = None

    for date, group in df.groupby(df.index.date):
        if len(group) == 0:
            continue
        first_time = group.index[0]
        end_time = first_time + pd.Timedelta(minutes=minutes)
        opening = group[group.index < end_time]
        if len(opening) > 0:
            or_high = float(opening["High"].max())
            or_low = float(opening["Low"].min())
            out.loc[group.index, "or_high"] = or_high
            out.loc[group.index, "or_low"] = or_low

    out["or_high"] = pd.to_numeric(out["or_high"], errors="coerce")
    out["or_low"] = pd.to_numeric(out["or_low"], errors="coerce")
    return out


def generate_intraday_signals(
    df: pd.DataFrame,
    or_minutes: int = 30,
    rsi_period: int = 9,
    rsi_min: float = 50.0,
    rsi_max: float = 75.0,
    atr_period: int = 14,
    volume_spike: float = 1.5,
) -> pd.DataFrame:
    """Intraday sinyaller üretir."""
    if df.empty:
        return df.copy()

    out = opening_range(df, minutes=or_minutes)
    out["vwap"] = session_vwap(out)
    out["rsi"] = rsi(out["Close"], rsi_period)
    out["atr"] = atr(out, atr_period)
    out["ema9"] = ema(out["Close"], 9)
    out["vol_avg"] = sma(out["Volume"], 20)
    out["vol_ratio"] = out["Volume"] / out["vol_avg"].replace(0, 1e-10)

    # LONG sinyali: ORB yukarı kırılım + VWAP üstü + RSI OK + hacim
    prev_close = out["Close"].shift(1)
    breakout_up = (out["Close"] > out["or_high"]) & (prev_close <= out["or_high"])
    above_vwap = out["Close"] > out["vwap"]
    rsi_ok = (out["rsi"] >= rsi_min) & (out["rsi"] <= rsi_max)
    vol_ok = out["vol_ratio"] >= volume_spike

    out["long_signal"] = breakout_up & above_vwap & rsi_ok & vol_ok

    # SHORT / exit: ORB aşağı kırılım veya VWAP altına düşüş
    breakout_down = (out["Close"] < out["or_low"]) & (prev_close >= out["or_low"])
    out["exit_signal"] = breakout_down | (out["Close"] < out["vwap"]) | (out["rsi"] > 80)

    out["stop_distance"] = out["atr"] * 1.0
    out["target1_distance"] = out["atr"] * 1.0
    out["target2_distance"] = out["atr"] * 2.0
    return out


def intraday_summary(df: pd.DataFrame) -> dict:
    """Bugünün intraday özetini döner."""
    if df.empty:
        return {}
    today = df.index[-1].date()
    today_df = df[df.index.date == today]
    if today_df.empty:
        return {}

    open_price = float(today_df["Open"].iloc[0])
    high = float(today_df["High"].max())
    low = float(today_df["Low"].min())
    last = float(today_df["Close"].iloc[-1])
    vwap_val = float(today_df["vwap"].iloc[-1]) if "vwap" in today_df.columns else 0
    or_high = float(today_df["or_high"].iloc[-1]) if "or_high" in today_df.columns and pd.notna(today_df["or_high"].iloc[-1]) else 0
    or_low = float(today_df["or_low"].iloc[-1]) if "or_low" in today_df.columns and pd.notna(today_df["or_low"].iloc[-1]) else 0
    volume = float(today_df["Volume"].sum())
    change_pct = (last / open_price - 1) * 100

    signal = "HOLD"
    if "long_signal" in today_df.columns and today_df["long_signal"].any():
        signal = "LONG"
    elif "exit_signal" in today_df.columns and bool(today_df["exit_signal"].iloc[-1]):
        signal = "EXIT"

    return {
        "open": open_price,
        "high": high,
        "low": low,
        "last": last,
        "change_pct": change_pct,
        "vwap": vwap_val,
        "or_high": or_high,
        "or_low": or_low,
        "volume": volume,
        "signal": signal,
        "above_vwap": last > vwap_val,
    }
