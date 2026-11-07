import html
import math

import pandas as pd
import streamlit as st

from core import ai, db, store
from core.analysis import full_analysis
from core.fundamental import BLOCK_W
from core.levels import MARCO_CORTO, MARCO_TEMPORAL, MODOS
from core.ui import (AMBER, DISCLAIMER, GREEN, MUTED, NEUTRAL, RED, SIGNAL_COLORS, color_for, equity_chart, is_mobile,
                     pill, plot_config, price_chart)

cfg = st.session_state.cfg
E = html.escape
MOBILE = is_mobile()


@st.cache_data(ttl=900, show_spinner=False)
def _run(ticker, tp, sl, hz, acct, risk, av, prov):
    return full_analysis(ticker, tp, sl, hz, acct, risk, av or None, prov)


def ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def money(x):
    return f"${float(x):,.2f}" if ok(x) else "—"


def fmt(v, kind):
    if not ok(v):
        return "—"
    if kind == "pct":
        return f"{v * 100:.1f}%"
    if kind == "big":
        return f"${v / 1e9:,.1f} B" if v >= 1e9 else f"${v / 1e6:,.0f} M"
    if kind == "money":
        return f"${v:,.2f}"
    return f"{v:,.2f}"


def pfmt(v):
    return f"{float(v) * 100:.0f}%" if ok(v) else "—"


def sfmt(v):
    return f"{float(v):+.0f}" if ok(v) else "—"


def col_score(v, g=15, b=-15):
    return MUTED if not ok(v) else (GREEN if v > g else RED if v < b else NEUTRAL)


# ---------------------------------------------------------------- barra superior
c1, c2, c3 = st.columns([5, 1, 1.2])
ticker = c1.text_input("Ticker", st.session_state.get("ticker", "AAPL"), label_visibility="collapsed",
                       placeholder="Ticker, p. ej. NVDA").strip().upper()
c2.button("Analizar", type="primary", use_container_width=True)
if not ticker:
    st.stop()
st.session_state.ticker = ticker
try:
    with st.spinner(f"Analizando {ticker}…"):
        A = _run(ticker, cfg["tp_atr"], cfg["sl_atr"], int(cfg["horizonte"]), cfg["capital"], cfg["riesgo_pct"],
                 cfg["alphavantage_key"], "alphavantage" if cfg.get("proveedor", "").startswith("Alpha") else "yahoo")
except Exception as e:
    st.error(f"No se pudo analizar {ticker}: {e}")
    st.stop()

d, tech, prob, m, fs = A["df"], A["tech"], A["prob"], A["metrics"], A["fscore"]
_rec = A["plan"]["modo_recomendado"]
_opts = {f"Auto · {MODOS[_rec].replace('Entrada ', '')}": "auto", "A mercado": "market", "Proyectada (Limit)": "limit"}
_mode_lbl = st.segmented_control("Modo de entrada", list(_opts), default=list(_opts)[0], key=f"emode_{ticker}",
                                 help="Auto elige la entrada proyectada (Limit) en el soporte más cercano cuando el "
                                      "impulso de corto plazo va en contra (MACD decreciente, pérdida de la EMA9, RSI "
                                      "agotado o precio extendido); si no, entrada a mercado.") or list(_opts)[0]
plan = A["planes"][_opts[_mode_lbl]]
_prof = st.session_state.get("profile") or {}
_seen = st.session_state.setdefault("_logged_analysis", set())
if _prof and ticker not in _seen:
    db.log_event(_prof["email"], "analysis", ticker)
    _seen.add(ticker)
last, prev = d.iloc[-1], d.iloc[-2]
chg = last["Close"] / prev["Close"] - 1
times = ai.time_estimates(plan, prob, cfg["tp_atr"])

if c3.button("⭐ A watchlist", use_container_width=True):
    store.add_to_watchlist([{"Ticker": ticker, "Precio": float(last["Close"]), "Señal": None,
                             "Prob. ganancia": prob["probabilidad"], "Entrada": plan["entrada"], "Stop": plan["stop"],
                             "Objetivo 1": plan["objetivo_1"], "Objetivo 2": plan["objetivo_2"]}])
    st.toast(f"{ticker} agregado a la watchlist", icon="⭐")

