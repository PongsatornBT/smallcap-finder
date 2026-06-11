# Smallcap Finder — Design

**Date:** 2026-06-11
**Status:** Approved by user (sections reviewed and accepted individually)

## Overview

A personal, completely free tool that finds US small-cap stocks getting unusual social attention. Once a day it scans Reddit and StockTwits for ticker chatter, scores each ticker by how abnormal today's attention is versus its own 30-day baseline, filters out junk companies using official SEC data, and publishes a ranked dashboard to a static website.

**It is an idea-discovery tool, not financial advice.** Buzz on small-caps often includes coordinated pumping; quality tags reduce but cannot eliminate that risk. The dashboard must carry this disclaimer.

## Goals

- Surface small-cap tickers with unusually rising discussion before they become widely known.
- Separate plausible companies from likely pump-and-dumps, transparently.
- Cost exactly $0 to build and run, forever. Free data sources only.
- Viewable from any device (phone or PC) with zero maintenance effort.

## Non-goals

- No trading or brokerage integration. The tool never buys, sells, or recommends.
- No real-time monitoring; one scheduled scan per day is the product.
- No Twitter/X (no free API), no paid data sources, no Thai market (possible future).
- No user accounts, no server, no database service.
- No ML or sentiment analysis in v1 (future idea).

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Market | US (NYSE/NASDAQ/AMEX) |
| Audience | Single user (personal tool) |
| Usage style | Daily scan + dashboard |
| Ranking | Buzz score + quality filter |
| Language | Python |
| Runtime | GitHub Actions (free) + GitHub Pages dashboard |

## Architecture

One public GitHub repository contains everything: scanner code, configuration, scan history, and the dashboard site.

1. A GitHub Actions workflow runs daily at **12:30 UTC** (~1 hour before US market open; evening in Thailand), every day of the week. Expected runtime 5–10 minutes — far inside GitHub's free tier (unlimited minutes for public repos).
2. The Python scanner pulls data, scores it, and writes JSON results plus updated history files.
3. The workflow commits results back to the repo. GitHub Pages serves `docs/` as a static website — that is the dashboard.

No server. No database. History accumulates as JSON files in git.

### Data sources (all free)

| Source | What it provides | Access | Reliability notes |
|---|---|---|---|
| Reddit API | Posts + comments, last 24h, from r/pennystocks, r/smallstreetbets, r/wallstreetbets, r/stocks (configurable) | Free script-app OAuth (client id + secret as GitHub secrets) | Official free tier, 100 req/min — ample |
| StockTwits API | Trending tickers list | Public endpoint, no auth | May throttle; treated as optional bonus signal |
| SEC EDGAR | Official ticker list (`company_tickers.json`), company financials (`companyfacts`) | Free official API, requires User-Agent header with contact email | Official and stable |
| Yahoo Finance (via `yfinance`) | Market cap, price, average volume, exchange, sector | Free unofficial library | Occasionally breaks when Yahoo changes; Stooq is the price fallback |
| Stooq | Daily prices (fallback) | Free CSV endpoint | Fallback only |

## Pipeline (daily run)

### Step 1 — Collect mentions
- Reddit: fetch new posts and their top-level comments from the configured subreddits for the last 24 hours. Record: text, author username, post URL, title, upvotes, subreddit.
- StockTwits: fetch the current trending-tickers list.
- Each collector is independent; failure of one does not stop the run (see Error handling).

### Step 2 — Extract tickers
- Match `$TICKER` cashtags and bare uppercase symbols (2–5 letters) in post titles, bodies, and comments.
- A symbol counts only if it appears in the SEC official ticker list.
- Bare symbols of 1–2 letters, and any symbol on the ambiguity blocklist (common words that are also tickers: `A, I, IT, ALL, CEO, DD, AI, EV, OR, ON, BE, GO, ARE, FOR, NOW, ANY, CAN, …` — maintained in config), count **only** when written as a cashtag (`$IT`).
- Output: per-ticker mention records with author usernames.

