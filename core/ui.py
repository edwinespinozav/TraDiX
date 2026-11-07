"""Estilo visual (tema terminal profesional) y gráficos."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

BG, PANEL, BORDER = "#0b0f17", "#111827", "#1f2937"
TXT, MUTED = "#e5e7eb", "#8b95a7"
GREEN, RED, AMBER, BLUE, VIOLET = "#22c55e", "#ef4444", "#f59e0b", "#3b82f6", "#a78bfa"
NEUTRAL = "#60a5fa"  # azul: mercado indeciso / pronóstico neutro

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stText {{ font-family: 'Inter', sans-serif; }}
html {{ font-size: 14px; }}
.block-container {{ padding: 2.2rem 1.2rem 1.5rem 1.2rem; max-width: 100%; }}
h1, h2, h3 {{ letter-spacing: -0.02em; }}
h2 {{ font-size: 1.35rem !important; }}
[data-testid="stSidebar"] {{ background: #0d1320; border-right: 1px solid {BORDER}; }}
[data-testid="stVerticalBlock"] {{ gap: 0.55rem; }}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{ padding: 0.15rem 0.1rem; }}
/* botones primarios en el color de la marca (independiente de config.toml) */
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
  background: #16a34a !important; border-color: #16a34a !important; color: #fff !important; }}
.stButton button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{ background: #15803d !important; }}
.kpi {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 10px; height: 100%; }}
.kpi .lbl {{ color: {MUTED}; font-size: 0.66rem; text-transform: uppercase; letter-spacing: .07em; }}
.kpi .val {{ font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 600; margin-top: 2px; }}
.kpi .sub {{ color: {MUTED}; font-size: 0.7rem; margin-top: 1px; }}
.pill {{ display:inline-block; padding: 2px 9px; border-radius: 999px; font-size: .72rem; font-weight: 600; margin-right: 4px; }}
.brand {{ font-weight: 700; font-size: 1.1rem; letter-spacing: -.01em; }}
.brand span {{ color: {GREEN}; }}
.muted {{ color: {MUTED}; font-size: .8rem; }}
.small {{ font-size: .78rem; }}
.bigpx {{ font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 600; }}
/* encabezado de la acción */
.qhead {{ display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; margin: 2px 0 4px; }}
.qhead .qt {{ font-size: 1.45rem; font-weight: 700; letter-spacing: -.02em; }}
.qhead .qpx {{ font-family: 'JetBrains Mono', monospace; font-size: 1.3rem; font-weight: 600; }}
.qhead .qch {{ font-family: 'JetBrains Mono', monospace; font-size: .95rem; }}
/* panel vertical de métricas */
.mp {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 10px 8px; }}
.mp-h {{ color: {MUTED}; font-size: .64rem; text-transform: uppercase; letter-spacing: .08em; margin: 8px 0 2px;
         border-bottom: 1px solid {BORDER}; padding-bottom: 2px; }}
.mp-h:first-child {{ margin-top: 2px; }}
.mp-r {{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; font-size: .8rem; padding: 2px 0; }}
.mp-r b {{ font-family: 'JetBrains Mono', monospace; font-size: .88rem; white-space: nowrap; }}
.mp-s {{ color: {MUTED}; font-size: .68rem; margin: -2px 0 3px; line-height: 1.25; }}
/* informe IA */
.sec {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: {MUTED}; font-weight: 600; padding-top: 6px; }}
.sec2 {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .07em; color: {MUTED}; font-weight: 600; margin: 8px 0 3px; }}
.rep p.lead {{ font-size: .92rem; margin: 6px 0 4px; line-height: 1.45; }}
.rep-b {{ background: #0f1626; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 9px; font-size: .8rem; line-height: 1.45; height: 100%; }}
ul.tl {{ margin: 0; padding-left: 16px; font-size: .8rem; line-height: 1.45; }}
ul.tl li {{ margin: 2px 0; }}
table.qt-tab {{ width: 100%; border-collapse: collapse; font-size: .78rem; }}
table.qt-tab th {{ text-align: left; color: {MUTED}; font-weight: 500; font-size: .66rem; text-transform: uppercase; letter-spacing: .05em;
                  border-bottom: 1px solid {BORDER}; padding: 4px 6px; }}
table.qt-tab td {{ border-bottom: 1px solid {BORDER}; padding: 4px 6px; vertical-align: top; }}
table.qt-tab td.n {{ font-family: 'JetBrains Mono', monospace; white-space: nowrap; }}
/* fundamentales clave */
.fr {{ display:grid; grid-template-columns: 10px 1fr auto; gap: 0 8px; align-items: baseline; padding: 3px 0; border-bottom: 1px dashed {BORDER}; }}
.fr .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.fr .fm {{ font-size: .8rem; font-weight: 600; }}
.fr .fv {{ font-family: 'JetBrains Mono', monospace; font-size: .8rem; }}
.fr .fl {{ grid-column: 2 / 4; color: {MUTED}; font-size: .7rem; line-height: 1.3; }}
.fr .fb {{ opacity: .7; }}
.verdict {{ border-radius: 10px; padding: 12px 14px; border: 1px solid {BORDER}; background: {PANEL}; }}
.verdict h2 {{ margin: 0 0 4px 0; font-size: 1.3rem; }}
.disclaimer {{ color: {MUTED}; font-size: .68rem; border-top: 1px solid {BORDER}; padding-top: 6px; margin-top: 16px; }}
div[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 8px; }}
/* ocultar barra de Streamlit (Deploy, menú, íconos de GitHub) */
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], #MainMenu, footer, .viewerBadge_container__1QSob, [class*="viewerBadge"] {{ display: none !important; }}
header[data-testid="stHeader"] {{ background: transparent; height: 2.6rem; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }}
/* ---------- celular ---------- */
@media (max-width: 700px) {{
  html {{ font-size: 13px; }}
  .block-container {{ padding: 3.2rem 0.55rem 1rem 0.55rem !important; }}
  .qhead {{ gap: 6px; }}
  .qhead .qt {{ font-size: 1.2rem; }}
  .qhead .qpx {{ font-size: 1.1rem; }}
  .qhead .muted {{ width: 100%; font-size: .72rem; }}
  .kpi {{ padding: 6px 8px; }}
  .kpi .val {{ font-size: .98rem; }}
  .mp {{ padding: 4px 8px 6px; }}
  .mp-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }}
  .mp-cols .mp-h {{ grid-column: 1 / -1; }}
  .rep p.lead {{ font-size: .88rem; }}
  table.qt-tab {{ display: block; overflow-x: auto; white-space: nowrap; }}
  div[data-testid="stHorizontalBlock"] {{ gap: .45rem !important; }}
  .stTabs [data-baseweb="tab-list"] {{ overflow-x: auto; flex-wrap: nowrap; }}
  .bias-top {{ flex-wrap: wrap; gap: 2px 10px; }}
}}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def color_for(v: float, good=0, bad=0) -> str:
    return GREEN if v > good else (RED if v < bad else NEUTRAL)


def kpi(col, label: str, value: str, sub: str = "", color: str = TXT):
    col.markdown(f"<div class='kpi'><div class='lbl'>{label}</div>"
                 f"<div class='val' style='color:{color}'>{value}</div>"
                 f"<div class='sub'>{sub}</div></div>", unsafe_allow_html=True)


def pill(text: str, color: str) -> str:
    return f"<span class='pill' style='background:{color}22;color:{color};border:1px solid {color}55'>{text}</span>"


SIGNAL_COLORS = {"COMPRA FUERTE": GREEN, "COMPRA": "#4ade80", "REBOTE (contratendencia)": AMBER,
                 "NEUTRAL": NEUTRAL, "EVITAR / VENTA": RED, "COMPRAR": GREEN, "ESPERAR": NEUTRAL,
                 "VENTA FUERTE": RED, "VENTA": "#f87171",
                 "EVITAR": RED, "VENDER EN CORTO": RED}


def _tag(fig, y, text, color, row=1, size=10.5):
    """Etiqueta de precio estilo TradingView en el eje derecho."""
    fig.add_annotation(xref="paper", x=1.0, xanchor="left", yref="y" if row == 1 else f"y{row}", y=y,
                       text=f"<b>{text}</b>", showarrow=False, font=dict(color="#0b0f17", size=size),
                       bgcolor=color, borderpad=2, opacity=0.95)


def price_chart(d: pd.DataFrame, plan: dict | None = None, vp: dict | None = None, verdict: dict | None = None,
                bars: int = 180, times: dict | None = None, show_bb: bool = False, show_vp: bool = True,
                mobile: bool = False, tf: str = "1D", crypto: bool = False, settings: dict | None = None) -> go.Figure:
    import numpy as np
    from .profiles import ma_color, ma_label
    from .timeframes import future_index, rangebreaks
    settings = settings or d.attrs.get("settings")
    fx = lambda n: future_index(x[-1], n, tf, crypto)  # fecha de la vela n en el futuro
    d = d.tail(bars)
    x = d.index
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.018,
                        row_heights=[0.62, 0.12, 0.13, 0.13], specs=[[{"secondary_y": True}], [{}], [{}], [{}]])
    # --- Volumen superpuesto (25% inferior del panel de precio) ---
    vc = np.where(d["Close"] >= d["Open"], "rgba(38,166,154,0.28)", "rgba(239,83,80,0.28)")
    fig.add_trace(go.Bar(x=x, y=d["Volume"], marker_color=vc, name="Volumen", showlegend=False,
                         hovertemplate="Vol %{y:,.0f}<extra></extra>"), 1, 1, secondary_y=True)
    # --- Velas y medias (EMA9 amarilla, EMA21 roja, SMA50 verde, SMA200 morada) ---
    fig.add_trace(go.Candlestick(x=x, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"], name="Precio",
                                 increasing=dict(line=dict(color="#26a69a", width=1), fillcolor="#26a69a"),
                                 decreasing=dict(line=dict(color="#ef5350", width=1), fillcolor="#ef5350")), 1, 1)
    for col, w in (("EMA9", 1.1), ("EMA21", 1.4), ("SMA50", 1.6), ("SMA200", 2.2)):
        fig.add_trace(go.Scatter(x=x, y=d[col], name=ma_label(settings, col), line=dict(color=ma_color(settings, col), width=w),
                                 hoverinfo="skip"), 1, 1)
    if show_bb:
        fig.add_trace(go.Scatter(x=x, y=d["BB_up"], name="Bollinger", line=dict(color="#64748b", width=0.8, dash="dot"), hoverinfo="skip"), 1, 1)
        fig.add_trace(go.Scatter(x=x, y=d["BB_low"], showlegend=False, line=dict(color="#64748b", width=0.8, dash="dot"),
                                 fill="tonexty", fillcolor="rgba(100,116,139,0.05)", hoverinfo="skip"), 1, 1)

    last_x, last_px = x[-1], float(d["Close"].iloc[-1])
    lo, hi = float(d["Low"].min()), float(d["High"].max())
    x_end = last_x
    if plan:
        e, sl, t1, t2, atr = plan["entrada"], plan["stop"], plan["objetivo_1"], plan["objetivo_2"], plan["atr"]
        s1 = (times or {}).get("sesiones_a_objetivo_1") or 10
        s2 = (times or {}).get("sesiones_a_objetivo_2") or max(s1 + 5, 18)
        x_end = fx(int(s2) + 3)
        limit = plan.get("modo_entrada") == "limit"
        # Entrada a mercado: la caja nace en el cierre actual. Entrada proyectada (Limit): la caja se desplaza
        # al futuro, a partir de la sesión en que se espera el retroceso al soporte.
        x0 = fx(2) if limit else x[max(0, len(x) - 6)]
        # zonas sombreadas: beneficio (verde) y riesgo (rojo)
        fig.add_shape(type="rect", x0=x0, x1=x_end, y0=e, y1=t2, fillcolor="rgba(34,197,94,0.10)", line_width=0, row=1, col=1)
        fig.add_shape(type="rect", x0=x0, x1=x_end, y0=e, y1=t1, fillcolor="rgba(34,197,94,0.12)", line_width=0, row=1, col=1)
        fig.add_shape(type="rect", x0=x0, x1=x_end, y0=sl, y1=e, fillcolor="rgba(239,68,68,0.16)", line_width=0, row=1, col=1)
        # zona de compra (±0.3 ATR alrededor de la entrada)
        fig.add_shape(type="rect", x0=x0, x1=x_end, y0=e - 0.3 * atr, y1=e + 0.3 * atr,
                      fillcolor="rgba(96,165,250,0.18)", line=dict(color="rgba(96,165,250,0.5)", width=1), row=1, col=1)
        fig.add_annotation(x=x0, y=e + 0.3 * atr, xanchor="left", yanchor="bottom",
                           text="" if mobile else ("ZONA DE ENTRADA PROYECTADA (LIMIT)" if limit else "ZONA DE ENTRADA (A MERCADO)"),
                           showarrow=False, font=dict(size=10, color="#93c5fd"), row=1, col=1)
        if limit:
            # retroceso esperado: del cierre actual hasta la zona de entrada
            fig.add_annotation(x=x0, y=e, ax=last_x, ay=last_px, xref="x", yref="y", axref="x", ayref="y",
                               showarrow=True, arrowhead=2, arrowsize=1.1, arrowwidth=1.4, arrowcolor="#fbbf24",
                               text="")
        if plan.get("estado"):
            wait = plan.get("estado_tipo") == "esperar"
            fig.add_annotation(xref="paper", yref="paper", x=0.005, y=0.995, xanchor="left", yanchor="top",
                               text=("⏳ " if wait else "✅ ") + plan["estado"] + ("" if mobile else "  ·  " + plan.get("marco_corto", "")),
                               showarrow=False, font=dict(size=11 if mobile else 12, color="#0b0f17"),
                               bgcolor="#fbbf24" if wait else "#22c55e", borderpad=4)
        # trayectoria proyectada
        px_path = [last_px] + ([e] if abs(e - last_px) > 0.15 * atr else []) + [t1, t2]
        xs = [last_x] + ([fx(2)] if len(px_path) == 4 else [])
        xs += [fx(int(s1)), fx(int(s2))]
        fig.add_trace(go.Scatter(x=xs, y=px_path, mode="lines+markers", name="Proyección",
                                 line=dict(color="#93c5fd", width=2, dash="dot"),
                                 marker=dict(size=[4] * (len(xs) - 1) + [9], symbol=["circle"] * (len(xs) - 1) + ["triangle-up" if t2 > e else "triangle-down"]),
                                 hovertemplate="%{x|%d-%b}: %{y:.2f}<extra>Proyección</extra>"), 1, 1)
        fig.add_annotation(x=xs[-2], y=t1, text=f"TP1 ~{int(s1)} ses.", showarrow=False, yshift=12,
                           font=dict(size=10, color="#86efac"), row=1, col=1)
        fig.add_annotation(x=xs[-1], y=t2, text=f"TP2 ~{int(s2)} ses.", showarrow=False, yshift=12,
                           font=dict(size=10, color="#86efac"), row=1, col=1)
        # líneas horizontales + etiquetas de precio
        for y, lbl, c, dash, wdt in ((e, ("E" if mobile else ("LIMIT" if limit else "ENTRADA")), "#60a5fa", "dash" if limit else "solid", 1.6),
                                     (sl, "SL" if mobile else "STOP", "#ef4444", "solid", 1.6),
                                     (t1, "TP1", "#22c55e", "dash", 1.3), (t2, "TP2", "#22c55e", "dash", 1.3)):
            fig.add_hline(y=y, line=dict(color=c, width=wdt, dash=dash), row=1, col=1)
            _tag(fig, y, f"{lbl} {y:,.2f}", c, size=9 if mobile else 10.5)
        for lv, n in plan.get("soportes", [])[:3]:
            fig.add_hline(y=lv, line=dict(color="rgba(38,166,154,0.45)", width=1, dash="dot"), row=1, col=1)
        for lv, n in plan.get("resistencias", [])[:3]:
            fig.add_hline(y=lv, line=dict(color="rgba(239,83,80,0.45)", width=1, dash="dot"), row=1, col=1)
        # niveles de la IA si difieren
        if verdict and verdict.get("entrada") and abs(float(verdict["entrada"]) / e - 1) > 0.003:
            for key, lbl, c in (("entrada", "IA E", "#60a5fa"), ("stop", "IA SL", "#ef4444"), ("objetivo_1", "IA TP1", "#22c55e")):
                if verdict.get(key):
                    fig.add_hline(y=float(verdict[key]), line=dict(color=c, width=1, dash="dashdot"), row=1, col=1)
        lv_all = [e, sl, t1, t2]
        lo, hi = min([lo] + lv_all), max([hi] + lv_all)
    # --- Perfil de volumen (VRVP) con POC y área de valor ---
    vp_axis = None
    if show_vp and vp and len(vp.get("precios", [])):
        tot = vp["up"] + vp["down"]
        fig.add_trace(go.Bar(y=vp["precios"], x=tot, orientation="h", width=vp["alto_bin"] * 0.92, xaxis="x5", yaxis="y",
                             marker_color="rgba(59,91,219,0.30)", name="VRVP", hovertemplate="%{y:.2f}: %{x:,.0f}<extra>Vol. total</extra>"))
        fig.add_trace(go.Bar(y=vp["precios"], x=vp["up"], orientation="h", width=vp["alto_bin"] * 0.92, xaxis="x5", yaxis="y",
                             marker_color="rgba(212,160,23,0.45)", showlegend=False, hovertemplate="%{y:.2f}: %{x:,.0f}<extra>Vol. comprador</extra>"))
        vp_axis = dict(overlaying="x", anchor="y", range=[float(tot.max()) * 4.5, 0], autorange=False,
                       visible=False, fixedrange=True, showgrid=False)
        fig.add_hline(y=vp["poc"], line=dict(color="#f59e0b", width=2), row=1, col=1)
        fig.add_annotation(xref="paper", x=0.775, xanchor="right", yref="y", y=vp["poc"], text=f"<b>POC {vp['poc']:,.2f}</b>",
                           showarrow=False, font=dict(size=10, color="#0b0f17"), bgcolor="#f59e0b", borderpad=2)
        for k in ("vah", "val"):
            fig.add_hline(y=vp[k], line=dict(color="rgba(245,158,11,0.5)", width=1, dash="dash"), row=1, col=1)
            fig.add_annotation(xref="paper", x=0.775, xanchor="right", yref="y", y=vp[k], text=k.upper(), showarrow=False,
                               font=dict(size=9, color="#fbbf24"), yshift=7)
    if not plan or abs(plan["entrada"] - last_px) > 0.25 * plan["atr"]:
        _tag(fig, last_px, f"{last_px:,.2f}", "#e5e7eb")

    # --- RSI con banda 30-70 ---
    _ob = float(settings["rsi"]["sobrecompra"]) if settings else 70
    _os = float(settings["rsi"]["sobreventa"]) if settings else 30
    fig.add_shape(type="rect", xref="x2 domain", x0=0, x1=1, yref="y3", y0=_os, y1=_ob, fillcolor="rgba(167,139,250,0.08)", line_width=0)
    fig.add_trace(go.Scatter(x=x, y=d["RSI"], name="RSI", line=dict(color="#c084fc", width=1.4), showlegend=False,
                             hovertemplate="RSI %{y:.1f}<extra></extra>"), 2, 1)
    for y, c in ((_ob, "rgba(239,68,68,.6)"), (50, "rgba(148,163,184,.35)"), (_os, "rgba(34,197,94,.6)")):
        fig.add_hline(y=y, line=dict(color=c, width=1, dash="dot"), row=2, col=1)
    # --- MACD con histograma de 4 tonos ---
    h = d["MACD_hist"].fillna(0)
    hp = h.shift().fillna(0)
    hc = np.where(h >= 0, np.where(h >= hp, "#26a69a", "#9adbd3"), np.where(h <= hp, "#ef5350", "#f4b6b5"))
    fig.add_trace(go.Bar(x=x, y=h, marker_color=hc, showlegend=False, hovertemplate="Hist %{y:.2f}<extra></extra>"), 3, 1)
    fig.add_trace(go.Scatter(x=x, y=d["MACD"], line=dict(color="#38bdf8", width=1.2), showlegend=False, name="MACD"), 3, 1)
    fig.add_trace(go.Scatter(x=x, y=d["MACD_signal"], line=dict(color="#fb923c", width=1.2), showlegend=False, name="Señal"), 3, 1)
    # --- ADX / DMI ---
    fig.add_trace(go.Scatter(x=x, y=d["+DI"], line=dict(color="#22c55e", width=1), showlegend=False, name="+DI"), 4, 1)
    fig.add_trace(go.Scatter(x=x, y=d["-DI"], line=dict(color="#ef4444", width=1), showlegend=False, name="−DI"), 4, 1)
    fig.add_trace(go.Scatter(x=x, y=d["ADX"], line=dict(color="#e5e7eb", width=1.6), showlegend=False, name="ADX",
                             fill="tozeroy", fillcolor="rgba(229,231,235,0.05)"), 4, 1)
    fig.add_hline(y=float(settings["adx"]["umbral"]) if settings else 25,
                  line=dict(color="rgba(148,163,184,.5)", width=1, dash="dot"), row=4, col=1)

    pad = (hi - lo) * 0.05
    fig.update_layout(template="plotly_dark", paper_bgcolor="#0f141f", plot_bgcolor="#0f141f",
                      height=640 if mobile else 820,
                      margin=dict(l=2, r=86 if mobile else 92, t=26 if not mobile else 6, b=6), xaxis_rangeslider_visible=False, barmode="overlay",
                      showlegend=not mobile,
                      hovermode="x unified", dragmode=False if mobile else "pan", bargap=0.15,
                      legend=dict(orientation="h", y=1.035, x=0, font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
                      font=dict(family="Inter", color=TXT, size=11))
    for r_ in (1, 2, 3, 4):
        fig.update_xaxes(gridcolor="#1c2433", rangebreaks=rangebreaks(tf, crypto), showspikes=True, spikecolor="#475569",
                         spikethickness=1, range=[x[0], x_end + pd.Timedelta(days=3)], row=r_, col=1)
    if vp_axis:
        fig.update_layout(xaxis5=vp_axis)
    fig.update_yaxes(gridcolor="#1c2433", side="right", tickfont=dict(size=10))
    fig.update_yaxes(range=[lo - pad, hi + pad], row=1, col=1, secondary_y=False)
    fig.update_yaxes(range=[0, float(d["Volume"].max()) * 4], visible=False, row=1, col=1, secondary_y=True)
    fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], row=2, col=1)
    _rl = f"RSI {settings['rsi']['periodo']}" if settings else "RSI 14"
    _ml = (f"MACD {settings['macd']['rapida']}·{settings['macd']['lenta']}·{settings['macd']['senal']}" if settings
           else "MACD 12·26·9")
    _al = f"ADX/DMI {settings['adx']['periodo']}" if settings else "ADX/DMI 14"
    for i, t in ((2, _rl), (3, _ml), (4, _al)):
        fig.add_annotation(xref="paper", x=0.002, xanchor="left", yref=f"y{i + 1 if i > 1 else i} domain", y=0.97,
                           text=t, showarrow=False, font=dict(size=10, color=MUTED))
    return fig


def equity_chart(trades: pd.DataFrame) -> go.Figure:
    eq = trades["R"].cumsum()
    fig = go.Figure(go.Scatter(x=trades["fecha"], y=eq, mode="lines+markers",
                               line=dict(color=GREEN if eq.iloc[-1] >= 0 else RED, width=2), marker=dict(size=5)))
    fig.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG, height=260,
                      margin=dict(l=10, r=10, t=10, b=10), yaxis_title="R acumulado")
    fig.update_xaxes(gridcolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zeroline=True, zerolinecolor=MUTED)
    return fig


DISCLAIMER = ("<div class='disclaimer'>Herramienta de apoyo al análisis. Las probabilidades son frecuencias históricas "
              "y no garantizan resultados futuros. No es asesoría financiera. Datos: Yahoo Finance (gratuito, puede tener "
              "retraso de ~15 min), Finviz y Alpha Vantage.</div>")


# --------------------------------------------------------------------------
# Mapa de calor de oportunidades (treemap por sector) y barra de sesgo
# --------------------------------------------------------------------------
def opportunity_treemap(df: pd.DataFrame, side: str, height: int = 560) -> go.Figure:  # noqa: C901
    """df con columnas Ticker, Sector, prob, ev, chg, size. side: 'LONG' | 'SHORT'."""
    import numpy as np
    total = float(df["size"].sum()) or 1.0
    ids, labels, parents, values, colors, texts, custom = [], [], [], [], [], [], []
    root = "LONG" if side == "LONG" else "SHORT"
    ids.append(root); labels.append(root); parents.append(""); values.append(total)
    w_ev = float(np.average(df["ev"], weights=df["size"])) if total else 0.0
    colors.append(w_ev); texts.append(""); custom.append([np.nan, w_ev, np.nan, len(df)])
    for sec, g in df.groupby("Sector"):
        sid = f"{root}/{sec}"
        sv = float(g["size"].sum())
        sev = float(np.average(g["ev"], weights=g["size"])) if sv else 0.0
        ids.append(sid); labels.append(sec); parents.append(root); values.append(sv)
        colors.append(sev); texts.append(f"{sec}"); custom.append([np.nan, sev, np.nan, len(g)])
        for r in g.itertuples(index=False):
            ids.append(f"{sid}/{r.Ticker}"); labels.append(r.Ticker); parents.append(sid); values.append(float(r.size))
            colors.append(float(r.ev))
            texts.append(f"<b>{r.Ticker}</b><br>{r.prob * 100:.0f}% · {r.ev:+.2f}R<br>{r.chg:+.2f}%")
            custom.append([r.prob, r.ev, r.chg, 1])
    if side == "LONG":
        scale = [[0, "#3b1d24"], [0.33, "#1c2c4a"], [0.6, "#15803d"], [1, "#22c55e"]]
    else:
        scale = [[0, "#173326"], [0.33, "#1c2c4a"], [0.6, "#b91c1c"], [1, "#ef4444"]]
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        text=texts, texttemplate="%{text}", textposition="middle center",
        customdata=custom, marker=dict(colors=colors, colorscale=scale, cmin=-0.6, cmax=1.2, line=dict(width=1, color="#0b0f17"),
                                       pad=dict(t=18, l=2, r=2, b=2)),
        hovertemplate="<b>%{label}</b><br>Prob.: %{customdata[0]:.0%}<br>Valor esperado: %{customdata[1]:+.2f} R"
                      "<br>Var. día: %{customdata[2]:+.2f}%<extra></extra>",
        pathbar=dict(visible=False), tiling=dict(pad=2), insidetextfont=dict(color="#f8fafc", size=12),
        outsidetextfont=dict(color=MUTED, size=11), root=dict(color=BG)))
    fig.update_layout(paper_bgcolor=BG, margin=dict(l=0, r=0, t=0, b=0), height=height, font=dict(family="Inter"))
    return fig


def bias_bar(n_long: int, n_short: int, strong_long: int = 0, strong_short: int = 0) -> str:
    tot = max(1, n_long + n_short)
    pl = n_long / tot * 100
    if pl >= 60:
        lab, c = "ALCISTA", GREEN
    elif pl >= 52:
        lab, c = "LIGERAMENTE ALCISTA", "#4ade80"
    elif pl > 48:
        lab, c = "NEUTRAL / INDECISO", NEUTRAL
    elif pl > 40:
        lab, c = "LIGERAMENTE BAJISTA", "#f87171"
    else:
        lab, c = "BAJISTA", RED
    return (f"<div style='margin:2px 0 6px'>"
            f"<div class='bias-top' style='display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:3px'>"
            f"<span style='color:{GREEN}'><b>▲ LONG {pl:.0f}%</b> · {n_long} acciones · {strong_long} fuertes</span>"
            f"<span>Sesgo del mercado: <b style='color:{c}'>{lab}</b></span>"
            f"<span style='color:{RED}'>{strong_short} fuertes · {n_short} acciones · <b>SHORT {100 - pl:.0f}% ▼</b></span></div>"
            f"<div style='display:flex;height:9px;border-radius:5px;overflow:hidden;background:{BORDER}'>"
            f"<div style='width:{pl:.1f}%;background:linear-gradient(90deg,#15803d,{GREEN})'></div>"
            f"<div style='width:{100 - pl:.1f}%;background:linear-gradient(90deg,{RED},#b91c1c)'></div></div></div>")


# --------------------------------------------------------------------------
# Estilo de tablas: verde = compra/alcista, rojo = venta/bajista, azul = indeciso.
# La intensidad del fondo crece con la probabilidad.
# --------------------------------------------------------------------------
def _rgba(hex_, a):
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a:.2f})"


def prob_css(p, p_opp, side: int) -> str:
    """Fondo de la celda de probabilidad. side 1 = long (verde), -1 = short (rojo)."""
    try:
        p = float(p)
    except (TypeError, ValueError):
        return ""
    if p_opp is not None and abs(p - float(p_opp)) <= 0.05:
        base = NEUTRAL
    else:
        base = GREEN if side > 0 else RED
    a = max(0.06, min(0.9, (p - 0.33) / 0.32 * 0.9))
    return f"background-color: {_rgba(base, a)}; color: #f8fafc; font-weight: 600"


def signed_css(v, good=0.1, bad=0.0, invert=False) -> str:
    """Color de texto: verde si favorable, rojo si desfavorable, azul si cerca de cero."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if invert:
        v = -v
    c = GREEN if v > good else (RED if v < bad else NEUTRAL)
    return f"color: {c}; font-weight: 600"


