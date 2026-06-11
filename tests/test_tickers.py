from scanner.pipeline.tickers import extract_tickers, group_mentions

DIRECTORY = {"QNTM": {}, "HLXH": {}, "IT": {}, "AB": {}, "CEO": {}}
BLOCKLIST = {"CEO"}
MAX_LEN = 2

CONFIG = {"ticker_blocklist": ["CEO"], "cashtag_only_max_len": 2}


def extract(text):
    return extract_tickers(text, DIRECTORY, BLOCKLIST, MAX_LEN)


def test_cashtag_matches():
    assert extract("loading up on $QNTM today") == {"QNTM"}


def test_cashtag_case_insensitive():
    assert extract("$qntm to the moon") == {"QNTM"}


def test_bare_uppercase_matches():
    assert extract("QNTM just got a contract") == {"QNTM"}


def test_bare_lowercase_ignored():
    assert extract("qntm just got a contract") == set()


def test_unknown_symbol_ignored():
    assert extract("$ZZZZ is pumping") == set()


def test_blocklisted_word_needs_cashtag():
    assert extract("the CEO resigned today") == set()
    assert extract("bought the $CEO fund") == {"CEO"}


def test_short_symbols_need_cashtag():
    assert extract("our AB testing showed IT issues") == set()
    assert extract("$AB and $IT both reported") == {"AB", "IT"}


def test_multiple_tickers_one_text():
    assert extract("rotating from $QNTM into HLXH") == {"QNTM", "HLXH"}


def _mention(author, text, kind="comment", upvotes=0):
    return {
        "source": "reddit",
        "kind": kind,
        "author": author,
        "text": text,
        "title": text if kind == "post" else None,
        "url": "https://www.reddit.com/x",
        "upvotes": upvotes,
        "subreddit": "pennystocks",
    }


def test_group_mentions_counts_and_dedupes_authors():
    mentions = [
        _mention("alice", "buy $QNTM", kind="post", upvotes=10),
        _mention("alice", "QNTM still cheap"),
        _mention("bob", "$QNTM dd inside", kind="post", upvotes=50),
        _mention("[deleted]", "QNTM yes"),
    ]
    grouped = group_mentions(mentions, DIRECTORY, CONFIG)
    entry = grouped["QNTM"]
    assert entry["mentions"] == 4
    assert entry["authors"] == {"alice", "bob"}
    assert len(entry["posts"]) == 2