### Step 3 — Score buzz
- For each ticker: `unique_authors_today` = distinct usernames mentioning it across all sources today.
- `buzz_score = unique_authors_today / max(avg_unique_authors_30d, 0.5)` where the average comes from the rolling history file. The 0.5 floor makes never-mentioned tickers that suddenly appear rank highest — intended, that is "early discovery".
- Eligibility: `unique_authors_today >= 5` (config), otherwise ignored as noise. Unique-author counting also blunts single-spammer manipulation.
- StockTwits trending membership: ×1.2 score bonus + a "trending" badge.
- The top 30 tickers by buzz score (config) proceed to Step 4.
- Append today's counts to the history file (rolling 90 days). During the first ~30 days, baselines are computed from whatever history exists — usable but noisier; the dashboard shows a "short history" note for tickers with <14 days of data.

### Step 4 — Quality gate
Fetch per-ticker data (only for the top 30, keeping API usage tiny) and evaluate every check. **Checks become visible tags; failing tickers are shown, not hidden.**

| Check | Pass rule (all configurable in `config.yaml`) |
|---|---|
| Market cap | $50M – $2B |
| Exchange | NYSE, NASDAQ, or AMEX (OTC fails) |
| Price | ≥ $1.00 |
| Liquidity | Average daily dollar volume (trailing 30 days) ≥ $200k |
| Real revenue | Latest annual/TTM revenue ≥ $1M per SEC EDGAR (`us-gaap` Revenues or RevenueFromContractWithCustomerExcludingAssessedTax) |

- Pass **all** checks → "Quality picks" list.
- Fail any → "Hyped — caution" list, with red tags naming each failed check.
- If data for a check cannot be fetched, the ticker goes to the caution list with a "data unavailable" tag (never silently dropped, never silently passed).

### Step 5 — Publish
- Write `docs/data/latest.json` and a dated snapshot `docs/data/YYYY-MM-DD.json`.
- Update `data/history.json`.
- Commit and push. GitHub Pages serves the updated dashboard automatically.

### Result JSON shape (`latest.json`)

```json
{
  "date": "2026-06-11",
  "scanned_at_utc": "2026-06-11T12:34:56Z",
  "sources": { "reddit": "ok", "stocktwits": "failed" },
  "summary": { "tickers_mentioned": 412, "passed": 6, "caution": 9 },
  "picks": [ { "...": "entry, see below" } ],
  "caution": [ { "...": "entry" } ]
}
```

Each entry: `ticker, name, sector, exchange, market_cap, price, buzz_score, unique_authors, mentions, avg_30d, spark` (last 7 daily author counts), `tags: {passed: [...], failed: [...]}, trending` (bool), `short_history` (bool), `sample_posts: [{title, url, subreddit, upvotes}]` (top 3 by upvotes), `links: {yahoo, edgar}`.

## Dashboard

A single static page (`docs/index.html` + `app.js` + `style.css`, plain HTML/JS/CSS, no framework, no build step) that fetches `data/latest.json` and renders:

- **Header:** scan date/time and per-source status ("Reddit ok · StockTwits unavailable").
- **Summary stats:** tickers mentioned / quality picks / caution count.
- **Quality picks** — ranked cards: ticker, company name, sector, market cap, price, exchange; large buzz multiplier with "N people today · 30-day avg M"; 7-day mention sparkline; green pass tags (+ amber "trending" badge); top sample post titles linking to the actual Reddit threads; links to Yahoo Finance and SEC EDGAR pages.
- **Hyped — caution** — same cards with red tags naming the failed checks (e.g. `no revenue`, `OTC market`, `under $1`).
- **Footer disclaimer:** not financial advice; buzz can be coordinated promotion.

Mobile-friendly (it is just cards in a column). No login — the page is public but unlisted.

## Project structure

