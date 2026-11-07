"""
Informe de analista con IA (Claude vía API de Anthropic).
Recibe la evidencia cuantitativa (técnico, fundamental, Finviz, probabilidad histórica,
backtest, plan, noticias) y devuelve un informe estructurado: veredicto, explicación
técnica y fundamental, proyecciones de precio por plazo con tiempo estimado,
gestión de toma de ganancias y señales que cambiarían la tesis.
Sin API key se usa una síntesis cuantitativa por reglas con la misma estructura.
"""
from __future__ import annotations

import json
import math
import re

MODELOS = {
    "Claude Sonnet 5.5 (rápido)": "claude-sonnet-5-5",
    "Claude Opus 5.5 (máxima calidad)": "claude-opus-5-5",
    "Claude Haiku 5.5 (económico)": "claude-haiku-5-5",
}

SYSTEM = """Eres un analista financiero y trader profesional de acciones de EE.UU. (20 años de experiencia, CFA y CMT).
Escribes informes breves, concretos y OBJETIVOS para un inversor que opera en Interactive Brokers.
Usa SOLO la evidencia entregada; no inventes cifras. Si añades contexto de negocio desde tu conocimiento general,
ponlo solo en "contexto_general" y advierte que puede estar desactualizado.

Reglas de análisis:
- La probabilidad histórica (triple barrera) es el ancla: solo ajústala ±10 puntos con justificación explícita.
- Explica el PORQUÉ: qué indicadores y qué métricas fundamentales/Finviz pesan más a favor y en contra.
- Proyecciones: da precios bajista / base / alcista para corto (1-4 semanas), mediano (1-3 meses) y largo plazo (6-12 meses).
  Corto plazo: usa ATR, soportes/resistencias y niveles del plan. Mediano: Fibonacci, VRVP (POC/VAH/VAL) y tendencia semanal.
  Largo: precio objetivo de analistas, crecimiento esperado de utilidades y P/E razonable. Indica el tiempo estimado
  para alcanzar el escenario base usando las "estimaciones_de_tiempo" entregadas (son medianas históricas, no promesas).
- Gestión de ganancias: dónde tomar parciales, cuándo mover el stop a la entrada (break-even), trailing stop (p.ej. bajo EMA21 o
  2×ATR), y qué hacer si se acerca el reporte de resultados.
- Señales de cambio: qué cambios en las métricas (RSI, MACD, cierre bajo EMA21/SMA50/POC, volumen, short float, revisiones de EPS,
  rating de analistas) cambiarían el pronóstico y qué acción tomar en cada caso.
- Marco temporal: el análisis usa velas diarias (1D), así que el plan, la probabilidad y los objetivos corresponden a
  inversiones de MEDIANO-LARGO PLAZO (1 a 3 meses, 24-50 sesiones). Dilo explícitamente en el resumen ejecutivo.
- Validación de impulso: si "plan_propuesto.estado_tipo" es "esperar" (la señal de fondo es favorable pero el corto plazo
  corrige: MACD decreciente, pérdida de la EMA9, RSI agotado o precio extendido), NO recomiendes entrar a precio de mercado.
  Usa veredicto "ESPERAR", indica textualmente el "plan_propuesto.estado" (p. ej. "Esperar Pullback a Soporte ($XX.XX)")
  y pon como "entrada" la "entrada_proyectada" (orden límite en el soporte), no el precio actual.
- Si la evidencia es contradictoria o débil, recomienda ESPERAR. Relación riesgo/beneficio mínima aceptable 1.5.
- Español claro y profesional, frases cortas.

Responde SOLO con un JSON válido con esta estructura exacta:
{"veredicto": "COMPRAR" | "ESPERAR" | "EVITAR" | "VENDER EN CORTO",
 "confianza": 0-100,
 "probabilidad_ajustada": 0-1,
 "resumen_ejecutivo": "2-3 frases con la conclusión",
 "lectura_tecnica": "3-5 frases: por qué del pronóstico técnico",
 "lectura_fundamental": "3-5 frases: por qué del pronóstico fundamental y de posicionamiento (Finviz)",
 "proyecciones": [
   {"plazo": "Corto (1-4 semanas)", "bajista": número, "base": número, "alcista": número,
    "probabilidad_base": 0-1, "tiempo_estimado": "texto", "fundamento": "1 frase"},
   {"plazo": "Mediano (1-3 meses)", ...}, {"plazo": "Largo (6-12 meses)", ...}],
 "entrada": número, "stop": número, "objetivo_1": número, "objetivo_2": número,
 "tiempo_objetivo_1": "texto", "tiempo_objetivo_2": "texto",
 "gestion_ganancias": ["acción concreta con precio", "..."],
 "senales_de_cambio": [{"senal": "qué observar", "implica": "qué significa", "accion": "qué hacer"}],
 "factores_a_favor": ["..."], "riesgos": ["..."],
 "invalidacion": "precio o evento que invalida la tesis",
 "catalizadores": ["..."],
 "contexto_general": "1-2 frases o vacío"}"""


