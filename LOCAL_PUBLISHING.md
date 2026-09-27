# Local-only automatic publishing

Owner requested local-only operation on 28 September 2026. Cloud generation is
disabled in the scheduled workflow; GitHub continues discovering and retaining
stories. No Gemini or Tavily credentials are passed to that workflow. No local
production host has been provisioned. This PC must not run the worker.

`local_worker.py` enables automatic publication of ordinary articles that pass
300–800 body words, source contribution limits, full sentence/title review and
final editorial classification. Unsupported or short articles remain pending;
specific high-impact publications still require the existing specific approval.
The previously failed benchmark remains a known limitation, not a bypass switch.
The writer and reviewer use the same pinned Qwen3 4B model and can share errors.
No claim of independent verification or guaranteed five-minute output is made.

Research uses accessible source links and related stories already discovered in
the queue. It is not whole-web search. Complete leading sentences are explicitly
marked as selected excerpts to fit the model context. Missing evidence remains
pending. Optional licensed Commons photos have a text-only fallback.

## Host setup once a suitable host is available

1. Use a private workspace on an authorized persistent machine. Install Python,
   requirements.txt and official Ollama. Bind Ollama to `127.0.0.1:11434`, with
   `OLLAMA_NO_CLOUD=1`. Pull `qwen3:4b`; the client verifies the pinned weight digest.
2. Stop the old cloud publisher/discovery workflow at final cutover. Download the
   latest authoritative state.json from main after its final run. Keep the local
   copy on persistent storage; never substitute the stale development queue.
3. With owner authorization for the chosen host, provide BLOGGER_CLIENT_ID,
   BLOGGER_CLIENT_SECRET and BLOGGER_REFRESH_TOKEN through private environment
   secrets. Do not expose the model server or secrets in a public app or repository.
4. Run `python local_worker.py --state /private/persistent/state.json --once` for
   the first observed batch. Verify a real source-backed public article and image.
5. Run without `--once` under the host's process supervisor. It enables local-only
   generation and automatic ordinary publication. It checks every five minutes
   when idle, never overlaps batches, and persists queue progress after each story.
   One article may take longer than five minutes. Back up the private queue.

Only a host with ongoing permitted free compute meets the PC-off requirement.
Lightning AI is a no-card candidate for limited sessions, but its Free plan needs
a restart every four hours. No account, credit-card entry, billing, hosting or
credential transfer has been performed. Do not automate around provider limits.

Validation: mocked tests cover cloud-call exclusion, preflight, publication
eligibility, rejected factual review, observed URLs and queue locking. This is
not a successful live local-model publication test. That test requires a host.
