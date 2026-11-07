"""
Base de datos de usuarios, invitaciones y uso.

Dos backends con la misma interfaz:
  * Supabase (Postgres, vía REST)  → producción en Streamlit Cloud (secrets SUPABASE_URL + SUPABASE_SERVICE_KEY)
  * SQLite local (datos/usuarios.db) → pruebas en tu PC o modo demo

Tablas (ver supabase_schema.sql):
  profiles     un registro por usuario (clave = email). Incluye plan y cuota de IA (base para suscripciones).
  invitations  enlaces de invitación con cuota de IA, usos y vencimiento.
  usage_events registro de uso: login, analysis, scan, ai_report.
"""
from __future__ import annotations

import json
import secrets as _secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from .store import secret

DB_PATH = Path(__file__).resolve().parent.parent / "datos" / "usuarios.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(email: str | None) -> str:
    return (email or "").strip().lower()


# =============================================================================
# Backends
# =============================================================================
class _Supabase:
    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1/"
        key = key.strip()
        self.h = {"apikey": key, "Content-Type": "application/json",
                  "Prefer": "return=representation"}
        # Claves legacy (JWT "eyJ...") van también en Authorization;
        # las nuevas "sb_secret_..." solo en el header apikey.
        if key.startswith("eyJ"):
            self.h["Authorization"] = f"Bearer {key}"

    def select(self, table, where: dict | None = None, order: str | None = None, limit: int | None = None):
        params = {"select": "*"}
        for k, v in (where or {}).items():
            params[k] = f"eq.{v}"
        if order:
            params["order"] = order
        if limit:
            params["limit"] = str(limit)
        r = requests.get(self.base + table, headers=self.h, params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def select_since(self, table, col, since_iso):
        r = requests.get(self.base + table, headers=self.h, timeout=30,
                         params={"select": "*", col: f"gte.{since_iso}", "order": f"{col}.desc", "limit": "20000"})
        r.raise_for_status()
        return r.json()

    def insert(self, table, row: dict):
        r = requests.post(self.base + table, headers=self.h, data=json.dumps(row), timeout=20)
        r.raise_for_status()
        return r.json()

    def upsert(self, table, row: dict, on_conflict: str):
        h = {**self.h, "Prefer": "resolution=merge-duplicates,return=representation"}
        r = requests.post(self.base + table, headers=h, params={"on_conflict": on_conflict}, data=json.dumps(row), timeout=20)
        r.raise_for_status()

    def update(self, table, where: dict, fields: dict):
        params = {k: f"eq.{v}" for k, v in where.items()}
        r = requests.patch(self.base + table, headers=self.h, params=params, data=json.dumps(fields), timeout=20)
        r.raise_for_status()
        return r.json()

    def delete(self, table, where: dict):
        params = {k: f"eq.{v}" for k, v in where.items()}
        r = requests.delete(self.base + table, headers=self.h, params=params, timeout=20)
        r.raise_for_status()


class _SQLite:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS profiles (
        email TEXT PRIMARY KEY, name TEXT, role TEXT DEFAULT 'user', status TEXT DEFAULT 'active',
        plan TEXT DEFAULT 'beta', ai_quota INTEGER DEFAULT 10, ai_used INTEGER DEFAULT 0,
        invite_code TEXT, auth_provider TEXT, created_at TEXT, last_login TEXT, login_count INTEGER DEFAULT 0,
        notes TEXT, password_hash TEXT, trader_profile TEXT, technical_settings TEXT, default_tf TEXT);
    CREATE TABLE IF NOT EXISTS invitations (
        code TEXT PRIMARY KEY, email TEXT, ai_quota INTEGER DEFAULT 10, max_uses INTEGER DEFAULT 1,
        uses INTEGER DEFAULT 0, expires_at TEXT, created_by TEXT, created_at TEXT, note TEXT,
        revoked INTEGER DEFAULT 0, inviter_name TEXT);
    CREATE TABLE IF NOT EXISTS usage_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, kind TEXT, detail TEXT, at TEXT);
    CREATE TABLE IF NOT EXISTS watchlist (email TEXT, ticker TEXT, data TEXT, PRIMARY KEY (email, ticker));
    """

    def __init__(self, path: Path):
        path.parent.mkdir(exist_ok=True)
        self.path = path
        with self._c() as c:
            c.executescript(self.SCHEMA)
            cols = {r[1] for r in c.execute("PRAGMA table_info(profiles)")}
            for col in ("trader_profile", "technical_settings", "default_tf"):  # bases locales antiguas
                if col not in cols:
                    c.execute(f"ALTER TABLE profiles ADD COLUMN {col} TEXT")

    def _c(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def select(self, table, where=None, order=None, limit=None):
        q, args = f"SELECT * FROM {table}", []
        if where:
            q += " WHERE " + " AND ".join(f"{k}=?" for k in where)
            args = list(where.values())
        if order:
            col, _, d = order.partition(".")
            q += f" ORDER BY {col} {'DESC' if d == 'desc' else 'ASC'}"
        if limit:
            q += f" LIMIT {int(limit)}"
        with self._c() as c:
            return [dict(r) for r in c.execute(q, args)]

    def select_since(self, table, col, since_iso):
        with self._c() as c:
            return [dict(r) for r in c.execute(f"SELECT * FROM {table} WHERE {col} >= ? ORDER BY {col} DESC", [since_iso])]

    def insert(self, table, row):
        cols = ", ".join(row)
        with self._c() as c:
            c.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(row))})",
                      [int(v) if isinstance(v, bool) else v for v in row.values()])
        return [row]

    def upsert(self, table, row, on_conflict):
        row = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in row.items()}
        cols = ", ".join(row)
        with self._c() as c:
            c.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values()))

    def update(self, table, where, fields):
        sets = ", ".join(f"{k}=?" for k in fields)
        cond = " AND ".join(f"{k}=?" for k in where)
        with self._c() as c:
            c.execute(f"UPDATE {table} SET {sets} WHERE {cond}",
                      [int(v) if isinstance(v, bool) else v for v in fields.values()] + list(where.values()))
        return self.select(table, where)

    def delete(self, table, where):
        cond = " AND ".join(f"{k}=?" for k in where)
        with self._c() as c:
            c.execute(f"DELETE FROM {table} WHERE {cond}", list(where.values()))


_backend = None


def backend():
    global _backend
    if _backend is None:
        url, key = secret("SUPABASE_URL"), secret("SUPABASE_SERVICE_KEY")
        _backend = _Supabase(url, key) if url and key else _SQLite(DB_PATH)
    return _backend


def backend_name() -> str:
    return "Supabase" if isinstance(backend(), _Supabase) else "SQLite local (se borra al reiniciar en Streamlit Cloud)"


# =============================================================================
# Perfiles
# =============================================================================
def admin_emails() -> set[str]:
    return {_norm(e) for e in secret("ADMIN_EMAILS").replace(";", ",").split(",") if e.strip()}


def get_profile(email: str) -> dict | None:
    rows = backend().select("profiles", {"email": _norm(email)})
    return rows[0] if rows else None


def list_profiles() -> list[dict]:
    return backend().select("profiles", order="created_at.desc")


def create_profile(email: str, name: str, role: str = "user", ai_quota: int = 10, invite_code: str | None = None,
                   provider: str | None = None, password_hash: str | None = None) -> dict:
    row = {"email": _norm(email), "name": name or "", "role": role, "status": "active", "plan": "beta",
           "ai_quota": int(ai_quota), "ai_used": 0, "invite_code": invite_code, "auth_provider": provider,
           "created_at": now_iso(), "last_login": now_iso(), "login_count": 1, "notes": "",
           "password_hash": password_hash}
    backend().insert("profiles", row)
    return row


def update_profile(email: str, **fields) -> None:
    backend().update("profiles", {"email": _norm(email)}, fields)


def save_trader_profile(email: str, trader_profile: str, settings: dict, default_tf: str) -> None:
    """Guarda el perfil de trader elegido en el onboarding y sus ajustes técnicos (JSON)."""
    update_profile(email, trader_profile=trader_profile, technical_settings=json.dumps(settings),
                   default_tf=default_tf)


def delete_profile(email: str, purge_events: bool = True) -> None:
    backend().delete("profiles", {"email": _norm(email)})
    if purge_events:
        backend().delete("usage_events", {"email": _norm(email)})


def touch_login(p: dict) -> None:
    update_profile(p["email"], last_login=now_iso(), login_count=int(p.get("login_count") or 0) + 1)
    log_event(p["email"], "login")


def ai_remaining(p: dict) -> int | None:
    """None = ilimitado (administradores)."""
    if p.get("role") == "admin":
        return None
    return max(0, int(p.get("ai_quota") or 0) - int(p.get("ai_used") or 0))


def consume_ai(p: dict, detail: str = "") -> dict:
    used = int(p.get("ai_used") or 0) + 1
    update_profile(p["email"], ai_used=used)
    log_event(p["email"], "ai_report", detail)
    p = dict(p)
    p["ai_used"] = used
    return p


# =============================================================================
# Invitaciones
# =============================================================================
def create_invite(created_by: str, ai_quota: int, max_uses: int = 1, days: int = 7, email: str = "",
                  note: str = "", inviter_name: str = "") -> dict:
    code = _secrets.token_urlsafe(9).replace("-", "x").replace("_", "y")
    row = {"code": code, "email": _norm(email) or None, "ai_quota": int(ai_quota), "max_uses": int(max_uses),
           "uses": 0, "expires_at": (datetime.now(timezone.utc) + timedelta(days=int(days))).replace(microsecond=0).isoformat(),
           "created_by": _norm(created_by), "created_at": now_iso(), "note": note, "revoked": False,
           "inviter_name": inviter_name}
    backend().insert("invitations", row)
    return row


def get_invite(code: str) -> dict | None:
    rows = backend().select("invitations", {"code": (code or "").strip()})
    return rows[0] if rows else None


def list_invites() -> list[dict]:
    return backend().select("invitations", order="created_at.desc")


def revoke_invite(code: str) -> None:
    backend().update("invitations", {"code": code}, {"revoked": True})


def invite_status(inv: dict) -> str:
    if inv.get("revoked") in (True, 1):
        return "Revocada"
    if int(inv.get("uses") or 0) >= int(inv.get("max_uses") or 1):
        return "Usada"
    try:
        if datetime.fromisoformat(str(inv["expires_at"])) < datetime.now(timezone.utc):
            return "Vencida"
    except Exception:
        pass
    return "Activa"


def check_invite(code: str, email: str) -> tuple[dict | None, str]:
    """Valida un código para este correo. Devuelve (invitación, mensaje de error)."""
    inv = get_invite(code)
    if not inv:
        return None, "El código de invitación no existe."
    st_ = invite_status(inv)
    if st_ != "Activa":
        return None, f"Esta invitación está {st_.lower()}. Pide un nuevo enlace al administrador."
    if inv.get("email") and _norm(inv["email"]) != _norm(email):
        return None, f"Esta invitación es para {inv['email']}. Entra con ese correo."
    return inv, ""


def find_invite_for_email(email: str) -> dict | None:
    for inv in backend().select("invitations", {"email": _norm(email)}):
        if invite_status(inv) == "Activa":
            return inv
    return None


def redeem_invite(inv: dict, email: str, name: str, provider: str | None, password_hash: str | None = None) -> dict:
    backend().update("invitations", {"code": inv["code"]}, {"uses": int(inv.get("uses") or 0) + 1})
    existing = get_profile(email)
    if existing:  # usuario eliminado que vuelve con nueva invitación
        f = {"status": "active", "invite_code": inv["code"], "last_login": now_iso(), "auth_provider": provider}
        if name:
            f["name"] = name
        if password_hash:
            f["password_hash"] = password_hash
        update_profile(email, **f)
        log_event(email, "login", "reactivado por invitación")
        return get_profile(email)
    p = create_profile(email, name, "user", int(inv.get("ai_quota") or 10), inv["code"], provider, password_hash)
    log_event(email, "signup", inv["code"])
    return p


# =============================================================================
# Uso
# =============================================================================
def log_event(email: str, kind: str, detail: str = "") -> None:
    try:
        backend().insert("usage_events", {"email": _norm(email), "kind": kind, "detail": (detail or "")[:200], "at": now_iso()})
    except Exception:
        pass


def events_since(days: int = 90) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    return backend().select_since("usage_events", "at", since)


# =============================================================================
# Watchlist por usuario
# =============================================================================
def watchlist_get(email: str) -> dict:
    out = {}
    for r in backend().select("watchlist", {"email": _norm(email)}):
        d = r.get("data")
        out[r["ticker"]] = json.loads(d) if isinstance(d, str) else (d or {})
    return out


def watchlist_put(email: str, ticker: str, data: dict) -> None:
    backend().upsert("watchlist", {"email": _norm(email), "ticker": ticker, "data": data}, "email,ticker")


def watchlist_del(email: str, ticker: str) -> None:
    backend().delete("watchlist", {"email": _norm(email), "ticker": ticker})
