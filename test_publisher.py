import unittest
from unittest.mock import patch, Mock
import publisher as p


def article():
    return {"title": "A factual feature", "labels": ["Science"], "blocks": [
        {"heading": "Context", "text": "word " * 160, "sources": [f"https://example.org/{i}"]}
        for i in range(5)]}


class PublishingTests(unittest.TestCase):
    def test_web_search_reserves_budget_and_uses_basic_url_discovery_only(self):
        state = {}
        response = Mock(status_code=200, ok=True, is_redirect=False)
        response.json.return_value = {"results": [
            {"url": "https://www.bbc.com/news/articles/real", "title": "Real", "content": "Never use snippet as evidence"},
            {"url": "http://unsafe.example", "title": "Ignored"}]}
        with patch.dict(p.os.environ, {"TAVILY_API_KEY": "fake-search-key", "TAVILY_FREE_TIER_CONFIRMED": "true"}), patch.object(p, "save_state") as save, patch.object(p.SESSION, "post", return_value=response) as post:
            rows = p.web_candidates(["public news", "public news"], state)
        self.assertEqual(rows, [{"url": "https://www.bbc.com/news/articles/real", "title": "Real"}])
        self.assertEqual(state["searchBudget"]["monthlyRequests"], 1)
        self.assertGreaterEqual(save.call_count, 2)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], "https://api.tavily.com/search")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["search_depth"], "basic")
        self.assertFalse(payload["auto_parameters"])
        self.assertFalse(payload["include_raw_content"])
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_search_requires_free_confirmation_and_stops_at_budget(self):
        state = {"searchBudget": {"month": p.time.strftime("%Y-%m", p.time.gmtime()),
                 "day": p.time.strftime("%Y-%m-%d", p.time.gmtime()), "monthlyRequests": 900, "dailyRequests": 0}}
        with patch.dict(p.os.environ, {"TAVILY_API_KEY": "fake", "TAVILY_FREE_TIER_CONFIRMED": "false"}), patch.object(p.SESSION, "post") as post:
            self.assertEqual(p.web_candidates(["news"], state), [])
            post.assert_not_called()
        with patch.dict(p.os.environ, {"TAVILY_API_KEY": "fake", "TAVILY_FREE_TIER_CONFIRMED": "true"}), patch.object(p, "save_state"), patch.object(p.SESSION, "post") as post:
            self.assertEqual(p.web_candidates(["news"], state), [])
            post.assert_not_called()

    def test_search_quota_keeps_sources_and_never_tries_paid_fallback(self):
        state = {}
        with patch.dict(p.os.environ, {"TAVILY_API_KEY": "fake", "TAVILY_FREE_TIER_CONFIRMED": "true"}), patch.object(p, "save_state"), patch.object(p.SESSION, "post", return_value=Mock(status_code=432)) as post:
            self.assertEqual(p.web_candidates(["one", "two"], state), [])
        self.assertEqual(post.call_count, 1)
        self.assertGreater(state["searchBudget"]["retryAfter"], p.time.time())

    def test_blocked_candidates_are_replaced_until_publication_target(self):
        state = {"stories": [{"sourceUrl": f"https://www.bbc.com/news/articles/{i}", "status": "pending"} for i in range(4)]}
        draft = article()
        draft.update(word_count=800, requires_approval=False, image=None)
        post = {"id": "new", "status": "LIVE", "url": "https://daylinedispatch.blogspot.com/news.html"}
        with patch.dict(p.os.environ, {"AI_ENABLED": "true", "MAX_STORIES_PER_RUN": "1", "GITHUB_STEP_SUMMARY": ""}), patch.object(p.Path, "read_text", return_value=p.json.dumps(state)), patch.object(p, "discover", return_value=[]), patch.object(p, "blogger_token", return_value="fake"), patch.object(p, "existing_posts", return_value=[]), patch.object(p, "save_state"), patch.object(p, "generate", side_effect=[p.Blocked("source unavailable"), p.Blocked("more research"), draft]) as generate, patch.object(p, "publish_article", return_value=post), patch.object(p, "verify_public"):
            p.run()
        self.assertEqual(generate.call_count, 3)
        self.assertEqual(p.CURRENT_STATE["lastRunStats"]["published"], 1)
        self.assertEqual(p.CURRENT_STATE["lastRunStats"]["neverAttempted"], 1)
        self.assertEqual(p.CURRENT_STATE["stories"][0]["status"], "pending")

    def test_article_candidates_precede_legacy_videos_without_deleting_them(self):
        video = {"sourceUrl": "https://www.bbc.com/news/videos/old", "status": "pending"}
        text = {"sourceUrl": "https://www.bbc.com/news/articles/new", "status": "pending"}
        state = {"stories": [video, text]}
        self.assertEqual(p.select_pending(state, 1), [text])
        self.assertIn(video, state["stories"])

    def test_text_only_article_renders_and_verifies_without_thumbnail(self):
        draft = article()
        draft["image"] = None
        output = p.render_article(draft, "https://www.bbc.com/news/articles/source")
        self.assertNotIn("<img", output)
        self.assertIn("https://example.org/0", output)
        post = {"title": draft["title"], "content": output, "url": "https://daylinedispatch.blogspot.com/post.html"}
        with patch.object(p, "public_get", return_value=Mock(text="<h1>" + draft["title"] + "</h1>" + output)) as get:
            p.verify_public(post)
        self.assertEqual(get.call_count, 1)

    def test_short_single_source_summary_is_withheld(self):
        url = "https://www.bbc.com/news/articles/source"
        draft = {"title": "An original summary", "labels": ["Culture"], "blocks": [
            {"text": "word " * 170, "sources": [url]}]}
        with self.assertRaisesRegex(p.Blocked, "300–800"):
            p.validate_article(draft, {url})
        draft["blocks"][0]["text"] = "word " * 400
        with self.assertRaisesRegex(p.Blocked, "200-word limit"):
            p.validate_article(draft, {url})

    def test_two_source_context_does_not_require_five_sources(self):
        draft = article()
        draft["blocks"] = draft["blocks"][:2]
        for block in draft["blocks"]:
            block["text"] = "word " * 200
        urls = {u for block in draft["blocks"] for u in block["sources"]}
        self.assertEqual(p.validate_article(draft, urls), 400)

    def test_length_boundaries_exclude_headings(self):
        for total, accepted in [(299, False), (300, True), (800, True), (801, False)]:
            draft = article()
            draft["blocks"] = [{"heading": "Heading " * 50, "text": "word " * min(200, total - start),
                                "sources": [f"https://example.org/{start}"]}
                               for start in range(0, total, 200)]
            urls = {u for block in draft["blocks"] for u in block["sources"]}
            if accepted:
                self.assertEqual(p.validate_article(draft, urls), total)
            else:
                with self.assertRaisesRegex(p.Blocked, "300–800"):
                    p.validate_article(draft, urls)

    def test_commons_thumbnail_host_is_accepted_but_lookalike_is_rejected(self):
        info = {"thumburl": "https://thumb.wikimedia.org/photo.jpg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Real.jpg",
                "extmetadata": {"LicenseShortName": {"value": "CC BY 2.0"}}}
        response = {"query": {"pages": {"1": {"imageinfo": [info]}}}}
        with patch.object(p, "api_json", return_value=response), patch.object(p, "public_get", return_value=Mock(headers={"Content-Type": "image/jpeg"})) as get:
            self.assertEqual(p.commons_image("File:Real.jpg")["url"], info["thumburl"])
            get.assert_called_once()
            get.reset_mock()
            info["thumburl"] = "https://thumb.wikimedia.org.attacker.example/photo.jpg"
            with self.assertRaisesRegex(p.Blocked, "Unexpected image host"):
                p.commons_image("File:Real.jpg")
            get.assert_not_called()

    def test_photo_selection_cannot_use_invented_file(self):
        with patch.object(p, "api_json", return_value={"query": {"search": [{"title": "File:Real.jpg"}]}}), patch.object(p, "response_json", return_value={"photo_title": "File:Invented.jpg"}), patch.object(p, "commons_image") as photo:
            with self.assertRaises(p.Blocked):
                p.find_photo("mountain photograph", {"text": "source"})
            photo.assert_not_called()

    def test_research_reads_observed_news_but_rejects_invented_and_wiki_urls(self):
        primary = "https://www.nasa.gov/research/"
        invented = "https://www.nasa.gov/invented/"
        bbc = "https://www.bbc.com/news/articles/secondary"
        wiki = "https://en.wikipedia.org/wiki/Research"
        evidence = [{"url": "https://www.bbc.com/news/articles/source"}]
        with patch.object(p, "article_text", return_value={"url": primary}) as read:
            p.read_selected_sources([primary, invented, bbc, wiki], {primary, bbc, wiki}, evidence)
        self.assertEqual([c.args[0] for c in read.call_args_list], [primary, bbc])
        self.assertEqual(len(evidence), 2)

    def test_reference_search_is_bounded_anonymous_and_only_returns_observed_links(self):
        responses = [
            {"query": {"search": [{"pageid": 1}, {"pageid": 2}]}},
            {"parse": {"externallinks": ["https://www.nasa.gov/science/", "http://bad.example/", "https://en.wikipedia.org/wiki/X"]}},
            {"parse": {"externallinks": ["https://www.nasa.gov/science/", "https://www.bbc.com/news/article/x"]}},
            {"query": {"search": [{"pageid": 1}]}}]
        with patch.object(p, "api_json", side_effect=responses) as api:
            links = p.reference_candidates(["space", "research", "ignored"])
        self.assertEqual(links, ["https://www.nasa.gov/science/", "https://www.bbc.com/news/article/x"])
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

    def test_reviewed_draft_uses_admin_view_and_no_duplicate_insert(self):
        url = "https://www.bbc.com/news/articles/abc"
        post = {"id": "123", "title": "News", "content": f"<!-- dayline-source:{p.fingerprint(url)} -->", "labels": ["News"]}
        story = {"sourceUrl": url, "requiresApproval": False, "wordCount": 480, "reviewedContentHash": p.reviewed_digest(post)}
        with patch.object(p, "api_json", side_effect=[post, {**post, "status": "LIVE"}]) as api:
            result = p.publish_reviewed_draft(story, post, "fake")
            self.assertEqual(result["status"], "LIVE")
            self.assertEqual(api.call_args_list[0].kwargs["params"], {"view": "ADMIN"})
            self.assertTrue(api.call_args_list[1].args[1].endswith("/123/publish"))
        with patch.object(p, "api_json", return_value={**post, "content": "Changed"}) as api:
            with self.assertRaises(p.Blocked):
                p.publish_reviewed_draft(story, post, "fake")
            self.assertEqual(api.call_count, 1)
        story["wordCount"] = 170
        with patch.object(p, "api_json") as api:
            with self.assertRaisesRegex(p.Blocked, "300–800"):
                p.publish_reviewed_draft(story, post, "fake")
            api.assert_not_called()
        story["requiresApproval"] = True
        with patch.object(p, "api_json") as api:
            with self.assertRaises(p.Blocked):
                p.publish_reviewed_draft(story, post, "fake")
            api.assert_not_called()

    def test_overlong_draft_gets_one_bounded_revision(self):
        source = "https://www.bbc.com/news/articles/abc"
        urls = [source, "https://example.org/a", "https://example.org/b"]
        evidence = [{"url": url} for url in urls]
        draft = {"title": "News", "labels": ["News"], "blocks": [{"text": "word " * (220 if i == 0 else 160), "sources": [url]} for i, url in enumerate(urls)]}
        revised = {"title": "News", "labels": ["News"], "blocks": [{"text": "word " * 160, "sources": [url]} for url in urls]}
        with patch.object(p, "response_json", return_value=revised) as model:
            result = p.validate_or_revise(draft, evidence, None)
            self.assertEqual(result["word_count"], 480)
            self.assertEqual(model.call_count, 1)
            feedback = model.call_args.args[1]
            self.assertEqual(feedback["measured_body_words"], 540)
            self.assertEqual(feedback["measured_words_per_source"][source], 220)
            self.assertIn("220", feedback["validation_error"])
        with patch.object(p, "response_json", return_value=draft) as model:
            with self.assertRaises(p.Blocked):
                p.validate_or_revise(draft, evidence, None)
            self.assertEqual(model.call_count, 1)

    def test_supported_outlet_urls_reject_navigation_and_lookalikes(self):
        self.assertEqual(p.news_provider("https://www.theguardian.com/science/2026/sep/27/new-discovery"), "The Guardian")
        self.assertEqual(p.news_provider("https://www.abc.net.au/news/2026-09-27/story/12345"), "ABC News Australia")
        self.assertEqual(p.news_provider("https://www.bbc.com/news/articles/abc123"), "BBC")
        for url in ["https://www.theguardian.com/world", "https://www.theguardian.com/world/live/2026/sep/27/report", "https://www.abc.net.au/news", "https://www.bbc.com.attacker.example/news/articles/abc", "http://www.bbc.com/news/articles/abc"]:
            self.assertIsNone(p.news_provider(url))

    def test_multi_outlet_discovery_is_deduplicated(self):
        guardian = "https://www.theguardian.com/science/2026/sep/27/discovery"
        abc = "https://www.abc.net.au/news/2026-09-27/science/12345"
        bbc = "https://www.bbc.com/news/articles/abc123"
        page = Mock(text=''.join(f'<a href="{u}">Title</a>' for u in [bbc, guardian, abc, guardian+'?tracking=1']))
        state = {"stories": []}
        with patch.object(p, "public_get", return_value=page), patch.object(p, "save_state"):
            self.assertEqual(p.discover(state), [])
            p.discover(state)
        self.assertEqual({s["sourceUrl"] for s in state["stories"]}, {bbc, guardian, abc})
        self.assertEqual(len(state["stories"]), 3)

    def test_large_bbc_backlog_does_not_starve_other_outlets(self):
        stories = [{"sourceUrl": f"https://www.bbc.com/news/articles/a{i}", "status": "pending"} for i in range(100)]
        stories += [{"sourceUrl": "https://www.theguardian.com/science/2026/sep/27/story", "status": "pending"},
                    {"sourceUrl": "https://www.abc.net.au/news/2026-09-27/story/12345", "status": "pending"}]
        state = {"stories": stories}
        self.assertEqual([p.news_provider(s["sourceUrl"]) for s in p.select_pending(state, 3)], ["BBC", "The Guardian", "ABC News Australia"])
        state["provider_index"] = 0
        self.assertEqual(p.news_provider(p.select_pending(state, 1)[0]["sourceUrl"]), "BBC")
        self.assertEqual(p.news_provider(p.select_pending(state, 1)[0]["sourceUrl"]), "The Guardian")
        stories[-1]["retryAfter"] = p.time.time() + 1000
        self.assertNotIn(stories[-1], p.select_pending(state, 10))

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

