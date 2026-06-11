"""SEC EDGAR: official ticker directory (with exchange) and annual revenue.

EDGAR is free but requires a User-Agent header identifying the caller.
"""
from datetime import date

import requests

TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

REVENUE_CONCEPTS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
]

# A reported period of roughly a year counts as annual revenue.
ANNUAL_SPAN_DAYS = (340, 400)


def _headers(config):
    return {"User-Agent": f"smallcap-finder personal research ({config['contact_email']})"}


def load_ticker_directory(config):
    """Return {ticker: {cik, name, exchange}} for every SEC-registered ticker."""
    resp = requests.get(TICKERS_URL, headers=_headers(config), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    idx = {field: i for i, field in enumerate(data["fields"])}
    directory = {}
    for row in data["data"]:
        ticker = (row[idx["ticker"]] or "").upper()
        if ticker:
            directory[ticker] = {
                "cik": int(row[idx["cik"]]),
                "name": row[idx["name"]],
                "exchange": row[idx["exchange"]] or "",
            }
    return directory


def extract_annual_revenue(gaap_facts):
    """Pick the most recent annual revenue value from a companyfacts us-gaap dict.

    Returns None when the company reports no annual revenue at all
    (e.g. pre-revenue biotech or a shell company).
    """
    best_end = None
    best_value = None
    for concept in REVENUE_CONCEPTS:
        for item in gaap_facts.get(concept, {}).get("units", {}).get("USD", []):
            start, end, val = item.get("start"), item.get("end"), item.get("val")
            if start is None or end is None or val is None:
                continue
            try:
                span = (date.fromisoformat(end) - date.fromisoformat(start)).days
            except ValueError:
                continue
            if ANNUAL_SPAN_DAYS[0] <= span <= ANNUAL_SPAN_DAYS[1]:
                if best_end is None or end > best_end:
                    best_end, best_value = end, float(val)
    return best_value


def annual_revenue(cik, config):
    """Latest annual revenue in USD, or None if the company reports none.

    Raises requests.RequestException when EDGAR itself is unreachable, so the
    caller can distinguish "no revenue" from "couldn't check".
    """
    resp = requests.get(FACTS_URL.format(cik=int(cik)), headers=_headers(config), timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    gaap = resp.json().get("facts", {}).get("us-gaap", {})
    return extract_annual_revenue(gaap)
