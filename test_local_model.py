import json
import time
import unittest
from unittest.mock import Mock
from local_model import LocalModel, LocalModelError, NewsIndex, MODEL, MODEL_DIGEST, ENDPOINT


class LocalModelTests(unittest.TestCase):
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
