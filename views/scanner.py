import plotly.express as px
import streamlit as st

from core import crypto, data, store
from core.scanner import scan
from core.ui import (BG, BORDER, DISCLAIMER, GREEN, RED, AMBER, MUTED, NEUTRAL, SIGNAL_COLORS, bias_bar, kpi,
                     is_mobile, kpi_row, opportunity_treemap, plot_config, prob_css, rs_css, signal_css, signed_css)

cfg = st.session_state.cfg
MOBILE = is_mobile()

st.markdown("## Escáner de mercado")
st.markdown("<div class='muted'>Ranking por <b>valor esperado</b> y <b>probabilidad histórica</b> de alcanzar el "
            "objetivo antes que el stop, con 12 indicadores técnicos profesionales.</div>", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _universe(name, custom, av_key):
    return data.universe_with_meta(name, custom, av_key)


@st.cache_data(ttl=900, show_spinner=False)
def _crypto_universe(n, criterio):
    return crypto.universe(n, criterio)


def _prices(tickers: tuple):
    """Caché de precios en la sesión (1 hora) con barra de progreso."""
    import time
    cache = st.session_state.setdefault("_price_cache", {})
    hit = cache.get(tickers)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    bar = st.progress(0.0, "Descargando precios…")
    out = data.batch_history(list(tickers), "2y", progress=lambda p, m: bar.progress(min(p, 1.0), m))
    bar.empty()
    cache.clear()
    cache[tickers] = (time.time(), out)
    return out


with st.container(border=True):
    c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1])
    uni = c1.selectbox("Universo", data.UNIVERSOS, index=0)
    IS_CRYPTO = uni == data.CRIPTO_UNIVERSO
    min_px = c2.number_input("Precio mínimo ($)", 0.0, 1000.0, 0.0 if IS_CRYPTO else 5.0, 1.0, key=f"minpx_{IS_CRYPTO}")
    min_dv = c3.number_input("Volumen $ diario mín. (M)", 0.0, 5000.0, 20.0, 5.0)
    only_up = c4.toggle("Solo sobre SMA200", value=False)
    custom = ""
    n_cr, crit = 25, "Capitalización de mercado"
    if IS_CRYPTO:
        k1, k2 = st.columns([1, 2])
        n_cr = k1.number_input("Cantidad de criptomonedas", 5, 100, 25, 5,
                               help="No se escanea todo el mercado cripto: solo las N primeras según el criterio.")
        crit = k2.selectbox("Criterio de selección (ranking de CoinGecko)", list(crypto.CRITERIOS))
        st.caption("Fuente: ranking de CoinGecko (sin monedas estables ni tokens envueltos). Los precios diarios se descargan "
                   "de Yahoo Finance como SÍMBOLO-USD; las monedas que Yahoo no tenga se omiten. "
                   "Para analizar una en detalle usa el ticker en Análisis, p. ej. BTC-USD.")
    if uni == "Lista personalizada":
        custom = st.text_area("Tickers separados por coma", "AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA, AMD")
    if uni.startswith("Finviz"):
        st.caption("Lista generada por el screener de Finviz (volumen promedio > 500K, precio > $5, empresas de EE.UU.); "
                   "luego XStock calcula indicadores y probabilidades para cada una.")
    if uni.startswith("Todo"):
        st.info("El mercado completo tiene ~6.000 acciones: la primera descarga tarda varios minutos "
                "(luego queda en caché 1 hora). El filtro de liquidez descarta las acciones poco negociadas.")
    if uni.startswith("Movers") and not cfg["alphavantage_key"]:
        st.warning("Este universo usa Alpha Vantage: agrega tu API key gratuita en ⚙️ Configuración.")
    run = st.button("🔍  Escanear mercado", type="primary", use_container_width=True)

