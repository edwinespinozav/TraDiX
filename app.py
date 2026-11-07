"""
XStock — Plataforma de análisis de acciones de EE.UU.
Ejecutar:  streamlit run app.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from core import store
from core.ai import MODELOS
from core.ui import inject_css

st.set_page_config(page_title="XStock · Trading · Data · Analytics", page_icon="assets/favicon.png", layout="wide",
                   initial_sidebar_state="auto")
inject_css()

# ---- Acceso: invitaciones + Auth0 (Google o correo con código) / modo personal ----
from core import auth, brand  # noqa: E402

profile = auth.gate()
ADMIN = profile.get("role") == "admin"

if "cfg" not in st.session_state:
    st.session_state.cfg = store.config()
cfg = st.session_state.cfg

# ---- Perfil de trader y ajustes técnicos (onboarding) ----
from core import profiles as _profiles  # noqa: E402

if "trader_profile" not in st.session_state:
    _src = cfg if profile.get("email") == "owner@local" else profile
    st.session_state.trader_profile = _src.get("trader_profile")
    st.session_state.technical_settings = _profiles.merge_settings(_src.get("technical_settings"))
    st.session_state.default_tf = _src.get("default_tf") or _profiles.get(_src.get("trader_profile"))["tf"]
NEEDS_ONBOARDING = not st.session_state.trader_profile or st.session_state.get("onboarding")

st.logo("assets/xstock_wordmark.png", size="large", icon_image="assets/xstock_icon.png")

with st.sidebar:
    if os.environ.get("TRADING_DEMO") == "1":
        st.warning("MODO DEMO: datos sintéticos")

_main = [
    st.Page("views/scanner.py", title="Escáner de mercado", icon=":material/radar:", default=True),
    st.Page("views/analisis.py", title="Análisis de acción", icon=":material/candlestick_chart:"),
    st.Page("views/watchlist.py", title="Watchlist", icon=":material/visibility:"),
]
_admin = [
    st.Page("views/admin_invitaciones.py", title="Invitaciones", icon=":material/person_add:"),
    st.Page("views/admin_usuarios.py", title="Usuarios y uso", icon=":material/group:"),
]
_onb = [st.Page("views/onboarding.py", title="Configurar perfil", icon=":material/tune:", default=True)]
if NEEDS_ONBOARDING:
    pages = st.navigation(_onb)
else:
    pages = st.navigation({"XStock": _main, "Administración": _admin} if ADMIN else _main)

with st.sidebar:
    st.divider()
    if not NEEDS_ONBOARDING:
        _P = _profiles.get(st.session_state.trader_profile)
        st.markdown(f"<div class='small'>Perfil: <b>{_P['icono']} {_P['nombre']}</b> · {' / '.join(_P['tfs'])}</div>",
                    unsafe_allow_html=True)
        if st.button("Cambiar perfil y ajustes técnicos", icon=":material/tune:", use_container_width=True):
            st.session_state.onboarding = True
            st.session_state.ob_step = 1
            st.rerun()
    with st.expander("⚙️ Configuración", expanded=False):
        cfg["capital"] = st.number_input("Capital de la cuenta (USD)", 100.0, 1e8, float(cfg["capital"]), 500.0)
        cfg["riesgo_pct"] = st.number_input("Riesgo por operación (%)", 0.1, 5.0, float(cfg["riesgo_pct"]), 0.1)
        c1, c2 = st.columns(2)
        cfg["tp_atr"] = c1.number_input("Objetivo (×ATR)", 1.0, 8.0, float(cfg["tp_atr"]), 0.5)
        cfg["sl_atr"] = c2.number_input("Stop (×ATR)", 0.5, 5.0, float(cfg["sl_atr"]), 0.25)
        cfg["horizonte"] = st.slider("Horizonte en 1D (sesiones)", 24, 50, min(50, max(24, int(cfg["horizonte"]))),
                                     help="Velas diarias (1D): mediano-largo plazo, 1 a 3 meses (24–50 sesiones). "
                                          "Las demás temporalidades usan su horizonte propio (p. ej. 26 velas en 30m).")
        st.caption("El escáner usa velas 1D. Temporalidad mínima de la app: 30m.")
        if not ADMIN:
            st.caption("Estos ajustes valen para esta sesión.")
    if ADMIN:
        with st.expander("🔑 IA y datos (administrador)", expanded=False):
            provs = ["Yahoo Finance (gratis)", "Alpha Vantage (premium)"]
            cfg["proveedor"] = st.selectbox("Proveedor de datos del análisis", provs,
                                            index=provs.index(cfg.get("proveedor", provs[0])) if cfg.get("proveedor") in provs else 0,
                                            help="El escáner masivo siempre usa Yahoo (Alpha Vantage gratis permite ~25 consultas/día). "
                                                 "Con Alpha Vantage premium el análisis usa su historial y fundamentales.")
            cfg["modelo"] = st.selectbox("Modelo de IA", list(MODELOS), index=list(MODELOS).index(cfg["modelo"])
                                         if cfg["modelo"] in MODELOS else 0)
            if store.secret("ANTHROPIC_API_KEY"):
                st.caption("✅ Anthropic API key cargada desde los secrets")
            else:
                cfg["anthropic_key"] = st.text_input("Anthropic API key", cfg["anthropic_key"], type="password",
                                                     help="console.anthropic.com → API Keys. Sin clave se usa síntesis por reglas.")
            if store.secret("ALPHAVANTAGE_API_KEY"):
                st.caption("✅ Alpha Vantage key cargada desde los secrets")
            else:
                cfg["alphavantage_key"] = st.text_input("Alpha Vantage API key (gratis)", cfg["alphavantage_key"], type="password",
                                                        help="alphavantage.co/support/#api-key — respaldo de fundamentales.")
            if st.button("Guardar configuración", use_container_width=True):
                store.save_config(cfg)
                st.success("Guardado en datos/config.json")
    wl = store.watchlist()
    st.caption(f"Watchlist: **{len(wl)}** acciones")
    st.divider()
    st.markdown(f"<div class='small'><b>{profile.get('name') or profile['email']}</b><br>"
                f"<span class='muted'>{profile['email']} · {'Administrador' if ADMIN else 'Invitado'}</span></div>",
                unsafe_allow_html=True)
    if profile.get("email") != "owner@local" and st.button("Cerrar sesión", use_container_width=True):
        auth.logout()

pages.run()
