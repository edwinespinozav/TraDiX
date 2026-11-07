"""
Capa de datos (gratuita):
  * Yahoo Finance vía yfinance  → precios diarios, fundamentales y estados financieros (sin clave)
  * Alpha Vantage (clave gratuita) → respaldo de fundamentales (OVERVIEW) y cotización
  * Universos: S&P 500 / Nasdaq 100 (Wikipedia), todo NYSE+NASDAQ (nasdaqtrader.com), Dow 30
  * Modo DEMO con datos sintéticos para probar sin internet
"""
from __future__ import annotations

import io
import os
import time
import zlib
from typing import Callable

import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

DOW30 = ["AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON", "IBM",
         "JNJ", "JPM", "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT"]

FALLBACK_LARGE_CAPS = sorted(set(DOW30 + [
    "GOOGL", "META", "TSLA", "AVGO", "BRK-B", "LLY", "XOM", "MA", "COST", "ORCL", "NFLX", "AMD", "ADBE", "PEP",
    "TMO", "ABT", "LIN", "ACN", "QCOM", "TXN", "INTU", "AMAT", "PM", "NOW", "ISRG", "BKNG", "UBER", "GE", "RTX",
    "SPGI", "PLD", "LOW", "BLK", "SYK", "ELV", "MDT", "ADI", "LRCX", "MU", "PANW", "KLAC", "SNPS", "CDNS", "ANET",
    "C", "BAC", "WFC", "MS", "SCHW", "DE", "UPS", "LMT", "T", "TMUS", "CMCSA", "PFE", "ABBV", "BMY", "GILD",
    "MO", "SBUX", "ADP", "MDLZ", "CI", "CB", "PGR", "MMC", "ZTS", "REGN", "VRTX", "SO", "DUK", "NEE", "COP",
    "SLB", "EOG", "FCX", "NEM", "PLTR", "CRWD", "SHOP", "MELI", "ABNB", "PYPL", "INTC", "F", "GM"]))

from .finviz import UNIVERSOS_FINVIZ

CRIPTO_UNIVERSO = "Cripto (ranking CoinGecko)"
UNIVERSOS = (["S&P 500", "Nasdaq 100", "Dow 30", "S&P 500 + Nasdaq 100"] + list(UNIVERSOS_FINVIZ)
             + ["Todo NYSE + NASDAQ (filtrado por liquidez)", "Movers del día (Alpha Vantage)", "Lista personalizada",
                CRIPTO_UNIVERSO])


def _demo() -> bool:
    return os.environ.get("TRADING_DEMO", "0") == "1"


# --------------------------------------------------------------------------
# Universos
# --------------------------------------------------------------------------
SECTOR_ES = {"Information Technology": "Tecnología", "Technology": "Tecnología", "Health Care": "Salud",
             "Healthcare": "Salud", "Financials": "Finanzas", "Financial": "Finanzas", "Consumer Discretionary": "Consumo discrecional",
             "Consumer Cyclical": "Consumo discrecional", "Consumer Staples": "Consumo básico", "Consumer Defensive": "Consumo básico",
             "Communication Services": "Comunicaciones", "Industrials": "Industria", "Energy": "Energía",
             "Utilities": "Servicios públicos", "Real Estate": "Inmobiliario", "Materials": "Materiales",
             "Basic Materials": "Materiales"}


def _wiki_table(url: str, col_candidates: list[str]):
    """(tickers, meta) de una tabla de Wikipedia con columna de sector GICS."""
    html = requests.get(url, headers=UA, timeout=20).text
    for t in pd.read_html(io.StringIO(html)):
        for c in col_candidates:
            if c in t.columns:
                tick = [str(s).strip().replace(".", "-") for s in t[c]]
                sec = t["GICS Sector"].tolist() if "GICS Sector" in t.columns else [None] * len(tick)
                meta = {k: {"sector": SECTOR_ES.get(v, v)} for k, v in zip(tick, sec) if k and k != "nan"}
                return list(meta), meta
    raise ValueError("tabla no encontrada")


