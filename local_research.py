"""Build/search a local news corpus without a search API. No AI or publication."""
import argparse
import datetime
import json
from pathlib import Path
import requests
from local_model import NewsIndex
from publisher import article_text, Blocked, canonical


def candidates(state, limit):
    urls, seen = [], set()
    def first_seen(story):
        value = story.get("firstSeenAt", 0)
        if isinstance(value, (int, float)):
            return value
        try:
            return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError, AttributeError):
            return 0
    stories = sorted(state.get("stories", []), key=first_seen, reverse=True)
    for story in stories:
        for url in [story.get("sourceUrl", "")] + story.get("researchUrls", []):
            if not isinstance(url, str) or not url.startswith("https://"):
                continue
            url = canonical(url)
            if url in seen or any(part in url for part in ("/video/", "/videos/", "/live/")):
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= max(1, min(20, limit)):
                return urls
    return urls


def collect(state, index, limit=6):
    result = {"indexed": 0, "deferred": [], "searchApiCalls": 0}
    for url in candidates(state, limit):
        try:
            page = article_text(url)  # Existing HTTPS, robots and private-address controls.
            index.add(page)
            result["indexed"] += 1
        except (Blocked, requests.RequestException, ValueError) as exc:
            result["deferred"].append({"url": url, "reason": str(exc)[:180] if isinstance(exc, Blocked) else type(exc).__name__})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["collect", "search"])
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--state", default="state.json")
    parser.add_argument("--database", default="local-corpus.sqlite")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    index = NewsIndex(args.database)
    try:
        if args.command == "collect":
            output = collect(json.loads(Path(args.state).read_text(encoding="utf-8")), index, args.limit)
        else:
            output = [{"url": p["url"], "title": p["title"], "excerpt": " ".join(p["text"].split()[:120])}
                      for p in index.search(args.query, args.limit)]
        print(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        index.close()


if __name__ == "__main__":
    main()
