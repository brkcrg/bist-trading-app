"""BIST Swing Trading Asistanı — Kısa Vadeli (3-10 gün)"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from bist_symbols import BIST100
from data import fetch
from strategy import generate_signals, latest_signal, signal_strength
from backtest import run_backtest
from scanner import scan
from portfolio import Portfolio
from fundamentals import get_fundamentals, format_value
from intraday import generate_intraday_signals, intraday_summary

st.set_page_config(
    page_title="BIST Swing Pro",
    layout="wide",
    page_icon="TR",
    initial_sidebar_state="expanded",
)

# -------- PROFESYONEL CSS --------
st.markdown("""
<style>
    .main > div { padding-top: 1rem; }
    section[data-testid="stSidebar"] { background-color: #0A0E17; }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8B92A8;
    }
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #1A1F2E 0%, #141824 100%);
        border: 1px solid #2A3142;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    }
    h1 {
        background: linear-gradient(90deg, #00D4AA 0%, #0099FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        letter-spacing: -0.02em;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #0A0E17;
        padding: 6px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        padding: 10px 18px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #00D4AA 0%, #0099FF 100%) !important;
        color: #0A0E17 !important;
    }
    .signal-buy {
        background: linear-gradient(135deg, #00D4AA22 0%, #00995522 100%);
        border-left: 4px solid #00D4AA;
        padding: 12px 18px;
        border-radius: 8px;
        font-weight: 600;
    }
    .signal-sell {
        background: linear-gradient(135deg, #FF445522 0%, #CC112222 100%);
        border-left: 4px solid #FF4455;
        padding: 12px 18px;
        border-radius: 8px;
        font-weight: 600;
    }
    .signal-hold {
        background: #1A1F2E;
        border-left: 4px solid #8B92A8;
        padding: 12px 18px;
        border-radius: 8px;
        font-weight: 600;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #2A3142;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# -------- SIDEBAR --------
with st.sidebar:
    st.markdown("### BIST Swing Pro")
    st.caption("Kısa Vadeli Swing Trading · 3-10 gün")
    st.divider()
    st.markdown("**Strateji Özeti**")
    st.markdown("""
- **Giriş:** EMA9 × EMA21 yukarı kesim
- **Filtre:** RSI(7) 40-65 + hacim 1.2x
- **Stop:** Giriş − 1.5 × ATR
- **Hedef:** Giriş + 2.5 × ATR
- **Risk/Ödül:** 1 : 1.67
    """)
    st.divider()
    st.caption("Bu uygulama yatırım tavsiyesi değildir. Tüm işlemler kendi sorumluluğundadır.")

st.title("BIST Swing Trading Pro")
st.caption("Kısa vadeli (3-10 gün tutma) swing stratejisi · EMA9/21 + RSI(7) + ATR")

tab_dashboard, tab_intraday, tab_analysis, tab_fundamental, tab_backtest, tab_scanner, tab_portfolio = st.tabs(
    ["GÖSTERGE PANELİ", "GÜNLÜK TRADE", "TEKNİK ANALİZ", "TEMEL ANALİZ", "BACKTEST", "FIRSAT TARAYICI", "PORTFÖY"]
)

# ============== DASHBOARD ==============
with tab_dashboard:
    pf = Portfolio.load(initial_cash=880_000.0)
    snap = pf.snapshot()
    total = pf.total_value()
    invested = float(snap["Maliyet"].sum()) if not snap.empty else 0.0
    pnl = float(snap["K/Z"].sum()) if not snap.empty else 0.0
    pnl_pct = (pnl / invested * 100) if invested else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Varlık", f"{total:,.0f} TL", f"{pnl_pct:+.2f}%" if invested else None)
    c2.metric("Nakit", f"{pf.cash:,.0f} TL")
    c3.metric("Yatırılan", f"{invested:,.0f} TL")
    c4.metric("Toplam K/Z", f"{pnl:+,.0f} TL")

    st.divider()
    st.subheader("Açık Pozisyonlar")
    if snap.empty:
        st.info("Henüz açık pozisyon yok. FIRSAT TARAYICI sekmesinden sinyal veren hisseleri görebilirsin.")
    else:
        st.dataframe(snap, use_container_width=True, hide_index=True)

# ============== INTRADAY / DAY TRADING ==============
with tab_intraday:
    # Üst kontrol barı - yatay, sade
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([2, 1, 1, 1])
    with ctrl1:
        id_symbol = st.selectbox("HİSSE", BIST100, key="id_sym",
                                 index=BIST100.index("THYAO") if "THYAO" in BIST100 else 0,
                                 label_visibility="visible")
    with ctrl2:
        id_interval = st.selectbox("ZAMAN", ["5m", "15m", "30m", "1h"], index=1, key="id_intv")
    with ctrl3:
        gun_sayisi = st.selectbox("GÖSTER", ["Bugün", "Son 2 gün", "Son 5 gün"], index=1, key="id_days")
    with ctrl4:
        st.write("")
        refresh = st.button("YENİLE", type="primary", use_container_width=True)

    period_map = {"5m": "5d", "15m": "10d", "30m": "30d", "1h": "60d"}
    id_period = period_map[id_interval]

    with st.spinner(f"{id_symbol} yükleniyor..."):
        df_i = fetch(id_symbol, period=id_period, interval=id_interval)

    if df_i.empty:
        st.error("Veri çekilemedi. BIST kapalı olabilir.")
    else:
        sig_i = generate_intraday_signals(df_i, or_minutes=30)
        summary = intraday_summary(sig_i)

        if summary:
            last_price = summary["last"]
            last_atr = float(sig_i["atr"].iloc[-1]) if pd.notna(sig_i["atr"].iloc[-1]) else last_price * 0.01
            stop_price = last_price - last_atr
            target1 = last_price + last_atr
            target2 = last_price + 2 * last_atr

            # ==== BÜYÜK AKSIYON KARTI ====
            sig = summary["signal"]
            above_vwap = summary["above_vwap"]
            or_high = summary["or_high"]
            or_low = summary["or_low"]

            if sig == "LONG":
                bg = "linear-gradient(135deg, #00D4AA33 0%, #00995533 100%)"
                border = "#00D4AA"
                baslik = "ŞU AN: ALIM FIRSATI VAR"
                aciklama = f"Fiyat ORB yüksek seviyesini ({or_high:.2f}) kırdı, VWAP üstünde, hacim güçlü."
            elif sig == "EXIT":
                bg = "linear-gradient(135deg, #FF445533 0%, #CC112233 100%)"
                border = "#FF4455"
                baslik = "ŞU AN: POZİSYONDAN ÇIKMA ZAMANI"
                aciklama = "Fiyat VWAP altına düştü veya aşırı alım sinyali var. Açık pozisyonu kapat."
            else:
                bg = "linear-gradient(135deg, #2A314233 0%, #1A1F2E33 100%)"
                border = "#8B92A8"
                if above_vwap:
                    baslik = "ŞU AN: BEKLE (VWAP üstünde ama kırılım yok)"
                    aciklama = f"Fiyat ({last_price:.2f}) VWAP üstünde. ORB yüksek seviyesi ({or_high:.2f}) kırılırsa alım sinyali gelir."
                else:
                    baslik = "ŞU AN: ALIM YOK (VWAP altında)"
                    aciklama = f"Fiyat ({last_price:.2f}) VWAP ({summary['vwap']:.2f}) altında — satıcı üstünlüğü var. Uzak dur."

            st.markdown(f"""
<div style="background:{bg}; border-left:6px solid {border}; padding:20px 24px;
            border-radius:12px; margin-bottom:20px;">
    <div style="font-size:1.6rem; font-weight:800; color:{border}; margin-bottom:8px;">{baslik}</div>
    <div style="font-size:1rem; color:#C8CFDE; margin-bottom:12px;">{aciklama}</div>
    <div style="display:flex; gap:24px; font-size:0.95rem; color:#8B92A8;">
        <div><b style="color:#FAFAFA;">{id_symbol}</b> · {last_price:.2f} TL · <span style="color:{'#00D4AA' if summary['change_pct']>=0 else '#FF4455'}">{summary['change_pct']:+.2f}%</span></div>
    </div>
</div>
            """, unsafe_allow_html=True)

            # ==== İŞLEM PLANI (büyük, net) ====
            if sig == "LONG":
                st.markdown("#### İşlem Planı")
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("GİRİŞ", f"{last_price:.2f} TL")
                p2.metric("STOP", f"{stop_price:.2f} TL", f"{-last_atr/last_price*100:.2f}%")
                p3.metric("HEDEF 1", f"{target1:.2f} TL", f"+{last_atr/last_price*100:.2f}%")
                p4.metric("HEDEF 2", f"{target2:.2f} TL", f"+{2*last_atr/last_price*100:.2f}%")
                st.caption("Öneri: HEDEF 1'de yarı pozisyonu kapat, kalan için stop'u giriş seviyesine çek (zararsız).")

            # ==== DURUM ÖZETİ (basit kart) ====
            st.markdown("#### Bugünün Durumu")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Açılış", f"{summary['open']:.2f} TL")
            d2.metric("Gün Yüksek", f"{summary['high']:.2f} TL")
            d3.metric("Gün Düşük", f"{summary['low']:.2f} TL")
            d4.metric("VWAP", f"{summary['vwap']:.2f} TL",
                      "Üstünde ✓" if above_vwap else "Altında ✗")

            # ==== GRAFİK — sade, temiz ====
            # Sadece istenen süreyi göster
            days_map = {"Bugün": 1, "Son 2 gün": 2, "Son 5 gün": 5}
            n_days = days_map[gun_sayisi]
            unique_dates = sorted(set(sig_i.index.date))[-n_days:]
            chart_df = sig_i[sig_i.index.map(lambda x: x.date() in unique_dates)].copy()

            if chart_df.empty:
                chart_df = sig_i.tail(50)

            # Intraday'de kategorik eksen kullan (boşluksuz)
            chart_df = chart_df.reset_index()
            chart_df["label"] = chart_df.iloc[:, 0].dt.strftime("%d %b %H:%M")
            x_idx = list(range(len(chart_df)))

            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                row_heights=[0.75, 0.25],
                vertical_spacing=0.04,
            )

            # Mumlar
            fig.add_trace(go.Candlestick(
                x=x_idx,
                open=chart_df["Open"], high=chart_df["High"],
                low=chart_df["Low"], close=chart_df["Close"],
                name="Fiyat",
                increasing_line_color="#00D4AA", increasing_fillcolor="#00D4AA",
                decreasing_line_color="#FF4455", decreasing_fillcolor="#FF4455",
                line=dict(width=1.2),
            ), row=1, col=1)

            # VWAP — tek belirgin çizgi
            fig.add_trace(go.Scatter(
                x=x_idx, y=chart_df["vwap"],
                name="VWAP", line=dict(color="#FFB400", width=3),
                hovertemplate="VWAP: %{y:.2f}<extra></extra>",
            ), row=1, col=1)

            # ORB band (gölge olarak) - sadece son gün
            today_mask = chart_df.iloc[:, 0].dt.date == unique_dates[-1]
            if today_mask.any() and or_high and or_low:
                first_idx = int(chart_df[today_mask].index[0])
                last_idx = int(chart_df[today_mask].index[-1])
                fig.add_shape(
                    type="rect",
                    x0=first_idx, x1=last_idx,
                    y0=or_low, y1=or_high,
                    fillcolor="#FFB400", opacity=0.08,
                    line=dict(color="#FFB400", width=1, dash="dot"),
                    row=1, col=1,
                )
                fig.add_annotation(
                    x=first_idx, y=or_high, text=f"ORB {or_high:.2f}",
                    showarrow=False, xanchor="left", yanchor="bottom",
                    font=dict(color="#FFB400", size=11), row=1, col=1,
                )

            # LONG sinyal okları
            longs = chart_df[chart_df["long_signal"] == True]
            if not longs.empty:
                fig.add_trace(go.Scatter(
                    x=longs.index.tolist(), y=longs["Low"] - last_atr * 0.3,
                    mode="markers+text", name="AL SİNYALİ",
                    text=["AL"] * len(longs), textposition="bottom center",
                    textfont=dict(color="#00D4AA", size=12, family="Arial Black"),
                    marker=dict(symbol="triangle-up", size=20, color="#00D4AA",
                                line=dict(color="white", width=2)),
                ), row=1, col=1)

            # Aktif sinyal varsa stop/hedef çizgileri
            if sig == "LONG" and len(chart_df) > 0:
                last_x = len(chart_df) - 1
                for y, label, color in [
                    (stop_price, f"STOP {stop_price:.2f}", "#FF4455"),
                    (target1, f"HEDEF 1 {target1:.2f}", "#00D4AA"),
                    (target2, f"HEDEF 2 {target2:.2f}", "#00FFCC"),
                ]:
                    fig.add_hline(y=y, line_dash="dash", line_color=color, line_width=2, row=1, col=1)
                    fig.add_annotation(
                        x=last_x, y=y, text=label, showarrow=False,
                        xanchor="right", yanchor="bottom",
                        font=dict(color=color, size=11, family="Arial Black"),
                        row=1, col=1,
                    )

            # Hacim
            colors = ["#00D4AA" if c >= o else "#FF4455"
                      for c, o in zip(chart_df["Close"], chart_df["Open"])]
            fig.add_trace(go.Bar(
                x=x_idx, y=chart_df["Volume"],
                marker_color=colors, opacity=0.7, name="Hacim",
                hovertemplate="Hacim: %{y:,.0f}<extra></extra>",
            ), row=2, col=1)

            # X ekseni etiketleri - her gün başlangıcında
            tickvals = []
            ticktext = []
            prev_date = None
            for i, dt in enumerate(chart_df.iloc[:, 0]):
                if dt.date() != prev_date:
                    tickvals.append(i)
                    ticktext.append(dt.strftime("%d %b"))
                    prev_date = dt.date()

            fig.update_xaxes(
                tickvals=tickvals, ticktext=ticktext,
                showgrid=True, gridcolor="#1A1F2E",
                row=1, col=1,
            )
            fig.update_xaxes(
                tickvals=tickvals, ticktext=ticktext,
                showgrid=False, row=2, col=1,
            )
            fig.update_yaxes(
                showgrid=True, gridcolor="#1A1F2E",
                title_text="Fiyat (TL)", row=1, col=1,
            )
            fig.update_yaxes(
                showgrid=False, title_text="Hacim", row=2, col=1,
            )

            fig.update_layout(
                height=600,
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
                plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)",
                ),
                margin=dict(l=10, r=10, t=30, b=10),
                hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True)

            # ==== BASIT AÇIKLAMA ====
            with st.expander("Bu grafikte ne görüyorum?"):
                st.markdown("""
- **Mumlar (yeşil/kırmızı):** Her mum bir zaman aralığını (seçtiğin periyot kadar) gösterir.
- **Turuncu çizgi (VWAP):** Günün ortalama işlem fiyatı. Fiyat bunun **üstündeyse alıcı**, altındaysa satıcı üstünlüğü var.
- **Turuncu gölgeli kutu (ORB):** Seansın ilk 30 dakikasının yüksek/alçak aralığı. **Üst sınırı kırılırsa alım**, alt sınırı kırılırsa satım sinyali.
- **Yeşil AL okları:** Tüm koşullar uyuştuğunda (VWAP üstü + ORB kırılım + RSI uygun + hacim) ortaya çıkan otomatik alım sinyalleri.
- **Kesikli çizgiler:** Aktif sinyalin stop-loss ve hedef seviyeleri.

**Kurallar basitçe:** Yeşil ok = al · Fiyat VWAP'ın altına düşerse veya stop'a değerse = sat.
                """)

            # Son sinyaller tablosu - sade
            recent_longs = sig_i[sig_i["long_signal"] == True].tail(5).copy()
            if not recent_longs.empty:
                st.markdown("#### Son 5 AL Sinyali")
                rows = []
                for idx, r in recent_longs.iterrows():
                    rows.append({
                        "Tarih / Saat": idx.strftime("%d %b %H:%M"),
                        "Fiyat": f"{float(r['Close']):.2f}",
                        "VWAP": f"{float(r['vwap']):.2f}",
                        "RSI": f"{float(r['rsi']):.0f}",
                        "Hacim": f"{float(r['vol_ratio']):.1f}x",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ============== ANALYSIS ==============
with tab_analysis:
    col_ctrl, col_main = st.columns([1, 4])
    with col_ctrl:
        symbol = st.selectbox("Hisse", BIST100, index=BIST100.index("THYAO") if "THYAO" in BIST100 else 0, key="a_sym")
        period = st.selectbox("Dönem", ["3mo", "6mo", "1y", "2y"], index=1, key="a_period")
        st.caption("Kısa vade için 3-6 ay önerilir")

    with col_main:
        with st.spinner(f"{symbol} verisi yükleniyor..."):
            df = fetch(symbol, period=period)
        if df.empty:
            st.error("Veri çekilemedi.")
        else:
            sig = generate_signals(df)
            current_signal = latest_signal(sig)
            strength = signal_strength(sig)
            last = sig.iloc[-1]
            last_price = float(last["Close"])
            last_rsi = float(last["rsi"]) if pd.notna(last["rsi"]) else 0
            last_atr = float(last["atr"]) if pd.notna(last["atr"]) else 0
            vol_ratio = float(last["vol_ratio"]) if pd.notna(last["vol_ratio"]) else 0

            # Sinyal kartı
            signal_class = {"BUY": "signal-buy", "SELL": "signal-sell", "HOLD": "signal-hold"}[current_signal]
            signal_text = {"BUY": "AL SİNYALİ", "SELL": "SAT SİNYALİ", "HOLD": "BEKLE"}[current_signal]
            suggested_stop = last_price - 1.5 * last_atr
            suggested_target = last_price + 2.5 * last_atr
            st.markdown(
                f'<div class="{signal_class}">'
                f'<b>{signal_text}</b> · {symbol} · {last_price:.2f} TL · Güç: {strength:.0f}/100'
                f'</div>',
                unsafe_allow_html=True,
            )

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Fiyat", f"{last_price:.2f} TL")
            m2.metric("RSI(7)", f"{last_rsi:.1f}")
            m3.metric("Hacim", f"{vol_ratio:.2f}x")
            m4.metric("Önerilen Stop", f"{suggested_stop:.2f}", f"{(suggested_stop/last_price-1)*100:.2f}%")
            m5.metric("Hedef", f"{suggested_target:.2f}", f"{(suggested_target/last_price-1)*100:+.2f}%")

            # Ana grafik
            fig = make_subplots(
                rows=3, cols=1, shared_xaxes=True,
                row_heights=[0.6, 0.2, 0.2],
                vertical_spacing=0.03,
                subplot_titles=("Fiyat + EMA", "RSI(7)", "Hacim"),
            )
            fig.add_trace(go.Candlestick(
                x=sig.index, open=sig["Open"], high=sig["High"],
                low=sig["Low"], close=sig["Close"], name=symbol,
                increasing_line_color="#00D4AA", decreasing_line_color="#FF4455",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=sig.index, y=sig["ema_fast"], name="EMA9", line=dict(color="#FFB400", width=2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=sig.index, y=sig["ema_slow"], name="EMA21", line=dict(color="#0099FF", width=2)), row=1, col=1)

            buys = sig[sig["buy_signal"]]
            sells = sig[sig["sell_signal"]]
            fig.add_trace(go.Scatter(
                x=buys.index, y=buys["Close"], mode="markers", name="AL",
                marker=dict(symbol="triangle-up", size=14, color="#00D4AA", line=dict(color="white", width=1)),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=sells.index, y=sells["Close"], mode="markers", name="SAT",
                marker=dict(symbol="triangle-down", size=14, color="#FF4455", line=dict(color="white", width=1)),
            ), row=1, col=1)

            fig.add_trace(go.Scatter(x=sig.index, y=sig["rsi"], name="RSI", line=dict(color="#BB88FF", width=2)), row=2, col=1)
            fig.add_hline(y=65, line_dash="dot", line_color="#FF4455", row=2, col=1)
            fig.add_hline(y=40, line_dash="dot", line_color="#00D4AA", row=2, col=1)

            colors = ["#00D4AA" if c >= o else "#FF4455" for c, o in zip(sig["Close"], sig["Open"])]
            fig.add_trace(go.Bar(x=sig.index, y=sig["Volume"], name="Hacim", marker_color=colors, opacity=0.6), row=3, col=1)

            fig.update_layout(
                height=750,
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
                plot_bgcolor="#0E1117",
                paper_bgcolor="#0E1117",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                margin=dict(l=0, r=0, t=30, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Son sinyaller tablosu
            recent_signals = sig[(sig["buy_signal"]) | (sig["sell_signal"])].tail(10).copy()
            if not recent_signals.empty:
                recent_signals["Tip"] = recent_signals.apply(
                    lambda r: "AL" if r["buy_signal"] else "SAT", axis=1
                )
                recent_signals["Tarih"] = recent_signals.index.strftime("%Y-%m-%d")
                display = recent_signals[["Tarih", "Tip", "Close", "rsi", "vol_ratio"]].rename(
                    columns={"Close": "Fiyat", "rsi": "RSI", "vol_ratio": "Hacim x"}
                )
                display["Fiyat"] = display["Fiyat"].round(2)
                display["RSI"] = display["RSI"].round(1)
                display["Hacim x"] = display["Hacim x"].round(2)
                st.subheader("Son Sinyaller")
                st.dataframe(display, use_container_width=True, hide_index=True)

# ============== FUNDAMENTAL ==============
with tab_fundamental:
    col_ctrl, col_main = st.columns([1, 4])
    with col_ctrl:
        fa_mode = st.radio("Mod", ["Tek Hisse", "Karşılaştır"], key="fa_mode")
        if fa_mode == "Tek Hisse":
            fa_symbol = st.selectbox("Hisse", BIST100, key="fa_sym",
                                     index=BIST100.index("THYAO") if "THYAO" in BIST100 else 0)
        else:
            fa_symbols = st.multiselect("Hisseler (2-6)", BIST100,
                                        default=["THYAO", "GARAN", "EREGL", "TUPRS"], key="fa_syms")

    with col_main:
        if fa_mode == "Tek Hisse":
            with st.spinner(f"{fa_symbol} temel verileri çekiliyor..."):
                f = get_fundamentals(fa_symbol)

            st.markdown(f"### {f.name}")
            st.caption(f"{f.sector} · {f.industry}" if f.sector else "Sektör bilgisi yok")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Temel Skor", f"{f.score:.0f}/100", f"Not: {f.grade}")
            c2.metric("Piyasa Değeri", format_value(f.market_cap, suffix=" TL"))
            c3.metric("F/K", format_value(f.pe_ratio))
            c4.metric("PD/DD", format_value(f.pb_ratio))

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("ROE", format_value(f.roe, pct=True))
            c6.metric("Kâr Marjı", format_value(f.profit_margin, pct=True))
            c7.metric("Gelir Büyüme", format_value(f.revenue_growth, pct=True))
            c8.metric("Temettü", format_value(f.dividend_yield, pct=True))

            if f.breakdown:
                st.subheader("Skor Dağılımı")
                bd_df = pd.DataFrame([
                    {"Metrik": k, "Puan (0-10)": round(v, 1), "Bar": "█" * int(v)}
                    for k, v in f.breakdown.items()
                ])
                st.dataframe(bd_df, use_container_width=True, hide_index=True)

            # Teknik + temel birleşik değerlendirme
            try:
                df_t = fetch(fa_symbol, period="3mo")
                if not df_t.empty:
                    sig_t = generate_signals(df_t)
                    tech_sig = latest_signal(sig_t)
                    tech_strength = signal_strength(sig_t)
                    st.divider()
                    st.subheader("Birleşik Değerlendirme")
                    bc1, bc2, bc3 = st.columns(3)
                    bc1.metric("Teknik Sinyal", tech_sig, f"Güç: {tech_strength:.0f}/100")
                    bc2.metric("Temel Skor", f"{f.score:.0f}/100", f"Not: {f.grade}")
                    combined = (tech_strength * 0.5 + f.score * 0.5)
                    bc3.metric("Birleşik Skor", f"{combined:.0f}/100")

                    if tech_sig == "BUY" and f.score >= 60:
                        st.success("**Güçlü alım adayı:** Hem teknik sinyal pozitif hem temel görünüm sağlam.")
                    elif tech_sig == "BUY" and f.score < 40:
                        st.warning("**Dikkat:** Teknik sinyal var ama temel zayıf — riskli, kısa vadeli spekülatif işlem.")
                    elif f.score >= 70 and tech_sig != "BUY":
                        st.info("Temel sağlam ama teknik sinyal yok. Giriş için kesişimi bekle.")
            except Exception:
                pass

        else:  # Karşılaştır
            if fa_symbols:
                with st.spinner("Temel veriler çekiliyor..."):
                    data = [get_fundamentals(s) for s in fa_symbols]
                cmp_df = pd.DataFrame([{
                    "Sembol": f.symbol,
                    "Sektör": f.sector or "—",
                    "Skor": f.score,
                    "Not": f.grade,
                    "F/K": round(f.pe_ratio, 2) if f.pe_ratio else None,
                    "PD/DD": round(f.pb_ratio, 2) if f.pb_ratio else None,
                    "ROE %": round(f.roe * 100, 2) if f.roe else None,
                    "Borç/Öz": round(f.debt_to_equity, 2) if f.debt_to_equity else None,
                    "Marj %": round(f.profit_margin * 100, 2) if f.profit_margin else None,
                    "Gelir Büy. %": round(f.revenue_growth * 100, 2) if f.revenue_growth else None,
                } for f in data]).sort_values("Skor", ascending=False)
                st.dataframe(cmp_df, use_container_width=True, hide_index=True)

                # Bar chart
                fig = go.Figure(go.Bar(
                    x=cmp_df["Sembol"], y=cmp_df["Skor"],
                    marker=dict(
                        color=cmp_df["Skor"],
                        colorscale=[[0, "#FF4455"], [0.5, "#FFB400"], [1, "#00D4AA"]],
                    ),
                    text=cmp_df["Not"], textposition="outside",
                ))
                fig.update_layout(
                    title="Temel Skor Karşılaştırması",
                    height=400, template="plotly_dark",
                    plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                    yaxis_range=[0, 110], margin=dict(l=0, r=0, t=50, b=0),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("En az 2 hisse seç.")

# ============== BACKTEST ==============
with tab_backtest:
    col_ctrl, col_main = st.columns([1, 4])
    with col_ctrl:
        bt_symbol = st.selectbox("Hisse", BIST100, key="bt_sym", index=BIST100.index("THYAO") if "THYAO" in BIST100 else 0)
        bt_period = st.selectbox("Dönem", ["6mo", "1y", "2y", "5y"], index=2, key="bt_period")
        bt_capital = st.number_input("Sermaye (TL)", 10_000, 100_000_000, 880_000, step=10_000)
        bt_risk = st.slider("İşlem başına risk %", 0.5, 5.0, 2.0, 0.5) / 100
        run_btn = st.button("BACKTEST ÇALIŞTIR", type="primary", use_container_width=True)

    with col_main:
        if run_btn:
            with st.spinner("Backtest çalışıyor..."):
                df = fetch(bt_symbol, period=bt_period)
                if df.empty:
                    st.error("Veri yok.")
                else:
                    sig = generate_signals(df)
                    result = run_backtest(sig, initial_capital=bt_capital, risk_per_trade=bt_risk)

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Toplam Getiri", f"{result.total_return_pct:+.2f}%")
                    m2.metric("İşlem", f"{result.num_trades}")
                    m3.metric("Kazanma %", f"{result.win_rate:.1f}%")
                    m4.metric("Max DD", f"{result.max_drawdown_pct:.1f}%")

                    m5, m6, m7 = st.columns(3)
                    m5.metric("Final Sermaye", f"{result.final_capital:,.0f} TL")
                    m6.metric("Net K/Z", f"{result.final_capital - bt_capital:+,.0f} TL")
                    m7.metric("Profit Factor", f"{result.profit_factor:.2f}")

                    bh_return = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
                    diff = result.total_return_pct - bh_return
                    if diff > 0:
                        st.success(f"Strateji Al-Tut'u **{diff:+.2f}%** geçti. (Strateji: {result.total_return_pct:+.2f}% · Al-Tut: {bh_return:+.2f}%)")
                    else:
                        st.warning(f"Al-Tut daha iyi performans gösterdi: **{diff:+.2f}%**. (Strateji: {result.total_return_pct:+.2f}% · Al-Tut: {bh_return:+.2f}%)")

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=result.equity_curve.index, y=result.equity_curve.values,
                        name="Strateji", line=dict(color="#00D4AA", width=2.5),
                        fill="tozeroy", fillcolor="rgba(0,212,170,0.1)",
                    ))
                    bh_curve = bt_capital * (df["Close"] / df["Close"].iloc[0])
                    fig.add_trace(go.Scatter(
                        x=bh_curve.index, y=bh_curve.values,
                        name="Al-Tut", line=dict(color="#8B92A8", width=2, dash="dash"),
                    ))
                    fig.update_layout(
                        title="Sermaye Eğrisi",
                        height=420,
                        template="plotly_dark",
                        plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                        yaxis_title="Sermaye (TL)",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                        margin=dict(l=0, r=0, t=50, b=0),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    if result.trades:
                        trades_df = pd.DataFrame([{
                            "Giriş": t.entry_date.strftime("%Y-%m-%d") if t.entry_date else "",
                            "Çıkış": t.exit_date.strftime("%Y-%m-%d") if t.exit_date else "AÇIK",
                            "Giriş TL": round(t.entry_price, 2),
                            "Çıkış TL": round(t.exit_price, 2) if t.exit_price else None,
                            "Lot": t.shares,
                            "K/Z TL": round(t.pnl, 2),
                            "K/Z %": round(t.pnl_pct, 2),
                            "Sebep": t.reason,
                        } for t in result.trades])
                        st.subheader("İşlem Geçmişi")
                        st.dataframe(trades_df, use_container_width=True, hide_index=True)
        else:
            st.info("Sol panelden parametreleri ayarla ve BACKTEST ÇALIŞTIR butonuna bas.")

# ============== SCANNER ==============
with tab_scanner:
    st.markdown("**BIST 100 tarayıcı** — bugün sinyal güç skoru en yüksek hisseleri bulur.")
    col_ctrl, col_main = st.columns([1, 4])
    with col_ctrl:
        scan_period = st.selectbox("Dönem", ["3mo", "6mo", "1y"], index=1, key="sc_period")
        min_strength = st.slider("Min. Teknik Güç", 0, 100, 50, 5)
        include_fund = st.checkbox("Temel analizi de dahil et", value=True)
        min_fund = st.slider("Min. Temel Skor", 0, 100, 40, 5, disabled=not include_fund)
        scan_btn = st.button("TARAMAYI BAŞLAT", type="primary", use_container_width=True)
        st.caption("Temel analiz dahil tarama 3-5 dakika sürebilir (ilk seferinde)")

    with col_main:
        if scan_btn:
            with st.spinner("BIST 100 taranıyor..."):
                results = scan(period=scan_period, include_fundamentals=include_fund)
            if not results.empty:
                sort_col = "Birleşik" if include_fund and "Birleşik" in results.columns else "Güç"
                results = results.sort_values(sort_col, ascending=False)
                filtered = results[results["Güç"] >= min_strength]
                if include_fund and "Temel" in filtered.columns:
                    filtered = filtered[filtered["Temel"].fillna(0) >= min_fund]
                st.success(f"**{len(filtered)}** hisse bulundu (toplam {len(results)} tarandı)")
                st.dataframe(filtered, use_container_width=True, hide_index=True)
            else:
                st.warning("Sonuç yok")
        else:
            st.info("Sol panelden TARAMAYI BAŞLAT butonuna bas.")

# ============== PORTFOLIO ==============
with tab_portfolio:
    pf = Portfolio.load(initial_cash=880_000.0)
    snap = pf.snapshot()

    c1, c2, c3 = st.columns(3)
    c1.metric("Nakit", f"{pf.cash:,.2f} TL")
    c2.metric("Toplam Değer", f"{pf.total_value():,.2f} TL")
    c3.metric("Pozisyon", f"{len(pf.positions)}")

    if not snap.empty:
        st.dataframe(snap, use_container_width=True, hide_index=True)

    st.divider()
    col_buy, col_sell = st.columns(2)

    with col_buy:
        st.markdown("#### ALIM")
        buy_sym = st.selectbox("Hisse", BIST100, key="buy_sym")
        bc1, bc2 = st.columns(2)
        buy_shares = bc1.number_input("Lot", 1, 1_000_000, 100, key="buy_lot")
        buy_price = bc2.number_input("Fiyat", 0.01, 100_000.0, 10.0, step=0.01, key="buy_price")
        buy_stop = st.number_input("Stop-Loss (0 = yok)", 0.0, 100_000.0, 0.0, step=0.01, key="buy_stop")
        if st.button("ALIM YAP", type="primary", use_container_width=True):
            try:
                pf.buy(buy_sym, buy_shares, buy_price, stop_loss=buy_stop if buy_stop > 0 else None)
                st.success(f"{buy_shares} lot {buy_sym} alındı")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    with col_sell:
        st.markdown("#### SATIM")
        if pf.positions:
            sell_sym = st.selectbox("Hisse", [p.symbol for p in pf.positions], key="sell_sym")
            sc1, sc2 = st.columns(2)
            sell_shares = sc1.number_input("Lot", 1, 1_000_000, 100, key="sell_lot")
            sell_price = sc2.number_input("Fiyat", 0.01, 100_000.0, 10.0, step=0.01, key="sell_price")
            if st.button("SATIM YAP", use_container_width=True):
                try:
                    pnl = pf.sell(sell_sym, sell_shares, sell_price)
                    st.success(f"Satıldı. K/Z: {pnl:+,.2f} TL")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        else:
            st.info("Açık pozisyon yok")
