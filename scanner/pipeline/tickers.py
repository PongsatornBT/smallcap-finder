"""Find ticker symbols in text and group mentions per ticker.

Rules (see design spec):
- $CASHTAGS count if the symbol is in the SEC directory.
- Bare uppercase words count only if in the directory, longer than
  cashtag_only_max_len, and not on the blocklist of word-like tickers.
- Company names count too: multi-word names are auto-derived from the SEC
  directory ("Virgin Galactic Holdings, Inc" -> "virgin galactic" -> SPCE);
  one-word nicknames come only from the user's ticker_aliases config.
"""
import re

CASHTAG_RE = re.compile(r"\$([A-Za-z]{1,5})\b")
BARE_RE = re.compile(r"\b([A-Z]{2,5})\b")
WORD_RE = re.compile(r"[a-z0-9']+")

IGNORED_AUTHORS = {"[deleted]", "AutoModerator"}

# Legal/corporate words stripped from the end of company names so the part
# people actually write remains ("Rocket Lab USA, Inc" -> "rocket lab").
NAME_SUFFIX_WORDS = {
    "inc", "incorporated", "corp", "corporation", "ltd", "limited", "llc",
    "llp", "lp", "plc", "co", "company", "companies", "holdings", "holding",
    "group", "trust", "sa", "nv", "ag", "se", "ab", "asa", "usa", "us",
}


def name_phrase(company_name):
    """Normalize a company name to the word tuple people actually write."""
    tokens = WORD_RE.findall(company_name.lower())
    if tokens and tokens[0] == "the":
        tokens = tokens[1:]
    while tokens and tokens[-1] in NAME_SUFFIX_WORDS:
        tokens = tokens[:-1]
    return tuple(tokens)


def build_name_lookup(directory, config):
    """Return {first_word: [(phrase_tuple, ticker), ...]} for name matching.

    Auto-derived names must have at least two words; one-word nicknames are
    only taken from the explicit ticker_aliases config, so common words like
    "apple" never match by accident.
    """
    blocked = {
        tuple(WORD_RE.findall(p.lower()))
        for p in config.get("company_name_blocklist") or []
    }
    lookup = {}

    def add(phrase, ticker):
        if phrase and phrase not in blocked:
            lookup.setdefault(phrase[0], []).append((phrase, ticker))

    if config.get("company_name_matching", True):
        for ticker, info in directory.items():
            phrase = name_phrase(info.get("name") or "")
            if len(phrase) >= 2:
                add(phrase, ticker)

    for ticker, aliases in (config.get("ticker_aliases") or {}).items():
        symbol = ticker.upper()
        if symbol not in directory:
            continue
        for alias in aliases:
            add(tuple(WORD_RE.findall(alias.lower())), symbol)

    return lookup


def extract_by_name(text, name_lookup):
    """Find tickers mentioned by company name (case-insensitive whole words)."""
    tokens = WORD_RE.findall(text.lower())
    found = set()
    for i, token in enumerate(tokens):
        for phrase, ticker in name_lookup.get(token, ()):
            if tuple(tokens[i:i + len(phrase)]) == phrase:
                found.add(ticker)
    return found


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


def group_mentions(mentions, directory, config, name_lookup=None):
    """Return {ticker: {mentions, authors (set), posts (list)}}."""
    blocklist = set(config["ticker_blocklist"])
    max_len = config["cashtag_only_max_len"]
    by_ticker = {}
    for record in mentions:
        symbols = extract_tickers(record["text"], directory, blocklist, max_len)
        if name_lookup:
            symbols |= extract_by_name(record["text"], name_lookup)
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
