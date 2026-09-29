# AI model decision guide

A compact decision guide for choosing among the OpenAI and Anthropic models available in Codex and Claude. The site distinguishes subscription usage limits from public API token pricing and includes a simple per-task API cost estimator.

## Live updates

The GitHub Actions workflow:

1. runs every day at 9:00 AM in `America/New_York`;
2. checks the official OpenAI and Anthropic pricing pages;
3. updates only prices it can identify unambiguously;
4. preserves the last-known-good page if fetching or parsing fails;
5. commits verified changes and deploys the static site to GitHub Pages.

You can also run the workflow manually from the repository's **Actions** tab.

## Local check

```bash
python3 refresh_pricing.py
```

The checker needs ordinary HTTPS access to:

- `developers.openai.com`
- `platform.claude.com`

Pricing displayed on the site is public API pricing. It is not a statement of how Codex or Claude subscription usage is metered.

