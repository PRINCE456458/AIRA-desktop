# Live web search for Aira's Agent mode, using DuckDuckGo (no account or key needed).
# Results are kept short on purpose, because a small model has a small memory.

MAX_RESULTS = 4
SNIPPET_LENGTH = 300


def _client():
    # Imported here, so Aira still starts even if the package is not installed yet.
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # the older name of the same package
        except ImportError:
            raise RuntimeError("web search is not installed. Run: pip install ddgs")
    return DDGS()


def format_results(results):
    """Turn raw search results into short numbered text the AI can read."""
    if not results:
        return "No results found."
    lines = []
    for number, item in enumerate(results[:MAX_RESULTS], start=1):
        title = (item.get("title") or "").strip()
        snippet = (item.get("body") or "").strip()[:SNIPPET_LENGTH]
        link = (item.get("href") or "").strip()
        lines.append(f"{number}. {title}\n   {snippet}\n   Source: {link}")
    return "\n\n".join(lines)


def search(query):
    query = query.strip()
    if not query:
        return "No search words were given."
    results = _client().text(query, max_results=MAX_RESULTS)
    return format_results(list(results))