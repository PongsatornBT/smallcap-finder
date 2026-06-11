"""Assemble dashboard entries and write the result JSON files."""
import json
from pathlib import Path


def build_entry(row, info, market, qdata, passed, failed, spark_counts):
    symbol = row["ticker"]
    return {
        "ticker": symbol,
        "name": info["name"],
        "sector": market.get("sector") or "",
        "exchange": qdata["exchange"],
        "market_cap": qdata["market_cap"],
        "price": qdata["price"],
        "buzz_score": row["buzz_score"],
        "unique_authors": row["unique_authors"],
        "mentions": row["mentions"],
        "avg_30d": row["avg_30d"],
        "spark": spark_counts,
        "tags": {"passed": passed, "failed": failed},
        "trending": row["trending"],
        "short_history": row["short_history"],
        "sample_posts": [
            {
                "title": p["title"],
                "url": p["url"],
                "subreddit": p["subreddit"],
                "upvotes": p["upvotes"],
            }
            for p in row["sample_posts"]
        ],
        "links": {
            "yahoo": f"https://finance.yahoo.com/quote/{symbol}",
            "edgar": (
                "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                f"&CIK={info['cik']:010d}&type=10-K"
            ),
        },
    }


def write_results(result, data_dir):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=1, ensure_ascii=False)
    (data_dir / "latest.json").write_text(payload, encoding="utf-8")
    (data_dir / f"{result['date']}.json").write_text(payload, encoding="utf-8")
