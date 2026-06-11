"""Find ticker symbols in text and group mentions per ticker.

Rules (see design spec):
- $CASHTAGS count if the symbol is in the SEC directory.
- Bare uppercase words count only if in the directory, longer than
  cashtag_only_max_len, and not on the blocklist of word-like tickers.
"""
import re

CASHTAG_RE = re.compile(r"\$([A-Za-z]{1,5})\b")
BARE_RE = re.compile(r"\b([A-Z]{2,5})\b")

IGNORED_AUTHORS = {"[deleted]", "AutoModerator"}


def extract_tickers(text, directory, blocklist, cashtag_only_max_len):
    found = set()
    for match in CASHTAG_RE.finditer(text):
        symbol = match.group(1).upper()
        if symbol in directory:
            found.add(symbol)
    for match in BARE_RE.finditer(text):
        symbol = match.group(1)
        if (
            symbol in directory
            and symbol not in blocklist
            and len(symbol) > cashtag_only_max_len
        ):
            found.add(symbol)
    return found


def group_mentions(mentions, directory, config):
    """Return {ticker: {mentions, authors (set), posts (list)}}."""
    blocklist = set(config["ticker_blocklist"])
    max_len = config["cashtag_only_max_len"]
    by_ticker = {}
    for record in mentions:
        symbols = extract_tickers(record["text"], directory, blocklist, max_len)
        for symbol in symbols:
            entry = by_ticker.setdefault(
                symbol, {"mentions": 0, "authors": set(), "posts": []}
            )
            entry["mentions"] += 1
            if record["author"] not in IGNORED_AUTHORS:
                entry["authors"].add(record["author"])
            if record.get("kind") == "post":
                entry["posts"].append(record)
    return by_ticker
