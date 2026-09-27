"""Hand-labelled fictional challenge set, distinct from the writing fixture.

Expected answers are never sent to the model. This small regression set is not a
statistical accuracy estimate or an independent evaluation of the foundation model.
"""
from local_editorial import review_claims

EVIDENCE = [
    {"url": "https://example.org/fictional-museum", "text":
     "The fictional Bellmere museum plans to reopen on 12 November 2026, subject to a final inspection. "
     "Entry to the permanent collection will be free. Special exhibitions may charge separately. "
     "The reopening plan does not add staff posts."},
    {"url": "https://example.org/fictional-bus", "text":
     "The fictional Eastford council voted to fund a six-month electric bus trial. "
     "The trial has not started. Survey participants need not provide their names. "
     "The survey service stores device identifiers. No fall in congestion has been measured."}]

CASES = [
    ("museum_plan", "The Bellmere museum plans to reopen on 12 November 2026, subject to a final inspection.", 0, True),
    ("museum_prices", "Entry to the permanent collection will be free, while special exhibitions may charge separately.", 0, True),
    ("bus_funding", "Eastford council voted to fund a six-month electric bus trial.", 1, True),
    ("survey_names", "Survey participants need not provide their names.", 1, True),
    ("bus_status", "The electric bus trial has not started.", 1, True),
    ("certainty", "The Bellmere museum will definitely reopen on 12 November 2026.", 0, False),
    ("overgeneralization", "All exhibitions at the museum will be free.", 0, False),
    ("invented_jobs", "The museum reopening will create paid staff posts.", 0, False),
    ("privacy_inference", "The council's survey is anonymous and collects no identifiers.", 1, False),
    ("invented_outcome", "The electric bus trial has already reduced congestion.", 1, False),
]


def evaluate(model):
    claims = [{"id": ident, "text": text, "sources": [EVIDENCE[source]["url"]]}
              for ident, text, source, expected in CASES]
    review = review_claims(model, claims, EVIDENCE)
    checks = {c["id"]: c for c in review["checks"]}
    deterministic = {issue["id"] for issue in review["issues"]}
    results = []
    for ident, text, source, expected in CASES:
        accepted = checks[ident]["verdict"] == "supported" and ident not in deterministic
        results.append({"id": ident, "claim": text, "expectedAccept": expected,
                        "accepted": accepted, "correct": accepted == expected,
                        "review": checks[ident]})
    return {"passed": all(r["correct"] for r in results), "cases": results,
            "falseAccepts": sum(not r["expectedAccept"] and r["accepted"] for r in results),
            "falseRejects": sum(r["expectedAccept"] and not r["accepted"] for r in results),
            "attempts": review["attempts"]}