def sp500() -> list[str]:
    return _wiki_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", ["Symbol"])[0]


def nasdaq100() -> list[str]:
    return _wiki_table("https://en.wikipedia.org/wiki/Nasdaq-100", ["Ticker", "Symbol"])[0]


def all_us_listed() -> list[str]:
    """Todas las acciones comunes listadas en NASDAQ, NYSE y NYSE American (sin ETFs ni test issues)."""
    out = []
    t1 = pd.read_csv(io.StringIO(requests.get(
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", headers=UA, timeout=20).text), sep="|")
    t1 = t1[(t1["Test Issue"] == "N") & (t1["ETF"] == "N")]
    out += t1["Symbol"].dropna().tolist()
    t2 = pd.read_csv(io.StringIO(requests.get(
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", headers=UA, timeout=20).text), sep="|")
    t2 = t2[(t2["Test Issue"] == "N") & (t2["ETF"] == "N") & (t2["Exchange"].isin(["N", "A"]))]
    out += t2["ACT Symbol"].dropna().tolist()
    clean = []
    for s in out:
        s = str(s)
        if any(ch in s for ch in "$^") or s.startswith("File"):
            continue
        # excluir warrants, units, rights, preferentes
        if len(s) >= 5 and s[-1] in "WURQ" and s not in ("GOOGL",):
            continue
        clean.append(s.replace(".", "-"))
    return sorted(set(clean))


def universe_with_meta(name: str, custom: str = "", av_key: str = ""):
    """Devuelve (tickers, {ticker: {sector, cap}}). El sector alimenta el mapa de calor."""
    if _demo():
        secs = list(SECTOR_ES.values())
        return FALLBACK_LARGE_CAPS, {t: {"sector": secs[zlib.crc32(t.encode()) % 11]} for t in FALLBACK_LARGE_CAPS}
    try:
        if name == "S&P 500":
            return _wiki_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", ["Symbol"])
        if name == "Nasdaq 100":
            return _wiki_table("https://en.wikipedia.org/wiki/Nasdaq-100", ["Ticker", "Symbol"])
        if name == "S&P 500 + Nasdaq 100":
            t1, m1 = _wiki_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", ["Symbol"])
            t2, m2 = _wiki_table("https://en.wikipedia.org/wiki/Nasdaq-100", ["Ticker", "Symbol"])
            m = {**m2, **m1}
            return list(m), m
        if name.startswith("Finviz"):
            from .finviz import universe_meta
            for k, v in (mm := universe_meta(name)[1]).items():
                v["sector"] = SECTOR_ES.get(v.get("sector"), v.get("sector"))
            if mm:
                return list(mm), mm
    except Exception:
        pass
    return get_universe(name, custom, av_key), {}


def get_universe(name: str, custom: str = "", av_key: str = "") -> list[str]:
    if _demo():
        return FALLBACK_LARGE_CAPS
    try:
        if name == "S&P 500":
            return sp500()
        if name == "Nasdaq 100":
            return nasdaq100()
        if name == "Dow 30":
            return DOW30
        if name == "S&P 500 + Nasdaq 100":
            return sorted(set(sp500()) | set(nasdaq100()))
        if name.startswith("Todo"):
            return all_us_listed()
        if name.startswith("Finviz"):
            from .finviz import universe as fv_universe
            tick = fv_universe(name)
            if tick:
                return tick
        if name.startswith("Movers"):
            return av_movers(av_key)
        if name == "Lista personalizada":
            return sorted({t.strip().upper() for t in custom.replace(";", ",").replace("\n", ",").split(",") if t.strip()})
    except Exception:
        pass
    return FALLBACK_LARGE_CAPS


# --------------------------------------------------------------------------
# Precios
# --------------------------------------------------------------------------
def _synthetic(ticker: str, n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(zlib.crc32(ticker.encode()))
    drift = rng.normal(0.0004, 0.0008)
    vol = rng.uniform(0.012, 0.035)
    # régimen cambiante para que haya tendencias
    regime = np.repeat(rng.normal(0, 0.0015, n // 60 + 1), 60)[:n]
    ret = rng.normal(drift + regime, vol, n)
    close = 50 * np.exp(np.cumsum(ret)) * rng.uniform(0.5, 8)
    hi = close * (1 + np.abs(rng.normal(0, vol / 2, n)))
    lo = close * (1 - np.abs(rng.normal(0, vol / 2, n)))
    op = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, vol / 4, n))
    hi = np.maximum.reduce([hi, op, close])
    lo = np.minimum.reduce([lo, op, close])
    volu = rng.lognormal(15, 0.5, n) * (1 + 3 * np.abs(ret) / vol / 10)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.DataFrame({"Open": op, "High": hi, "Low": lo, "Close": close, "Volume": volu}, index=idx)


def history(ticker: str, period: str = "3y", provider: str = "yahoo", av_key: str = "") -> pd.DataFrame:
    if _demo():
        return _synthetic(ticker)
    if provider == "alphavantage" and av_key:
        try:
            df = av_daily(ticker, av_key, full=True)
            if len(df) >= 260:
                return df.tail(1300)
        except Exception:
            pass  # cae a Yahoo
    import yfinance as yf
    df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    if df.empty:
        raise ValueError(f"Sin datos para {ticker}")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def _synthetic_tf(ticker: str, tf: str, n: int = 600) -> pd.DataFrame:
    """Datos sintéticos (modo demo) con el índice de tiempo de la temporalidad pedida."""
    from .timeframes import is_crypto
    df = _synthetic(ticker + tf, n)
    end = pd.Timestamp.today().normalize() + pd.Timedelta(hours=15, minutes=30)
    if tf in ("30m", "1h", "4h"):
        step = {"30m": "30min", "1h": "60min", "4h": "240min"}[tf]
        if is_crypto(ticker):
            idx = pd.date_range(end=end, periods=n, freq=step)
        else:
            per_day = {"30m": 13, "1h": 7, "4h": 2}[tf]
            days = pd.bdate_range(end=end.normalize(), periods=n // per_day + 2)
            stamps = [d + pd.Timedelta(hours=9, minutes=30) + i * pd.Timedelta(step) for d in days for i in range(per_day)]
            idx = pd.DatetimeIndex(stamps[-n:])
    elif tf == "1W":
        idx = pd.date_range(end=end.normalize(), periods=n, freq="W-FRI")
    elif tf == "1M":
        idx = pd.date_range(end=end.normalize(), periods=min(n, 240), freq="ME")
        df = df.tail(len(idx))
    else:
        idx = (pd.date_range(end=end.normalize(), periods=n, freq="D") if is_crypto(ticker)
               else pd.bdate_range(end=end.normalize(), periods=n))
    df.index = idx
    return df


def history_tf(ticker: str, tf: str = "1D", provider: str = "yahoo", av_key: str = "") -> pd.DataFrame:
    """Historial OHLCV en la temporalidad pedida. Mínimo 30m: 1m/5m/15m no se solicitan nunca."""
    from .timeframes import TIMEFRAMES, validate
    tf = validate(tf)
    if tf == "1D":
        return history(ticker, "5y", provider, av_key)
    if _demo():
        return _synthetic_tf(ticker, tf)
    spec = TIMEFRAMES[tf]
    import yfinance as yf
    df = yf.Ticker(ticker).history(period=spec["period"], interval=spec["yf"], auto_adjust=True)
    if df.empty:
        raise ValueError(f"Sin datos {tf} para {ticker}")
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    df.index = idx
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if spec["resample"]:
        df = df.resample(spec["resample"], origin="start_day", offset="9h30min").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    return df


def batch_history(tickers: list[str], period: str = "2y", chunk: int = 100,
                  progress: Callable[[float, str], None] | None = None) -> dict[str, pd.DataFrame]:
    """Descarga masiva en bloques. Devuelve {ticker: DataFrame OHLCV}."""
    out: dict[str, pd.DataFrame] = {}
    if _demo():
        for i, t in enumerate(tickers):
            out[t] = _synthetic(t)
            if progress:
                progress((i + 1) / len(tickers), t)
        return out
    import yfinance as yf
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        if progress:
            progress(i / len(tickers), f"Descargando {i + 1}–{i + len(part)} de {len(tickers)}")
        for attempt in range(3):
            try:
                raw = yf.download(part, period=period, auto_adjust=True, group_by="ticker",
                                  threads=True, progress=False)
                break
            except Exception:
                time.sleep(2 * (attempt + 1))
                raw = None
        if raw is None or raw.empty:
            continue
        for t in part:
            try:
                d = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
                if len(d) > 0:
                    d.index = pd.to_datetime(d.index).tz_localize(None)
                    out[t] = d
            except Exception:
                continue
    if progress:
        progress(1.0, "Descarga completa")
    return out


# --------------------------------------------------------------------------
# Fundamentales
# --------------------------------------------------------------------------
def _demo_info(ticker: str) -> dict:
    rng = np.random.default_rng(zlib.crc32((ticker + "f").encode()))
    px = float(_synthetic(ticker)["Close"].iloc[-1])
    return {
        "longName": f"{ticker} Corp (DEMO)", "sector": rng.choice(["Technology", "Healthcare", "Financials", "Energy"]),
        "industry": "Demo", "marketCap": rng.uniform(5e9, 2e12), "trailingPE": rng.uniform(8, 60),
        "forwardPE": rng.uniform(8, 45), "pegRatio": rng.uniform(0.6, 3.5), "priceToBook": rng.uniform(1, 15),
        "enterpriseToEbitda": rng.uniform(6, 35), "freeCashflow": rng.uniform(-1e9, 2e10),
        "returnOnEquity": rng.uniform(-0.05, 0.45), "returnOnAssets": rng.uniform(-0.02, 0.2),
        "grossMargins": rng.uniform(0.2, 0.8), "operatingMargins": rng.uniform(-0.05, 0.4),
        "profitMargins": rng.uniform(-0.05, 0.3), "revenueGrowth": rng.uniform(-0.1, 0.4),
        "earningsGrowth": rng.uniform(-0.3, 0.6), "debtToEquity": rng.uniform(10, 250),
        "currentRatio": rng.uniform(0.7, 3), "beta": rng.uniform(0.6, 1.8),
        "targetMeanPrice": px * rng.uniform(0.85, 1.35), "recommendationMean": rng.uniform(1.4, 3.2),
        "numberOfAnalystOpinions": int(rng.integers(5, 45)), "currentPrice": px,
    }


def info(ticker: str, av_key: str | None = None, provider: str = "yahoo") -> dict:
    if _demo():
        return _demo_info(ticker)
    data = {}
    if provider == "alphavantage" and av_key:
        try:
            av = av_overview(ticker, av_key)
            if av.get("longName"):
                data = av
        except Exception:
            pass
    try:
        import yfinance as yf
        yinfo = yf.Ticker(ticker).info or {}
        data = {**yinfo, **{k: v for k, v in data.items() if v is not None}}
    except Exception:
        pass
    if (not data or data.get("trailingPE") is None) and av_key:
        try:
            from .fundamental import alpha_vantage_overview_to_info
            ov = requests.get("https://www.alphavantage.co/query",
                              params={"function": "OVERVIEW", "symbol": ticker, "apikey": av_key}, timeout=20).json()
            if ov.get("Symbol"):
                av = alpha_vantage_overview_to_info(ov)
                data = {**av, **{k: v for k, v in data.items() if v is not None}}
        except Exception:
            pass
    return data


def statements(ticker: str):
    if _demo():
        return None, None, None
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        return t.financials, t.balance_sheet, t.cashflow
    except Exception:
        return None, None, None


def news(ticker: str, n: int = 8, av_key: str = "") -> list[dict]:
    if _demo():
        return []
    if av_key:
        try:
            items = av_news(ticker, av_key, n)
            if items:
                return items
        except Exception:
            pass
    try:
        import yfinance as yf
        items = yf.Ticker(ticker).news or []
        out = []
        for it in items[:n]:
            c = it.get("content", it)
            out.append({"titulo": c.get("title"), "fuente": (c.get("provider") or {}).get("displayName", c.get("publisher")),
                        "link": ((c.get("canonicalUrl") or {}).get("url") or c.get("link"))})
        return [o for o in out if o["titulo"]]
    except Exception:
        return []


# --------------------------------------------------------------------------
# Alpha Vantage (REST — la misma fuente que el conector MCP de Claude)
#   Gratis: TIME_SERIES_DAILY compacto (100 días), TOP_GAINERS_LOSERS, NEWS_SENTIMENT, ~25 llamadas/día
#   Premium: historial completo (outputsize=full), OVERVIEW, estados financieros, sin límite diario
# --------------------------------------------------------------------------
AV_URL = "https://www.alphavantage.co/query"


class AlphaVantageError(RuntimeError):
    pass


def _av(params: dict, key: str) -> dict:
    if not key:
        raise AlphaVantageError("Falta la API key de Alpha Vantage")
    j = requests.get(AV_URL, params={**params, "apikey": key}, timeout=30).json()
    msg = j.get("Information") or j.get("Note") or j.get("Error Message")
    if msg and len(j) <= 2:
        raise AlphaVantageError(msg)
    return j


def av_daily(ticker: str, key: str, full: bool = True) -> pd.DataFrame:
    """OHLCV diario. full=True requiere plan premium; si falla, cae a 'compact' (100 días)."""
    try:
        j = _av({"function": "TIME_SERIES_DAILY_ADJUSTED" if full else "TIME_SERIES_DAILY", "symbol": ticker,
                 "outputsize": "full" if full else "compact"}, key)
    except AlphaVantageError:
        if not full:
            raise
        j = _av({"function": "TIME_SERIES_DAILY", "symbol": ticker, "outputsize": "compact"}, key)
    ts = next(v for k, v in j.items() if "Time Series" in k)
    df = pd.DataFrame(ts).T.astype(float)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    ren = {"1. open": "Open", "2. high": "High", "3. low": "Low", "4. close": "Close"}
    if "5. adjusted close" in df.columns:  # ajustar por splits/dividendos
        f = df["5. adjusted close"] / df["4. close"]
        for c in ("1. open", "2. high", "3. low", "4. close"):
            df[c] = df[c] * f
        df = df.rename(columns={"6. volume": "Volume"})
    else:
        df = df.rename(columns={"5. volume": "Volume"})
    return df.rename(columns=ren)[["Open", "High", "Low", "Close", "Volume"]]


def av_overview(ticker: str, key: str) -> dict:
    from .fundamental import alpha_vantage_overview_to_info
    return alpha_vantage_overview_to_info(_av({"function": "OVERVIEW", "symbol": ticker}, key))


def av_movers(key: str) -> list[str]:
    """Más activas + mayores alzas/bajas del día (endpoint gratuito). Excluye warrants/units/rights."""
    j = _av({"function": "TOP_GAINERS_LOSERS"}, key)
    out = []
    for grp in ("most_actively_traded", "top_gainers", "top_losers"):
        for it in j.get(grp, []):
            t = it["ticker"]
            if any(ch in t for ch in "+^.") or (len(t) >= 5 and t[-1] in "WUR"):
                continue
            out.append(t)
    return list(dict.fromkeys(out))


def av_news(ticker: str, key: str, n: int = 8) -> list[dict]:
    j = _av({"function": "NEWS_SENTIMENT", "tickers": ticker, "limit": 50}, key)
    out = []
    for it in j.get("feed", [])[:n]:
        sent = next((s for s in it.get("ticker_sentiment", []) if s.get("ticker") == ticker), {})
        out.append({"titulo": it.get("title"), "fuente": it.get("source"), "link": it.get("url"),
                    "sentimiento": sent.get("ticker_sentiment_label")})
    return out
