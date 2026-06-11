"""Buzz scoring against each ticker's own 30-day baseline, plus history upkeep.

History file shape:
{
  "_meta": {"first_run": "YYYY-MM-DD"},
  "tickers": {"QNTM": {"YYYY-MM-DD": unique_author_count, ...}, ...}
}
"""
import json
from datetime import date, timedelta
from pathlib import Path

BASELINE_WINDOW_DAYS = 30


def load_history(path):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_history(history, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=1, sort_keys=True), encoding="utf-8")


def effective_baseline_days(history, today):
    """How many days of history actually exist, capped at the 30-day window."""
    meta = history.setdefault("_meta", {})
    if "first_run" not in meta:
        meta["first_run"] = today.isoformat()
    first_run = date.fromisoformat(meta["first_run"])
    return min(BASELINE_WINDOW_DAYS, max((today - first_run).days, 0))


def score_tickers(by_ticker, trending, history, today, config):
    """Return the top-N eligible tickers sorted by buzz score (descending)."""
    days = effective_baseline_days(history, today)
    ticker_history = history.get("tickers", {})

    results = []
    for symbol, info in by_ticker.items():
        authors_today = len(info["authors"])
        if authors_today < config["min_unique_authors"]:
            continue
        counts = ticker_history.get(symbol, {})
        if days > 0:
            window_total = sum(
                counts.get((today - timedelta(days=i)).isoformat(), 0)
                for i in range(1, days + 1)
            )
            avg = window_total / days
        else:
            avg = 0.0
        baseline = max(avg, config["baseline_floor"])
        score = authors_today / baseline
        if symbol in trending:
            score *= config["trending_bonus"]
        results.append({
            "ticker": symbol,
            "unique_authors": authors_today,
            "mentions": info["mentions"],
            "avg_30d": round(avg, 2),
            "buzz_score": round(score, 1),
            "trending": symbol in trending,
            "short_history": days < config["short_history_days"],
            "sample_posts": sorted(
                info["posts"], key=lambda p: -p["upvotes"]
            )[: config["sample_posts_per_ticker"]],
        })

    results.sort(key=lambda r: -r["buzz_score"])
    return results[: config["top_n"]]


def update_history(history, by_ticker, today, config):
    """Record today's unique-author counts and drop entries past retention."""
    ticker_history = history.setdefault("tickers", {})
    for symbol, info in by_ticker.items():
        ticker_history.setdefault(symbol, {})[today.isoformat()] = len(info["authors"])
    cutoff = (today - timedelta(days=config["history_days"])).isoformat()
    for symbol in list(ticker_history):
        kept = {d: v for d, v in ticker_history[symbol].items() if d >= cutoff}
        if kept:
            ticker_history[symbol] = kept
        else:
            del ticker_history[symbol]
    return history


def spark(history, symbol, today, days):
    """Daily unique-author counts for the last `days` days, oldest first."""
    counts = history.get("tickers", {}).get(symbol, {})
    return [
        counts.get((today - timedelta(days=i)).isoformat(), 0)
        for i in range(days - 1, -1, -1)
    ]