def _clean(o):
    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 4)
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item"):  # numpy
        return _clean(o.item())
    return o


def time_estimates(plan: dict, prob: dict, tp_atr: float) -> dict:
    """Sesiones estimadas a cada objetivo a partir de la mediana histórica de casos ganadores."""
    base = prob.get("sesiones_tipicas_a_objetivo")
    atr = plan.get("atr") or 0
    if not base or not math.isfinite(base) or not atr:
        return {}
    ref = tp_atr * atr  # distancia de la barrera usada en la estadística
    d1 = abs(plan["objetivo_1"] - plan["entrada"])
    d2 = abs(plan["objetivo_2"] - plan["entrada"])
    # escala sub-lineal (el precio no avanza en línea recta)
    s1 = max(2, round(base * (d1 / ref) ** 1.3))
    s2 = max(s1 + 2, round(base * (d2 / ref) ** 1.3))
    return {"sesiones_a_objetivo_1": int(s1), "sesiones_a_objetivo_2": int(s2),
            "mediana_historica_sesiones": round(float(base), 1)}


def build_payload(ticker, tech, fund_metrics, fund_score, pio, prob, bt, plan, news, finviz=None,
                  finviz_items=None, vprofile=None, tp_atr=3.0, last=None) -> dict:
    finviz = finviz or {}
    vp = vprofile or {}
    return _clean({
        "ticker": ticker,
        "marco_temporal": plan.get("marco_temporal"),
        "precio_actual": plan.get("precio"),
        "contexto_precio": last or {},
        "tecnico": {"score": tech["score"], "señales": tech["señales"]},
        "fundamental": {"score": fund_score.get("score") if fund_score else None,
                        "bloques": {k: v["score"] for k, v in (fund_score or {}).get("bloques", {}).items()},
                        "metricas_evaluadas": (fund_score or {}).get("items"),
                        "metricas": fund_metrics, "piotroski": pio},
        "finviz": {"senales": finviz.get("signals"), "cambios_rating_analistas": finviz.get("ratings"),
                   "metricas_con_peso": finviz_items},
        "perfil_volumen_180d": {"POC": vp.get("poc"), "VAH": vp.get("vah"), "VAL": vp.get("val")},
        "probabilidad_historica": prob,
        "backtest_senal": {k: v for k, v in (bt or {}).items() if k != "trades"},
        "plan_propuesto": {k: v for k, v in plan.items() if k not in ("fibonacci",)},
        "fibonacci": plan.get("fibonacci"),
        "estimaciones_de_tiempo": time_estimates(plan, prob, tp_atr),
        "noticias_recientes": [n["titulo"] for n in (news or [])],
    })


def analyze(payload: dict, api_key: str, model: str = "claude-sonnet-5-5") -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": "Evidencia (JSON):\n" + json.dumps(payload, ensure_ascii=False)}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("La IA no devolvió JSON: " + text[:300])
    out = json.loads(m.group(0))
    out["_modelo"] = model
    return out


