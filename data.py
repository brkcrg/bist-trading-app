"""yfinance üzerinden BIST veri çekme - retry + cache fallback."""

import time
from pathlib import Path
import pandas as pd
import yfinance as yf

from bist_symbols import to_yahoo

CACHE_DIR = Path(__file__).parent / ".cache"
try:
    CACHE_DIR.mkdir(exist_ok=True)
    _CACHE_OK = True
except OSError:
    _CACHE_OK = False


def _read_cache(cache_file: Path) -> pd.DataFrame | None:
    if not _CACHE_OK or not cache_file.exists():
        return None
    try:
        return pd.read_parquet(cache_file)
    except Exception:
        return None


def _write_cache(cache_file: Path, df: pd.DataFrame) -> None:
    if not _CACHE_OK:
        return
    try:
        df.to_parquet(cache_file)
    except Exception:
        pass


def fetch(symbol: str, period: str = "2y", interval: str = "1d", use_cache: bool = True) -> pd.DataFrame:
    """
    BIST hissesi için OHLCV verisi çeker.
    Yahoo rate-limit yerse cache fallback'e döner.
    """
    ticker = to_yahoo(symbol)
    cache_file = CACHE_DIR / f"{ticker}_{period}_{interval}.parquet"

    max_age_hours = 0.25 if interval != "1d" else 12

    # Taze cache varsa kullan
    if use_cache:
        cached = _read_cache(cache_file)
        if cached is not None and cache_file.exists():
            age_hours = (pd.Timestamp.now().timestamp() - cache_file.stat().st_mtime) / 3600
            if age_hours < max_age_hours:
                return cached

    # 3 kez retry (Yahoo rate-limit için)
    df = None
    last_err = None
    for attempt in range(3):
        try:
            df = yf.download(
                ticker, period=period, interval=interval,
                progress=False, auto_adjust=True, threads=False,
            )
            if df is not None and not df.empty:
                break
        except Exception as e:
            last_err = e
        time.sleep(0.5 * (attempt + 1))

    if df is None or df.empty:
        # Fallback: bayat cache varsa onu döndür
        stale = _read_cache(cache_file)
        if stale is not None and not stale.empty:
            return stale
        if last_err:
            print(f"[{symbol}] yfinance hatası: {last_err}")
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    _write_cache(cache_file, df)
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
