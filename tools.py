import ast
import datetime
import json
import operator
import os

import requests
import paths

import commands
import timetable
import websearch

BASE_DIR = paths.DATA_DIR
NOTES_FILE = os.path.join(BASE_DIR, "notes.txt")

# The menu of tools the AI is allowed to ask for.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Calculate a maths expression exactly, for example '23*47+19'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "The maths expression"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time on the user's laptop.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wikipedia",
            "description": "Look up facts about a person, place, thing or concept on Wikipedia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "What to look up"}
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search the documents the user added (notes, syllabus, PDFs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Save a fact about the user to long-term memory, only when they ask you to remember something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to save"}
                },
                "required": ["fact"],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, for example Ahmedabad"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app_or_website",
            "description": "Open an app or website on the user's laptop, for example youtube, notepad or calculator.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the app or website"}
                },
                "required": ["name"],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the internet for recent or current information, such as news, "
                "new software versions, dates, prices or anything you are not sure about."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Short search words"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Save a note for the user, only when they ask to note something down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The note to save"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_notes",
            "description": "Read the user's saved notes.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
        {
        "type": "function",
        "function": {
            "name": "create_timetable",
            "description": (
                "Create a timetable website from a list of lessons and open it in the "
                "browser. Write each lesson as 'Day start-end Subject' and separate "
                "lessons with semicolons, for example "
                "'Mon 9-10 Maths; Mon 10-11 Physics; Tue 9-11 Python lab'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "schedule": {"type": "string", "description": "The lessons, separated by semicolons"}
                },
                "required": ["schedule"],
            },
        },
    },
]

# A safe calculator: it only allows numbers and + - * / ** %, never real code.
OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _evaluate(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("that exponent is too big")
        return OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](_evaluate(node.operand))
    raise ValueError("only numbers and + - * / ** % are allowed")


def calculate(expression):
    tree = ast.parse(expression.strip(), mode="eval")
    return str(_evaluate(tree.body))

def describe_weather_code(code):
    if code == 0:
        return "clear sky"
    if code in (1, 2, 3):
        return "partly cloudy"
    if code in (45, 48):
        return "foggy"
    if 51 <= code <= 57:
        return "drizzle"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77:
        return "snow"
    if code >= 95:
        return "thunderstorm"
    return "unknown conditions"


def get_weather(city):
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=10,
    )
    geo.raise_for_status()
    results = geo.json().get("results")
    if not results:
        return f"Could not find a place called {city}."
    place = results[0]

    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "auto",
        },
        timeout=10,
    )
    weather.raise_for_status()
    now = weather.json()["current"]
    return (
        f"{place['name']}, {place.get('country', '')}: "
        f"{describe_weather_code(now['weather_code'])}, "
        f"{now['temperature_2m']} C, humidity {now['relative_humidity_2m']}%, "
        f"wind {now['wind_speed_10m']} km/h"
    )


def open_app_or_website(name):
    # Only things in the safe lists from commands.py can be opened.
    result = commands.try_command("open " + name.strip().lower())
    if result:
        return result
    allowed = ", ".join(list(commands.WEBSITES) + list(commands.APPS))
    return f"I am not allowed to open '{name}'. Allowed: {allowed}"


def add_note(text):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {text.strip()}\n")
    return "Note saved."


def read_notes():
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
    except FileNotFoundError:
        return "There are no notes yet."
    if not lines:
        return "There are no notes yet."
    return "\n".join(lines[-20:])  # the latest 20 notes


def run_tool(name, args, kb, memory_store):
    """Run one tool and return the result as text. Never crashes the app."""
    try:
        if isinstance(args, str):
            args = json.loads(args)
        if name == "calculate":
            return calculate(args.get("expression", ""))
        if name == "get_time":
            return datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")
        if name == "wikipedia":
            page = websearch.wikipedia_lookup(args.get("topic", ""))
            if not page:
                return "Nothing found on Wikipedia."
            return f"{page['title']}: {page['text']}"
        if name == "search_documents":
            hits = kb.search(args.get("query", ""))
            if not hits:
                return "No relevant notes found in the user's documents."
            return "\n\n".join(f"[{h['source']}] {h['text']}" for h in hits)
        if name == "remember_fact":
            memory_store.add(args.get("fact", ""))
            return "Saved to memory."
        if name == "get_weather":
            return get_weather(args.get("city", ""))
        if name == "open_app_or_website":
            return open_app_or_website(args.get("name", ""))
        if name == "add_note":
            return add_note(args.get("text", ""))
        if name == "read_notes":
            return read_notes()
        if name == "create_timetable":
            entries = timetable.parse_schedule(args.get("schedule", ""))
        if not entries:
                return "No lessons found. " + timetable.HELP
        return timetable.build_and_open(entries, "My Timetable")
        if name == "web_search":
            return internet.search(args.get("query", ""))
        return f"Unknown tool: {name}"
    except Exception as error:
        return f"Tool error: {error}"
    