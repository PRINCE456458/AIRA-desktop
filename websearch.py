from urllib.parse import quote

import requests

HEADERS = {"User-Agent": "AiraAI/1.0 (student learning project)"}


def extract_topic(text):
    """If the text starts with 'look up' or 'wiki', return the topic, else None."""
    cleaned = text.strip()
    lower = cleaned.lower()
    for prefix in ("look up ", "lookup ", "wikipedia ", "wiki "):
        if lower.startswith(prefix):
            topic = cleaned[len(prefix):].strip().rstrip(".!?")
            return topic or None
    return None


def wikipedia_lookup(topic):
    """Return {'title', 'text', 'url'} for the best matching page, or None."""
    search = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": topic,
            "srlimit": 1,
            "format": "json",
        },
        headers=HEADERS,
        timeout=10,
    )
    search.raise_for_status()
    results = search.json().get("query", {}).get("search", [])
    if not results:
        return None

    title = results[0]["title"]
    summary = requests.get(
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
        + quote(title.replace(" ", "_")),
        headers=HEADERS,
        timeout=10,
    )
    summary.raise_for_status()
    data = summary.json()
    text = data.get("extract", "").strip()
    if not text:
        return None
    return {
        "title": data.get("title", title),
        "text": text,
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
    }