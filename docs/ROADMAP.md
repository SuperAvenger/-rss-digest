# Roadmap

## Now

- Rename the repository to `rss-digest` so CLI and URL usage are less error-prone.
- Add fixture-based feed tests, delivery result checks, and structured run summaries.
- Stop retaining article-level API logs by default; enable bounded diagnostics only when needed.

## Next

- Extract providers, ranking, summarization, and destinations into reusable interfaces.
- Share the generic pipeline with `ai-news-daily` while keeping separate product presets.
- Add idempotent delivery and a small local state store for cross-run deduplication.

## Later

- Expose read-only MCP tools for listing feeds, searching collected items, and previewing digests.
- Keep send/publish actions separate with explicit open-world and destructive annotations.
