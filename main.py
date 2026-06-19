import asyncio
import json
import urllib.parse
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import requests
from openai import AsyncOpenAI
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup

import os

MORPH_API_KEY = os.environ.get("MORPH_API_KEY", "")
COMPACT_URL = "https://api.morphllm.com/v1/compact"
OPENAI_BASE = "https://api.morphllm.com/v1"
MODEL = "morph-dsv4flash"

from importlib.metadata import version as pkg_version

try:
    __version__ = pkg_version("websearch-mcp")
except Exception:
    __version__ = "0.1.0"

server = Server("websearch-mcp", version=__version__)
_crawler = None


async def get_crawler():
    global _crawler
    if _crawler is None:
        _crawler = AsyncWebCrawler()
        await _crawler.__aenter__()
    return _crawler


def get_markdown(result):
    md = result.markdown
    if isinstance(md, str):
        return md
    if hasattr(md, "raw_markdown"):
        return md.raw_markdown
    return str(md)


async def compact_text(text, query, ratio=0.5):
    if not text:
        return ""
    try:
        response = await asyncio.to_thread(
            lambda: requests.post(
                COMPACT_URL,
                headers={"Authorization": f"Bearer {MORPH_API_KEY}"},
                json={
                    "input": text,
                    "query": query,
                    "compression_ratio": ratio,
                    "preserve_recent": 0,
                    "include_markers": False,
                },
                timeout=60,
            )
        )
        if response.status_code == 200:
            return response.json()["output"]
    except Exception:
        pass
    return text


def _resolve_ddg_url(href):
    if not href:
        return ""
    if href.startswith("//duckduckgo.com/l/") or "uddg=" in href:
        parsed = urllib.parse.urlparse(href, scheme="https")
        params = urllib.parse.parse_qs(parsed.query)
        encoded = params.get("uddg", [""])[0]
        if encoded:
            return urllib.parse.unquote(encoded)
    if href.startswith("//"):
        return "https:" + href
    return href


async def websearch_impl(query, num_results=5):
    crawler = await get_crawler()
    ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    result = await crawler.arun(ddg_url)
    html = getattr(result, "html", "") or ""
    soup = BeautifulSoup(html, "html.parser")

    result_elements = soup.select(".result")
    parsed = []
    for item in result_elements:
        classes = item.get("class", [])
        if "result--ad" in classes:
            continue
        link_el = item.select_one("a.result__a")
        snippet_el = item.select_one("a.result__snippet")
        if not link_el:
            continue
        title = link_el.get_text(strip=True)
        url = _resolve_ddg_url(link_el.get("href", ""))
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            continue
        parsed.append({"title": title, "url": url, "snippet": snippet})
        if len(parsed) >= num_results:
            break

    for r in parsed:
        r["content"] = ""

    urls = [r["url"] for r in parsed]
    if urls:
        try:
            crawl_results = await crawler.arun_many(urls)
            url_to_content = {}
            for cr in crawl_results:
                if cr and cr.url:
                    md = get_markdown(cr)
                    url_to_content[cr.url] = await compact_text(md, query, 0.3) if md else ""
            for r in parsed:
                r["content"] = url_to_content.get(r["url"], "")
        except Exception:
            pass

    return parsed


async def webfetch_impl(url):
    crawler = await get_crawler()
    result = await crawler.arun(url)
    md = get_markdown(result)
    content = await compact_text(md, url, 0.5) if md else ""
    return {"url": url, "content": content}


async def webextract_impl(query):
    client = AsyncOpenAI(api_key=MORPH_API_KEY, base_url=OPENAI_BASE)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "websearch",
                "description": "Search the web for information using DuckDuckGo",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "num_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "webfetch",
                "description": "Fetch and extract content from a URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to fetch"}
                    },
                    "required": ["url"],
                },
            },
        },
    ]

    messages = [
        {
            "role": "system",
            "content": "You are a web research agent. Your job is to answer user queries by searching the web and fetching web pages. You have access to two functions: websearch(query, num_results) and webfetch(url). Use them to find the answer. When you have enough information, output your final answer in a clear format with links to sources.",
        },
        {"role": "user", "content": query},
    ]

    sources = []

    for _ in range(5):
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return {"answer": msg.content, "sources": sources}

        tool_calls_data = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
        messages.append(
            {"role": "assistant", "tool_calls": tool_calls_data}
        )

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            if tc.function.name == "websearch":
                results = await websearch_impl(
                    args.get("query", ""), args.get("num_results", 5)
                )
                for r in results:
                    if r.get("title") and r.get("url"):
                        sources.append({"title": r["title"], "url": r["url"]})
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(results)}
                )
            elif tc.function.name == "webfetch":
                result = await webfetch_impl(args.get("url", ""))
                if result.get("url"):
                    sources.append({"title": result["url"], "url": result["url"]})
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)}
                )

    final_response = await client.chat.completions.create(
        model=MODEL,
        messages=messages
        + [
            {
                "role": "user",
                "content": "You have reached the maximum number of research steps. Provide your final answer now based on what you found, with links to sources.",
            }
        ],
    )
    return {"answer": final_response.choices[0].message.content, "sources": sources}


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="websearch",
            description="Search the web using DuckDuckGo and return results with full page content",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "num_results": {
                        "type": "integer",
                        "default": 5,
                        "description": "Number of results to return",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="webfetch",
            description="Fetch and extract content from a URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="webextract",
            description="Agentic web research — searches and fetches pages to answer a query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The research query to answer",
                    }
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name, arguments):
    if name == "websearch":
        results = await websearch_impl(
            arguments.get("query", ""), arguments.get("num_results", 5)
        )
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    elif name == "webfetch":
        result = await webfetch_impl(arguments.get("url", ""))
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "webextract":
        result = await webextract_impl(arguments.get("query", ""))
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    return [TextContent(type="text", text="Unknown tool")]


async def serve():
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    finally:
        global _crawler
        if _crawler:
            await _crawler.__aexit__(None, None, None)


def main():
    asyncio.run(serve())


if __name__ == "__main__":
    main()
