# Local model development prototype

This is custom Dayline software using **Qwen3 4B Q4_K_M**, an existing Apache-2.0 open-weight model. It is not a newly trained foundation model and no training or fine-tuning is claimed.

`local_model.py` runs inference through Ollama on 127.0.0.1 only. It verifies the exact model digest, disables environment proxies, rejects redirects/truncated responses, limits context/output, and has no paid fallback. The manual GitHub development test disables Ollama Cloud and receives no Blogger, Gemini or Tavily credentials. It tests labelled factual challenges and one fictional article, with at most one structural revision and one factual repair, and saves timing, word count and generated text for review. Structural validation alone does not prove factual reliability.

`NewsIndex` offers SQLite full-text search over public pages already read by the application, with URL deduplication and seven-day expiry. This can replace Tavily for searching a collected corpus; it cannot search the whole internet or retrieve missing facts from model weights. A production collector still needs permitted RSS feeds, publisher pages and primary-source links, with rate limits and access restrictions respected. Existing cloud production is unchanged by this prototype.

The bounded collector is included: `python local_research.py collect --state state.json --limit 6` reads up to six known source/context URLs through the existing access checks and stores them in the ignored `local-corpus.sqlite`. Search with `python local_research.py search "your topic"`. Failed fetches are reported; unavailable pages are not bypassed. The corpus is private local data and must not be uploaded as public training data. This is collection/indexing, not model training. The collector can still fetch stale stories from a backlog; verify event dates before writing.

Run tests: `python -m unittest discover -p 'test_*.py' -v`.
For a local benchmark, install Ollama, disable cloud features (`OLLAMA_NO_CLOUD=1`), run `ollama serve`, pull `qwen3:4b`, then run `python local_model_benchmark.py`. Do not publish the fictional fixture.

GitHub: Actions → Local model development test → Run workflow. This is an occasional software evaluation, not a scheduled inference host. Standard public Linux runners have four CPUs and 16 GB RAM, so generation must be measured rather than assumed fast. GitHub's product terms restrict general serverless/application hosting and unrelated workloads. A production model needs a suitable always-on computer or hosting plan; free inference weights do not provide free, unlimited hosting. No billing service has been enabled.

Sources: [Qwen model and license](https://ollama.com/library/qwen3:4b), [Ollama local-only mode](https://docs.ollama.com/faq), [runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [Actions terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features).
# Editorial reliability development

The local prototype now audits the title, headings and each body sentence against
its cited evidence. The review rejects incomplete claim coverage, invented source
excerpts, unknown citations and unsupported numerical values. It also flags near
duplicate sentences. One factual repair is allowed, followed by a fresh review and
the existing 300–800 body-word/source-contribution checks. The audit records hashes
of the article and evidence. An unresolved finding fails the development benchmark.

`editorial_eval.py` contains ten hand-labelled fictional cases spanning a museum
and a transport trial: five supported statements and five seeded errors covering
certainty, price scope, jobs, privacy and claimed outcomes. Expected answers are
not included in model prompts. The benchmark reports false accepts and false
rejects, then generates and reviews a separate fictional seed-library article.
These few examples do not establish real-world accuracy. Same-model review shares
the writer's possible blind spots; exact quote matching establishes provenance,
not logical entailment. Source trust, freshness, contradictions, attribution,
image suitability and editorial judgment still require broader evaluation.

The reviewer selects constrained IDs for numbered source passages. The program
resolves those IDs to exact source text and verifies that the source is cited by
the claim. This avoids model-generated evidence quotations. Unknown IDs and passages
from an uncited source fail closed. Audit artifacts preserve the first draft and
first review even when later evaluation fails.

No test article is published. This development gate is not connected to Blogger.