if run:
    try:
        tickers, umeta = (_crypto_universe(int(n_cr), crit) if IS_CRYPTO
                          else _universe(uni, custom, cfg["alphavantage_key"]))
    except Exception as e:
        st.error(f"No se pudo obtener el ranking de CoinGecko: {e}. Intenta de nuevo en un minuto.")
        st.stop()
    if IS_CRYPTO:
        uni = f"Cripto · top {len(tickers)} por {crit.lower()}"
    with st.status(f"Escaneando {len(tickers)} activos de «{uni}»…", expanded=True) as status:
        prices = _prices(tuple(tickers))
        st.write(f"Precios recibidos: {len(prices)} acciones")
        bar = st.progress(0.0)
        res = scan(prices, min_px, min_dv * 1e6, cfg["tp_atr"], cfg["sl_atr"], int(cfg["horizonte"]),
                   progress=lambda p, m: bar.progress(min(p, 1.0), m), meta=umeta)
        bar.empty()
        if res.empty:
            status.update(label="Ninguna acción pasó los filtros", state="error")
        else:
            store.save_scan(res, {"universo": uni, "n_universo": len(tickers), "n_validas": len(res)})
            _pf = st.session_state.get("profile")
            if _pf:
                from core import db as _db
                _db.log_event(_pf["email"], "scan", f"{uni} · {len(res)} acciones")
            status.update(label=f"Escaneo completo: {len(res)} acciones evaluadas", state="complete", expanded=False)

res, meta = store.load_scan()
if res is None or res.empty:
    st.info("Elige un universo y pulsa **Escanear mercado** para generar el ranking.")
    st.markdown(DISCLAIMER, unsafe_allow_html=True)
    st.stop()

if "Lado" not in res.columns:
    st.warning("Este escaneo es de una versión anterior. Vuelve a pulsar **Escanear mercado** para ver el lado corto y el mapa de calor.")
    st.stop()

base = res.copy()
if only_up:
    base = base[base["Sobre SMA200"]]

# ---------------- KPIs ----------------
n_l, n_s = int((res["Lado"] == "LONG").sum()), int((res["Lado"] == "SHORT").sum())
pct_up = res["Sobre SMA200"].mean() * 100
best = base.sort_values("Ranking score", ascending=False).iloc[0] if len(base) else None
st.markdown(kpi_row([
    ("Acciones evaluadas", f"{len(res):,}", f"{meta.get('universo', '')} · {meta.get('fecha', '')}", "#e5e7eb"),
    ("Señales de compra", f"{int(res['Señal'].isin(['COMPRA FUERTE', 'COMPRA']).sum())}",
     f"{int((res['Señal'] == 'COMPRA FUERTE').sum())} fuertes", GREEN),
    ("Señales de venta en corto", f"{int(res['Señal corto'].isin(['VENTA FUERTE', 'VENTA']).sum())}",
     f"{int((res['Señal corto'] == 'VENTA FUERTE').sum())} fuertes", RED),
    ("Amplitud de mercado", f"{pct_up:.0f}%", "acciones sobre su SMA200",
     GREEN if pct_up > 55 else RED if pct_up < 40 else NEUTRAL),
    ("Mejor compra", best["Ticker"] if best is not None else "—",
     f"{best['Prob. ganancia'] * 100:.0f}% · EV {best['Valor esperado (R)']:+.2f}R" if best is not None else "", GREEN),
]), unsafe_allow_html=True)

# ---------------- Mapa de oportunidades ----------------
st.write("")
m1, m2, m3 = st.columns([1.6, 1.4, 3])
mode = m1.segmented_control("Visualización", ["Mapa de calor", "Dispersión"], default="Mapa de calor") or "Mapa de calor"
size_by = m2.segmented_control("Tamaño", ["Volumen $", "Market cap"], default="Volumen $",
                               help="Market cap solo está disponible en los universos de Finviz") or "Volumen $"
st.markdown(bias_bar(n_l, n_s, int((res["Señal"] == "COMPRA FUERTE").sum()), int((res["Señal corto"] == "VENTA FUERTE").sum())),
            unsafe_allow_html=True)
