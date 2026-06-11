from datetime import date, timedelta

from scanner.pipeline import scoring

CONFIG = {
    "min_unique_authors": 5,
    "baseline_floor": 0.5,
    "trending_bonus": 1.2,
    "top_n": 30,
    "history_days": 90,
    "short_history_days": 14,
    "spark_days": 7,
    "sample_posts_per_ticker": 3,
}
TODAY = date(2026, 6, 11)


def ticker_info(n_authors):
    return {
        "mentions": n_authors,
        "authors": {f"user{i}" for i in range(n_authors)},
        "posts": [],
    }


def days_ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


def test_first_run_uses_floor_baseline():
    top = scoring.score_tickers({"QNTM": ticker_info(5)}, set(), {}, TODAY, CONFIG)
    assert top[0]["buzz_score"] == 10.0
    assert top[0]["short_history"] is True


def test_baseline_from_full_history():
    history = {
        "_meta": {"first_run": days_ago(40)},
        "tickers": {"QNTM": {days_ago(i): 2 for i in range(1, 31)}},
    }
    top = scoring.score_tickers({"QNTM": ticker_info(8)}, set(), history, TODAY, CONFIG)
    assert top[0]["avg_30d"] == 2.0
    assert top[0]["buzz_score"] == 4.0
    assert top[0]["short_history"] is False


def test_early_days_use_actual_history_length():
    history = {
        "_meta": {"first_run": days_ago(10)},
        "tickers": {"QNTM": {days_ago(i): 2 for i in range(1, 11)}},
    }
    top = scoring.score_tickers({"QNTM": ticker_info(8)}, set(), history, TODAY, CONFIG)
    assert top[0]["avg_30d"] == 2.0
    assert top[0]["short_history"] is True


def test_too_few_unique_authors_filtered():
    top = scoring.score_tickers({"QNTM": ticker_info(4)}, set(), {}, TODAY, CONFIG)
    assert top == []


def test_trending_bonus_applied():
    top = scoring.score_tickers({"QNTM": ticker_info(5)}, {"QNTM"}, {}, TODAY, CONFIG)
    assert top[0]["buzz_score"] == 12.0
    assert top[0]["trending"] is True


def test_top_n_cut_keeps_highest_scores():
    config = dict(CONFIG, top_n=1)
    by_ticker = {"AAAA": ticker_info(5), "BBBB": ticker_info(20)}
    top = scoring.score_tickers(by_ticker, set(), {}, TODAY, config)
    assert [r["ticker"] for r in top] == ["BBBB"]


def test_update_history_records_today_and_prunes_old():
    history = {
        "tickers": {
            "OLDY": {days_ago(120): 3},
            "QNTM": {days_ago(120): 2, days_ago(1): 4},
        }
    }
    scoring.update_history(history, {"QNTM": ticker_info(6)}, TODAY, CONFIG)
    assert history["tickers"]["QNTM"] == {days_ago(1): 4, TODAY.isoformat(): 6}
    assert "OLDY" not in history["tickers"]


def test_spark_is_oldest_first_with_gaps_as_zero():
    history = {"tickers": {"QNTM": {TODAY.isoformat(): 7, days_ago(1): 3}}}
    assert scoring.spark(history, "QNTM", TODAY, 3) == [0, 3, 7]
