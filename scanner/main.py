"""Daily scan orchestrator. Run as: python -m scanner.main [--dry-run]"""
import argparse
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yaml

from scanner import report
from scanner.collectors import CollectorUnavailable, edgar, prices, reddit, stocktwits
from scanner.pipeline import quality, scoring
from scanner.pipeline import tickers as ticker_pipeline

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("scanner")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Smallcap buzz daily scan")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write results to tmp/ and leave docs/data and data/history.json untouched",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    today = date.today()
    sources = {}

    mentions = []
    try:
        mentions = reddit.collect(config)
        sources["reddit"] = "ok"
        log.info("reddit: %d records", len(mentions))
    except CollectorUnavailable as exc:
        log.warning("reddit unavailable: %s", exc)
        sources["reddit"] = "failed"

    trending = set()
    try:
        trending = stocktwits.collect(config)
        sources["stocktwits"] = "ok"
        log.info("stocktwits: %d trending symbols", len(trending))
    except CollectorUnavailable as exc:
        log.warning("stocktwits unavailable: %s", exc)
        sources["stocktwits"] = "failed"

    if all(state == "failed" for state in sources.values()):
        log.error("every mention source failed; aborting so the workflow alerts")
        return 1

    try:
        directory = edgar.load_ticker_directory(config)
        log.info("edgar: %d tickers in directory", len(directory))
    except requests.RequestException as exc:
        log.error("EDGAR ticker directory unavailable, cannot validate symbols: %s", exc)
        return 1

    by_ticker = ticker_pipeline.group_mentions(mentions, directory, config)
    log.info("tickers mentioned: %d", len(by_ticker))

    history_path = ROOT / "data" / "history.json"
    history = scoring.load_history(history_path)
    top = scoring.score_tickers(by_ticker, trending, history, today, config)
    scoring.update_history(history, by_ticker, today, config)

    picks, caution = [], []
    for row in top:
        symbol = row["ticker"]
        info = directory[symbol]
        market = prices.fetch_market_data(symbol, config)
        revenue, revenue_known = None, True
        try:
            revenue = edgar.annual_revenue(info["cik"], config)
        except requests.RequestException as exc:
            log.warning("EDGAR facts failed for %s: %s", symbol, exc)
            revenue_known = False
        time.sleep(0.2)  # stay politely under EDGAR's request-rate guidance

        qdata = {
            "market_cap": market["market_cap"],
            "price": market["price"],
            "dollar_volume_30d": market["dollar_volume_30d"],
            "exchange": quality.normalize_exchange(info["exchange"]),
            "revenue": revenue,
            "revenue_known": revenue_known,
        }
        passed, failed = quality.evaluate(qdata, config["quality"])
        spark_counts = scoring.spark(history, symbol, today, config["spark_days"])
        entry = report.build_entry(row, info, market, qdata, passed, failed, spark_counts)
        (picks if not failed else caution).append(entry)
        log.info(
            "%s buzz x%.1f -> %s", symbol, row["buzz_score"],
            "pick" if not failed else f"caution ({', '.join(failed)})",
        )

    result = {
        "date": today.isoformat(),
        "scanned_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources,
        "summary": {
            "tickers_mentioned": len(by_ticker),
            "passed": len(picks),
            "caution": len(caution),
        },
        "picks": picks,
        "caution": caution,
    }

    if args.dry_run:
        out_dir = ROOT / "tmp"
        report.write_results(result, out_dir / "docs-data")
        scoring.save_history(history, out_dir / "history.json")
        log.info("dry run: results in %s", out_dir)
    else:
        report.write_results(result, ROOT / "docs" / "data")
        scoring.save_history(history, history_path)

    log.info("done: %d picks, %d caution", len(picks), len(caution))
    return 0


if __name__ == "__main__":
    sys.exit(main())