def rule_based(payload: dict) -> dict:
    """Síntesis determinista (sin IA) con la misma estructura del informe."""
    t = payload["tecnico"]["score"] or 0
    f = payload["fundamental"]["score"]
    p = payload["probabilidad_historica"]["probabilidad"]
    ev = payload["probabilidad_historica"]["valor_esperado_R"]
    plan = payload["plan_propuesto"]
    te = payload.get("estimaciones_de_tiempo") or {}
    fib = (payload.get("fibonacci") or {}).get("niveles", {})
    vp = {k.lower(): v for k, v in (payload.get("perfil_volumen_180d") or {}).items()}
    tgt = (payload["fundamental"]["metricas"] or {}).get("Precio objetivo analistas")
    px, atr = plan["precio"], plan["atr"]
    sgn = 1 if plan["direccion"].startswith("COMPRA") else -1
    comb = 0.6 * t + 0.4 * (f if f is not None else 0)
    v = "COMPRAR" if (ev > 0.2 and comb > 20) else ("EVITAR" if (comb < -30 and ev < 0) else "ESPERAR")
    wait = plan.get("estado_tipo") == "esperar"
    if wait and v == "COMPRAR":
        v = "ESPERAR"  # regla de impulso: no entrar a mercado durante la corrección de corto plazo
    entrada_rec = plan.get("entrada_proyectada", plan["entrada"]) if wait else plan["entrada"]
    sig = payload["tecnico"]["señales"]
    favor = [s["Indicador"] + ": " + s["Lectura"] for s in sig if s["Señal"] * sgn > 0.3][:4]
    contra = [s["Indicador"] + ": " + s["Lectura"] for s in sig if s["Señal"] * sgn < -0.3][:4]
    items = payload["fundamental"].get("metricas_evaluadas") or []
    f_good = [i["metrica"] for i in items if i["score"] >= 35][:4]
    f_bad = [i["metrica"] for i in items if i["score"] <= -35][:4]
    s1, s2 = te.get("sesiones_a_objetivo_1"), te.get("sesiones_a_objetivo_2")
    fib_vals = sorted(fib.values()) if fib else []
    up_ = next((x for x in fib_vals if x > px * 1.02), px + 6 * atr)
    dn_ = next((x for x in reversed(fib_vals) if x < px * 0.98), px - 6 * atr)
    mid_base, mid_adv = (up_, dn_) if sgn > 0 else (dn_, up_)
    word_low, word_ema = ("bajista", "bajo") if sgn > 0 else ("alcista", "sobre")
    return {
        "veredicto": v,
        "confianza": int(min(90, abs(comb) * 0.6 + abs(ev) * 30)),
        "probabilidad_ajustada": p,
        "resumen_ejecutivo": (f"{plan.get('estado')}: " if wait else "") +
                             "Análisis en velas 1D (mediano-largo plazo, 1-3 meses). " +
                             f"Puntaje combinado {comb:.0f}/100 (técnico {t:.0f}, fundamental "
                             f"{f if f is not None else 'n/d'}). Configuraciones similares alcanzaron el objetivo antes que "
                             f"el stop {p*100:.0f}% de las veces (valor esperado {ev:+.2f}R).",
        "lectura_tecnica": ("A favor: " + "; ".join(favor) + ". " if favor else "") +
                           ("En contra: " + "; ".join(contra) + "." if contra else ""),
        "lectura_fundamental": ("Atractivo: " + ", ".join(f_good) + ". " if f_good else "") +
                               ("Riesgo: " + ", ".join(f_bad) + "." if f_bad else ""),
        "proyecciones": [
            {"plazo": "Corto (1-4 semanas)", "bajista": plan["stop"], "base": plan["objetivo_1"],
             "alcista": plan["objetivo_2"], "probabilidad_base": p,
             "tiempo_estimado": f"≈{s1} sesiones" if s1 else "n/d", "fundamento": "Niveles del plan (ATR y estructura)"},
            {"plazo": "Mediano (1-3 meses)", "bajista": min(mid_adv, mid_base + sgn * 3 * atr), "base": mid_base,
             "alcista": max(mid_adv, mid_base + sgn * 3 * atr), "probabilidad_base": None,
             "tiempo_estimado": "1-3 meses", "fundamento": "Fibonacci de 6 meses y perfil de volumen"},
            {"plazo": "Largo (6-12 meses)", "bajista": None, "base": tgt, "alcista": None, "probabilidad_base": None,
             "tiempo_estimado": "6-12 meses", "fundamento": "Precio objetivo medio de analistas"},
        ],
        "entrada": entrada_rec, "stop": plan["stop"],
        "objetivo_1": plan["objetivo_1"], "objetivo_2": plan["objetivo_2"],
        "tiempo_objetivo_1": f"≈{s1} sesiones" if s1 else "n/d",
        "tiempo_objetivo_2": f"≈{s2} sesiones" if s2 else "n/d",
        "gestion_ganancias": [
            f"Tomar 50% en el objetivo 1 ({plan['objetivo_1']:.2f}) y mover el stop a la entrada ({plan['entrada']:.2f}).",
            f"Para el resto, trailing stop a 2×ATR ({2 * atr:.2f}) o cierre diario {word_ema} la EMA21.",
            f"Cerrar el resto en el objetivo 2 ({plan['objetivo_2']:.2f}) o si aparece divergencia {word_low} de RSI/MACD.",
        ],
        "senales_de_cambio": [
            {"senal": f"Cierre diario {word_ema} la EMA21", "implica": "Pérdida del momento de corto plazo", "accion": "Ajustar stop o reducir posición"},
            {"senal": f"Cruce {word_low} del MACD con volumen alto", "implica": "Cambio de momento", "accion": "Tomar ganancias parciales"},
            {"senal": f"Cierre {'bajo' if sgn > 0 else 'sobre'} el POC ({vp.get('poc') or 0:.2f})",
             "implica": "El precio sale de su zona de mayor volumen en contra", "accion": "Revisar la tesis"},
        ],
        "factores_a_favor": favor + [f"Fundamental: {x}" for x in f_good],
        "riesgos": contra + [f"Fundamental: {x}" for x in f_bad],
        "invalidacion": f"Cierre por debajo de {plan['stop']:.2f}" if sgn > 0 else f"Cierre por encima de {plan['stop']:.2f}",
        "catalizadores": [],
        "contexto_general": "",
        "_modelo": "reglas (sin IA)",
    }


