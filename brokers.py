"""
Aracı kurum işlemleri analizi - CSV upload tabanlı.

Kullanıcı Matriks/Foreks/broker terminalinden veya KAP'tan aracı kurum
bazında işlem özetini CSV olarak indirir, uygulamaya yükler.

Beklenen CSV formatı (esnek — kolon isimleri farklı olabilir):
  - Sembol / Hisse / Kod
  - Aracı Kurum / Broker
  - Alış Adet (opsiyonel)
  - Alış TL / Alış Tutar
  - Satış Adet (opsiyonel)
  - Satış TL / Satış Tutar
  - Net TL (opsiyonel - hesaplanabilir)
  - Tarih (opsiyonel)
"""

from __future__ import annotations
import pandas as pd
from io import StringIO, BytesIO


COLUMN_ALIASES = {
    "symbol": ["sembol", "hisse", "kod", "kodu", "hisse kodu", "symbol"],
    "broker": ["aracı kurum", "aracikurum", "aracı", "kurum", "broker"],
    "buy_qty": ["alış adet", "alis adet", "alış lot", "buy qty"],
    "buy_tl": ["alış tl", "alis tl", "alış tutar", "alis tutar", "buy value"],
    "sell_qty": ["satış adet", "satis adet", "satış lot", "sell qty"],
    "sell_tl": ["satış tl", "satis tl", "satış tutar", "satis tutar", "sell value"],
    "net_tl": ["net tl", "net tutar", "net", "net value"],
    "date": ["tarih", "date"],
}


def _match_col(df: pd.DataFrame, aliases: list[str]) -> str | None:
    norm = {c.strip().lower(): c for c in df.columns}
    for a in aliases:
        if a in norm:
            return norm[a]
    return None


def parse_csv(raw: bytes | str) -> pd.DataFrame:
    """CSV / Excel byte'larını normalize edilmiş DataFrame'e çevirir."""
    if isinstance(raw, bytes):
        # Excel mi CSV mi tespit et
        if raw[:2] == b"PK" or raw[:4] == b"\xd0\xcf\x11\xe0":
            df = pd.read_excel(BytesIO(raw))
        else:
            text = None
            for enc in ("utf-8", "utf-8-sig", "cp1254", "iso-8859-9"):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                raise ValueError("Dosya kodlaması okunamadı")
            # Ayırıcı tahmini
            sep = ";" if text.count(";") > text.count(",") else ","
            df = pd.read_csv(StringIO(text), sep=sep, decimal=",", thousands=".")
    else:
        sep = ";" if raw.count(";") > raw.count(",") else ","
        df = pd.read_csv(StringIO(raw), sep=sep, decimal=",", thousands=".")

    # Kolonları eşle
    mapping = {}
    for key, aliases in COLUMN_ALIASES.items():
        col = _match_col(df, aliases)
        if col:
            mapping[col] = key

    if not mapping:
        raise ValueError(f"Tanınan kolon yok. Mevcut kolonlar: {list(df.columns)}")

    df = df.rename(columns=mapping)

    # Zorunlu kolonlar
    if "symbol" not in df.columns:
        raise ValueError("'Sembol' kolonu bulunamadı")
    if "broker" not in df.columns:
        raise ValueError("'Aracı Kurum' kolonu bulunamadı")

    # Numeric dönüşüm
    for col in ["buy_qty", "buy_tl", "sell_qty", "sell_tl", "net_tl"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Net TL hesaplanabilir
    if "net_tl" not in df.columns:
        buy = df.get("buy_tl", 0)
        sell = df.get("sell_tl", 0)
        df["net_tl"] = buy - sell

    # Temizlik
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["broker"] = df["broker"].astype(str).str.strip()
    df = df[df["symbol"].str.len() > 1]

    return df


def list_brokers(df: pd.DataFrame) -> list[str]:
    if df.empty or "broker" not in df.columns:
        return []
    return sorted(df["broker"].unique().tolist())


def broker_summary(df: pd.DataFrame, broker: str, mode: str = "accumulate", limit: int = 30) -> pd.DataFrame:
    """
    mode:
      - 'accumulate' → en çok alınan (net TL pozitif, büyükten küçüğe)
      - 'distribute' → en çok satılan (net TL negatif, küçükten büyüğe)
    """
    if df.empty:
        return df
    filtered = df[df["broker"].str.lower() == broker.lower()].copy()
    if filtered.empty:
        return filtered

    # Aynı sembol birden fazla satırda varsa topla
    agg_cols = {}
    for c in ["buy_qty", "buy_tl", "sell_qty", "sell_tl", "net_tl"]:
        if c in filtered.columns:
            agg_cols[c] = "sum"
    if agg_cols:
        filtered = filtered.groupby("symbol", as_index=False).agg(agg_cols)

    if mode == "accumulate":
        filtered = filtered[filtered["net_tl"] > 0].sort_values("net_tl", ascending=False)
    else:
        filtered = filtered[filtered["net_tl"] < 0].sort_values("net_tl", ascending=True)

    return filtered.head(limit).reset_index(drop=True)


def format_display(df: pd.DataFrame) -> pd.DataFrame:
    """Türkçe kolon isimleriyle görüntü için formatlar."""
    if df.empty:
        return df
    rename = {
        "symbol": "Sembol",
        "buy_qty": "Alış Adet",
        "buy_tl": "Alış TL",
        "sell_qty": "Satış Adet",
        "sell_tl": "Satış TL",
        "net_tl": "Net TL",
    }
    cols = [c for c in rename if c in df.columns]
    out = df[cols].rename(columns=rename).copy()
    # Sayısal formatla
    for c in ["Alış TL", "Satış TL", "Net TL"]:
        if c in out.columns:
            out[c] = out[c].round(0).astype(int)
    for c in ["Alış Adet", "Satış Adet"]:
        if c in out.columns:
            out[c] = out[c].round(0).astype(int)
    return out
