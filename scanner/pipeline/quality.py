"""The quality gate: every check becomes a visible tag, pass or fail.

A ticker is a "quality pick" only when the failed-tag list is empty.
Unknown data is always a failed tag — never a silent pass or a silent drop.
"""

EXCHANGE_MAP = {
    "Nasdaq": "NASDAQ",
    "NYSE": "NYSE",
    "NYSE American": "AMEX",
    "NYSE MKT": "AMEX",
    "NYSE Arca": "ARCA",
    "CBOE": "CBOE",
    "OTC": "OTC",
}


def normalize_exchange(raw):
    if not raw:
        return ""
    return EXCHANGE_MAP.get(raw, raw.upper())


def fmt_money(value):
    if value is None:
        return "—"
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= divisor:
            text = f"{value / divisor:.1f}".rstrip("0").rstrip(".")
            return f"${text}{suffix}"
    return f"${value:.0f}"


def evaluate(data, qcfg):
    """data keys: market_cap, price, dollar_volume_30d, exchange, revenue, revenue_known.

    Returns (passed_tags, failed_tags).
    """
    passed, failed = [], []

    cap = data["market_cap"]
    if cap is None:
        failed.append("cap unknown")
    elif cap < qcfg["market_cap_min"]:
        failed.append(f"cap too small {fmt_money(cap)}")
    elif cap > qcfg["market_cap_max"]:
        failed.append(f"cap too big {fmt_money(cap)}")
    else:
        passed.append(f"cap {fmt_money(cap)}")

    exchange = data["exchange"]
    if not exchange:
        failed.append("exchange unknown")
    elif exchange in qcfg["allowed_exchanges"]:
        passed.append(exchange)
    elif exchange == "OTC":
        failed.append("OTC market")
    else:
        failed.append(f"{exchange} listed")

    price = data["price"]
    if price is None:
        failed.append("price unknown")
    elif price < qcfg["min_price"]:
        failed.append(f"under ${qcfg['min_price']:g}")

    volume = data["dollar_volume_30d"]
    if volume is None:
        failed.append("liquidity unknown")
    elif volume < qcfg["min_dollar_volume"]:
        failed.append("illiquid")
    else:
        passed.append("liquid")

    if not data["revenue_known"]:
        failed.append("revenue unknown")
    elif data["revenue"] is None or data["revenue"] < qcfg["min_revenue"]:
        failed.append("no revenue")
    else:
        passed.append(f"revenue {fmt_money(data['revenue'])}")

    return passed, failed