hi52, lo52 = float(d["High"].tail(252).max()), float(d["Low"].tail(252).min())
st.markdown(
    f"<div class='qhead'><span class='qt'>{E(ticker)}</span>"
    f"<span class='qpx'>${last['Close']:,.2f}</span>"
    f"<span style='color:{GREEN if chg >= 0 else RED}' class='qch'>{chg * 100:+.2f}%</span>"
    f"<span class='muted'>{E(m.get('Nombre', ''))} · {E(m.get('Sector', ''))} · {E(m.get('Industria', ''))} · "
    f"cierre {d.index[-1]:%d-%b-%Y} · rango 52s {money(lo52)} – {money(hi52)}</span>"
    f"<span class='muted small' style='display:block;margin-top:2px'>🕒 {E(MARCO_TEMPORAL)}</span></div>",
    unsafe_allow_html=True)

# ---------------------------------------------------------------- gráfico + panel vertical
cc1, cc2, cc3, _ = st.columns([2.2, 1, 1, 3])
rng = cc1.segmented_control("Rango", ["3M", "6M", "1A", "2A"], default="3M" if MOBILE else "6M",
                            label_visibility="collapsed") or "6M"
show_vp = cc2.toggle("VRVP", value=True)
show_bb = cc3.toggle("Bollinger", value=False)
bars = {"3M": 63, "6M": 126, "1A": 252, "2A": 504}[rng]

akey = f"ai_{ticker}_{d.index[-1]:%Y%m%d}_{cfg['tp_atr']}_{cfg['sl_atr']}_{plan['modo_entrada']}"
V = st.session_state.get(akey)

from core.technical import volume_profile
_vp = volume_profile(d.tail(bars)) if show_vp else None
_fig = price_chart(d, plan, _vp, V, bars=bars, times=times, show_bb=show_bb, show_vp=show_vp, mobile=MOBILE)
if MOBILE:
    right = st.container()  # en celular: métricas primero, luego el gráfico
    chart_box = st.container()
else:
    chart_box, right = st.columns([4.1, 1.15], gap="small")

ts, fsc, comb = tech["score"], fs["score"], A["combinado"]
p, ev = prob["probabilidad"], prob["valor_esperado_R"]
be = 1 / (1 + cfg["tp_atr"] / cfg["sl_atr"])
pio = A["piotroski"]
vpa = A["vprofile"] or {}
risk_pct = abs(plan["entrada"] - plan["stop"]) / plan["entrada"]


def row(label, val, color="#e5e7eb", sub=""):
    return (f"<div class='mp-i'><div class='mp-r'><span>{label}</span><b style='color:{color}'>{val}</b></div>"
            + (f"<div class='mp-s'>{sub}</div>" if sub else "") + "</div>")


panel = "<div class='mp'>"
_wait = plan["estado_tipo"] == "esperar"
_sc = AMBER if _wait else GREEN
panel += (f"<div style='border:1px solid {_sc};border-radius:8px;padding:7px 9px;margin-bottom:8px;"
          f"background:rgba(0,0,0,.18)'><div style='color:{_sc};font-weight:700;font-size:13.5px'>"
          f"{'⏳ ' if _wait else '✅ '}{E(plan['estado'])}</div>"
          + (f"<div class='mp-s'>{E(' · '.join(plan['motivos_impulso']))}</div>" if plan["motivos_impulso"] else
             "<div class='mp-s'>Impulso de corto plazo a favor de la señal de fondo.</div>")
          + f"<div class='mp-s'>🕒 {E(MARCO_CORTO)}</div></div>")
panel += "<div class='mp-h'>Puntajes</div>"
panel += row("Score técnico", f"{ts:+.0f}", col_score(ts))
panel += row("Score fundamental", "—" if fsc is None else f"{fsc:+.0f}", col_score(fsc))
panel += row("Score combinado", f"{comb:+.0f}", col_score(comb), "60% técnico · 40% fundamental")
panel += row("Prob. de ganancia", f"{p * 100:.1f}%", GREEN if p > be + 0.05 else (RED if p < be else NEUTRAL),
             f"{prob['casos_similares']} casos · equilibrio {be * 100:.0f}%")
