import json
from pathlib import Path

from scanner.collectors.edgar import extract_annual_revenue
from scanner.pipeline.quality import evaluate, fmt_money, normalize_exchange

QCFG = {
    "market_cap_min": 50_000_000,
    "market_cap_max": 2_000_000_000,
    "min_price": 1.0,
    "min_dollar_volume": 200_000,
    "min_revenue": 1_000_000,
    "allowed_exchanges": ["NYSE", "NASDAQ", "AMEX"],
}

FIXTURES = Path(__file__).parent / "fixtures"


def data(**overrides):
    base = {
        "market_cap": 740_000_000,
        "price": 12.40,
        "dollar_volume_30d": 5_000_000,
        "exchange": "NASDAQ",
        "revenue": 58_000_000,
        "revenue_known": True,
    }
    base.update(overrides)
    return base


def test_all_checks_pass():
    passed, failed = evaluate(data(), QCFG)
    assert failed == []
    assert "cap $740M" in passed
    assert "NASDAQ" in passed
    assert "liquid" in passed
    assert "revenue $58M" in passed


def test_cap_too_small():
    _, failed = evaluate(data(market_cap=30_000_000), QCFG)
    assert any(tag.startswith("cap too small") for tag in failed)


def test_cap_too_big():
    _, failed = evaluate(data(market_cap=5_000_000_000), QCFG)
    assert any(tag.startswith("cap too big") for tag in failed)


def test_cap_unknown():
    _, failed = evaluate(data(market_cap=None), QCFG)
    assert "cap unknown" in failed


def test_otc_fails():
    _, failed = evaluate(data(exchange="OTC"), QCFG)
    assert "OTC market" in failed


def test_other_exchange_fails():
    _, failed = evaluate(data(exchange="ARCA"), QCFG)
    assert "ARCA listed" in failed


def test_price_below_minimum():
    _, failed = evaluate(data(price=0.99), QCFG)
    assert "under $1" in failed


def test_illiquid():
    _, failed = evaluate(data(dollar_volume_30d=199_999), QCFG)
    assert "illiquid" in failed


def test_no_revenue():
    _, failed = evaluate(data(revenue=None), QCFG)
    assert "no revenue" in failed


def test_revenue_below_minimum():
    _, failed = evaluate(data(revenue=999_999), QCFG)
    assert "no revenue" in failed


def test_revenue_unknown_distinct_from_none():
    _, failed = evaluate(data(revenue=None, revenue_known=False), QCFG)
    assert "revenue unknown" in failed
    assert "no revenue" not in failed


def test_fmt_money():
    assert fmt_money(740_000_000) == "$740M"
    assert fmt_money(1_500_000_000) == "$1.5B"
    assert fmt_money(950) == "$950"
    assert fmt_money(None) == "—"


def test_normalize_exchange():
    assert normalize_exchange("Nasdaq") == "NASDAQ"
    assert normalize_exchange("NYSE American") == "AMEX"
    assert normalize_exchange("OTC") == "OTC"
    assert normalize_exchange("") == ""


def test_extract_annual_revenue_prefers_latest_annual_value():
    gaap = json.loads((FIXTURES / "companyfacts_usgaap.json").read_text(encoding="utf-8"))
    assert extract_annual_revenue(gaap) == 58_000_000.0


def test_extract_annual_revenue_ignores_quarterly_only_data():
    gaap = {
        "Revenues": {
            "units": {"USD": [{"start": "2025-01-01", "end": "2025-03-31", "val": 9_000_000}]}
        }
    }
    assert extract_annual_revenue(gaap) is None
