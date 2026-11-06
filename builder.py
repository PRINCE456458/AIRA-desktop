import json
import os
import re
import paths
import webbrowser
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = paths.DATA_DIR
OUT_DIR = os.path.join(BASE_DIR, "builds")
OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM = (
    "You are an expert web developer who builds small study tools for students. "
    "Reply with ONE complete HTML file and nothing else, inside a single ```html code block. "
    "Rules: put everything in one file (HTML, CSS inside <style>, JavaScript inside <script>). "
    "Use NO external libraries, fonts, images or links, so it works offline. "
    "Make it mobile friendly with a clean, modern design and clear labels. "
    "Save the user's data with localStorage inside try/catch when that is useful. "
    "The app must fully work, with no placeholder comments such as 'add code here'. "
    "Keep it simple and under about 250 lines."
)

IDEAS = (
    "Things you can ask me to make (type one, or describe your own):\n"
    "WEBSITES AND WEB APPS\n"
    "- build a flashcard app where I can add cards and flip them\n"
    "- build a pomodoro study timer website with start, pause and reset\n"
    "- build a GPA calculator website\n"
    "- build a quiz app about Python basics with a score at the end\n"
    "PDF AND WORD FILES\n"
    "- make a pdf study guide about operating systems\n"
    "- write a word document about the water cycle\n"
    "- make a pdf summary of my notes   (after you click Add document)\n"
    "PYTHON PROGRAMS\n"
    "- write a python program that guesses a number\n"
    "- write a python app that tracks my expenses\n"
    "After a web page opens, type: change it: <what you want> to improve it."
)

START = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?(?:build|create|make|generate|design)\s+"
    r"(?:me\s+|us\s+)?(?:a\s+|an\s+|the\s+|my\s+)?(?:[\w'-]+\s+){0,6}?"
    r"(?:website|web\s?site|web\s?page|web\s?app|app|application|page)\b",
    re.IGNORECASE,
)
FOLLOW_UPS = (
    "change it", "update it", "modify it", "edit it", "improve it", "fix it",
    "change the app", "change the website", "update the app", "update the website",
)
RISKY = re.compile(
    r"""(?:src|href)\s*=\s*["']https?://|fetch\s*\(|XMLHttpRequest|<form[^>]+action""",
    re.IGNORECASE,
)


def quick_reply(text):
    if text.lower().strip(" .!?") in ("build ideas", "app ideas", "website ideas", "builder help"):
        return IDEAS
    return None


def is_request(text, has_previous):
    lower = text.lower().strip()
    if has_previous and lower.startswith(FOLLOW_UPS):
        return True
    return bool(START.match(lower))


def pick_model(default_model):
    """Prefer an installed coding model, otherwise use the normal chat model."""
    try:
        reply = requests.get("http://localhost:11434/api/tags", timeout=3)
        for model in reply.json().get("models", []):
            if model["name"].startswith("qwen2.5-coder"):
                return model["name"]
    except Exception:
        pass
    return default_model


def extract_html(text):
    match = re.search(r"```(?:html)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        code = match.group(1)
    else:
        fence = re.search(r"```(?:html)?\s*(.*)", text, re.DOTALL | re.IGNORECASE)
        code = fence.group(1) if fence else text
    lower = code.lower()
    start = lower.find("<!doctype")
    if start == -1:
        start = lower.find("<html")
    if start == -1:
        return None
    return code[start:].strip()


def build(request, default_model, previous_html, should_stop):
    """Ask the AI for a page, save it, open it. Returns {'html': ..., 'message': ...}."""
    model = pick_model(default_model)

    if previous_html and len(previous_html) < 12000:
        user = (
            f"Here is the current page:\n```html\n{previous_html}\n```\n\n"
            f"Change it like this: {request}\n"
            "Return the COMPLETE updated file in one html code block."
        )
    else:
        user = f"Build this: {request}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "options": {"temperature": 0.3, "num_ctx": 8192, "num_predict": 4096},
    }

    text = ""
    with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=600) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if should_stop():
                return {"html": None, "message": "Stopped. No page was made."}
            if not line:
                continue
            data = json.loads(line)
            text += data.get("message", {}).get("content", "")
            if data.get("done"):
                break

    code = extract_html(text)
    if not code:
        return {
            "html": None,
            "message": (
                "I could not make a page this time. Try a simpler description, or "
                "install the coding model: ollama pull qwen2.5-coder:3b"
            ),
        }

    notes = []
    if "</html>" not in code.lower():
        code += "\n</body></html>"
        notes.append("The answer was cut off, so the page may be incomplete. Try a simpler idea.")
    if RISKY.search(code):
        notes.append(
            "Careful: this page tries to load something from the internet or send data. "
            "Do not type passwords or personal details into it."
        )

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", request.lower()).strip("-")[:30] or "page"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUT_DIR, f"{slug}_{stamp}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    webbrowser.open(Path(path).as_uri())

    message = (
        f"Done! I built your page with {model} and opened it in your browser.\n"
        f"Saved at: {path}\n"
        "To change it, type: change it: <what you want>"
    )
    if notes:
        message += "\n" + "\n".join(notes)
    return {"html": code, "message": message}