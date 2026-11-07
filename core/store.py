"""Persistencia local: watchlist, último escaneo y configuración (archivos en ./datos)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).resolve().parent.parent / "datos"
BASE.mkdir(exist_ok=True)
WL = BASE / "watchlist.json"
CFG = BASE / "config.json"
SCAN = BASE / "ultimo_escaneo.parquet"
SCAN_META = BASE / "ultimo_escaneo.json"


def secret(name: str, default: str = "") -> str:
    """Lee st.secrets (Streamlit Cloud) o variables de entorno."""
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


# ---- Backend en la nube para la watchlist: GitHub Gist privado (opcional) ----
GIST_FILE = "quantdesk_watchlist.json"
_gist_id_cache: dict = {}


def _gist_headers():
    return {"Authorization": f"Bearer {secret('GIST_TOKEN')}", "Accept": "application/vnd.github+json"}


def _gist_id() -> str | None:
    if not secret("GIST_TOKEN"):
        return None
    if "id" in _gist_id_cache:
        return _gist_id_cache["id"]
    gid = secret("GIST_ID")
    if not gid:
        r = requests.get("https://api.github.com/gists?per_page=100", headers=_gist_headers(), timeout=15)
        r.raise_for_status()
        gid = next((g["id"] for g in r.json() if GIST_FILE in g.get("files", {})), None)
        if not gid:
            r = requests.post("https://api.github.com/gists", headers=_gist_headers(), timeout=15,
                              json={"description": "XStock watchlist", "public": False,
                                    "files": {GIST_FILE: {"content": "{}"}}})
            r.raise_for_status()
            gid = r.json()["id"]
    _gist_id_cache["id"] = gid
    return gid


def cloud_enabled() -> bool:
    return bool(secret("GIST_TOKEN"))


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(p: Path, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, p)


# ---- Watchlist ------------------------------------------------------------
def _user_email():
    try:
        import streamlit as st
        p = st.session_state.get("profile")
        return p["email"] if p and p.get("email") not in (None, "owner@local") else None
    except Exception:
        return None


def watchlist() -> dict:
    em = _user_email()
    if em:
        from . import db
        return db.watchlist_get(em)
    if cloud_enabled():
        try:
            r = requests.get(f"https://api.github.com/gists/{_gist_id()}", headers=_gist_headers(), timeout=15)
            r.raise_for_status()
            f = r.json()["files"][GIST_FILE]
            content = f["content"] if not f.get("truncated") else requests.get(f["raw_url"], timeout=15).text
            return json.loads(content or "{}")
        except Exception:
            pass
    return _read(WL, {})


def _save_wl(wl: dict, changed: list | None = None, removed: list | None = None):
    em = _user_email()
    if em:
        from . import db
        for t in changed or []:
            db.watchlist_put(em, t, wl[t])
        for t in removed or []:
            db.watchlist_del(em, t)
        return
    if cloud_enabled():
        try:
            r = requests.patch(f"https://api.github.com/gists/{_gist_id()}", headers=_gist_headers(), timeout=15,
                               json={"files": {GIST_FILE: {"content": json.dumps(wl, ensure_ascii=False, indent=2, default=str)}}})
            r.raise_for_status()
        except Exception:
            pass
    _write(WL, wl)


def add_to_watchlist(rows: list[dict]) -> int:
    wl = watchlist()
    n, added = 0, []
    for r in rows:
        t = r["Ticker"]
        if t in wl:
            continue
        wl[t] = {
            "agregado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "precio_agregado": r.get("Precio"),
            "señal_agregado": r.get("Señal"),
            "prob_agregado": r.get("Prob. ganancia"),
            "entrada": r.get("Entrada"), "stop": r.get("Stop"),
            "objetivo_1": r.get("Objetivo 1"), "objetivo_2": r.get("Objetivo 2"),
            "dir": int(r.get("dir") or 1),
            "notas": "",
        }
        n += 1
        added.append(t)
    _save_wl(wl, changed=added)
    return n


def remove_from_watchlist(tickers: list[str]):
    wl = watchlist()
    for t in tickers:
        wl.pop(t, None)
    _save_wl(wl, removed=list(tickers))


def update_watch(ticker: str, **fields):
    wl = watchlist()
    if ticker in wl:
        wl[ticker].update(fields)
        _save_wl(wl, changed=[ticker])


# ---- Escaneo --------------------------------------------------------------
def save_scan(df: pd.DataFrame, meta: dict):
    df.to_parquet(SCAN, index=False)
    _write(SCAN_META, {**meta, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")})


def load_scan():
    if SCAN.exists():
        try:
            return pd.read_parquet(SCAN), _read(SCAN_META, {})
        except Exception:
            pass
    return None, {}


# ---- Configuración --------------------------------------------------------
DEFAULT_CFG = {"anthropic_key": "", "alphavantage_key": "", "modelo": "Claude Sonnet 5.5 (rápido)",
               "proveedor": "Yahoo Finance (gratis)", "capital": 10000.0, "riesgo_pct": 1.0, "tp_atr": 3.0, "sl_atr": 1.5, "horizonte": 35}


def config() -> dict:
    c = {**DEFAULT_CFG, **_read(CFG, {})}
    c["anthropic_key"] = secret("ANTHROPIC_API_KEY") or c["anthropic_key"]
    c["alphavantage_key"] = secret("ALPHAVANTAGE_API_KEY") or c["alphavantage_key"]
    return c


def save_config(c: dict):
    # Las claves que vienen de los secrets nunca se escriben en disco
    c = dict(c)
    if secret("ANTHROPIC_API_KEY"):
        c["anthropic_key"] = ""
    if secret("ALPHAVANTAGE_API_KEY"):
        c["alphavantage_key"] = ""
    _write(CFG, c)
