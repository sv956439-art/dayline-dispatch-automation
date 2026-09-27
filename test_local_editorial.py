import copy
import unittest
from unittest.mock import Mock
from local_editorial import article_claims, deterministic_issues, review_claims, validate_review
from local_model import LocalModelError

PAGE = {"url": "https://example.org/test", "text": "The museum plans to reopen on 12 October. Admission is free."}
CLAIM = {"id": "one", "text": "Admission is free.", "sources": [PAGE["url"]]}
CHECK = {"id": "one", "verdict": "supported", "reason": "Explicit", "excerpts": [
    {"url": PAGE["url"], "quote": "Admission is free."}]}


class EditorialTests(unittest.TestCase):
    def test_requires_complete_and_unique_claim_coverage(self):
        for checks in [[], [CHECK, CHECK], [{**CHECK, "id": "other"}]]:
            with self.assertRaises(LocalModelError):
                validate_review({"checks": checks}, [CLAIM], [PAGE])

    def test_fabricated_empty_or_uncited_quotes_cannot_pass(self):
        for excerpts in [[], [{"url": PAGE["url"], "quote": "Admission costs money."}],
                         [{"url": "https://example.org/other", "quote": "Admission is free."}]]:
            with self.assertRaises(LocalModelError):
                validate_review({"checks": [{**CHECK, "excerpts": excerpts}]}, [CLAIM], [PAGE])

    def test_accepts_exact_evidence_with_normalized_whitespace(self):
        check = copy.deepcopy(CHECK)
        check["excerpts"][0]["quote"] = "Admission  is\nfree."
        self.assertEqual(len(validate_review({"checks": [check]}, [CLAIM], [PAGE])), 1)

    def test_unknown_verdict_or_malformed_response_fails_closed(self):
        for check in [{**CHECK, "verdict": "probably"}, {**CHECK, "excerpts": "yes"}, None]:
            with self.assertRaises(LocalModelError):
                validate_review({"checks": [check]}, [CLAIM], [PAGE])

    def test_title_headings_and_all_sentences_covered(self):
        article = {"title": "Museum plan", "blocks": [{"heading": "Admission", "text":
            "Admission is free. The museum plans to reopen on 12 October.", "sources": [PAGE["url"]]}]}
        claims = article_claims(article)
        self.assertEqual([c["id"] for c in claims], ["title", "b0.heading", "b0.s0", "b0.s1"])

    def test_numeric_and_repetition_checks_do_not_depend_on_model_approval(self):
        text = "The museum plans to reopen its large exhibition hall on 12 October."
        claims = [{**CLAIM, "id": "b0.s0", "text": text}, {**CLAIM, "id": "b1.s0", "text": text},
                  {**CLAIM, "id": "b2.s0", "text": "The museum opens on 19 October."}]
        issues = deterministic_issues(claims, [PAGE])
        self.assertEqual({i["id"] for i in issues}, {"b1.s0", "b2.s0"})

    def test_unsupported_or_uncertain_verdict_blocks_and_audit_is_bound(self):
        for verdict in ["unsupported", "uncertain", "contradicted", "supported"]:
            model = Mock(metrics={})
            model.generate_json.return_value = {"checks": [{**CHECK, "verdict": verdict}]}
            report = review_claims(model, [CLAIM], [PAGE])
            self.assertEqual(report["passed"], verdict == "supported")
            self.assertEqual(len(report["claimsHash"]), 64)
            self.assertEqual(len(report["evidenceHash"]), 64)

    def test_overlarge_review_rejected_before_inference(self):
        model = Mock()
        with self.assertRaises(LocalModelError):
            review_claims(model, [{**CLAIM, "id": str(i)} for i in range(49)], [PAGE])
        model.generate_json.assert_not_called()
