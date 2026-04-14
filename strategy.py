"""
KISA VADELİ SWING STRATEJİSİ (3-10 gün tutma süresi)

Kurallar:
- Trend filtresi: EMA9 > EMA21 (kısa vade yukarı trend)
- 2 tip giriş:
  1) BREAKOUT: EMA9 EMA21'i yukarı keser (trend başlangıcı)
  2) PULLBACK: Trend içinde RSI 40-50 bölgesine düşüp yukarı dönüş (dip alım)
- Filtre: RSI(14) < 70 (aşırı alım bölgesinde yeni alım yok)
- Hacim: normal üstü yeterli (1.0x)
- ÇIKIŞ: Sadece EMA9 EMA21'i aşağı keserse (trend biter) veya stop
  (RSI ile çıkış YAPMIYORUZ — trend boyunca tut, bırak çalışsın)
- Stop-loss: Giriş - 1.5 × ATR
- Hedef: Giriş + 2.5 × ATR

Neden değişti?
- Önceki versiyonda RSI > 75 sat sinyali verince, güçlü trendlerde sürekli
  "sat" çıkıyordu. RSI yüksekliği trendin gücüdür, satış sebebi değil.
- Sadece 1 giriş tipi (crossover) olduğu için çoğu zaman "al yok" durumu oluşuyordu.
  Şimdi pullback girişleri de var — trend içinde düzeltmelerde de sinyal gelir.
"""

import pandas as pd
from indicators import ema, rsi, atr, sma


def generate_signals(
    df: pd.DataFrame,
    fast: int = 9,
    slow: int = 21,
    rsi_period: int = 14,
    rsi_max_entry: float = 70.0,
    atr_period: int = 10,
    atr_stop_mult: float = 1.5,
    atr_target_mult: float = 2.5,
    volume_mult: float = 1.0,
) -> pd.DataFrame:
    """Kısa vadeli swing sinyalleri üretir — breakout + pullback."""
    out = df.copy()
    out["ema_fast"] = ema(out["Close"], fast)
    out["ema_slow"] = ema(out["Close"], slow)
    out["rsi"] = rsi(out["Close"], rsi_period)
    out["atr"] = atr(out, atr_period)
    out["vol_avg"] = sma(out["Volume"], 20)
    out["vol_ratio"] = out["Volume"] / out["vol_avg"].replace(0, 1e-10)

    # Trend: EMA9 > EMA21
    in_uptrend = out["ema_fast"] > out["ema_slow"]
    prev_uptrend = in_uptrend.shift(1).fillna(False)

    # 1) BREAKOUT: trend az önce başladı (crossover)
    breakout = in_uptrend & ~prev_uptrend

    # 2) PULLBACK: Trend içinde RSI 50'nin altından yukarı döndü
    rsi_cross_up_50 = (out["rsi"] > 50) & (out["rsi"].shift(1) <= 50)
    pullback = in_uptrend & rsi_cross_up_50

    # Ortak filtreler
    rsi_ok = out["rsi"] < rsi_max_entry
    volume_ok = out["vol_ratio"] >= volume_mult

    out["buy_signal"] = (breakout | pullback) & rsi_ok & volume_ok

    # SATIM: yalnız trend kırıldığında
    cross_down = (out["ema_fast"] < out["ema_slow"]) & (
        out["ema_fast"].shift(1) >= out["ema_slow"].shift(1)
    )
    out["sell_signal"] = cross_down

    out["stop_distance"] = out["atr"] * atr_stop_mult
    out["target_distance"] = out["atr"] * atr_target_mult
    return out


def latest_signal(df: pd.DataFrame) -> str:
    if len(df) == 0:
        return "HOLD"
    last = df.iloc[-1]
    if bool(last.get("buy_signal", False)):
        return "BUY"
    if bool(last.get("sell_signal", False)):
        return "SELL"
    return "HOLD"


def signal_strength(df: pd.DataFrame) -> float:
    """0-100 arası sinyal gücü — alım için ne kadar uygun olduğu."""
    if len(df) < 2:
        return 0.0
    last = df.iloc[-1]
    score = 0.0
    # Trend: EMA9 > EMA21
    if pd.notna(last.get("ema_fast")) and pd.notna(last.get("ema_slow")):
        if last["ema_fast"] > last["ema_slow"]:
            score += 35
            # Trend ne kadar güçlü (EMA'lar arası mesafe)
            gap = (last["ema_fast"] - last["ema_slow"]) / last["ema_slow"]
            if gap > 0.02:
                score += 10
    # RSI sağlıklı bölgede (aşırı alım değil, zayıf da değil)
    if pd.notna(last.get("rsi")):
        r = float(last["rsi"])
        if 45 <= r <= 65:
            score += 20
        elif 35 <= r < 45 or 65 < r <= 70:
            score += 10
        elif r >= 70:
            score -= 10
    # Hacim
    if pd.notna(last.get("vol_ratio")):
        vr = float(last["vol_ratio"])
        if vr >= 1.5:
            score += 15
        elif vr >= 1.0:
            score += 8
    # Yakın zamanda alım sinyali
    if len(df) >= 3 and df["buy_signal"].tail(3).any():
        score += 20
    return max(0.0, min(score, 100.0))
