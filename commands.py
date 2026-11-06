import datetime
import os
import webbrowser
from urllib.parse import quote_plus

# Websites Aira can open. Add your own: "name": "https://link"
WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "whatsapp": "https://web.whatsapp.com",
}

# Apps Aira can open. Add your own: "name": "program.exe"
APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "chrome": "chrome",
}

TIME_PHRASES = {"time", "what time is it", "what is the time", "what's the time", "tell me the time"}
DATE_PHRASES = {"date", "what is the date", "what's the date", "what day is it", "today's date", "what is today's date"}


def try_command(text):
    """Return Aira's reply if the text is a known command, otherwise None."""
    cleaned = text.lower().strip().rstrip(".!?")

    if cleaned in TIME_PHRASES:
        return "It's " + datetime.datetime.now().strftime("%I:%M %p") + "."

    if cleaned in DATE_PHRASES:
        return "Today is " + datetime.datetime.now().strftime("%A, %d %B %Y") + "."

    for prefix in ("search for ", "search ", "google "):
        if cleaned.startswith(prefix):
            query = cleaned[len(prefix):].strip()
            if query:
                webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
                return f"Searching Google for '{query}'."

    if cleaned.startswith("open "):
        name = cleaned[5:].strip()
        if name in WEBSITES:
            webbrowser.open(WEBSITES[name])
            return f"Opening {name}."
        if name in APPS:
            try:
                os.startfile(APPS[name])
                return f"Opening {name}."
            except Exception:
                return f"I could not open {name} on this laptop."

    return None  # not a command, so the AI answers normally