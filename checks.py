import requests


def find_problems(settings):
    """Return a list of problems (empty list means everything is fine)."""
    try:
        reply = requests.get("http://localhost:11434/api/tags", timeout=3)
        installed = [m["name"] for m in reply.json().get("models", [])]
    except Exception:
        return ["Ollama is not running. Open the Ollama app, then restart Aira."]

    problems = []
    for label, key in (("Chat model", "model"), ("Vision model", "vision_model")):
        name = settings[key]
        if name not in installed and f"{name}:latest" not in installed:
            problems.append(f"{label} '{name}' is not installed. Run: ollama pull {name}")
    return problems

def list_models():
    """Names of chat models installed in Ollama (embedding models are hidden)."""
    try:
        reply = requests.get("http://localhost:11434/api/tags", timeout=3)
        names = [m["name"] for m in reply.json().get("models", [])]
        return sorted(n for n in names if "embed" not in n)
    except Exception:
        return []