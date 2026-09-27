import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import publisher as p
import local_publisher as lp
import local_worker as worker
from local_model import LocalModelError


def page(url):
    return {"url": url, "text": ("The museum notice describes the new gallery and its opening arrangements. " * 22),
            "published": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "links": ["https://example.org/second"]}


def draft():
    return {"title": "Museum opening arrangements", "labels": ["Culture"], "high_impact": False,
            "blocks": [{"heading": "", "text": "verified " * 160, "sources": [url]}
                       for url in ["https://example.org/first", "https://example.org/second"]]}


class LocalPublishingTests(unittest.TestCase):
    def test_local_backend_never_calls_cloud_even_with_cloud_keys(self):
        with patch.dict(os.environ, {"AI_BACKEND": "local", "GEMINI_API_KEY": "unused",
                                     "TAVILY_API_KEY": "unused"}), \
             patch("local_model.LocalModel") as model, patch.object(p.SESSION, "post") as cloud:
            model.return_value.generate_json.return_value = {"ok": True}
            self.assertEqual(p.response_json("check", {}), {"ok": True})
            self.assertEqual(p.web_candidates(["news"], {}), [])
            model.return_value.generate_json.side_effect = LocalModelError("offline")
            with self.assertRaisesRegex(p.Blocked, "offline"):
                p.response_json("check", {})
            cloud.assert_not_called()

    def test_worker_enables_local_automatic_publication_without_ai_keys(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), \
             patch.object(p, "STATE"):
            path = Path(folder) / "state.json"
            path.write_text('{"stories": []}')
            os.environ["GEMINI_API_KEY"] = "unused"
            os.environ["TAVILY_API_KEY"] = "unused"
            worker.configure(path)
            self.assertEqual(os.environ["AI_BACKEND"], "local")
            self.assertEqual(os.environ["AUTO_PUBLISH"], "true")
            self.assertNotIn("GEMINI_API_KEY", os.environ)
            self.assertNotIn("TAVILY_API_KEY", os.environ)

    def test_excerpt_is_explicit_and_does_not_cut_a_sentence(self):
        result = lp.excerpt(page("https://example.org/first"), limit=900)
        self.assertTrue(result["text"].endswith("arrangements."))
        self.assertIn("not the complete page", result["selection"])
        with self.assertRaises(p.Blocked):
            lp.excerpt({"url": "https://example.org/first", "text": "x" * 9000})

    def test_passed_local_article_is_eligible_for_automatic_publication(self):
        model = Mock()
        model.generate_json.side_effect = [
            {"primary_urls": ["https://invented.org/x", "https://example.org/second"]},
            draft(), {"pass": True, "high_impact": False}]
        story, state = {"sourceUrl": "https://example.org/first"}, {"stories": []}
        with patch.object(lp, "LocalModel", return_value=model), \
             patch.object(p, "article_text", side_effect=lambda url: page(url)) as read, \
             patch.object(lp, "review_article", return_value={"passed": True, "issues": [],
                          "articleHash": "hash", "evidenceHash": "evidence"}):
            article = lp.generate_local(story, state)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(article["word_count"], 320)
        self.assertFalse(article["requires_approval"])
        self.assertIsNone(article["image"])
        self.assertTrue(story["localReview"]["passed"])

    def test_failed_claim_review_cannot_return_publishable_article(self):
        model = Mock()
        model.generate_json.side_effect = [{"primary_urls": ["https://example.org/second"]}, draft(), draft()]
        with patch.object(lp, "LocalModel", return_value=model), \
             patch.object(p, "article_text", side_effect=lambda url: page(url)), \
             patch.object(lp, "review_article", return_value={"passed": False,
                          "issues": [{"reason": "Claim contradicts source"}]}):
            with self.assertRaisesRegex(p.Blocked, "Claim contradicts source"):
                lp.generate_local({"sourceUrl": "https://example.org/first"}, {"stories": []})

    def test_model_preflight_precedes_blogger_and_ignores_gemini_cooldown(self):
        state = {"stories": [], "aiRetryAfter": p.time.time() + 9999}
        with patch.dict(os.environ, {"AI_BACKEND": "local", "AI_ENABLED": "true"}), \
             patch.object(p.Path, "read_text", return_value=json.dumps(state)), \
             patch.object(p, "discover", return_value=[]), patch("local_model.LocalModel") as model, \
             patch.object(p, "blogger_token") as blogger:
            model.return_value.verify_model.side_effect = LocalModelError("no model host")
            with self.assertRaisesRegex(p.Blocked, "no model host"):
                p.run()
            model.return_value.verify_model.assert_called_once()
            blogger.assert_not_called()

    def test_queue_lock_prevents_overlapping_workers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            with worker.queue_lock(path):
                with self.assertRaises(OSError):
                    with worker.queue_lock(path):
                        self.fail("Second worker entered lock")
            with worker.queue_lock(path):
                pass


if __name__ == "__main__":
    unittest.main()
