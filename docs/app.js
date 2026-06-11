"use strict";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function fmtMoney(value) {
  if (value === null || value === undefined) return "—";
  const units = [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
  for (const [div, suffix] of units) {
    if (Math.abs(value) >= div) {
      let text = (value / div).toFixed(1);
      if (text.endsWith(".0")) text = text.slice(0, -2);
      return "$" + text + suffix;
    }
  }
  return "$" + Math.round(value);
}

function fmtPrice(value) {
  if (value === null || value === undefined) return "—";
  return "$" + value.toFixed(2);
}

function renderStats(summary) {
  const section = document.getElementById("summary");
  const stats = [
    ["Tickers mentioned", summary.tickers_mentioned],
    ["Quality picks", summary.passed],
    ["Caution list", summary.caution],
  ];
  for (const [label, value] of stats) {
    const card = el("div", "stat");
    card.appendChild(el("div", "label", label));
    card.appendChild(el("div", "value", String(value)));
    section.appendChild(card);
  }
}

function renderCard(entry) {
  const card = el("div", "card");

  const top = el("div", "card-top");
  const left = el("div");
  const titleRow = el("div");
  titleRow.appendChild(el("span", "ticker", entry.ticker));
  const companyBits = [entry.name, entry.sector].filter(Boolean).join(" · ");
  titleRow.appendChild(el("span", "company", companyBits));
  left.appendChild(titleRow);
  const statBits = [
    fmtMoney(entry.market_cap) + " cap",
    fmtPrice(entry.price),
    entry.exchange || "exchange unknown",
  ].join(" · ");
  left.appendChild(el("div", "statline", statBits));
  top.appendChild(left);

  const buzz = el("div", "buzz");
  const score = el("div", "score", "×" + entry.buzz_score);
  const small = el("small", null, " buzz");
  score.appendChild(small);
  buzz.appendChild(score);
  buzz.appendChild(el("div", "detail",
    entry.unique_authors + " people today · 30-day avg " + entry.avg_30d));
  top.appendChild(buzz);
  card.appendChild(top);

  if (Array.isArray(entry.spark) && entry.spark.length) {
    const sparkMax = Math.max(...entry.spark, 1);
    const spark = el("div", "spark");
    spark.setAttribute("aria-hidden", "true");
    for (const count of entry.spark) {
      const bar = el("div");
      bar.style.height = Math.max(3, Math.round((count / sparkMax) * 26)) + "px";
      bar.title = String(count);
      spark.appendChild(bar);
    }
    card.appendChild(spark);
  }

  const tags = el("div", "tags");
  for (const tag of entry.tags.passed) tags.appendChild(el("span", "tag pass", tag));
  for (const tag of entry.tags.failed) tags.appendChild(el("span", "tag fail", tag));
  if (entry.trending) tags.appendChild(el("span", "tag warn", "StockTwits trending"));
  if (entry.short_history) tags.appendChild(el("span", "tag warn", "short history"));
  card.appendChild(tags);

  if (entry.sample_posts && entry.sample_posts.length) {
    const posts = el("div", "posts");
    for (const post of entry.sample_posts) {
      const row = el("div");
      const link = el("a", null, "“" + post.title + "”");
      link.href = post.url;
      link.target = "_blank";
      link.rel = "noopener";
      row.appendChild(link);
      row.appendChild(el("span", "meta",
        " · r/" + post.subreddit + " · " + post.upvotes + " upvotes"));
      posts.appendChild(row);
    }
    card.appendChild(posts);
  }

  const links = el("div", "extlinks");
  const yahoo = el("a", null, "Yahoo Finance");
  yahoo.href = entry.links.yahoo;
  yahoo.target = "_blank";
  yahoo.rel = "noopener";
  const edgar = el("a", null, "SEC filings");
  edgar.href = entry.links.edgar;
  edgar.target = "_blank";
  edgar.rel = "noopener";
  links.appendChild(yahoo);
  links.appendChild(edgar);
  card.appendChild(links);

  return card;
}

function renderList(containerId, entries, emptyText) {
  const container = document.getElementById(containerId);
  if (!entries || !entries.length) {
    container.appendChild(el("div", "empty", emptyText));
    return;
  }
  for (const entry of entries) container.appendChild(renderCard(entry));
}

function sourceText(sources) {
  const parts = [];
  for (const [name, state] of Object.entries(sources)) {
    parts.push(name + (state === "ok" ? " ok" : " unavailable"));
  }
  return parts.join(" · ");
}

async function load() {
  const meta = document.getElementById("scan-meta");
  let data;
  try {
    const resp = await fetch("data/latest.json?_=" + Date.now());
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    data = await resp.json();
  } catch (err) {
    meta.textContent = "Could not load scan data (" + err.message + ")";
    return;
  }

  if (!data.date) {
    meta.textContent = "No scan results yet — the first daily run hasn't happened.";
    renderStats(data.summary || { tickers_mentioned: 0, passed: 0, caution: 0 });
    renderList("picks", [], "Nothing yet.");
    renderList("caution", [], "Nothing yet.");
    return;
  }

  meta.textContent = "scanned " + data.scanned_at_utc + " · " + sourceText(data.sources);
  renderStats(data.summary);
  renderList("picks", data.picks,
    "No tickers passed every check today. See the caution list below.");
  renderList("caution", data.caution, "Nothing on the caution list today.");
}

load();
