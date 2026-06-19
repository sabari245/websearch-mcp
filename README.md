# morph-websearch-mcp

Web search, page fetching, and AI-powered research for MCP-compatible clients.

`morph-websearch-mcp` searches DuckDuckGo, fetches pages with [crawl4ai](https://crawl4ai.com), and compacts noisy webpage content with [Morph](https://morphllm.com) before returning it to your MCP client. It is useful when an assistant needs current web context without dumping full pages full of navigation, ads, cookie banners, and tracking boilerplate into the model.

## Features

| Tool | Description |
| --- | --- |
| `websearch` | Searches DuckDuckGo, fetches result pages, compacts each page, and returns clean results with content. |
| `webfetch` | Fetches one URL and returns compacted markdown. |
| `webextract` | Runs an agentic research loop that searches and fetches pages until it can answer the query with sources. |

## Requirements

- Python 3.13 or newer
- A Morph API key from [morphllm.com/dashboard/api-keys](https://morphllm.com/dashboard/api-keys)
- An MCP-compatible client, such as OpenCode, Claude Desktop, Cursor, or another client that can launch local MCP servers

## Install

For most MCP clients, install the server as a standalone command:

```bash
pipx install morph-websearch-mcp
```

If you prefer installing into the current Python environment:

```bash
pip install morph-websearch-mcp
```

For local development from an existing checkout:

```bash
cd morph-websearch-mcp
uv sync
```

## Configure Your API Key

Set `MORPH_API_KEY` in the environment used by your MCP client:

```bash
export MORPH_API_KEY="sk-..."
```

If your client is launched from a desktop app, make sure the desktop app can see that environment variable. When in doubt, put the key directly in the client MCP config instead of relying on your shell startup files.

## OpenCode Setup

Add the server to your OpenCode config:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "websearch": {
      "type": "local",
      "command": ["websearch-mcp"],
      "environment": {
        "MORPH_API_KEY": "{env:MORPH_API_KEY}"
      },
      "enabled": true
    }
  }
}
```

Verify OpenCode can see the server:

```bash
opencode mcp list
```

You should see `websearch` listed as connected.

## Generic MCP Client Setup

For clients that use the common `mcpServers` shape:

```json
{
  "mcpServers": {
    "websearch": {
      "command": "websearch-mcp",
      "env": {
        "MORPH_API_KEY": "sk-..."
      }
    }
  }
}
```

Some clients expect `command` and `args` separately. This server does not need arguments, so only the command is required.

## Local Development Setup

Install dependencies:

```bash
uv sync
```

Run the MCP server from the local checkout:

```bash
uv run websearch-mcp
```

Use this local command in an MCP client while developing:

```json
{
  "mcpServers": {
    "websearch": {
      "command": "uv",
      "args": ["run", "websearch-mcp"],
      "env": {
        "MORPH_API_KEY": "sk-..."
      }
    }
  }
}
```

## Tool Inputs

### `websearch`

Searches the web and returns a list of results with compacted page content.

```json
{
  "query": "latest Python 3.13 release notes",
  "num_results": 5
}
```

### `webfetch`

Fetches one page and returns compacted markdown.

```json
{
  "url": "https://example.com"
}
```

### `webextract`

Runs an agentic research loop and returns an answer with sources.

```json
{
  "query": "What changed in the latest crawl4ai release?"
}
```

## How It Works

```text
query -> DuckDuckGo HTML -> crawl4ai fetch -> Morph compact -> clean MCP result
                                                        |
                                                        v
                                  webextract agent loop with morph-dsv4flash
```

`websearch` and `webfetch` compact fetched page content before returning it. `webextract` uses Morph's OpenAI-compatible chat API with tool calls to search, fetch, and synthesize an answer across several research steps.

## Troubleshooting

If the command is not found, confirm your install location is on `PATH`:

```bash
command -v websearch-mcp
```

If OpenCode cannot connect, check the configured server status:

```bash
opencode mcp list
```

If requests fail or return uncompressed content, confirm the API key is visible to the server process:

```bash
echo "$MORPH_API_KEY"
```

If browser-based crawling fails on a new machine, reinstall the package and make sure crawl4ai's browser dependencies are available in that environment.

## Services Used

| Service | Purpose | Docs |
| --- | --- | --- |
| [crawl4ai](https://crawl4ai.com) | Headless crawling and HTML-to-markdown extraction | [docs.crawl4ai.com](https://docs.crawl4ai.com) |
| [Morph compact](https://morphllm.com) | Context compaction for fetched web content | [docs.morphllm.com/sdk/components/compact](https://docs.morphllm.com/sdk/components/compact) |
| [Morph fast models](https://morphllm.com) | Agent reasoning for `webextract` | [docs.morphllm.com/sdk/components/fast-models](https://docs.morphllm.com/sdk/components/fast-models) |

## License

MIT
