# websearch-mcp

MCP server providing web search, web fetch, and AI-powered web extraction — all results compacted for minimal context usage.

## Tools

| Tool | Input | Output |
|------|-------|--------|
| `websearch` | `{query, num_results?}` | `[{title, url, snippet, content}]` |
| `webfetch` | `{url}` | `{url, content}` |
| `webextract` | `{query}` | `{answer, sources: [{title, url}]}` |

All page content is compacted via morph before returning, stripping irrelevant boilerplate.

## Install

```bash
pip install morph-websearch-mcp
# or
uv add morph-websearch-mcp
```

## Setup

Set your morph API key:

```bash
export MORPH_API_KEY="sk-..."
```

## MCP Client Config

```json
{
  "mcpServers": {
    "websearch-mcp": {
      "command": "websearch-mcp",
      "env": {
        "MORPH_API_KEY": "sk-..."
      }
    }
  }
}
```

If installing from source:

```json
{
  "mcpServers": {
    "websearch-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/websearch-mcp", "main.py"],
      "env": {
        "MORPH_API_KEY": "sk-..."
      }
    }
  }
}
```
