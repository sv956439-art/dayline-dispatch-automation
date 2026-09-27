# Dayline Dispatch cloud publishing

For https://daylinedispatch.blogspot.com/ (Blogger ID `8702417009340647398`).

**Blogger and Gemini connections are verified; automatic public posting is awaiting a successful staged article test.** Discovery and draft research are enabled. The owner selected free-tier only: no paid APIs, billing upgrades or paid fallback. Excess stories remain queued.

## Operation

GitHub-hosted Linux checks accessible BBC homepage and rotating sections every five minutes, subject to scheduling delays. It retains discovered stories, follows accessible primary-source links, writes original summaries with useful context, reviews factual claims and selects licensed Commons photographs. There is no fixed five-source requirement. Length follows the evidence: a single-source summary is normally 150–180 words; richer evidence can support longer articles up to 1,200 words. Do not pad a short story or closely paraphrase a complete BBC article. It creates drafts first; sensitive material stays in drafts for approval. Ordinary articles can be published after the staged test succeeds. Draft bodies and credentials are never committed publicly.

The fixed model is `gemini-3.5-flash-lite`, using standard text generation without paid search, Maps, image-generation or other tools. Google lists a free text tier for this model. Older 2.5 models have free search but access is restricted for new projects, so this workflow does not depend on them. Source discovery is link-based; insufficient evidence stays pending. No AI-generated URL is trusted without reading it. Extra verified source URLs may be added to a story's `researchUrls` list. All paragraphs need citations and each source contributes at most 200 words. Automated editorial checks are fallible; review the first draft and sample later posts.

A quota response stops generation for that run and sets a one-hour cooldown. Discovery continues during cooldown; there is no paid fallback and no discarded backlog. The configured batch size limits runtime, not total daily posts. Free quotas may be much lower than BBC output, so a growing queue is possible. Full coverage and realtime publication are not guaranteed.

When BBC links are insufficient, the workflow searches up to two related topics using Wikipedia's public API and reads external reference URLs. Wikipedia text is never article evidence. The model selects candidate primary sources from observed links; each selected page must be fetched and reviewed. BBC, Wikipedia and archive mirrors are excluded as supplemental sources. A link appearing in a reference list does not itself establish that it is authoritative.

Use the manual workflow's `check_connections` checkbox to verify Blogger access and one tiny Gemini response without creating posts. Service connectivity passing does not establish article quality or publication success.

## One-time setup

1. In [Google AI Studio](https://aistudio.google.com/), create/select a **Free tier project with Cloud Billing disabled**. Do not start a paid trial, link a billing account or upgrade. Create an API key and enter it directly into GitHub **Settings → Secrets and variables → Actions → New repository secret**, named `GEMINI_API_KEY`. Do not paste keys in chat, code or issues. Google states that free-tier inputs and outputs may be used to improve its products: send only public reporting and generated copy, never private personal material.
2. Verify the key belongs to that unbilled project before setting `FREE_TIER_CONFIRMED=true`. This is an operator confirmation, not a billing API check. The code cannot determine billing tier from an API key. Keep billing disabled permanently; if the model becomes unavailable, the job queues work rather than choosing a paid replacement.
3. In [Google Cloud Console](https://console.cloud.google.com/), enable Blogger API v3 in an unbilled project. Configure Google Auth consent and an OAuth client. Request only `https://www.googleapis.com/auth/blogger`, with offline access for a refresh token. The owner must approve access. This scope grants Blogger management access; application code writes only the fixed blog above. Use your own OAuth client. Testing-mode refresh tokens normally expire after seven days for this scope; complete appropriate production configuration for unattended operation.
4. Save repository secrets `BLOGGER_CLIENT_ID`, `BLOGGER_CLIENT_SECRET`, `BLOGGER_REFRESH_TOKEN`. Never commit client JSON or token files. Browser login alone does not authorize a cloud runner.
5. Set `CLOUD_ENABLED=true`, `AI_ENABLED=false`, `AUTO_PUBLISH=false`, then manually run the workflow to verify discovery. Next, with all credentials and the free-tier confirmation in place, set `AI_ENABLED=true` and run once with `AUTO_PUBLISH=false`. Inspect the Blogger draft, citations, photo, dates and formatting.
6. After the staged draft and publication checks pass, set `AUTO_PUBLISH=true`. Disable the desktop heartbeat at cutover to avoid competing publishers. Do not assume cloud posting works with the PC off until this test succeeds.

## Variables and secrets

| Variable | Initial value | Purpose |
|---|---|---|
| `CLOUD_ENABLED` | false / unset | Runs discovery and publishing job |
| `AI_ENABLED` | false | Allows AI research and Blogger drafts |
| `FREE_TIER_CONFIRMED` | false | Owner verified Free tier and billing disabled |
| `AUTO_PUBLISH` | false | Publishes verified ordinary articles |
| `MAX_STORIES_PER_RUN` | 1 | Runtime work chunk; retains excess stories |

Secrets: `GEMINI_API_KEY`, `BLOGGER_CLIENT_ID`, `BLOGGER_CLIENT_SECRET`, `BLOGGER_REFRESH_TOKEN`. These go only to their designated API endpoints. Public sources are fetched without credentials and robots restrictions are respected. Duplicate markers and existing citation URLs reconcile interrupted writes before inserting another post.

## Validation

Run `python -m pip install -r requirements.txt` then `python -m unittest discover -p 'test_*.py' -v`. Tests mock API calls and cover free-tier gating, quota retention, duplicate recovery and publication controls. Live Gemini/Blogger integration still needs credentials and a staged test. Existing short articles are not automatically expanded. Photo metadata is checked automatically and needs visual inspection during setup.

Standard runners are free for public repositories. GitHub schedules can be delayed and disabled after 60 days of repository inactivity. Check failures regularly. No payment service is enabled by this repository.

Sources: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini billing tiers](https://ai.google.dev/gemini-api/docs/billing), [model availability](https://ai.google.dev/gemini-api/docs/deprecations), [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Blogger insertion](https://developers.google.com/blogger/docs/3.0/reference/posts/insert), [Google offline authorization](https://developers.google.com/identity/protocols/oauth2/web-server).

Photographs are optional under the owner's latest instruction. Use a relevant Commons photograph only when its reuse license and metadata pass verification. If no suitable licensed photo is accessible, publish the verified text with citations instead; never copy an unlicensed web photo. The free-tier quota cooldown still applies.
