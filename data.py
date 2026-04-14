"""yfinance üzerinden BIST veri çekme - basit disk cache ile."""

from pathlib import Path
import pandas as pd
import yfinance as yf

from bist_symbols import to_yahoo

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


def fetch(symbol: str, period: str = "2y", interval: str = "1d", use_cache: bool = True) -> pd.DataFrame:
    """
    BIST hissesi için OHLCV verisi çeker.
    symbol: 'THYAO', 'GARAN' gibi (nokta/IS gerekmez)
    period: '1y', '2y', '5y', 'max', veya intraday için '5d', '60d'
    interval: '1d', '1h', '30m', '15m', '5m'
    """
    ticker = to_yahoo(symbol)
    cache_file = CACHE_DIR / f"{ticker}_{period}_{interval}.parquet"

    # Intraday için cache ömrü çok kısa (canlı fiyat gerekir)
    max_age_hours = 0.25 if interval != "1d" else 12

    if use_cache and cache_file.exists():
        age_hours = (pd.Timestamp.now().timestamp() - cache_file.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            return pd.read_parquet(cache_file)

    df = yf.download(
        ticker, period=period, interval=interval, progress=False, auto_adjust=True
    )
    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.to_parquet(cache_file)
    return df


def fetch_many(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Birden fazla sembol için veri çeker."""
    out = {}
    for s in symbols:
        try:
            df = fetch(s, period=period)
            if not df.empty:
                out[s] = df
        except Exception as e:
            print(f"[{s}] hata: {e}")
    return out
