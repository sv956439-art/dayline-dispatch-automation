import json
import time
import unittest
from unittest.mock import Mock, patch
from local_research import collect, candidates
from local_model import LocalModel, LocalModelError, NewsIndex, MODEL, MODEL_DIGEST, ENDPOINT


class LocalModelTests(unittest.TestCase):
    def test_collector_uses_checked_fetch_and_keeps_failures(self):
        state = {"stories": [{"sourceUrl": "https://example.org/a", "researchUrls": ["https://example.org/b"]}]}
        index = NewsIndex()
        with patch("local_research.article_text", side_effect=[{"url": "https://example.org/a", "text": "Library news"}, ValueError("bad")]) as read:
            report = collect(state, index, 2)
        self.assertEqual(report["indexed"], 1)
        self.assertEqual(len(report["deferred"]), 1)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(index.search("Library")[0]["url"], "https://example.org/a")
        index.close()

    def test_collector_deduplicates_and_caps_requests(self):
        state = {"stories": [{"sourceUrl": "https://example.org/a", "researchUrls": ["https://example.org/a", "https://example.org/b"]}]}
        self.assertEqual(candidates(state, 1), ["https://example.org/a"])
        mixed = {"stories": [{"sourceUrl": "https://example.org/old", "firstSeenAt": "2025-01-01T00:00:00Z"},
                             {"sourceUrl": "https://example.org/new", "firstSeenAt": 1767225600}]}
        self.assertEqual(candidates(mixed, 1), ["https://example.org/new"])

    def client(self, result=None):
        client = LocalModel()
        client.session = Mock()
        client.session.get.return_value = Mock(status_code=200)
        client.session.get.return_value.json.return_value = {"models": [{"name": MODEL, "digest": MODEL_DIGEST}]}
        client.session.post.return_value = Mock(status_code=200)
        client.session.post.return_value.json.return_value = result or {
            "done": True, "done_reason": "stop", "response": '{"ok": true}'}
        return client

    def test_pinned_local_inference_without_proxy_cloud_or_redirects(self):
        self.assertFalse(LocalModel().session.trust_env)
        client = self.client()
        self.assertEqual(client.generate_json("Return an object", {}), {"ok": True})
        call = client.session.post.call_args
        self.assertEqual(call.args[0], ENDPOINT + "/api/generate")
        self.assertFalse(call.kwargs["allow_redirects"])
        self.assertFalse(call.kwargs["json"]["think"])
        self.assertEqual(call.kwargs["json"]["options"]["num_gpu"], 0)

    def test_wrong_model_stops_before_generation(self):
        client = self.client()
        client.session.get.return_value.json.return_value = {"models": [{"name": MODEL, "digest": "changed"}]}
        with self.assertRaises(LocalModelError):
            client.generate_json("", {})
        client.session.post.assert_not_called()

    def test_truncation_and_non_objects_fail_closed(self):
        for response in [{"done": True, "done_reason": "length", "response": "{}"},
                         {"done": True, "done_reason": "stop", "response": "[]"}]:
            with self.assertRaises(LocalModelError):
                self.client(response).generate_json("", {})

    def test_oversize_evidence_never_silently_truncates(self):
        client = self.client()
        with self.assertRaises(LocalModelError):
            client.generate_json("", {"text": "x" * 15000})
        client.session.get.assert_not_called()

    def test_index_search_is_bounded_deduplicated_and_expires(self):
        index = NewsIndex()
        index.add({"url": "https://example.org/a", "title": "Library", "text": "Seed library opens"})
        index.add({"url": "https://example.org/a", "title": "Library", "text": "Seed library expanded"})
        index.add({"url": "https://example.org/old", "text": "Seed library"}, time.time() - 8 * 86400)
        rows = index.search('seed" OR library:*')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text"], "Seed library expanded")
        self.assertEqual(index.search("???"), [])
        index.close()
