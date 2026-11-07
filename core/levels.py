"""
Plan de operación: entrada, stop-loss, objetivos y tamaño de posición.
Basado en ATR (volatilidad), soportes/resistencias y relación riesgo/beneficio.

Marco temporal: velas diarias (1D) → operaciones de mediano-largo plazo (1 a 3 meses, 24–50 sesiones).

Dos modos de entrada:
  * "market": entrada a mercado, en el último cierre.
  * "limit":  entrada proyectada (orden límite) en el soporte técnico ideal más cercano
              (soporte por fractales, EMA21 o SMA50), donde se espera el retroceso.
  * "auto":   elige "limit" cuando el impulso de corto plazo va en contra de la señal de fondo
              (MACD decreciente, pérdida de la EMA9, RSI agotado o precio extendido) y "market" si no.
"""
from __future__ import annotations

import pandas as pd

from .profiles import ma_label
from .technical import fibonacci, pivot_levels
from .timeframes import marco, marco_corto

MARCO_TEMPORAL = marco("1D")
MARCO_CORTO = marco_corto("1D")
MODOS = {"market": "Entrada a mercado", "limit": "Entrada proyectada (Limit)"}


def momentum_check(df: pd.DataFrame, direction: str = "long") -> dict:
    """Regla de validación de impulso de corto plazo frente a la señal de fondo.

    Para un largo, el impulso va en contra si el histograma del MACD decrece dos sesiones seguidas o el cierre
    perdió la EMA9; hay agotamiento si el RSI está en sobrecompra (o cae desde ella) o el precio
    está a más de 1 ATR sobre la EMA21. Para un corto se evalúa el espejo.
    """
    r, p, pp = df.iloc[-1], df.iloc[-2], df.iloc[-3]
    st_ = df.attrs.get("settings")
    fast, mid = ma_label(st_, "EMA9"), ma_label(st_, "EMA21")
    ob = float(st_["rsi"]["sobrecompra"]) if st_ else 70.0
    os_ = float(st_["rsi"]["sobreventa"]) if st_ else 30.0
    long = direction == "long"
    px, a = float(r["Close"]), float(r["ATR"])
    hist, hist_p, hist_pp = float(r["MACD_hist"]), float(p["MACD_hist"]), float(pp["MACD_hist"])
    rsi, rsi_p = float(r["RSI"]), float(p["RSI"])
    motivos = []
    if long:
        if hist < hist_p < hist_pp:  # dos sesiones seguidas: filtra el ruido de un solo día
            motivos.append("MACD con histograma decreciente (2 sesiones)")
        if px < float(r["EMA9"]):
            motivos.append(f"Cierre por debajo de la {fast}")
        if rsi >= ob or (rsi_p >= ob - 5 and rsi < rsi_p):
            motivos.append(f"RSI agotado ({rsi:.0f})")
        if px - float(r["EMA21"]) > 1.0 * a:
            motivos.append(f"Precio extendido > 1 ATR sobre la {mid}")
    else:
        if hist > hist_p > hist_pp:
            motivos.append("MACD con histograma creciente (2 sesiones)")
        if px > float(r["EMA9"]):
            motivos.append(f"Cierre por encima de la {fast}")
        if rsi <= os_ or (rsi_p <= os_ + 5 and rsi > rsi_p):
            motivos.append(f"RSI agotado ({rsi:.0f})")
        if float(r["EMA21"]) - px > 1.0 * a:
            motivos.append(f"Precio extendido > 1 ATR bajo la {mid}")
    return {"en_contra": bool(motivos), "motivos": motivos}


def projected_entry(df: pd.DataFrame, direction: str = "long") -> tuple[float, str]:
    """Nivel de entrada proyectado (orden límite): el soporte ideal más cercano por debajo del precio
    (o la resistencia más cercana por encima, para cortos), dentro de 3 ATR."""
    r = df.iloc[-1]
    px, a = float(r["Close"]), float(r["ATR"])
    supports, resist = pivot_levels(df)
    long = direction == "long"
    cands: list[tuple[float, str]] = []
    st_ = df.attrs.get("settings")
    for col in ("EMA21", "SMA50"):
        name = ma_label(st_, col)
        v = float(r[col])
        if v == v:  # no NaN
            cands.append((v, name))
    for lv, n in (supports if long else resist)[:4]:
        cands.append((float(lv), f"soporte ({n} toques)" if long else f"resistencia ({n} toques)"))
    gap = 0.25 * a
    if long:
        ok = [(v, nm) for v, nm in cands if px - 3 * a <= v <= px - gap]
        if ok:
            return max(ok, key=lambda t: t[0])
        return px - a, "1 ATR bajo el cierre"
    ok = [(v, nm) for v, nm in cands if px + gap <= v <= px + 3 * a]
    if ok:
        return min(ok, key=lambda t: t[0])
    return px + a, "1 ATR sobre el cierre"


