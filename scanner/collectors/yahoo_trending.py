"""Fetch Yahoo Finance's US trending-tickers list (free, no auth).

Unlike StockTwits, this endpoint is reachable from cloud CI runners,
so the daily GitHub Actions run always has at least one trending source.
"""
import requests

from scanner.collectors import CollectorUnavailable

TRENDING_URL = "https://query1.finance.yahoo.com/v1/finance/trending/US?count=25"


def collect(config):
    """Return a set of trending ticker symbols (uppercase)."""
    try:
        resp = requests.get(
            TRENDING_URL,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) smallcap-finder",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise CollectorUnavailable(f"Yahoo trending: {exc}") from exc
    try:
        quotes = data["finance"]["result"][0]["quotes"]
    except (KeyError, IndexError, TypeError) as exc:
        raise CollectorUnavailable(f"Yahoo trending: unexpected response shape: {exc}") from exc
    return {q["symbol"].upper() for q in quotes if q.get("symbol")}
