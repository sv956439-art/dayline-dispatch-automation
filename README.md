# Dayline Dispatch cloud publishing

Prepared for https://daylinedispatch.blogspot.com/ (Blogger ID `8702417009340647398`).

**Setup is incomplete and publishing is disabled.** No AI request or Blogger write should run until credentials, model, costs and a staged test are configured. The local desktop monitor remains the current publisher until cloud cutover is verified.

## What the workflow does

Runs on GitHub-hosted Linux, independent of the owner's PC. Discovers accessible BBC homepage/section links; retains the queue; researches primary sources; generates 800–1,200-word original articles; independently reviews factual support; verifies Commons photo licenses; creates Blogger drafts; optionally publishes ordinary low-impact articles. Sensitive/high-impact material stays in Blogger drafts. Draft article bodies are not committed to this public repository.

The schedule is every five minutes, offset from the top of the hour. GitHub can delay runs. One article per run is a runtime control, not a daily quota. All pending stories are retained. Source access, API quotas, research quality and image availability can prevent publication; full BBC coverage is not guaranteed. Automated editorial review is fallible and should be sampled by the owner.

## One-time setup

1. Create an [OpenAI API account/project](https://platform.openai.com/). API usage is separate from ChatGPT. Review pricing and set an acceptable project budget before enabling generation. Create a project API key and place it directly in this repository's **Settings → Secrets and variables → Actions → New repository secret** as `OPENAI_API_KEY`. Do not paste it into chat, issues or code. Choose an available Responses API model supporting `web_search`, then set repository variable `AI_MODEL` to its exact ID. No model or paid budget has been selected for you.
2. In [Google Cloud Console](https://console.cloud.google.com/), create/select a project, enable **Blogger API v3**, configure the Google Auth consent screen, and create an OAuth client. Request only the Blogger scope `https://www.googleapis.com/auth/blogger`, using offline access to obtain a refresh token. The owner must approve the Google consent screen. This scope grants Blogger access; application code restricts writes to the blog ID above. Use your own OAuth client, not a shared playground client. Google testing-mode refresh tokens normally expire after seven days for this scope, so complete the appropriate production configuration for unattended use.
3. Save these **repository secrets**: `BLOGGER_CLIENT_ID`, `BLOGGER_CLIENT_SECRET`, `BLOGGER_REFRESH_TOKEN`. Never commit downloaded OAuth client JSON or token files. A normal Blogger browser session cannot replace these credentials.
4. Set repository variables `CLOUD_ENABLED=true`, `AI_ENABLED=false`, `AUTO_PUBLISH=false`. Manually run **Actions → Dayline Dispatch → Run workflow** to test discovery without AI charges or Blogger writes. Check retained errors before proceeding.
5. After authorizing API spending and confirming the chosen model, set `AI_ENABLED=true`, keep `AUTO_PUBLISH=false`, and run once. Review the generated Blogger draft, citations, dates, photograph and formatting. Check the Actions summary and state file. API generation, research tools and review calls can incur separate charges.
6. Once the staged run is verified, set `AUTO_PUBLISH=true` for ordinary articles and hand publishing ownership to GitHub. Disable the desktop news-monitor heartbeat at cutover to prevent two independent publishers working on the same story. Do not turn the PC off expecting cloud posting until this step succeeds.

## Repository variables

| Variable | Initial value | Purpose |
|---|---|---|
| `CLOUD_ENABLED` | unset / false | Enables the entire scheduled job |
| `AI_ENABLED` | false | Enables AI usage and Blogger drafts |
| `AUTO_PUBLISH` | false | Allows verified ordinary articles to be published |
| `AI_MODEL` | unset | Exact model chosen by owner |
| `MAX_STORIES_PER_RUN` | 1 | Work chunk size; does not discard the queue |

Secrets go only to their designated API endpoints. Source retrieval uses unauthenticated HTTPS and honours robots rules; blocked pages remain queued. An interrupted write is reconciled against Blogger before another insertion. Only this workflow should write `state.json` once cloud operation starts.

## Validation and current limits

Run `python -m pip install -r requirements.txt` and `python -m unittest discover -p 'test_*.py' -v`. Tests use fake credentials and mocked API calls; they do not spend money or publish articles. Live AI/Blogger integration is not verified until account setup is complete. Automatic photo selection uses Commons metadata and needs visual review during the staged run. Existing older short articles are not automatically rewritten.

Public repositories get free standard GitHub runners. AI usage can cost money. Public schedules may disable after 60 days without repository activity. This workflow commits queue changes, but the owner should still check failures and inactivity. No paid service is purchased by this code.

Documentation: [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Blogger insertion](https://developers.google.com/blogger/docs/3.0/reference/posts/insert), [Google offline authorization](https://developers.google.com/identity/protocols/oauth2/web-server), [OpenAI web search](https://developers.openai.com/api/docs/guides/tools-web-search).

