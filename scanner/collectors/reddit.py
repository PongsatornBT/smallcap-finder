"""Collect recent posts and comments from the configured subreddits.

Needs REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in the environment
(a free "script" app from https://www.reddit.com/prefs/apps).
"""
import logging
import os
import time

from scanner.collectors import CollectorUnavailable

log = logging.getLogger(__name__)

WINDOW_SECONDS = 24 * 3600


def collect(config):
    """Return a list of mention records from the last 24 hours."""
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise CollectorUnavailable("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set")

    import praw  # imported here so tests don't need the dependency loaded

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=f"smallcap-finder personal scan (contact: {config['contact_email']})",
    )
    reddit.read_only = True

    cutoff = time.time() - WINDOW_SECONDS
    rcfg = config["reddit"]
    mentions = []
    failures = []
    for sub_name in config["subreddits"]:
        try:
            sub = reddit.subreddit(sub_name)
            for post in sub.new(limit=rcfg["posts_per_subreddit"]):
                if post.created_utc < cutoff:
                    break
                mentions.append({
                    "source": "reddit",
                    "kind": "post",
                    "author": str(post.author) if post.author else "[deleted]",
                    "text": f"{post.title}\n{post.selftext or ''}",
                    "title": post.title,
                    "url": f"https://www.reddit.com{post.permalink}",
                    "upvotes": int(post.score),
                    "subreddit": sub_name,
                })
            for comment in sub.comments(limit=rcfg["comments_per_subreddit"]):
                if comment.created_utc < cutoff:
                    break
                mentions.append({
                    "source": "reddit",
                    "kind": "comment",
                    "author": str(comment.author) if comment.author else "[deleted]",
                    "text": comment.body or "",
                    "title": None,
                    "url": f"https://www.reddit.com{comment.permalink}",
                    "upvotes": int(comment.score),
                    "subreddit": sub_name,
                })
        except Exception as exc:  # one bad subreddit must not sink the others
            log.warning("subreddit %s failed: %s", sub_name, exc)
            failures.append(sub_name)

    if failures and not mentions:
        raise CollectorUnavailable(f"all subreddits failed: {', '.join(failures)}")
    return mentions