def rs_css(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if 45 <= v <= 55:
        return f"background-color: {_rgba(NEUTRAL, 0.25)}"
    base = GREEN if v > 55 else RED
    a = min(0.75, abs(v - 50) / 50 * 0.8 + 0.08)
    return f"background-color: {_rgba(base, a)}"


def signal_css(s) -> str:
    return f"color: {SIGNAL_COLORS.get(str(s), MUTED)}; font-weight: 600"


# --------------------------------------------------------------------------
# Celular (navegador web): se detecta por el User-Agent
# --------------------------------------------------------------------------
def is_mobile() -> bool:
    import re as _re
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:
        ua = ""
    if st.session_state.get("force_mobile") is not None:
        return bool(st.session_state["force_mobile"])
    return bool(_re.search(r"Mobi|Android|iPhone|iPod|Windows Phone", ua))


def plot_config(mobile: bool) -> dict:
    return ({"displayModeBar": False, "scrollZoom": False, "responsive": True} if mobile
            else {"displaylogo": False, "scrollZoom": False})


def kpi_row(items: list[tuple]) -> str:
    """Fila de KPIs en una cuadrícula que se acomoda sola (2 por fila en celular)."""
    cells = "".join(
        f"<div class='kpi'><div class='lbl'>{lbl}</div><div class='val' style='color:{c}'>{val}</div>"
        f"<div class='sub'>{sub}</div></div>" for lbl, val, sub, c in items)
    return f"<div class='kpi-grid'>{cells}</div>"