if mode == "Mapa de calor":
    sz = res["Market cap"] if (size_by == "Market cap" and res["Market cap"].notna().mean() > 0.8) else res["Vol. $ prom (M)"]
    hm = res.assign(size=sz.fillna(res["Vol. $ prom (M)"]).clip(lower=0.01), chg=res["Var. 1d %"])
    L = hm[hm["Lado"] == "LONG"].assign(prob=lambda x: x["Prob. ganancia"], ev=lambda x: x["Valor esperado (R)"])
    S = hm[hm["Lado"] == "SHORT"].assign(prob=lambda x: x["Prob. corto"], ev=lambda x: x["EV corto (R)"])
    wl_ = max(0.22, n_l / max(1, n_l + n_s))
    cL, cS = (st.container(), st.container()) if MOBILE else st.columns([wl_, max(0.22, 1 - wl_)], gap="small")
    with cL:
        st.markdown(f"<div class='sec2' style='color:{GREEN}'>▲ Candidatas a compra (long) · color = valor esperado</div>",
                    unsafe_allow_html=True)
        if len(L):
            st.plotly_chart(opportunity_treemap(L, "LONG", 420 if MOBILE else 560), use_container_width=True,
                            config=plot_config(MOBILE))
    with cS:
        st.markdown(f"<div class='sec2' style='color:{RED}'>▼ Candidatas a venta en corto (short)</div>", unsafe_allow_html=True)
        if len(S):
            st.plotly_chart(opportunity_treemap(S, "SHORT", 420 if MOBILE else 560), use_container_width=True,
                            config=plot_config(MOBILE))
    st.caption("Cada acción va al lado con mayor valor esperado histórico. Verde o rojo intenso = mayor ventaja; gris = sin ventaja "
               "(valor esperado ≤ 0). Tamaño = " + ("capitalización" if size_by == "Market cap" else "volumen negociado en $") + ".")
