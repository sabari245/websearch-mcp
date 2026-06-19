# morph-websearch-mcp

MCP server that brings web search, page fetching, and AI-powered research to any MCP-compatible client. Backed by [crawl4ai](https://crawl4ai.com) for crawling and [morphllm](https://morphllm.com) for context compaction and agent reasoning.

## Why

LLMs drown in boilerplate. Every webpage you feed them includes nav bars, cookie banners, tracking hashes, and ads. morph-websearch-mcp solves this by compacting every page through [morph compact](https://docs.morphllm.com/sdk/components/compact) — a 33,000 tok/s engine that drops irrelevant lines without rewriting — before the content ever reaches your LLM.

## Tools

| Tool | What it does |
|------|--------------|
| `websearch` | Searches DuckDuckGo, fetches all result pages, compacts each, returns clean content |
| `webfetch` | Fetches a single URL and returns compacted markdown |
| `webextract` | AI agent that iteratively searches and fetches to answer a query using [morph-dsv4flash](https://docs.morphllm.com/sdk/components/fast-models) |

## Install

```bash
pip install morph-websearch-mcp
# or
uv add morph-websearch-mcp
```

## Setup

Get an API key from [morphllm](https://morphllm.com/dashboard/api-keys), then:

```bash
export MORPH_API_KEY="sk-..."
```

## MCP Client Config

```json
{
  "mcpServers": {
    "websearch": {
      "command": "websearch-mcp",
      "env": { "MORPH_API_KEY": "sk-..." }
    }
  }
}
```

## How it works

```
query → DuckDuckGo HTML → crawl4ai (parallel fetch) → morph compact → clean results
                                                                          ↓
                                                              morph-dsv4flash agent loop
                                                        (only for webextract — searches
                                                         and fetches autonomously)
```

Every page fetched by `websearch` and `webfetch` passes through morph compact before being returned. The `webextract` agent uses morph-dsv4flash (DeepSeek V4 Flash, ~150 tok/s) in an OpenAI-compatible tool-calling loop to find answers across multiple search/fetch cycles.

## Services used

| Service | Purpose | Docs |
|---------|---------|------|
| [crawl4ai](https://crawl4ai.com) | Headless web crawling, HTML-to-markdown | [docs.crawl4ai.com](https://docs.crawl4ai.com) |
| [morph compact](https://morphllm.com) | Context compression at 33k tok/s, 50-70% reduction | [docs.morphllm.com/sdk/components/compact](https://docs.morphllm.com/sdk/components/compact) |
| [morph fast models](https://morphllm.com) | DeepSeek V4 Flash for agent reasoning | [docs.morphllm.com/sdk/components/fast-models](https://docs.morphllm.com/sdk/components/fast-models) |

## License

MIT