```
smallcap-finder/
├── .github/workflows/daily-scan.yml   # schedule, secrets, run + commit
├── config.yaml                        # thresholds, subreddits, blocklist, schedule knobs
├── requirements.txt                   # requests, praw, yfinance, pyyaml, pytest
├── scanner/
│   ├── main.py                        # orchestrates steps 1–5
│   ├── collectors/
│   │   ├── reddit.py
│   │   ├── stocktwits.py
│   │   ├── prices.py                  # yfinance with Stooq fallback
│   │   └── edgar.py                   # ticker list + companyfacts
│   ├── pipeline/
│   │   ├── tickers.py                 # extraction + validation + blocklist
│   │   ├── scoring.py                 # buzz math + history update
│   │   └── quality.py                 # checks → tags
│   └── report.py                      # JSON writing
├── data/history.json                  # rolling 90-day per-ticker author counts
├── docs/                              # GitHub Pages root
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── data/latest.json, YYYY-MM-DD.json
└── tests/
    ├── test_tickers.py
    ├── test_scoring.py
    ├── test_quality.py
    └── fixtures/                      # recorded sample API payloads
```

Each module has one purpose and a small surface: collectors return plain lists of records; pipeline functions are pure (data in → data out) so they are trivially testable offline.

## Error handling

- **Per-source isolation:** each collector failure is caught; the run continues with remaining sources and the dashboard header reports the degraded source. Buzz baselines are not updated from a partially-failed source in a way that poisons history (a failed source contributes nothing rather than zeros).
- **Per-ticker isolation:** a failed price/financials lookup skips only that ticker (tagged "data unavailable" in the caution list).
- **Total failure:** if no mention source succeeds, the workflow exits non-zero → GitHub automatically emails the repo owner (free alerting, zero setup).
- **Rate limits:** polite delays between API calls; daily volume is far below every source's free limits. EDGAR requests carry the required User-Agent.
- **yfinance breakage:** prices fall back to Stooq; fundamentals come from EDGAR (official). If market cap is unavailable from both, the ticker is tagged "data unavailable".
- **Cron drift:** GitHub may delay scheduled runs by up to ~30 minutes under load — acceptable for a daily digest.

## Testing

- **Unit tests (offline, run on every push via Actions):**
  - `test_tickers.py` — cashtag matching, bare-symbol validation, blocklist ("CEO" rejected, "$IT" accepted, "QNTM" caught in plain text).
  - `test_scoring.py` — buzz math, the 0.5 floor, the ≥5-author eligibility rule, history roll-off at 90 days.
  - `test_quality.py` — every check's pass/fail boundary, tag generation, "data unavailable" path.
  - All use recorded fixture payloads in `tests/fixtures/` — no network.
- **Dry-run mode:** `python -m scanner.main --dry-run` runs the full pipeline locally against live APIs but writes to a temp folder and skips the git commit — for manual verification before trusting the schedule.

## One-time setup (the only manual steps)

1. Create a public GitHub repository and push this project.
2. Enable GitHub Pages, serving from the `docs/` folder.
3. Create a free Reddit account → create a "script" app at reddit.com/prefs/apps → store `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` as GitHub Actions secrets.
4. Put a contact email in `config.yaml` for the EDGAR User-Agent.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `yfinance` breaks when Yahoo changes | Stooq fallback for prices; EDGAR for fundamentals; degrade to "data unavailable" tags |
| Reddit API policy changes | Collector isolation; StockTwits still works; revisit sources if it happens |
| StockTwits throttles/blocks | It is a bonus signal only; run completes without it |
| Buzz is manipulated (pumping) | Unique-author counting, quality tags, caution list, visible disclaimer — reduced, not eliminated |
| Public repo exposes the tool | Acceptable: output is non-sensitive scan data; no secrets in the repo (API keys live in Actions secrets) |
| GitHub free tier changes | Low likelihood; design is portable (plain Python + static site runs anywhere, including locally) |

## Acceptance criteria

- The daily workflow completes in under 15 minutes and commits updated `latest.json`.
- The dashboard renders both lists with buzz scores, tags, sparklines, and working Reddit/Yahoo/EDGAR links on desktop and phone.
- A source outage degrades gracefully and is visible in the header.
- All unit tests pass offline.
- Total recurring cost: $0. No credit card required anywhere.

## Future ideas (explicitly out of scope for v1)

- Telegram/email alert when a ticker spikes above a threshold.
- Simple sentiment analysis on mention text (e.g. VADER).
- Thai market (SET/mai) coverage.
- On-demand local runs with a `--now` flag feeding the same dashboard.
- Historical browsing UI (the dated JSON snapshots already preserve the data).
