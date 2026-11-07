"""Onboarding: paso 1 elegir perfil de trader, paso 2 ajustar los indicadores técnicos."""
import copy

import streamlit as st

from core import db, profiles, store
from core.timeframes import TIMEFRAMES

prof = st.session_state.get("profile") or {}
saved_key = st.session_state.get("trader_profile")
step = st.session_state.setdefault("ob_step", 1)

st.markdown("<div class='sec'>Configura tu espacio de trabajo</div>", unsafe_allow_html=True)
st.progress(0.5 if step == 1 else 1.0, text=f"Paso {step} de 2 · " + ("Perfil de trader" if step == 1 else "Ajustes técnicos"))

# ---------------------------------------------------------------- PASO 1
if step == 1:
    st.markdown("### ¿Cómo operas?")
    st.caption("El perfil define tus temporalidades y qué se destaca en el resumen. El motor siempre calcula todo, "
               "y puedes cambiar de perfil cuando quieras desde la barra lateral.")
    keys = list(profiles.PERFILES)
    cols = st.columns(len(keys))
    for c, k in zip(cols, keys):
        P = profiles.PERFILES[k]
        with c.container(border=True):
            st.markdown(f"<div style='font-size:28px'>{P['icono']}</div><b>{P['nombre']}</b>", unsafe_allow_html=True)
            st.caption(" · ".join(P["tfs"]))
            st.markdown(f"<div class='small muted'>{P['descripcion']}</div>", unsafe_allow_html=True)
            if st.button("Elegir", key=f"ob_{k}", type="primary" if k == saved_key else "secondary",
                         use_container_width=True):
                st.session_state.ob_profile = k
                st.session_state.ob_settings = (profiles.merge_settings(st.session_state.get("technical_settings"))
                                                if k == saved_key else profiles.default_settings(k))
                st.session_state.ob_step = 2
                st.rerun()
    st.caption("Temporalidad mínima de la plataforma: 30 minutos.")
    st.stop()

# ---------------------------------------------------------------- PASO 2
k = st.session_state.get("ob_profile") or profiles.DEFAULT_PERFIL
P = profiles.get(k)
S = st.session_state.get("ob_settings") or profiles.default_settings(k)
st.markdown(f"### {P['icono']} {P['nombre']} · ajustes técnicos")
st.caption("Valores pre-seteados para tu perfil. Ajústalos si quieres y pulsa **Guardar y entrar a la plataforma**.")

tf = st.selectbox("Temporalidad por defecto", P["tfs"], index=P["tfs"].index(P["tf"]),
                  format_func=lambda t: f"{t} · {TIMEFRAMES[t]['marco']}")

with st.container(border=True):
    st.markdown("**Medias móviles**")
    new_mas = []
    for i, (role, m) in enumerate(zip(profiles.MA_ROLES, S["mas"])):
        c1, c2, c3, c4 = st.columns([1.1, 1, 2.4, 0.8])
        c1.markdown(f"<div style='padding-top:30px'>{role}</div>", unsafe_allow_html=True)
        tipo = c2.selectbox("Tipo", profiles.MA_TYPES, index=profiles.MA_TYPES.index(m["tipo"]), key=f"ma_t{i}")
        per = c3.slider("Periodo", 2, 300, int(m["periodo"]), key=f"ma_p{i}")
        col = c4.color_picker("Color", m["color"], key=f"ma_c{i}")
        new_mas.append({"tipo": tipo, "periodo": per, "color": col})

a, b = st.columns(2)
with a.container(border=True):
    st.markdown("**RSI**")
    rsi_p = st.slider("Periodo RSI", 2, 50, int(S["rsi"]["periodo"]))
    rsi_lo, rsi_hi = st.slider("Sobreventa / sobrecompra", 5, 95, (int(S["rsi"]["sobreventa"]), int(S["rsi"]["sobrecompra"])))
with b.container(border=True):
    st.markdown("**MACD**")
    m1, m2, m3 = st.columns(3)
    mf = m1.number_input("Rápida", 2, 50, int(S["macd"]["rapida"]))
    ms = m2.number_input("Lenta", 5, 100, int(S["macd"]["lenta"]))
    mg = m3.number_input("Señal", 2, 50, int(S["macd"]["senal"]))
c, d = st.columns(2)
with c.container(border=True):
    st.markdown("**ADX / DMI**")
    adx_p = st.slider("Periodo ADX", 5, 50, int(S["adx"]["periodo"]))
    adx_u = st.slider("Umbral de tendencia", 10, 40, int(S["adx"]["umbral"]))
with d.container(border=True):
    st.markdown("**Bollinger y Fibonacci**")
    bb_p = st.slider("Periodo Bollinger", 5, 60, int(S["bollinger"]["periodo"]))
    bb_k = st.slider("Desviaciones", 1.0, 4.0, float(S["bollinger"]["desv"]), 0.1)
    fib = st.slider("Velas para Fibonacci", 20, 300, int(S["fibonacci"]["velas"]))

new = {"mas": new_mas, "rsi": {"periodo": rsi_p, "sobrecompra": rsi_hi, "sobreventa": rsi_lo},
       "macd": {"rapida": int(mf), "lenta": int(ms), "senal": int(mg)},
       "adx": {"periodo": adx_p, "umbral": adx_u},
       "bollinger": {"periodo": bb_p, "desv": float(bb_k)}, "fibonacci": {"velas": fib}}
if new["macd"]["rapida"] >= new["macd"]["lenta"]:
    st.warning("En el MACD, la media rápida debe ser menor que la lenta.")

c1, c2, c3 = st.columns([1, 1, 2])
if c1.button("← Cambiar perfil", use_container_width=True):
    st.session_state.ob_step = 1
    st.rerun()
if c2.button("Restaurar valores del perfil", use_container_width=True):
    st.session_state.ob_settings = profiles.default_settings(k)
    for key in list(st.session_state):
        if key.startswith("ma_"):
            del st.session_state[key]
    st.rerun()
if c3.button("Guardar y entrar a la plataforma", type="primary", use_container_width=True,
             disabled=new["macd"]["rapida"] >= new["macd"]["lenta"]):
    email = prof.get("email")
    if email and email != "owner@local":
        db.save_trader_profile(email, k, new, tf)
    else:  # modo personal sin base de datos: se guarda en la configuración local
        cfg = st.session_state.cfg
        cfg.update({"trader_profile": k, "technical_settings": copy.deepcopy(new), "default_tf": tf})
        store.save_config(cfg)
    st.session_state.trader_profile = k
    st.session_state.technical_settings = new
    st.session_state.default_tf = tf
    st.session_state.ob_step = 1
    st.session_state.pop("onboarding", None)
    st.rerun()
