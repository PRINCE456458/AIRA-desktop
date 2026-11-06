import json
import os
import platform
import sys
import urllib.parse

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "feedback.json")

# ----- Change these when you want -----
APP_NAME = "Aira"
APP_VERSION = "1.0"
SUPPORT_PHONE = "917359100656"        # country code 91 (India) + your number, digits only
SUPPORT_HOURS = "Replies usually come within a day."
# --------------------------------------

CATEGORIES = ["Problem", "Idea", "Question", "Praise"]
MAX_TEXT = 1000
MAX_LOG = 200

WORDS = {
    "help", "support", "feedback", "contact support", "help and support", "help & support",
    "report a problem", "send feedback", "contact", "contact us",
}

FAQ = [
    ("It says Ollama is not running",
     "Aira needs the Ollama app to think. Open Ollama from the Start menu, wait a few seconds "
     "until its icon appears near the clock, then close and open Aira again."),
    ("It says a model is not installed",
     "Open a terminal and run: ollama pull llama3.2:3b (use the model name shown in the message). "
     "Wait for the download to finish, then restart Aira. The Check my setup button shows what is missing."),
    ("Answers are slow",
     "The first answer after starting is the slowest, because the model is loading. Keep the Ollama app "
     "running, close heavy programs like games or many browser tabs, and use a smaller model in Settings if "
     "your laptop is struggling."),
    ("The microphone or voice does not work",
     "Check that Windows allows apps to use the microphone (Settings, Privacy, Microphone). The first time you "
     "use speech recognition it downloads a model, so it needs the internet once. For spoken replies, turn on "
     "'Speak replies' in Settings."),
    ("Image creation fails or is slow",
     "Pictures are made by a free online service, so you need the internet. The service only allows about one "
     "picture every 15 seconds. If it fails, wait a minute and try again with a simpler description."),
    ("My task did not run",
     "Tasks only run while Aira is open. Check that the task's On switch is on, that the time is in the future, "
     "and that Ollama is running. A repeating task that was missed by more than 6 hours is skipped."),
    ("My Pro key does not work",
     "Check your internet, then open Pro and press Check again. A key works on one laptop at a time: press "
     "Remove key on the old laptop first. If it still fails, contact support and tell us the email you paid with."),
    ("How do I ask questions about my own files?",
     "Click Add document in the sidebar and choose a PDF or text file. Then ask your question in normal words. "
     "Inside a project, documents belong to that project only."),
    ("How do I make a website, PDF or Word file?",
     "Just type what you want, for example: build a pomodoro timer, make a pdf about the solar system, or write "
     "a word document about healthy food. Everything you make appears in the Library."),
    ("Where are my files saved?",
     "On your own laptop, in folders inside the Aira folder (images, builds, plans, timetables and expense_reports). "
     "The Library window shows them all in one place."),
    ("Does Aira send my chats to the internet?",
     "No. Your chats, documents and notes stay on your laptop and the AI runs on your laptop. Only a few features "
     "use the internet: image creation (your picture description), weather (the city name) and Wikipedia lookups "
     "(the search words). If you subscribe to Pro, your license key is checked online."),
]


def is_request(text):
    return text.lower().strip(" .!?") in WORDS


# ---------- links ----------
def whatsapp_link(message=""):
    link = f"https://wa.me/{SUPPORT_PHONE}"
    if message:
        link += "?text=" + urllib.parse.quote(message[:1500])
    return link


def phone_text():
    digits = SUPPORT_PHONE
    if digits.startswith("91") and len(digits) == 12:
        return f"+91 {digits[2:7]} {digits[7:]}"
    return "+" + digits


# ---------- help ----------
def search_faq(needle):
    words = [w for w in needle.lower().split() if len(w) > 1]
    if not words:
        return list(FAQ)
    found = []
    for question, answer in FAQ:
        text = (question + " " + answer).lower()
        if all(w in text for w in words):
            found.append((question, answer))
    return found


# ---------- technical info (no chats, no name, no key) ----------
def ollama_status():
    try:
        reply = requests.get("http://localhost:11434/api/tags", timeout=2)
        names = [m["name"] for m in reply.json().get("models", [])]
        return "running, " + str(len(names)) + " models installed"
    except Exception:
        return "not running"


def tech_info(settings=None, plan="free", check_ollama=True):
    settings = settings or {}
    lines = [
        f"{APP_NAME} version: {APP_VERSION}",
        f"Windows: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
        f"Chat model: {settings.get('model', '?')}",
        f"Vision model: {settings.get('vision_model', '?')}",
        f"Theme: {settings.get('theme', '?')}",
        f"Plan: {plan}",
    ]
    if check_ollama:
        lines.append("Ollama: " + ollama_status())
    return "\n".join(lines)


# ---------- feedback ----------
def build_message(category, rating, text, info=""):
    text = " ".join(text.split())[:MAX_TEXT]
    stars = "★" * rating + "☆" * (5 - rating) if 1 <= rating <= 5 else "not rated"
    lines = [f"{APP_NAME} feedback", f"Type: {category}", f"Rating: {stars}", "", text]
    if info:
        lines += ["", "Technical info:", info]
    return "\n".join(lines)


def check_feedback(category, text):
    if category not in CATEGORIES:
        return "Please pick a type."
    if len(" ".join(text.split())) < 5:
        return "Please write a few words about it."
    return ""


def load_log():
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_feedback(category, rating, text, sent_how, when):
    """Keep a copy on your laptop so nothing is lost if you never press Send in WhatsApp."""
    log = load_log()
    log.append({
        "when": when.isoformat(timespec="seconds"), "type": category, "rating": rating,
        "text": " ".join(text.split())[:MAX_TEXT], "how": sent_how,
    })
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log[-MAX_LOG:], f, indent=2, ensure_ascii=False)