else:
    fig = px.scatter(res, x="Score técnico", y="Prob. ganancia", color="Señal", hover_name="Ticker",
                     size=res["Vol. $ prom (M)"].clip(upper=res["Vol. $ prom (M)"].quantile(0.95)),
                     color_discrete_map=SIGNAL_COLORS, template="plotly_dark", height=460)
    fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG, margin=dict(l=10, r=10, t=10, b=10))
    fig.update_xaxes(gridcolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

# ---------------- Ranking ----------------
st.write("")
r1, f1, f2, f3 = st.columns([1.6, 2, 1, 1])
side = r1.segmented_control("Ranking", ["Compras (long)", "Ventas en corto"], default="Compras (long)") or "Compras (long)"
is_long = side.startswith("Compras")
if is_long:
    view = base.sort_values("Ranking score", ascending=False).copy()
    view["_p_opp"] = view["Prob. corto"]
    sig_opts, sig_def = ["COMPRA FUERTE", "COMPRA", "REBOTE (contratendencia)", "NEUTRAL", "EVITAR / VENTA"], ["COMPRA FUERTE", "COMPRA"]
else:
    view = base.sort_values("Ranking corto", ascending=False).copy()
    view["_p_opp"] = view["Prob. ganancia"]
    view["Señal"] = view["Señal corto"]
    view["Prob. ganancia"] = view["Prob. corto"]
    view["Valor esperado (R)"] = view["EV corto (R)"]
    view["Entrada"], view["Stop"] = view["Entrada corto"], view["Stop corto"]
    view["Objetivo 1"], view["Objetivo 2"] = view["Obj. corto 1"], view["Obj. corto 2"]
    view["Casos similares"] = view["Casos similares corto"]
    sig_opts, sig_def = ["VENTA FUERTE", "VENTA", "NEUTRAL"], ["VENTA FUERTE", "VENTA"]
sig_filter = f1.multiselect("Filtrar señal", sig_opts, default=sig_def)
min_prob = f2.slider("Prob. mínima", 0, 90, 0, 5) / 100
top_n = f3.selectbox("Mostrar", [25, 50, 100, 250, 1000], index=1)
if sig_filter:
    view = view[view["Señal"].isin(sig_filter)]
view = view[view["Prob. ganancia"] >= min_prob].head(top_n)
view["#"] = range(1, len(view) + 1)
view["dir"] = 1 if is_long else -1

cols = ["#", "Ticker", "Sector", "Señal", "Prob. ganancia", "Valor esperado (R)", "Score técnico", "Fuerza relativa 3m",
        "Precio", "Var. 1d %", "Ret. 3m %", "RSI", "ADX", "Vol. relativo", "ATR %", "Entrada", "Stop",
        "Objetivo 1", "Objetivo 2", "Casos similares"]
if MOBILE:  # tabla compacta en celular
    cols = ["#", "Ticker", "Señal", "Prob. ganancia", "Valor esperado (R)", "Precio", "Entrada", "Stop", "Objetivo 1"]
st.markdown(f"##### Ranking de {'compras' if is_long else 'ventas en corto'} · selecciona filas para enviarlas a tu watchlist o analizarlas")
sgn = 1 if is_long else -1
vt = view[cols].rename(columns={"Fuerza relativa 3m": "RS 3m"})
opp = view["_p_opp"]
_rs = ["RS 3m"] if "RS 3m" in vt.columns else []
_chg = [c for c in ("Var. 1d %", "Ret. 3m %") if c in vt.columns]
_sc = [c for c in ("Score técnico",) if c in vt.columns]
_obj = [c for c in ("Objetivo 1", "Objetivo 2") if c in vt.columns]
sty = (vt.style
       .format({k_: v_ for k_, v_ in {"Prob. ganancia": "{:.1%}", "Valor esperado (R)": "{:+.2f} R", "Score técnico": "{:+.0f}", "RS 3m": "{:.0f}",
                "Precio": "${:,.2f}", "Var. 1d %": "{:+.2f}%", "Ret. 3m %": "{:+.1f}%", "RSI": "{:.0f}", "ADX": "{:.0f}",
                "Vol. relativo": "{:.1f}x", "ATR %": "{:.1f}%", "Entrada": "${:,.2f}", "Stop": "${:,.2f}",
                "Objetivo 1": "${:,.2f}", "Objetivo 2": "${:,.2f}"}.items() if k_ in vt.columns}, na_rep="—")
       .apply(lambda col: [prob_css(v, opp.loc[i], sgn) for i, v in col.items()], subset=["Prob. ganancia"])
       .map(lambda v: signed_css(v, 0.1, 0.0, invert=False).replace(GREEN, GREEN if sgn > 0 else RED), subset=["Valor esperado (R)"])
       .map(lambda v: signed_css(v, 15, -15), subset=_sc)
       .map(lambda v: signed_css(v, 0.0, 0.0), subset=_chg)
       .map(rs_css, subset=_rs)
       .map(signal_css, subset=["Señal"])
       .map(lambda v: f"color: {NEUTRAL}", subset=["Entrada"])
       .map(lambda v: f"color: {RED}", subset=["Stop"])
       .map(lambda v: f"color: {GREEN}", subset=_obj))
sel = st.dataframe(
    sty, hide_index=True, use_container_width=True, height=460 if MOBILE else 560,
    on_select="rerun", selection_mode="multi-row", key=f"scan_table_{is_long}",
    column_config={"#": st.column_config.NumberColumn(width="small")},
)
st.caption("Probabilidad: verde = ventaja de compra · rojo = ventaja de venta en corto · azul = indeciso (compra y venta "
           "difieren ≤ 5 puntos). Más intenso = mayor probabilidad.")
picked = view.iloc[sel.selection.rows] if sel and sel.selection.rows else view.iloc[0:0]

b1, b2, b3 = st.columns([1.3, 1.3, 3])
if b1.button(f"⭐ Agregar a watchlist ({len(picked)})", disabled=picked.empty, type="primary", use_container_width=True):
    n = store.add_to_watchlist(picked.to_dict("records"))
    st.toast(f"{n} acción(es) agregadas a tu watchlist", icon="⭐")
if b2.button("📊 Analizar selección", disabled=len(picked) != 1, use_container_width=True,
             help="Selecciona una sola fila"):
    st.session_state.ticker = picked.iloc[0]["Ticker"]
    st.switch_page("views/analisis.py")
b3.download_button("⬇️ Exportar ranking (CSV)", view[cols].to_csv(index=False).encode("utf-8"),
                   "ranking_xstock.csv", "text/csv")

with st.expander("¿Cómo se calcula la probabilidad?"):
    st.markdown(f"""
- Para cada día de los últimos 2 años se simula una compra al cierre con **objetivo = +{cfg['tp_atr']}×ATR** y
  **stop = −{cfg['sl_atr']}×ATR**, máximo **{cfg['horizonte']} sesiones** (método de triple barrera).
- Se toman los días cuyo **puntaje técnico era similar al de hoy (±15 puntos)** y se mide qué porcentaje tocó el objetivo antes que el stop.
- Ese porcentaje se **ajusta (bayesiano)** hacia la tasa del universo completo con el mismo puntaje, para no sobreconfiar en pocas muestras.
- **Valor esperado (R)** = p × {cfg['tp_atr'] / cfg['sl_atr']:.1f} − (1 − p). Con esta relación, el punto de equilibrio es
  {1 / (1 + cfg['tp_atr'] / cfg['sl_atr']) * 100:.0f}% de acierto.
""")
st.markdown(DISCLAIMER, unsafe_allow_html=True)
