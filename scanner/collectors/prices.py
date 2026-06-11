"""Market data per ticker: price, market cap, liquidity, sector.

Primary source is Yahoo Finance via the unofficial yfinance library; daily
prices fall back to Stooq when Yahoo breaks. Never raises — missing values
come back as None and turn into "unknown" quality tags downstream.
"""
import csv
import io
import logging

import requests

log = logging.getLogger(__name__)

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}.us&i=d"


def fetch_market_data(symbol, config):
    out = {"price": None, "market_cap": None, "dollar_volume_30d": None, "sector": None}
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo", auto_adjust=False)
        if not hist.empty:
            out["price"] = float(hist["Close"].iloc[-1])
            out["dollar_volume_30d"] = float((hist["Close"] * hist["Volume"]).mean())
        out["market_cap"] = _fast_info(ticker, "marketCap", "market_cap")
        try:
            out["sector"] = (ticker.info or {}).get("sector")
        except Exception:
            pass
    except Exception as exc:
        log.warning("yfinance failed for %s: %s", symbol, exc)

    if out["price"] is None or out["dollar_volume_30d"] is None:
        try:
            rows = _stooq_daily(symbol)
            if rows:
                closes = [float(r["Close"]) for r in rows]
                volumes = [float(r.get("Volume") or 0) for r in rows]
                out["price"] = out["price"] or closes[-1]
                if out["dollar_volume_30d"] is None:
                    out["dollar_volume_30d"] = sum(c * v for c, v in zip(closes, volumes)) / len(rows)
        except Exception as exc:
            log.warning("stooq fallback failed for %s: %s", symbol, exc)
    return out


def _fast_info(ticker, *keys):
    for key in keys:
        try:
            value = ticker.fast_info[key]
        except Exception:
            value = getattr(ticker.fast_info, key, None)
        if value:
            return float(value)
    return None


def _stooq_daily(symbol, sessions=22):
    resp = requests.get(STOOQ_URL.format(symbol=symbol.lower()), timeout=20)
    resp.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    return rows[-sessions:]
