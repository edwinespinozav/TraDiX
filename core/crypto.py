"""
Universo cripto para el escáner, tomado del ranking de CoinGecko.

No se escanea "todo el mercado cripto" (miles de monedas sin liquidez): el usuario elige
cuántas monedas y con qué criterio se arma la lista. Los precios se descargan luego de
Yahoo Finance con el formato SÍMBOLO-USD (p. ej. BTC-USD).

API pública de CoinGecko (sin clave). Si existe el secret COINGECKO_API_KEY (plan Demo gratuito),
se envía para tener más margen de consultas.
"""
from __future__ import annotations

import requests

from .store import secret

API = "https://api.coingecko.com/api/v3"

CRITERIOS = {
    "Capitalización de mercado": "market_cap",
    "Volumen 24h": "volume",
    "Mayores subidas 24h": "gainers",
    "Mayores caídas 24h": "losers",
}

# Monedas estables y tokens "envueltos": no tienen sentido para análisis técnico de tendencia
EXCLUIR = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE", "USDS", "PYUSD", "BUSD", "USDD", "FRAX", "USD1", "RLUSD",
           "WBTC", "WETH", "STETH", "WSTETH", "WEETH", "CBBTC", "RETH", "BETH", "WBETH", "LBTC", "SOLVBTC", "BSC-USD"}

DEMO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD", "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD",
        "DOT-USD", "LTC-USD", "BCH-USD", "XLM-USD", "ATOM-USD", "NEAR-USD"]


def _get(path: str, params: dict) -> list | dict:
    h = {"accept": "application/json"}
    key = secret("COINGECKO_API_KEY")
    if key:
        h["x-cg-demo-api-key"] = key
    r = requests.get(API + path, params=params, headers=h, timeout=20)
    r.raise_for_status()
    return r.json()


def universe(n: int = 25, criterio: str = "Capitalización de mercado") -> tuple[list[str], dict]:
    """Devuelve (tickers estilo Yahoo, {ticker: meta}) según el criterio de CoinGecko."""
    from .data import _demo
    n = max(5, min(100, int(n)))
    if _demo():
        t = DEMO[:n]
        return t, {x: {"sector": "Cripto"} for x in t}
    kind = CRITERIOS.get(criterio, "market_cap")
    order = "volume_desc" if kind == "volume" else "market_cap_desc"
    # Para subidas/caídas se parte de las 250 más grandes, así se evitan monedas sin liquidez.
    per_page = n * 2 + 20 if kind in ("market_cap", "volume") else 250
    rows = _get("/coins/markets", {"vs_currency": "usd", "order": order, "per_page": min(per_page, 250), "page": 1,
                                   "price_change_percentage": "24h"})
    rows = [r for r in rows if (r.get("symbol") or "").upper() not in EXCLUIR]
    if kind == "gainers":
        rows.sort(key=lambda r: -(r.get("price_change_percentage_24h") or -1e9))
    elif kind == "losers":
        rows.sort(key=lambda r: (r.get("price_change_percentage_24h") or 1e9))
    out, meta = [], {}
    for r in rows:
        t = f"{r['symbol'].upper()}-USD"
        if t in meta:
            continue
        out.append(t)
        meta[t] = {"sector": "Cripto", "nombre": r.get("name"), "cap": r.get("market_cap"),
                   "rank": r.get("market_cap_rank"), "var_24h": r.get("price_change_percentage_24h")}
        if len(out) >= n:
            break
    return out, meta
