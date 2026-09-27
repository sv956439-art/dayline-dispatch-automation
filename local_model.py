"""Experimental local inference and a private index of already-read public pages.

No cloud AI/search calls and no Blogger access. This is not a trained Dayline model.
"""
import json
import re
import sqlite3
import time
import requests

MODEL = "qwen3:4b"
MODEL_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
ENDPOINT = "http://127.0.0.1:11434"


class LocalModelError(RuntimeError):
    pass


class LocalModel:
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False  # Never route prompts through a proxy.
        self.metrics = {}

    def verify_model(self):
        response = self.session.get(ENDPOINT + "/api/tags", timeout=10, allow_redirects=False)
        if response.status_code != 200:
            raise LocalModelError("Local model server unavailable")
        matches = [m for m in response.json().get("models", []) if m.get("name") == MODEL]
        if len(matches) != 1 or matches[0].get("digest", "").removeprefix("sha256:") != MODEL_DIGEST:
            raise LocalModelError("Expected pinned Qwen model is not installed")

    def generate_json(self, instructions, payload, schema=None):
        prompt = json.dumps(payload, ensure_ascii=False)
        if len(prompt) + len(instructions) > 14000:
            raise LocalModelError("Evidence exceeds prototype context budget; select fewer relevant passages")
        self.verify_model()
        start = time.monotonic()
        response = self.session.post(ENDPOINT + "/api/generate", json={
            "model": MODEL, "system": instructions + " Return one JSON object only. /no_think",
            "prompt": prompt, "format": schema or "json", "stream": False, "think": False,
            "keep_alive": "5m", "options": {"num_ctx": 8192, "num_predict": 1800,
                "num_thread": 4, "num_gpu": 0, "temperature": 0.2, "seed": 42}},
            timeout=(10, 900), allow_redirects=False)
        if response.status_code != 200:
            raise LocalModelError(f"Local inference HTTP {response.status_code}; no cloud fallback")
        data = response.json()
        if data.get("done") is not True or data.get("done_reason") != "stop":
            raise LocalModelError("Local response was truncated or incomplete")
        try:
            result = json.loads(data["response"])
            if not isinstance(result, dict):
                raise ValueError()
        except (KeyError, ValueError, TypeError) as exc:
            raise LocalModelError("Local response was not a JSON object") from exc
        seconds = data.get("eval_duration", 0) / 1e9
        self.metrics = {"model": MODEL, "digest": MODEL_DIGEST,
            "elapsedSeconds": round(time.monotonic() - start, 2),
            "outputTokens": data.get("eval_count", 0),
            "tokensPerSecond": round(data.get("eval_count", 0) / seconds, 2) if seconds else None}
        return result


class NewsIndex:
    """Keyword search of pages we actually fetched; NOT an index of the whole web."""
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(url UNINDEXED, title, text, fetched UNINDEXED)")

    def add(self, page, fetched=None):
        url, body = page["url"], page["text"]
        if not url.startswith("https://") or not isinstance(body, str) or not body.strip():
            raise ValueError("Index requires a read HTTPS page with text")
        with self.db:
            self.db.execute("DELETE FROM pages WHERE url = ?", (url,))
            self.db.execute("INSERT INTO pages VALUES (?, ?, ?, ?)",
                (url, page.get("title", ""), body[:24000], fetched or time.time()))

    def search(self, query, limit=5):
        words = list(dict.fromkeys(re.findall(r"[A-Za-z0-9]{3,}", query.lower())))[:12]
        if not words:
            return []
        expression = " OR ".join('"' + word + '"' for word in words)
        rows = self.db.execute("SELECT url, title, text FROM pages WHERE pages MATCH ? "
            "AND CAST(fetched AS REAL) >= ? ORDER BY bm25(pages) LIMIT ?",
            (expression, time.time() - 7 * 86400, max(1, min(10, limit)))).fetchall()
        return [dict(zip(("url", "title", "text"), row)) for row in rows]

    def close(self):
        self.db.close()
