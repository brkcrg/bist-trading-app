"""Teknik göstergeler - pandas tabanlı, saf Python."""

import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range - volatilite ölçümü, stop-loss için kullanılır."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume Weighted Average Price - intraday için kritik."""
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    cum_vol = df["Volume"].cumsum()
    cum_pv = (typical * df["Volume"]).cumsum()
    return cum_pv / cum_vol.replace(0, 1e-10)


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Her gün için ayrı VWAP (seans başlangıcında sıfırlanır)."""
    out = pd.Series(index=df.index, dtype=float)
    for date, group in df.groupby(df.index.date):
        typical = (group["High"] + group["Low"] + group["Close"]) / 3
        cum_vol = group["Volume"].cumsum()
        cum_pv = (typical * group["Volume"]).cumsum()
        out.loc[group.index] = cum_pv / cum_vol.replace(0, 1e-10)
    return out


def bollinger(series: pd.Series, period: int = 20, num_std: float = 2.0):
    mid = sma(series, period)
    std = series.rolling(window=period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower
