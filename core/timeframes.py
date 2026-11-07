"""
Temporalidades permitidas en XStock.

Regla obligatoria: la temporalidad mínima es 30 minutos. Nunca se solicitan ni procesan velas
de 1m, 5m o 15m (evita saturar la API de datos y la memoria del servidor).
"""
from __future__ import annotations

import pandas as pd

# yf = intervalo de yfinance · period = historial máximo útil que entrega Yahoo para ese intervalo
# resample = agregación propia (Yahoo no entrega 4h) · bars_day = velas por sesión bursátil (6.5 h)
TIMEFRAMES: dict[str, dict] = {
    "30m": {"yf": "30m", "period": "60d", "resample": None, "bars_day": 13, "nombre": "30 minutos",
            "horizonte": 26, "marco": "Intradía / Day trading · horas a 2–3 días (≈26 velas)"},
    "1h": {"yf": "60m", "period": "730d", "resample": None, "bars_day": 7, "nombre": "1 hora",
           "horizonte": 35, "marco": "Corto plazo · días a 2 semanas (≈35 velas)"},
    "4h": {"yf": "60m", "period": "730d", "resample": "4h", "bars_day": 2, "nombre": "4 horas",
           "horizonte": 30, "marco": "Swing · 1 a 4 semanas (≈30 velas)"},
    "1D": {"yf": "1d", "period": "5y", "resample": None, "bars_day": 1, "nombre": "Diario",
           "horizonte": 35, "marco": "Mediano-Largo plazo · 1 a 3 meses (24–50 sesiones)"},
    "1W": {"yf": "1wk", "period": "10y", "resample": None, "bars_day": 0.2, "nombre": "Semanal",
           "horizonte": 26, "marco": "Largo plazo · 3 a 12 meses (≈26 semanas)"},
    "1M": {"yf": "1mo", "period": "max", "resample": None, "bars_day": 0.05, "nombre": "Mensual",
           "horizonte": 18, "marco": "Muy largo plazo · 1 a 3 años (≈18 meses)"},
}
INTRADAY = {"30m", "1h", "4h"}
PROHIBIDAS = {"1m", "2m", "5m", "15m", "90m"}  # nunca se usan (mínimo 30m)
MIN_TF = "30m"


def validate(tf: str) -> str:
    """Devuelve la temporalidad normalizada o lanza error si no está permitida (mínimo 30m)."""
    if tf in PROHIBIDAS or tf not in TIMEFRAMES:
        raise ValueError(f"Temporalidad no permitida: {tf}. La mínima es {MIN_TF}; "
                         f"permitidas: {', '.join(TIMEFRAMES)}.")
    return tf


def marco(tf: str) -> str:
    """Texto del marco temporal para mostrar en widgets e informes."""
    t = TIMEFRAMES[validate(tf)]
    return f"Velas {tf} ({t['nombre']}) · {t['marco']}"


def marco_corto(tf: str) -> str:
    return f"{tf} · {TIMEFRAMES[validate(tf)]['marco']}"


def unidad(tf: str, n: int | float | None = None) -> str:
    """'sesiones' en diario, 'velas' en el resto."""
    word = "sesiones" if tf == "1D" else ("semanas" if tf == "1W" else ("meses" if tf == "1M" else "velas"))
    return word if n is None else f"{int(n)} {word}"


def is_crypto(ticker: str) -> bool:
    return ticker.upper().endswith(("-USD", "-USDT", "-EUR"))


def future_index(last: pd.Timestamp, n: int, tf: str, crypto: bool = False) -> pd.Timestamp:
    """Fecha aproximada de la vela n en el futuro (para dibujar proyecciones)."""
    n = max(1, int(n))
    if tf == "1W":
        return last + pd.Timedelta(weeks=n)
    if tf == "1M":
        return last + pd.DateOffset(months=n)
    if tf == "1D":
        return last + pd.Timedelta(days=n) if crypto else pd.bdate_range(last, periods=n + 1)[-1]
    hours = {"30m": 0.5, "1h": 1, "4h": 4}[tf]
    if crypto:
        return last + pd.Timedelta(hours=hours * n)
    # acciones: 6.5 h de mercado por sesión → avanzar en sesiones hábiles
    bars_day = TIMEFRAMES[tf]["bars_day"]
    days = int(n // bars_day)
    rest = (n % bars_day) * hours
    base = pd.bdate_range(last.normalize(), periods=days + 1)[-1] if days else last.normalize()
    t = base + (last - last.normalize()) + pd.Timedelta(hours=rest)
    return t


def rangebreaks(tf: str, crypto: bool = False) -> list[dict]:
    """Huecos del eje X en Plotly (fines de semana y horas sin mercado)."""
    if crypto or tf in ("1W", "1M"):
        return []
    rb = [dict(bounds=["sat", "mon"])]
    if tf in INTRADAY:
        rb.append(dict(bounds=[16, 9.5], pattern="hour"))
    return rb
