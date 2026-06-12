# Smallcap buzz finder

A personal, completely free tool that scans Reddit and StockTwits once a day for
US small-cap stocks getting **unusual** attention, filters out junk companies
using official SEC data, and publishes the results to a simple dashboard on
GitHub Pages.

> **Not financial advice.** Buzz on small-caps often includes coordinated
> promotion ("pump and dump"). The quality tags reduce that risk; they cannot
> eliminate it. Always do your own research.

Full design: [docs/superpowers/specs/2026-06-11-smallcap-finder-design.md](docs/superpowers/specs/2026-06-11-smallcap-finder-design.md)

## How it works

Every day at 12:30 UTC a GitHub Actions workflow:

1. **Collects** the last 24h of posts/comments from r/pennystocks,
   r/smallstreetbets, r/wallstreetbets, r/stocks + trending-ticker lists from
   StockTwits (local runs; it blocks cloud IPs) and Yahoo Finance.
2. **Extracts tickers**, validated against the SEC's official ticker list
   (so words like "CEO" don't count). Company names count too: ~8,000
   multi-word names are learned automatically from the SEC list ("Virgin
   Galactic" → SPCE), and you can add one-word nicknames in `config.yaml`
   under `ticker_aliases` (e.g. "palantir" → PLTR).
3. **Scores buzz**: unique people talking today ÷ that ticker's own 30-day
   average. Sudden attention on a quiet stock ranks highest.
4. **Quality-checks** the top 30: market cap $50M–$2B, NYSE/NASDAQ/AMEX listing,
   price ≥ $1, real liquidity, real revenue per SEC EDGAR. Every check becomes
   a visible pass/fail tag — failing tickers are shown in a "caution" list,
   not hidden.
5. **Publishes** JSON + dashboard via GitHub Pages and commits the scan history
   back to the repo.

Everything is free: GitHub Actions + Pages (free for public repos), Reddit API
(free script app), StockTwits (public endpoint), SEC EDGAR (free, official),
Yahoo Finance/Stooq (free).

## One-time setup

1. **Create a public GitHub repository** and push this project to it.
2. **Enable GitHub Pages**: repo Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main`, folder `/docs`. Your dashboard will be at
   `https://<username>.github.io/<repo>/`.
3. **Create a free Reddit API app**: log in to Reddit →
   <https://www.reddit.com/prefs/apps> → "create another app…" → type
   **script**, any name, redirect URI `http://localhost:8080`. Note the client
   ID (under the app name) and the secret.
4. **Add the secrets**: repo Settings → Secrets and variables → Actions →
   New repository secret: `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`.
5. Done. The scan runs daily, or trigger it now from the Actions tab →
   "Daily scan" → "Run workflow".

If a run fails completely, GitHub emails you automatically.

## Running locally

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# run the tests (offline)
.venv\Scripts\pytest -q

# full pipeline, writes to tmp/ instead of the real output files
$env:REDDIT_CLIENT_ID = "..."; $env:REDDIT_CLIENT_SECRET = "..."
.venv\Scripts\python -m scanner.main --dry-run
```

Without Reddit credentials the dry run still works in degraded mode
(StockTwits + SEC only) — the same way the daily scan degrades if a source is
down.

To preview the dashboard locally:

```powershell
.venv\Scripts\python -m http.server 8000 -d docs
# then open http://localhost:8000
```

## Tuning

All knobs live in [config.yaml](config.yaml): subreddits, market-cap range,
minimum unique authors, blocklisted word-like tickers, schedule-independent
thresholds. Edit, commit, push — the next run uses them.

The schedule itself is the cron line in
[.github/workflows/daily-scan.yml](.github/workflows/daily-scan.yml).
