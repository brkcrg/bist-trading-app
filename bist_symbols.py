"""BIST 100 sembolleri - yfinance formatında (.IS son eki)."""

BIST100 = [
    "AEFES", "AGHOL", "AKBNK", "AKCNS", "AKFGY", "AKSA", "AKSEN", "ALARK",
    "ALBRK", "ALFAS", "ARCLK", "ASELS", "ASTOR", "BERA", "BIENY", "BIMAS",
    "BRSAN", "BRYAT", "BUCIM", "CCOLA", "CIMSA", "DOAS", "DOHOL", "ECILC",
    "ECZYT", "EGEEN", "EKGYO", "ENJSA", "ENKAI", "EREGL", "EUPWR", "FROTO",
    "GARAN", "GESAN", "GUBRF", "HALKB", "HEKTS", "IPEKE", "ISCTR", "ISMEN",
    "IZMDC", "KARSN", "KCAER", "KCHOL", "KLKIM", "KMPUR", "KONTR", "KONYA",
    "KORDS", "KOZAA", "KOZAL", "KRDMD", "MAVI", "MGROS", "MIATK", "ODAS",
    "OTKAR", "OYAKC", "PAPIL", "PARSN", "PEKGY", "PENTA", "PETKM", "PGSUS",
    "QUAGR", "SAHOL", "SASA", "SDTTR", "SELEC", "SISE", "SKBNK", "SMRTG",
    "SOKM", "TABGD", "TAVHL", "TCELL", "THYAO", "TKFEN", "TOASO", "TSKB",
    "TTKOM", "TTRAK", "TUKAS", "TUPRS", "TURSG", "ULKER", "VAKBN", "VESBE",
    "VESTL", "YEOTK", "YKBNK", "ZOREN",
    # Ek hisseler
    "NUGYO", "TERA", "TRHOL", "SEKFK", "TMPOL", "TEHOL", "GLRMK",
]


def to_yahoo(symbol: str) -> str:
    """BIST sembolünü yfinance formatına çevirir."""
    return f"{symbol.upper().strip()}.IS"
