"""Resumen Ejecutivo adaptativo: elige qué métricas destacar según el perfil de trader."""
from __future__ import annotations

import math

from .profiles import get as get_profile, ma_label
from .timeframes import unidad

GREEN, RED, AMBER, NEUTRAL, BLUE = "#22c55e", "#ef4444", "#f59e0b", "#94a3b8", "#60a5fa"


def _ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _m(x):
    return f"${float(x):,.2f}" if _ok(x) else "—"


def _pct(x):
    return f"{float(x) * 100:.1f}%" if _ok(x) else "—"


def cards(A: dict, plan: dict, times: dict, profile_key: str) -> list[dict]:
    """Tarjetas (titulo, valor, color, detalle) priorizadas para el perfil."""
    d = A["df"]
    r = d.iloc[-1]
    px = float(r["Close"])
    tf = A.get("tf", "1D")
    st_ = d.attrs.get("settings")
    m, fs, prob, pio, vp = A["metrics"], A["fscore"], A["prob"], A.get("piotroski"), A.get("vprofile") or {}
    risk = abs(plan["entrada"] - plan["stop"]) or float("nan")
    s1, s2 = (times or {}).get("sesiones_a_objetivo_1"), (times or {}).get("sesiones_a_objetivo_2")
    wait = plan.get("estado_tipo") == "esperar"
    ob = float(st_["rsi"]["sobrecompra"]) if st_ else 70
    os_ = float(st_["rsi"]["sobreventa"]) if st_ else 30

    def pct_from(lv):
        return f"{(lv / px - 1) * 100:+.1f}% vs precio" if _ok(lv) and px else ""

    C = {
        "estado": dict(t="Estado de la entrada", v=plan["estado"], c=AMBER if wait else GREEN,
                       s=" · ".join(plan.get("motivos_impulso") or []) or "Impulso a favor"),
        "entrada": dict(t="Entrada", v=_m(plan["entrada"]), c=BLUE, s=plan["tipo_entrada"]),
        "stop": dict(t="Stop-loss", v=_m(plan["stop"]), c=RED, s=f"−{risk / plan['entrada'] * 100:.1f}%"),
        "tp1": dict(t="TP1", v=_m(plan["objetivo_1"]), c=GREEN,
                    s=f"R/B {plan['rr_1']:.1f}" + (f" · ~{unidad(tf, s1)}" if s1 else "")),
        "tp2": dict(t="TP2", v=_m(plan["objetivo_2"]), c=GREEN,
                    s=f"R/B {plan['rr_2']:.1f}" + (f" · ~{unidad(tf, s2)}" if s2 else "")),
        "rr": dict(t="Riesgo / beneficio", v=f"1 : {plan['rr_2']:.1f}" if plan.get("rr_2") else "—", c=NEUTRAL,
                   s=f"riesgo {_m(risk)} por acción"),
        "prob": dict(t="Prob. de ganancia", v=_pct(prob["probabilidad"]),
                     c=GREEN if prob["valor_esperado_R"] > 0.1 else (RED if prob["valor_esperado_R"] < 0 else NEUTRAL),
                     s=f"VE {prob['valor_esperado_R']:+.2f} R · {prob['casos_similares']} casos"),
        "poc": dict(t="POC (VRVP)", v=_m(vp.get("poc")), c=AMBER, s=pct_from(vp.get("poc"))),
        "vah_val": dict(t="Área de valor", v=f"{_m(vp.get('val'))} – {_m(vp.get('vah'))}", c=NEUTRAL, s="VAL – VAH"),
        "vwap": dict(t="VWAP (20 velas)", v=_m(r["VWAP20"]), c=GREEN if px > r["VWAP20"] else RED,
                     s="precio sobre VWAP" if px > r["VWAP20"] else "precio bajo VWAP"),
        "ma_rapida": dict(t=ma_label(st_, "EMA9"), v=_m(r["EMA9"]), c=GREEN if px > r["EMA9"] else RED,
                          s="precio sobre la media rápida" if px > r["EMA9"] else "precio bajo la media rápida"),
        "rsi": dict(t="RSI", v=f"{r['RSI']:.1f}", c=RED if r["RSI"] >= ob else (GREEN if r["RSI"] <= os_ else NEUTRAL),
                    s="sobrecompra" if r["RSI"] >= ob else ("sobreventa" if r["RSI"] <= os_ else "zona neutral")),
        "vol_rel": dict(t="Volumen relativo", v=f"{r['Volume'] / r['VOL_SMA20']:.2f}×" if r["VOL_SMA20"] else "—",
                        c=GREEN if r["VOL_SMA20"] and r["Volume"] > 1.5 * r["VOL_SMA20"] else NEUTRAL, s="vs promedio 20 velas"),
        "atr": dict(t="Volatilidad (ATR)", v=_m(r["ATR"]), c=NEUTRAL, s=f"{r['ATR'] / px * 100:.1f}% del precio"),
        "tendencia": dict(t="Tendencia de fondo",
                          v="Alcista" if r["SMA50"] > r["SMA200"] else "Bajista",
                          c=GREEN if r["SMA50"] > r["SMA200"] else RED,
                          s=f"{ma_label(st_, 'SMA50')} {'sobre' if r['SMA50'] > r['SMA200'] else 'bajo'} {ma_label(st_, 'SMA200')}"),
        "combinado": dict(t="Score combinado", v=f"{A['combinado']:+.0f}",
                          c=GREEN if A["combinado"] > 15 else (RED if A["combinado"] < -15 else NEUTRAL),
                          s="60% técnico · 40% fundamental"),
        "fundamental": dict(t="Score fundamental", v="—" if fs["score"] is None else f"{fs['score']:+.0f}",
                            c=NEUTRAL if fs["score"] is None else (GREEN if fs["score"] > 15 else RED if fs["score"] < -15 else NEUTRAL),
                            s="valoración, calidad, crecimiento y deuda"),
        "piotroski": dict(t="Piotroski F-Score", v=f"{pio['score']}/{pio['max']}" if pio else "—",
                          c=(GREEN if pio["score"] >= 7 else RED if pio["score"] <= 3 else NEUTRAL) if pio else NEUTRAL,
                          s="fortaleza financiera"),
        "peg": dict(t="PEG", v=f"{m['PEG']:.2f}" if _ok(m.get("PEG")) else "—",
                    c=(GREEN if m["PEG"] < 1 else RED if m["PEG"] > 2 else NEUTRAL) if _ok(m.get("PEG")) else NEUTRAL,
                    s="P/E ajustado por crecimiento"),
        "pe_fwd": dict(t="P/E forward", v=f"{m['P/E forward']:.1f}" if _ok(m.get("P/E forward")) else "—", c=NEUTRAL,
                       s=f"P/E actual {m['P/E (TTM)']:.1f}" if _ok(m.get("P/E (TTM)")) else ""),
        "roe": dict(t="ROE", v=_pct(m.get("ROE")),
                    c=(GREEN if m["ROE"] > 0.15 else RED if m["ROE"] < 0.05 else NEUTRAL) if _ok(m.get("ROE")) else NEUTRAL,
                    s="rentabilidad sobre patrimonio"),
        "fcf": dict(t="FCF yield", v=_pct(m.get("FCF yield")),
                    c=(GREEN if m["FCF yield"] > 0.05 else RED if m["FCF yield"] < 0 else NEUTRAL) if _ok(m.get("FCF yield")) else NEUTRAL,
                    s="flujo de caja libre / capitalización"),
        "objetivo_analistas": dict(t="Objetivo analistas", v=_m(m.get("Precio objetivo analistas")), c=NEUTRAL,
                                   s=pct_from(m.get("Precio objetivo analistas"))),
    }
    return [C[k] for k in get_profile(profile_key)["prioridad"] if k in C]


def html(cards_: list[dict], title: str) -> str:
    cells = "".join(
        f"<div style='background:#111a2c;border:1px solid #1f2b44;border-radius:10px;padding:9px 11px'>"
        f"<div style='font-size:11px;color:#8fa3bf;text-transform:uppercase;letter-spacing:.06em'>{c['t']}</div>"
        f"<div style='font-size:17px;font-weight:700;color:{c['c']};margin-top:2px'>{c['v']}</div>"
        f"<div style='font-size:11px;color:#94a3b8;margin-top:1px'>{c['s']}</div></div>"
        for c in cards_)
    return (f"<div class='sec' style='margin-top:6px'>{title}</div>"
            f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:6px 0 10px'>"
            f"{cells}</div>")