panel += row("Valor esperado", f"{ev:+.2f} R", GREEN if ev > 0.1 else (RED if ev < 0 else NEUTRAL))
panel += row("Piotroski", f"{pio['score']}/{pio['max']}" if pio else "—",
             (GREEN if pio["score"] >= 7 else RED if pio["score"] <= 3 else NEUTRAL) if pio else MUTED)
panel += f"<div class='mp-h'>Plan · {E(plan['direccion'])} · 1D 1–3 meses</div>"
panel += row("Entrada", money(plan["entrada"]), "#60a5fa", E(plan["tipo_entrada"]))
if plan["modo_entrada"] == "limit":
    panel += row("Precio actual", money(plan["entrada_mercado"]), "#e5e7eb",
                 f"esperar retroceso de {abs(plan['entrada'] / plan['entrada_mercado'] - 1) * 100:.1f}%")
else:
    panel += row("Entrada proyectada", money(plan["entrada_proyectada"]), "#93c5fd",
                 f"alternativa Limit en {E(plan['referencia_proyectada'])}")
panel += row("Stop-loss", money(plan["stop"]), RED, f"−{risk_pct * 100:.1f}% · {E(plan['tipo_stop'])}")
panel += row("Objetivo 1", money(plan["objetivo_1"]), GREEN,
             f"R/B {plan['rr_1']:.1f} · {abs(plan['objetivo_1'] / plan['entrada'] - 1) * 100:.1f}%"
             + (f" · ~{times['sesiones_a_objetivo_1']} ses." if times else ""))
panel += row("Objetivo 2", money(plan["objetivo_2"]), GREEN,
             f"R/B {plan['rr_2']:.1f} · {abs(plan['objetivo_2'] / plan['entrada'] - 1) * 100:.1f}%"
             + (f" · ~{times['sesiones_a_objetivo_2']} ses." if times else ""))
panel += row("Tamaño", f"{plan['acciones']} acc.", "#e5e7eb",
             f"capital {money(plan['capital_requerido'])} · riesgo {money(plan['riesgo_monetario'])}")
panel += "<div class='mp-h'>Niveles</div>"
panel += row("POC (180d)", money(vpa.get("poc")), AMBER)
panel += row("Área de valor", f"{money(vpa.get('val'))} – {money(vpa.get('vah'))}", "#e5e7eb")
if plan["soportes"]:
    panel += row("Soporte cercano", money(plan["soportes"][0][0]), "#26a69a")
if plan["resistencias"]:
    panel += row("Resistencia cercana", money(plan["resistencias"][0][0]), "#ef5350")
panel += row("ATR (14)", f"{money(plan['atr'])} · {plan['atr'] / last['Close'] * 100:.1f}%", "#e5e7eb")
panel += "</div>"
if MOBILE:
    panel = panel.replace("<div class='mp'>", "<div class='mp mp-cols'>", 1)
right.markdown(panel, unsafe_allow_html=True)
chart_box.plotly_chart(_fig, use_container_width=True, config=plot_config(MOBILE))