# =============================================================================
# Gemini (Google AI Studio, plan gratuito) — para usuarios invitados
# =============================================================================
# "gemini-flash-latest" es el alias que Google mantiene apuntando al Flash vigente;
# los demás son respaldo si el alias falla o un modelo se retira.
GEMINI_FALLBACK = ["gemini-flash-latest", "gemini-3-flash-preview", "gemini-2.5-flash",
                   "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]


def analyze_gemini(payload: dict, api_key: str, model: str | None = None) -> dict:
    """Mismo informe que Claude, generado con Gemini Flash (REST, sin dependencias extra)."""
    import requests
    api_key = (api_key or "").strip()
    models = ([model] if model else []) + [m for m in GEMINI_FALLBACK if m != model]
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": "Evidencia (JSON):\n" + json.dumps(payload, ensure_ascii=False)}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 16384, "responseMimeType": "application/json"},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    last_err = None
    for mdl in models:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent",
                              headers=headers, json=body, timeout=90)
        except requests.RequestException as e:
            last_err = f"{mdl}: {e}"
            continue
        if r.status_code == 429:
            raise RuntimeError("Gemini alcanzó su límite gratuito. Espera un minuto y vuelve a intentar.")
        if r.status_code in (400, 401, 403, 404, 500, 503):
            # modelo retirado, no habilitado para este tipo de clave o saturado: probar el siguiente
            last_err = f"{mdl} → {r.status_code}: {r.text[:160]}"
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini respondió {r.status_code}: {r.text[:200]}")
        j = r.json()
        try:
            text = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError):
            raise RuntimeError("Gemini no devolvió contenido (posible bloqueo de seguridad).")
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError("Gemini no devolvió JSON: " + text[:300])
        out = json.loads(m.group(0))
        out["_modelo"] = mdl
        return out
    raise RuntimeError("Gemini no respondió con ningún modelo. Revisa que GEMINI_API_KEY en los Secrets sea correcta y esté activa en Google AI Studio. Detalle: " + str(last_err))
