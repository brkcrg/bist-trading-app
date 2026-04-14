# BIST Trading Asistanı

BIST hisseleri için teknik analiz, backtest, sinyal tarayıcı ve portföy takip uygulaması.

## ONEMLI UYARI

**Bu uygulama yatırım tavsiyesi değildir.** "Sürekli kazandıran" bir sistem
yoktur — bu araç sana **disiplin, risk yönetimi ve geçmiş veriyle test
edilmiş stratejiler** sunar. Gerçek parayı riske atmadan önce mutlaka
backtest yap ve anladığından emin ol.

## Kurulum

```bash
cd c:\Users\Burak\Desktop\bist_app
pip install -r requirements.txt
```

## Çalıştırma

```bash
streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır.

## Özellikler

1. **Özet** — Portföy toplam değeri, K/Z, açık pozisyonlar
2. **Hisse Analizi** — Mum grafik, SMA, RSI, alım/satım sinyalleri
3. **Backtest** — Geçmiş veriyle strateji testi, Al-Tut karşılaştırması
4. **Sinyal Tarayıcı** — BIST 100 içinden alım/satım sinyali verenler
5. **Portföyüm** — Gerçek alım/satım kayıtları, K/Z takibi

## Strateji

**SMA Crossover + RSI + ATR Stop-Loss**

- ALIM: SMA20 > SMA50 (yukarı kesim) ve RSI < 70
- SATIM: SMA20 < SMA50 (aşağı kesim) veya stop-loss
- Stop: Giriş - 2×ATR
- Pozisyon boyutu: Sermayenin %2'si risk

## Dosya Yapısı

- [app.py](app.py) — Streamlit UI
- [data.py](data.py) — yfinance veri çekme + cache
- [indicators.py](indicators.py) — Teknik göstergeler
- [strategy.py](strategy.py) — Sinyal üretimi
- [backtest.py](backtest.py) — Backtest motoru
- [scanner.py](scanner.py) — BIST 100 tarayıcı
- [portfolio.py](portfolio.py) — Portföy takip
- [bist_symbols.py](bist_symbols.py) — BIST 100 sembolleri

## Sonraki Adımlar

1. Önce **backtest** ile stratejiyi birkaç farklı hissede test et
2. Al-Tut'u yenemiyorsa bu strateji o hisse için uygun değil demektir
3. Sinyal geldiğinde **küçük pozisyonla başla** (880k'nın tamamını koyma)
4. Stop-loss'u **her zaman** kullan
5. Kayıpları kabullenmeyi öğren — kazanma oranı %40-50 bile olsa kârlı olabilirsin