# ---------------------------------------------------------------- informe IA + fundamentales clave
la, lb = (st.container(), st.container()) if MOBILE else st.columns([1.55, 1], gap="small")
with la:
    with st.container(border=True):
        h1, h2 = st.columns([3, 1.3])
        h1.markdown("<div class='sec'>Informe del analista (IA) · elige el motor</div>", unsafe_allow_html=True)
        # Motores de IA: Claude (solo administrador, tu API de Anthropic) y Gemini (todos, plan gratuito)
        _is_admin = (_prof or {}).get("role") == "admin"
        _gem_key = store.secret("GEMINI_API_KEY")
        _cl_key = cfg["anthropic_key"]
        b1, b2, b3 = st.columns(3)
        go_claude = b1.button("Claude", icon=":material/auto_awesome:", type="primary", use_container_width=True,
                              disabled=not (_is_admin and _cl_key),
                              help=("Informe con Claude (Anthropic)" if _is_admin else
                                    "Disponible solo para el administrador") if _cl_key else "Falta ANTHROPIC_API_KEY")
        go_gemini = b2.button("Gemini", icon=":material/bolt:", type="primary" if not _is_admin else "secondary",
                              use_container_width=True, disabled=not _gem_key,
                              help="Informe con Gemini Flash (Google, plan gratuito)" if _gem_key else "Falta GEMINI_API_KEY")
        go_rules = b3.button("Sin IA", icon=":material/calculate:", use_container_width=True,
                             help="Síntesis cuantitativa por reglas (no usa IA)")
        go = go_claude or go_gemini or go_rules
        engine = "claude" if go_claude else ("gemini" if go_gemini else "reglas")
        payload = ai.build_payload(ticker, tech, m, fs, pio, prob, A["bt"], plan, A["news"], A.get("finviz"),
                                   A.get("finviz_items"), A.get("vprofile"), cfg["tp_atr"],
                                   {"max_52s": hi52, "min_52s": lo52,
                                    "ret_3m": float(last["Close"] / d["Close"].iloc[-64] - 1),
                                    "ret_12m": float(last["Close"] / d["Close"].iloc[-253] - 1) if len(d) > 253 else None})
        if go:
            try:
                with st.spinner("Generando el informe del analista…"):
                    if engine == "claude":
                        V = ai.analyze(payload, cfg["anthropic_key"], ai.MODELOS[cfg["modelo"]])
                    elif engine == "gemini":
                        V = ai.analyze_gemini(payload, _gem_key, store.secret("GEMINI_MODEL") or None)
                    else:
                        V = ai.rule_based(payload)
                if engine != "reglas" and _prof:
                    db.log_event(_prof["email"], "ai_report", f"{ticker} · {engine}")
            except Exception as e:
                st.error(f"Error con la IA: {e}. Se muestra la síntesis por reglas.")
                V = ai.rule_based(payload)
            st.session_state[akey] = V
            st.rerun()
        if _is_admin and not (_cl_key and _gem_key):
            st.caption("Agrega `ANTHROPIC_API_KEY` (Claude, solo para ti) y `GEMINI_API_KEY` (Gemini, para todos) en los "
                       "Secrets de Streamlit para activar ambos botones.")
        if V:
            col = SIGNAL_COLORS.get(V.get("veredicto"), NEUTRAL)
            pa = V.get("probabilidad_ajustada")
            st.markdown(
                f"<div class='rep'>{pill(E(str(V.get('veredicto', ''))), col)} "
                f"{pill('Confianza ' + str(V.get('confianza', '—')) + '%', col)} "
                f"{pill('Prob. ajustada ' + (f'{float(pa) * 100:.0f}%' if ok(pa) else '—'), col)} "
                f"<span class='muted small'>&nbsp;{E(V.get('_modelo', ''))}</span>"
                f"<p class='lead'>{E(V.get('resumen_ejecutivo') or V.get('tesis', ''))}</p></div>", unsafe_allow_html=True)
            t_a, t_b = st.columns(2)
            t_a.markdown(f"<div class='rep-b'><b>Lectura técnica</b><br>{E(V.get('lectura_tecnica', ''))}</div>", unsafe_allow_html=True)
            t_b.markdown(f"<div class='rep-b'><b>Lectura fundamental</b><br>{E(V.get('lectura_fundamental', ''))}</div>", unsafe_allow_html=True)
            pj = V.get("proyecciones") or []
            if pj:
                rows = "".join(
                    f"<tr><td>{E(str(x.get('plazo', '')))}</td><td class='n' style='color:{RED}'>{money(x.get('bajista'))}</td>"
                    f"<td class='n'><b>{money(x.get('base'))}</b></td><td class='n' style='color:{GREEN}'>{money(x.get('alcista'))}</td>"
                    f"<td class='n'>{pfmt(x.get('probabilidad_base'))}</td>"
                    f"<td>{E(str(x.get('tiempo_estimado', '')))}</td><td class='small'>{E(str(x.get('fundamento', '')))}</td></tr>"
                    for x in pj)
                st.markdown("<div class='sec2'>Proyecciones de precio</div><table class='qt-tab'><thead><tr><th>Plazo</th>"
                            "<th>Bajista</th><th>Base</th><th>Alcista</th><th>Prob.</th><th>Tiempo</th><th>Fundamento</th>"
                            f"</tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
            g1, g2 = st.columns(2)
            g1.markdown("<div class='sec2'>Toma de ganancias</div>" + "<ul class='tl'>" + "".join(
                f"<li>{E(str(x))}</li>" for x in V.get("gestion_ganancias", [])) + "</ul>"
                + f"<div class='small muted'>TP1 {E(str(V.get('tiempo_objetivo_1', '')))} · TP2 {E(str(V.get('tiempo_objetivo_2', '')))}</div>",
                unsafe_allow_html=True)
            g2.markdown("<div class='sec2'>Si cambian las métricas…</div><ul class='tl'>" + "".join(
                f"<li><b>{E(str(x.get('senal', '')))}</b> → {E(str(x.get('implica', '')))}. <i>{E(str(x.get('accion', '')))}</i></li>"
                if isinstance(x, dict) else f"<li>{E(str(x))}</li>" for x in V.get("senales_de_cambio", [])) + "</ul>",
                unsafe_allow_html=True)
            f1, f2 = st.columns(2)
            f1.markdown("<div class='sec2' style='color:#22c55e'>A favor</div><ul class='tl'>" +
                        "".join(f"<li>{E(str(x))}</li>" for x in V.get("factores_a_favor", [])) + "</ul>", unsafe_allow_html=True)
            f2.markdown("<div class='sec2' style='color:#ef4444'>Riesgos</div><ul class='tl'>" +
                        "".join(f"<li>{E(str(x))}</li>" for x in V.get("riesgos", [])) + "</ul>", unsafe_allow_html=True)
            extra = f"<b>Invalidación:</b> {E(str(V.get('invalidacion', '')))}"
            if V.get("catalizadores"):
                extra += " · <b>Catalizadores:</b> " + " · ".join(E(str(c)) for c in V["catalizadores"])
            if V.get("contexto_general"):
                extra += f"<br><span class='muted'>Contexto general (conocimiento de Claude, puede estar desactualizado): {E(V['contexto_general'])}</span>"
            st.markdown(f"<div class='small'>{extra}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='muted small'>Pulsa el botón para obtener un informe tipo analista: el porqué del pronóstico "
                        "técnico y fundamental, proyecciones de precio a corto, mediano y largo plazo con tiempo estimado, "
                        "plan de toma de ganancias y qué cambios en las métricas alterarían la tesis.</div>", unsafe_allow_html=True)

with lb:
    with st.container(border=True):
        st.markdown(f"<div class='sec'>Fundamentales clave <span style='color:{col_score(fsc)}'>"
                    f"{'' if fsc is None else f'{fsc:+.0f}'}</span></div>", unsafe_allow_html=True)
        items = sorted(fs.get("items", []), key=lambda i: -i["score"])
        good = [i for i in items if i["score"] >= 35]
        bad = [i for i in items if i["score"] <= -35][::-1]
        neu = [i for i in items if -35 < i["score"] < 35]

        def frow(i, c):
            return (f"<div class='fr'><span class='dot' style='background:{c}'></span><span class='fm'>{E(i['metrica'])}</span>"
                    f"<span class='fv'>{E(i['valor'])}</span><div class='fl'>{E(i['lectura'])}"
                    f"<span class='fb'> · {E(i['bloque'])}</span></div></div>")
        out = ""
        if good:
            out += f"<div class='sec2' style='color:{GREEN}'>La hacen atractiva</div>" + "".join(frow(i, GREEN) for i in good)
        if bad:
            out += f"<div class='sec2' style='color:{RED}'>La hacen riesgosa</div>" + "".join(frow(i, RED) for i in bad)
        st.markdown(out or "<div class='muted small'>Sin datos fundamentales.</div>", unsafe_allow_html=True)
        if neu:
            with st.expander(f"Neutrales ({len(neu)})"):
                st.markdown("".join(frow(i, NEUTRAL) for i in neu), unsafe_allow_html=True)
        bl = fs.get("bloques", {})
        st.markdown("<div class='sec2'>Puntaje por bloque (peso)</div>" + "".join(
            f"<div class='mp-r'><span>{E(b)} <span class='muted'>×{BLOCK_W[b]}</span></span>"
            f"<b style='color:{col_score(v['score'])}'>{sfmt(v['score'])}</b></div>"
            for b, v in bl.items()), unsafe_allow_html=True)

# ---------------------------------------------------------------- pestañas de detalle
t1, t6, t3, t4, t5 = st.tabs(["📈 Técnico", "🔎 Finviz", "🎲 Probabilidad y backtest", "📐 Niveles", "📰 Noticias"])

with t1:
    sig = pd.DataFrame(tech["señales"])
    sig["Aporte"] = sig["Señal"] * sig["Peso"]
    sig["Sesgo"] = sig["Señal"].map(lambda v: "▲ Alcista" if v > 0.15 else ("▼ Bajista" if v < -0.15 else "● Neutral"))
    sig = sig[["Indicador", "Sesgo", "Señal", "Peso", "Aporte", "Lectura"]]
    colr = lambda v: f"color: {GREEN if v > 0.15 else RED if v < -0.15 else NEUTRAL}; font-weight: 600"
    sty = (sig.style.format({"Señal": "{:+.2f}", "Aporte": "{:+.2f}", "Peso": "{:.1f}"})
           .map(colr, subset=["Señal", "Aporte"])
           .map(lambda s: colr(1 if s.startswith("▲") else -1 if s.startswith("▼") else 0), subset=["Sesgo"]))
    st.dataframe(sty, hide_index=True, use_container_width=True)
    st.caption("Cada indicador emite una señal de −1 a +1 ponderada por su fiabilidad; el score técnico es el promedio ponderado × 100.")

with t6:
    fv = A.get("finviz") or {}
    fitems = A.get("finviz_items") or []
    if not fv.get("snapshot"):
        st.info("Finviz no respondió para este ticker (o estás en modo demo).")
    else:
        bsc = (fs.get("bloques", {}).get("Posicionamiento (Finviz)") or {}).get("score")
        wtot = sum(BLOCK_W[b] for b, v in fs.get("bloques", {}).items() if v["score"] is not None)
        share = BLOCK_W["Posicionamiento (Finviz)"] / wtot * 100 if wtot else 0
        st.markdown(f"**Peso de Finviz en el pronóstico:** bloque *Posicionamiento* con puntaje "
                    f"<b style='color:{col_score(bsc)}'>{'—' if bsc is None else f'{bsc:+.0f}'}</b>, que representa "
                    f"**{share:.0f}%** del score fundamental (y {share * 0.4:.0f}% del score combinado).",
                    unsafe_allow_html=True)
        if fitems:
            fdf = pd.DataFrame([{"Métrica": i["metrica"], "Valor": i["valor"], "Impacto": i["impacto"],
                                 "Efecto": "▲ Suma" if i["impacto"] > 0.15 else ("▼ Resta" if i["impacto"] < -0.15 else "● Neutro"),
                                 "Lectura": i["lectura"]} for i in fitems])
            colr2 = lambda v: f"color: {GREEN if v > 0.15 else RED if v < -0.15 else NEUTRAL}; font-weight: 600"
            st.dataframe(fdf.style.format({"Impacto": "{:+.2f}"}).map(colr2, subset=["Impacto"])
                         .map(lambda s: colr2(1 if s.startswith("▲") else -1 if s.startswith("▼") else 0), subset=["Efecto"]),
                         hide_index=True, use_container_width=True)
        c1, c2 = st.columns([1, 1.3])
        with c1:
            if fv.get("signals"):
                st.markdown("**Señales de Finviz:** " + " · ".join(fv["signals"]))
            st.caption("Además, Finviz completa los fundamentales que falten en Yahoo (P/E, márgenes, deuda, objetivo de analistas…).")
        with c2:
            st.markdown("**Cambios de rating de analistas**")
            if fv.get("ratings"):
                st.dataframe(pd.DataFrame(fv["ratings"]), hide_index=True, use_container_width=True)
            else:
                st.caption("Sin cambios recientes.")
        with st.expander("Ficha completa de Finviz"):
            st.dataframe(pd.DataFrame([{"Campo": k_, "Valor": v} for k_, v in fv["snapshot"].items()]),
                         hide_index=True, use_container_width=True)
        st.markdown(f"[Ver {ticker} en Finviz ↗](https://finviz.com/quote.ashx?t={ticker.replace('-', '.')})")

with t3:
    bt = A["bt"]
    st.markdown(
        f"<div class='mp' style='display:grid;grid-template-columns:repeat(5,1fr);gap:6px 18px'>"
        + row("Tasa base de la acción", f"{(prob['tasa_base_accion'] or 0) * 100:.1f}%")
        + row("Casos similares (±15)", f"{prob['casos_similares']}")
        + row("R medio en similares", f"{prob['R_promedio_similares']:+.2f} R" if ok(prob["R_promedio_similares"]) else "—")
        + row("Sesiones medias a salida", f"{prob['dias_promedio_salida']:.0f}" if ok(prob["dias_promedio_salida"]) else "—")
        + row("Sesiones típicas a objetivo", f"{prob['sesiones_tipicas_a_objetivo']:.0f}" if ok(prob.get("sesiones_tipicas_a_objetivo")) else "—")
        + "</div>", unsafe_allow_html=True)
    st.caption(prob["parametros"])
    if bt.get("n"):
        st.markdown(f"**Backtest de la señal** (entrada cuando el puntaje cruza ±40, 5 años, sin solapamiento): "
                    f"{bt['n']} operaciones · acierto {bt['win_rate'] * 100:.0f}% · R medio {bt['avg_R']:+.2f} · "
                    f"profit factor {bt['profit_factor']:.2f} · total {bt['total_R']:+.1f} R · drawdown máx {bt['max_dd_R']:.1f} R")
        st.plotly_chart(equity_chart(bt["trades"]), use_container_width=True)
    else:
        st.info("La señal no generó operaciones en el periodo analizado.")

with t4:
    c1, c2, c3 = st.columns(3)
    c1.markdown("**Soportes**")
    c1.dataframe(pd.DataFrame([{"Nivel": f"${lv:,.2f}", "Toques": n, "Distancia": f"{(lv / last['Close'] - 1) * 100:+.1f}%"}
                               for lv, n in plan["soportes"]]), hide_index=True, use_container_width=True)
    c2.markdown("**Resistencias**")
    c2.dataframe(pd.DataFrame([{"Nivel": f"${lv:,.2f}", "Toques": n, "Distancia": f"{(lv / last['Close'] - 1) * 100:+.1f}%"}
                               for lv, n in plan["resistencias"]]), hide_index=True, use_container_width=True)
    fib = plan["fibonacci"]
    c3.markdown(f"**Fibonacci** (tramo {fib['tramo']} 6 meses)")
    c3.dataframe(pd.DataFrame([{"Retroceso": k_, "Precio": f"${v:,.2f}"} for k_, v in fib["niveles"].items()]),
                 hide_index=True, use_container_width=True)

with t5:
    if A["news"]:
        for n in A["news"]:
            s_ = f" · sentimiento: {n['sentimiento']}" if n.get("sentimiento") else ""
            st.markdown(f"- [{n['titulo']}]({n['link']}) <span class='muted'>· {n['fuente'] or ''}{s_}</span>",
                        unsafe_allow_html=True)
    else:
        st.info("Sin noticias recientes disponibles.")

st.markdown(DISCLAIMER, unsafe_allow_html=True)