def _plan_for_entry(df: pd.DataFrame, entry: float, direction: str, sl_atr: float, tp_atr: float,
                    account: float, risk_pct: float) -> dict:
    """Stop, objetivos y tamaño a partir de un precio de entrada dado."""
    r = df.iloc[-1]
    a = float(r["ATR"])
    supports, resist = pivot_levels(df)
    long = direction == "long"
    sgn = 1 if long else -1

    # --- Stop ------------------------------------------------------------
    base_stop = entry - sgn * sl_atr * a
    struct = None
    if long and supports:
        below = [lv for lv, _ in supports if lv < entry - 0.1 * a]
        if below:
            struct = below[0] - 0.25 * a
    if not long and resist:
        above = [lv for lv, _ in resist if lv > entry + 0.1 * a]
        if above:
            struct = above[0] + 0.25 * a
    stop, stop_type = base_stop, f"{sl_atr} × ATR"
    if struct is not None and 1.0 * a <= abs(entry - struct) <= 3.0 * a:
        stop, stop_type = struct, "Bajo soporte estructural − 0.25 ATR" if long else "Sobre resistencia + 0.25 ATR"
    risk = abs(entry - stop)

    # --- Objetivos -------------------------------------------------------
    t1 = entry + sgn * 2 * risk
    t2 = entry + sgn * max(3 * risk, tp_atr * a)
    obstacles = [lv for lv, _ in (resist if long else supports)]
    obstacles = [lv for lv in obstacles if (lv - entry) * sgn > 1.2 * risk]
    t1_type = "2R"
    if obstacles and abs(obstacles[0] - entry) < abs(t1 - entry) * 1.25:
        t1 = obstacles[0] - sgn * 0.1 * a
        t1_type = "Resistencia más cercana" if long else "Soporte más cercano"
    if (t2 - t1) * sgn <= 0:
        t2 = t1 + sgn * risk

    # --- Tamaño ----------------------------------------------------------
    risk_money = account * risk_pct / 100
    shares = int(risk_money // risk) if risk > 0 else 0
    shares = min(shares, int(account // entry)) if entry > 0 else 0
    return {"stop": stop, "tipo_stop": stop_type, "objetivo_1": t1, "tipo_obj1": t1_type, "objetivo_2": t2,
            "riesgo_por_accion": risk,
            "rr_1": abs(t1 - entry) / risk if risk else None,
            "rr_2": abs(t2 - entry) / risk if risk else None,
            "acciones": shares, "capital_requerido": shares * entry, "riesgo_monetario": shares * risk}


def trade_plan(df: pd.DataFrame, direction: str = "long", sl_atr: float = 1.5, tp_atr: float = 3.0,
               account: float = 10_000, risk_pct: float = 1.0, entry_mode: str = "auto", tf: str = "1D") -> dict:
    """Plan de operación. entry_mode: "auto" (recomendado), "market" o "limit". tf: temporalidad de las velas."""
    r = df.iloc[-1]
    px, a = float(r["Close"]), float(r["ATR"])
    supports, resist = pivot_levels(df)
    long = direction == "long"

    mom = momentum_check(df, direction)
    lim_px, lim_ref = projected_entry(df, direction)
    recomendado = "limit" if mom["en_contra"] else "market"
    modo = recomendado if entry_mode == "auto" else entry_mode

    if modo == "limit":
        entry = lim_px
        entry_type = f"Proyectada (Limit) en {lim_ref}"
    else:
        entry = px
        entry_type = "A mercado / cierre actual"

    # Estado principal del panel (regla de validación de impulso)
    nivel = "soporte" if long else "resistencia"
    if mom["en_contra"]:
        estado = (f"Esperar Pullback a Soporte (${lim_px:,.2f})" if long
                  else f"Esperar Rebote a Resistencia (${lim_px:,.2f})")
        estado_tipo = "esperar"
    else:
        estado = "Entrada a mercado válida" if long else "Venta en corto a mercado válida"
        estado_tipo = "mercado"

    plan = {
        "direccion": "COMPRA (largo)" if long else "VENTA (corto)",
        "precio": px,
        "atr": a,
        "entrada": entry,
        "tipo_entrada": entry_type,
        "modo_entrada": modo,
        "modo_recomendado": recomendado,
        "entrada_mercado": px,
        "entrada_proyectada": lim_px,
        "referencia_proyectada": lim_ref,
        "estado": estado,
        "estado_tipo": estado_tipo,
        "motivos_impulso": mom["motivos"],
        "nivel_espera": nivel,
        "marco_temporal": marco(tf),
        "marco_corto": marco_corto(tf),
        "tf": tf,
        "soportes": supports[:4],
        "resistencias": resist[:4],
        "fibonacci": fibonacci(df, int((df.attrs.get("settings") or {}).get("fibonacci", {}).get("velas", 126))),
    }
    plan.update(_plan_for_entry(df, entry, direction, sl_atr, tp_atr, account, risk_pct))
    return plan
