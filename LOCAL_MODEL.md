# Local model development prototype

This is custom Dayline software using **Qwen3 4B Q4_K_M**, an existing Apache-2.0 open-weight model. It is not a newly trained foundation model and no training or fine-tuning is claimed.

`local_model.py` runs inference through Ollama on 127.0.0.1 only. It verifies the exact model digest, disables environment proxies, rejects redirects/truncated responses, limits context/output, and has no paid fallback. The manual GitHub development test disables Ollama Cloud and receives no Blogger, Gemini or Tavily credentials. It tests one fictional article with at most one revision and saves timing, word count and generated text for review. Structural validation alone does not prove factual reliability.

`NewsIndex` offers SQLite full-text search over public pages already read by the application, with URL deduplication and seven-day expiry. This can replace Tavily for searching a collected corpus; it cannot search the whole internet or retrieve missing facts from model weights. A production collector still needs permitted RSS feeds, publisher pages and primary-source links, with rate limits and access restrictions respected. Existing cloud production is unchanged by this prototype.

Run tests: `python -m unittest discover -p 'test_*.py' -v`.
For a local benchmark, install Ollama, disable cloud features (`OLLAMA_NO_CLOUD=1`), run `ollama serve`, pull `qwen3:4b`, then run `python local_model_benchmark.py`. Do not publish the fictional fixture.

GitHub: Actions → Local model development test → Run workflow. This is an occasional software evaluation, not a scheduled inference host. Standard public Linux runners have four CPUs and 16 GB RAM, so generation must be measured rather than assumed fast. GitHub's product terms restrict general serverless/application hosting and unrelated workloads. A production model needs a suitable always-on computer or hosting plan; free inference weights do not provide free, unlimited hosting. No billing service has been enabled.

Sources: [Qwen model and license](https://ollama.com/library/qwen3:4b), [Ollama local-only mode](https://docs.ollama.com/faq), [runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [Actions terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features).
