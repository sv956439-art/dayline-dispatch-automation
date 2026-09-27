import unittest
from unittest.mock import patch, Mock
import publisher as p


def article():
    return {"title": "A factual feature", "labels": ["Science"], "blocks": [
        {"heading": "Context", "text": "word " * 160, "sources": [f"https://example.org/{i}"]}
        for i in range(5)]}


class PublishingTests(unittest.TestCase):
    def test_supported_single_source_summary_is_accepted(self):
        url = "https://www.bbc.com/news/articles/source"
        draft = {"title": "An original summary", "labels": ["Culture"], "blocks": [
            {"text": "word " * 170, "sources": [url]}]}
        self.assertEqual(p.validate_article(draft, {url}), 170)
        draft["blocks"][0]["text"] = "word " * 201
        with self.assertRaisesRegex(p.Blocked, "200-word limit"):
            p.validate_article(draft, {url})

    def test_two_source_context_does_not_require_five_sources(self):
        draft = article()
        draft["blocks"] = draft["blocks"][:2]
        urls = {u for block in draft["blocks"] for u in block["sources"]}
        self.assertEqual(p.validate_article(draft, urls), 320)

    def test_photo_selection_cannot_use_invented_file(self):
        with patch.object(p, "api_json", return_value={"query": {"search": [{"title": "File:Real.jpg"}]}}), patch.object(p, "response_json", return_value={"photo_title": "File:Invented.jpg"}), patch.object(p, "commons_image") as photo:
            with self.assertRaises(p.Blocked):
                p.find_photo("mountain photograph", {"text": "source"})
            photo.assert_not_called()

    def test_research_never_reads_invented_or_secondary_urls(self):
        primary = "https://www.nasa.gov/research/"
        invented = "https://www.nasa.gov/invented/"
        bbc = "https://www.bbc.com/news/articles/secondary"
        wiki = "https://en.wikipedia.org/wiki/Research"
        evidence = [{"url": "https://www.bbc.com/news/articles/source"}]
        with patch.object(p, "article_text", return_value={"url": primary}) as read:
            p.read_selected_sources([primary, invented, bbc, wiki], {primary, bbc, wiki}, evidence)
        read.assert_called_once_with(primary)
        self.assertEqual(len(evidence), 2)

    def test_reference_search_is_bounded_anonymous_and_only_returns_observed_links(self):
        responses = [
            {"query": {"search": [{"pageid": 1}, {"pageid": 2}]}},
            {"parse": {"externallinks": ["https://www.nasa.gov/science/", "http://bad.example/", "https://en.wikipedia.org/wiki/X"]}},
            {"parse": {"externallinks": ["https://www.nasa.gov/science/", "https://www.bbc.com/news/article/x"]}},
            {"query": {"search": [{"pageid": 1}]}}]
        with patch.object(p, "api_json", side_effect=responses) as api:
            links = p.reference_candidates(["space", "research", "ignored"])
        self.assertEqual(links, ["https://www.nasa.gov/science/"])
        self.assertEqual(api.call_count, 4)
        for call in api.call_args_list:
            self.assertEqual(call.args, ("GET", "https://en.wikipedia.org/w/api.php"))
            self.assertNotIn("token", call.kwargs)

    def test_timeout_does_not_expose_request_or_credential(self):
        with patch.dict(p.os.environ, {"FREE_TIER_CONFIRMED": "true", "GEMINI_API_KEY": "fake"}), patch.object(p.SESSION, "post", side_effect=p.requests.ReadTimeout("secret-request-details")):
            with self.assertRaisesRegex(p.Blocked, "Gemini request timed out") as error:
                p.response_json("test", {})
            self.assertNotIn("secret-request-details", str(error.exception))

    def test_free_tier_must_be_confirmed_before_any_request(self):
        with patch.dict(p.os.environ, {}, clear=True), patch.object(p.SESSION, "post") as api:
            with self.assertRaises(p.Blocked):
                p.response_json("test", {})
            api.assert_not_called()

    def test_free_quota_is_retryable_and_never_falls_back(self):
        with patch.dict(p.os.environ, {"FREE_TIER_CONFIRMED": "true", "GEMINI_API_KEY": "fake"}), patch.object(p.SESSION, "post", return_value=Mock(status_code=429)) as api:
            with self.assertRaises(p.QuotaReached):
                p.response_json("test", {})
            self.assertEqual(api.call_count, 1)
            self.assertNotIn("tools", api.call_args.kwargs["json"])
            self.assertNotIn("fake", api.call_args.args[0])

    def test_gemini_truncated_output_cannot_publish(self):
        response = Mock(status_code=200, ok=True, is_redirect=False)
        response.json.return_value = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]}
        with patch.dict(p.os.environ, {"FREE_TIER_CONFIRMED": "true", "GEMINI_API_KEY": "fake"}), patch.object(p.SESSION, "post", return_value=response):
            with self.assertRaises(p.Blocked):
                p.response_json("test", {})

    def test_quota_stops_batch_without_discarding_pending_stories(self):
        state = {"stories": [{"sourceUrl": "https://www.bbc.com/news/articles/a", "status": "pending"}, {"sourceUrl": "https://www.bbc.com/news/articles/b", "status": "pending"}]}
        with patch.dict(p.os.environ, {"AI_ENABLED": "true", "MAX_STORIES_PER_RUN": "2", "GITHUB_STEP_SUMMARY": ""}), patch.object(p.Path, "read_text", return_value=p.json.dumps(state)), patch.object(p, "discover", return_value=[]), patch.object(p, "blogger_token", return_value="fake"), patch.object(p, "existing_posts", return_value=[]), patch.object(p, "save_state"), patch.object(p, "generate", side_effect=p.QuotaReached("quota")) as generate:
            p.run()
        self.assertEqual(generate.call_count, 1)
        self.assertEqual([s["status"] for s in p.CURRENT_STATE["stories"]], ["pending", "pending"])
        self.assertGreater(p.CURRENT_STATE["aiRetryAfter"], p.time.time())

    def test_tracking_parameters_do_not_create_duplicates(self):
        self.assertEqual(p.fingerprint("https://www.bbc.com/news/articles/abc?tracking=1#top"), p.fingerprint("https://www.bbc.com/news/articles/abc"))

    def test_interrupted_post_reconciles_by_marker(self):
        url = "https://www.bbc.com/news/articles/abc"
        post = {"id": "123", "content": f"<!-- dayline-source:{p.fingerprint(url)} -->"}
        self.assertEqual(p.find_existing([post], url)["id"], "123")

    def test_old_desktop_post_reconciles_by_citation(self):
        url = "https://www.bbc.com/news/articles/abc"
        self.assertIsNotNone(p.find_existing([{"content": f'<a href="{url}">BBC</a>'}], url))

    def test_body_length_and_source_budget(self):
        draft = article()
        urls = {u for b in draft["blocks"] for u in b["sources"]}
        self.assertEqual(p.validate_article(draft, urls), 800)
        draft["blocks"][1]["sources"] = draft["blocks"][0]["sources"]
        with self.assertRaises(p.Blocked):
            p.validate_article(draft, urls)

    def test_uncited_paragraph_is_rejected(self):
        draft = article()
        draft["blocks"][0]["sources"] = []
        with self.assertRaises(p.Blocked):
            p.validate_article(draft, set())

    def test_private_network_sources_are_rejected(self):
        with patch.object(p.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(p.Blocked):
                p.public_url("https://example.org/")

    def test_untrusted_markup_is_escaped(self):
        draft = article()
        draft.update(image_alt='<script>bad</script>', image_caption='Archive photograph', image={"url": "https://upload.wikimedia.org/photo.jpg", "creator": "Person", "page": "https://commons.wikimedia.org/wiki/File:Photo.jpg", "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"})
        draft["blocks"][0]["text"] = '<script>alert("bad")</script>'
        output = p.render_article(draft, "https://www.bbc.com/news/articles/abc")
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)

    def test_high_impact_content_stays_draft(self):
        draft = article()
        draft.update(image={}, requires_approval=True)
        story = {"sourceUrl": "https://www.bbc.com/news/articles/abc"}
        with patch.object(p, "render_article", return_value="body"), patch.object(p, "save_state"), patch.object(p, "api_json", return_value={"id": "9", "status": "DRAFT"}) as api:
            result = p.publish_article(story, draft, "fake", [], True)
        self.assertEqual(result["status"], "DRAFT")
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.kwargs["params"], {"isDraft": "true"})

    def test_retry_does_not_create_second_post(self):
        story = {"sourceUrl": "https://www.bbc.com/news/articles/abc"}
        existing = {"id": "1", "content": '<a href="https://www.bbc.com/news/articles/abc">BBC</a>'}
        with patch.object(p, "api_json") as api:
            self.assertEqual(p.publish_article(story, {}, "fake", [existing], True), existing)
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()

