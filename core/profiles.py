"""
Perfiles de trader y ajustes técnicos.

Cada perfil define sus temporalidades, la temporalidad por defecto, los ajustes técnicos
pre-seteados (medias, RSI, MACD, ADX, Bollinger, Fibonacci) y qué métricas prioriza el
Resumen Ejecutivo. El motor calcula todo siempre; el perfil solo decide qué se destaca.

Las cuatro medias móviles ocupan "ranuras" fijas en el DataFrame (EMA9, EMA21, SMA50, SMA200)
para no romper el resto del motor; su tipo, periodo, color y etiqueta salen de los ajustes.
"""
from __future__ import annotations

import copy
import json

MA_SLOTS = ["EMA9", "EMA21", "SMA50", "SMA200"]  # rápida, media, lenta, larga
MA_ROLES = ["Rápida", "Media", "Lenta", "Larga"]
MA_TYPES = ["EMA", "SMA", "WMA"]

BASE_SETTINGS = {
    "mas": [
        {"tipo": "EMA", "periodo": 9, "color": "#facc15"},
        {"tipo": "EMA", "periodo": 21, "color": "#ef4444"},
        {"tipo": "SMA", "periodo": 50, "color": "#22c55e"},
        {"tipo": "SMA", "periodo": 200, "color": "#a855f7"},
    ],
    "rsi": {"periodo": 14, "sobrecompra": 70, "sobreventa": 30},
    "macd": {"rapida": 12, "lenta": 26, "senal": 9},
    "adx": {"periodo": 14, "umbral": 25},
    "bollinger": {"periodo": 20, "desv": 2.0},
    "fibonacci": {"velas": 126},
}


def _s(**over) -> dict:
    s = copy.deepcopy(BASE_SETTINGS)
    for k, v in over.items():
        if k == "mas":
            s["mas"] = v
        else:
            s[k].update(v)
    return s


PERFILES: dict[str, dict] = {
    "day": {
        "nombre": "Day Trader", "icono": "⚡", "tfs": ["30m", "1h"], "tf": "30m",
        "descripcion": "Operaciones de horas a 2–3 días. Prioriza VWAP, la media rápida, RSI y volumen relativo.",
        "settings": _s(mas=[{"tipo": "EMA", "periodo": 9, "color": "#facc15"},
                            {"tipo": "EMA", "periodo": 20, "color": "#ef4444"},
                            {"tipo": "EMA", "periodo": 50, "color": "#22c55e"},
                            {"tipo": "SMA", "periodo": 200, "color": "#a855f7"}],
                       rsi={"periodo": 9}, bollinger={"periodo": 20}, fibonacci={"velas": 78}),
        "prioridad": ["estado", "vwap", "ma_rapida", "rsi", "vol_rel", "atr", "entrada", "stop", "tp1"],
    },
    "swing": {
        "nombre": "Swing Trader", "icono": "🌊", "tfs": ["1h", "4h", "1D"], "tf": "1D",
        "descripcion": "Operaciones de días a semanas. Prioriza entrada, TP1/TP2 con tiempo estimado y el perfil de volumen (VRVP).",
        "settings": _s(),
        "prioridad": ["estado", "entrada", "tp1", "tp2", "rr", "prob", "poc", "vah_val"],
    },
    "position": {
        "nombre": "Position Trader", "icono": "🏔️", "tfs": ["1D", "1W"], "tf": "1W",
        "descripcion": "Posiciones de meses. Prioriza la tendencia de largo plazo, el puntaje combinado y la probabilidad.",
        "settings": _s(mas=[{"tipo": "EMA", "periodo": 10, "color": "#facc15"},
                            {"tipo": "EMA", "periodo": 20, "color": "#ef4444"},
                            {"tipo": "SMA", "periodo": 50, "color": "#22c55e"},
                            {"tipo": "SMA", "periodo": 100, "color": "#a855f7"}],
                       fibonacci={"velas": 104}),
        "prioridad": ["estado", "tendencia", "combinado", "prob", "entrada", "tp2", "objetivo_analistas", "piotroski"],
    },
    "fundamental": {
        "nombre": "Fundamental", "icono": "📊", "tfs": ["1D", "1M"], "tf": "1D",
        "descripcion": "Inversión por valor y calidad. Prioriza Piotroski, PEG, P/E, ROE, flujo de caja y el objetivo de analistas.",
        "settings": _s(),
        "prioridad": ["fundamental", "piotroski", "peg", "pe_fwd", "roe", "fcf", "objetivo_analistas", "tendencia"],
    },
    "crypto": {
        "nombre": "Crypto", "icono": "₿", "tfs": ["30m", "4h", "1D"], "tf": "4h",
        "descripcion": "Criptomonedas (p. ej. BTC-USD), mercado 24/7. Prioriza volatilidad, RSI, VWAP y niveles del plan.",
        "settings": _s(rsi={"sobrecompra": 75, "sobreventa": 25}, bollinger={"desv": 2.5}),
        "prioridad": ["estado", "rsi", "atr", "vwap", "entrada", "tp1", "tp2", "stop"],
    },
}
DEFAULT_PERFIL = "swing"


def get(key: str | None) -> dict:
    return PERFILES.get(key or DEFAULT_PERFIL, PERFILES[DEFAULT_PERFIL])


def default_settings(key: str | None) -> dict:
    return copy.deepcopy(get(key)["settings"])


def merge_settings(saved) -> dict:
    """Ajustes guardados (dict o JSON) completados con los valores base."""
    if isinstance(saved, str):
        try:
            saved = json.loads(saved)
        except Exception:
            saved = None
    s = copy.deepcopy(BASE_SETTINGS)
    if isinstance(saved, dict):
        for k, v in saved.items():
            if k == "mas" and isinstance(v, list) and len(v) == 4:
                s["mas"] = [{**BASE_SETTINGS["mas"][i], **(v[i] or {})} for i in range(4)]
            elif k in s and isinstance(v, dict):
                s[k].update(v)
    return s


def ma_label(settings: dict | None, slot: str) -> str:
    """Etiqueta visible de una ranura de media (p. ej. 'EMA9' → 'EMA20' si el usuario la cambió)."""
    if not settings:
        return slot
    m = settings["mas"][MA_SLOTS.index(slot)]
    return f"{m['tipo']}{int(m['periodo'])}"


def ma_color(settings: dict | None, slot: str) -> str:
    base = {"EMA9": "#facc15", "EMA21": "#ef4444", "SMA50": "#22c55e", "SMA200": "#a855f7"}
    if not settings:
        return base[slot]
    return settings["mas"][MA_SLOTS.index(slot)].get("color") or base[slot]
