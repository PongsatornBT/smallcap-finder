"""Fetch the StockTwits trending-tickers list (public endpoint, no auth)."""
import requests

from scanner.collectors import CollectorUnavailable

TRENDING_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"


def collect(config):
    """Return a set of trending ticker symbols (uppercase)."""
    try:
        resp = requests.get(
            TRENDING_URL,
            timeout=20,
            headers={"User-Agent": f"smallcap-finder (contact: {config['contact_email']})"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise CollectorUnavailable(f"StockTwits: {exc}") from exc
    return {s["symbol"].upper() for s in data.get("symbols", []) if s.get("symbol")}
