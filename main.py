import asyncio, json, os, urllib.parse
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from openai import AsyncOpenAI
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup

KEY = os.environ.get("MORPH_API_KEY", "")
COMPACT = "https://api.morphllm.com/v1/compact"
BASE = "https://api.morphllm.com/v1"
MODEL = "morph-dsv4flash"
WARN = "MORPH_API_KEY not set — running without AI compaction. Results may be verbose and could overflow the context window. Set MORPH_API_KEY in your MCP server config to enable compact mode and reduce inference costs."
HINT = "Unenriched results. For AI-synthesized answers with cited sources, re-run with enrich=True. To fetch full page content for any result below, copy its URL and call webfetch."

app = Server("websearch-mcp")
_crawler = None


def markdown(r):
    m = r.markdown
    return m.raw_markdown if hasattr(m, "raw_markdown") else (m if isinstance(m, str) else str(m))


def resolve(url):
    if not url:
        return ""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url, scheme="https").query)
    return urllib.parse.unquote(q["uddg"][0]) if "uddg" in q else ("https:" + url if url.startswith("//") else url)


async def compact(text, query, ratio=0.5):
    if not text:
        return ""
    if not KEY:
        return text
    try:
        r = (await asyncio.to_thread(__import__("requests").post, COMPACT,
            headers={"Authorization": f"Bearer {KEY}"},
            json={"input": text, "query": query, "compression_ratio": ratio, "preserve_recent": 0, "include_markers": False},
            timeout=60))
        return r.json()["output"] if r.status_code == 200 else text
    except Exception:
        return text


async def crawler():
    global _crawler
    if not _crawler:
        _crawler = AsyncWebCrawler()
        await _crawler.__aenter__()
    return _crawler


async def _do_search(query, n=5):
    c = await crawler()
    soup = BeautifulSoup((await c.arun(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}")).html or "", "html.parser")
    results = [
        {"title": le.get_text(strip=True) or "",
         "url": u,
         "snippet": (s := r.select_one("a.result__snippet")) and s.get_text(strip=True) or "",
         "content": ""}
        for r in soup.select(".result")
        if "result--ad" not in (r.get("class") or [])
        and (le := r.select_one("a.result__a"))
        and (u := resolve(le.get("href", "")))
        and u.startswith("http")
    ][:n]
    if results:
        try:
            contents = {cr.url: cr for cr in await c.arun_many([r["url"] for r in results]) if cr and cr.url}
            for r in results:
                if (cr := contents.get(r["url"])) and (md := markdown(cr)):
                    r["content"] = await compact(md, query, 0.3)
        except Exception:
            pass
    if not KEY:
        results.append({"_warning": WARN})
    return results


async def _do_fetch(url):
    r = await (await crawler()).arun(url)
    md = markdown(r)
    content = await compact(md, url, 0.5) if md else ""
    return {"url": url, "content": content, "_warning": WARN} if not KEY else {"url": url, "content": content}


async def _enrich(query, results):
    cl = AsyncOpenAI(api_key=KEY, base_url=BASE)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "websearch",
                "description": "Search the web using DuckDuckGo and return results with full page content",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "num_results": {"type": "integer", "default": 5}},
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
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        },
    ]
    msgs = [
        {"role": "system", "content": "You are a web research agent. Your job is to answer user queries by searching the web and fetching web pages. Use websearch(query, num_results) and webfetch(url). When you have enough information, output your final answer in a clear format with links to sources."},
        {"role": "user", "content": query},
    ]
    initial = json.dumps(results)
    msgs.append({"role": "user", "content": f"Here are initial search results for your query. Use these as a starting point:\n{initial}"})
    sources = [{"title": r["title"], "url": r["url"]} for r in results if r.get("title") and r.get("url")]
    for _ in range(5):
        msg = (await cl.chat.completions.create(model=MODEL, messages=msgs, tools=tools)).choices[0].message
        if not msg.tool_calls:
            return {"answer": msg.content, "sources": sources}
        msgs.append({"role": "assistant", "tool_calls": [{"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}} for t in msg.tool_calls]})
        for t in msg.tool_calls:
            args = json.loads(t.function.arguments)
            if t.function.name == "websearch":
                r = await _do_search(args.get("query", ""), args.get("num_results", 5))
                sources += [{"title": x["title"], "url": x["url"]} for x in r if x.get("title") and x.get("url")]
                msgs.append({"role": "tool", "tool_call_id": t.id, "content": json.dumps(r)})
            else:
                r = await _do_fetch(args.get("url", ""))
                if r.get("url"):
                    sources.append({"title": r["url"], "url": r["url"]})
                msgs.append({"role": "tool", "tool_call_id": t.id, "content": json.dumps(r)})
    final = (await cl.chat.completions.create(model=MODEL, messages=msgs + [{"role": "user", "content": "You have reached the maximum number of research steps. Provide your final answer now based on what you found, with links to sources."}])).choices[0].message.content
    return {"answer": final, "sources": sources}


async def search(query, n=5, enrich=True):
    results = await _do_search(query, n)
    if enrich and not KEY:
        return results
    if enrich:
        return await _enrich(query, results)
    results.append({"_hint": HINT})
    return results


@app.list_tools()
async def list_tools():
    return [
        Tool(name="websearch", description="Search the web using DuckDuckGo and return results with full page content",
             inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "num_results": {"type": "integer", "default": 5}, "enrich": {"type": "boolean", "default": True}}, "required": ["query"]}),
        Tool(name="webfetch", description="Fetch and extract content from a URL",
             inputSchema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}),
    ]


@app.call_tool()
async def call_tool(name, args):
    result = await (
        search(args.get("query", ""), args.get("num_results", 5), args.get("enrich", True)) if name == "websearch"
        else (_do_fetch(args.get("url", "")) if name == "webfetch" else None)
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))] if result else [TextContent(type="text", text="Unknown tool")]


def main():
    asyncio.run(_serve())


async def _serve():
    try:
        async with stdio_server() as (read, write):
            await app.run(read, write, app.create_initialization_options())
    finally:
        if _crawler:
            await _crawler.__aexit__(None, None, None)


if __name__ == "__main__":
    main()
