import json
import os
import re
import paths
from datetime import datetime, time, timedelta

BASE_DIR = paths.DATA_DIR
FILE = os.path.join(BASE_DIR, "reminders.json")
MAX_REMINDERS = 50

HELP = (
    "To set a reminder, type for example:\n"
    "- remind me in 10 minutes to drink water\n"
    "- remind me at 6:30 pm to call mom\n"
    "- remind me tomorrow at 9 am to pay the bill\n"
    "- set a timer for 25 minutes\n"
    "Other commands: show reminders, delete reminder 2, clear reminders"
)

START = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?"
    r"(?:remind\s+me|set\s+(?:a\s+|an\s+|my\s+)?(?:reminder|alarm|timer))\b",
    re.IGNORECASE,
)
RELATIVE = re.compile(
    r"\b(?:in|for|after)\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b",
    re.IGNORECASE,
)
CLOCK = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)

SECONDS = {"s": 1, "min": 60, "hour": 3600, "day": 86400}
LIST_WORDS = {
    "show reminders", "my reminders", "list reminders", "reminders",
    "show my reminders", "what are my reminders",
}
CLEAR_WORDS = {"clear reminders", "delete reminders", "delete all reminders", "cancel all reminders"}


def in_words(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return "in less than a minute"
    minutes = seconds // 60
    if minutes < 60:
        return f"in {minutes} min"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"in {hours} h {minutes} min" if minutes else f"in {hours} h"
    return f"in {hours // 24} day(s)"


def clock_to_datetime(hour, minute, ampm, tomorrow, now):
    """Turn '6:30 pm' into a real moment in the future."""
    if hour > 23 or minute > 59:
        return None
    if ampm:
        hour = hour % 12 + (12 if ampm.lower() == "pm" else 0)
        hours = [hour]
    elif hour > 12 or hour == 0:
        hours = [hour % 24]
    else:
        hours = [hour % 12, hour % 12 + 12]  # "6" could be 6 am or 6 pm
    base = now.date() + timedelta(days=1 if tomorrow else 0)
    candidates = sorted(datetime.combine(base, time(h, minute)) for h in hours)
    for candidate in candidates:
        if candidate > now:
            return candidate
    return candidates[0] + timedelta(days=1)


def parse_when(text, now):
    """Return (due moment, the text without the time words), or (None, text)."""
    relative = RELATIVE.search(text)
    if relative:
        amount = float(relative.group(1))
        unit = relative.group(2).lower()
        if unit.startswith("day"):
            key = "day"
        elif unit.startswith(("hour", "hr")):
            key = "hour"
        elif unit.startswith("min"):
            key = "min"
        else:
            key = "s"
        due = now + timedelta(seconds=amount * SECONDS[key])
        return due, text[:relative.start()] + " " + text[relative.end():]

    clock = CLOCK.search(text)
    if clock:
        tomorrow = re.search(r"\btomorrow\b", text, re.IGNORECASE) is not None
        due = clock_to_datetime(
            int(clock.group(1)), int(clock.group(2) or 0), clock.group(3), tomorrow, now
        )
        if due is None:
            return None, text
        rest = text[:clock.start()] + " " + text[clock.end():]
        rest = re.sub(r"\b(?:tomorrow|today|tonight)\b", " ", rest, flags=re.IGNORECASE)
        return due, rest

    return None, text


def clean_message(rest, label):
    rest = re.sub(r"\s+", " ", rest).strip(" ,.:;-")
    rest = re.sub(r"^(?:to|that|about|for)\s+", "", rest, flags=re.IGNORECASE)
    rest = re.sub(r"\s+(?:please|pls)$", "", rest, flags=re.IGNORECASE).strip(" ,.:;-")
    if not rest:
        return {"timer": "Timer is done", "alarm": "Alarm"}.get(label, "Your reminder")
    return rest[:1].upper() + rest[1:]


class ReminderStore:
    def __init__(self):
        self.items = self._load()

    def _load(self):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [i for i in data if "text" in i and "due" in i]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=2, ensure_ascii=False)

    def _sorted(self):
        return sorted(self.items, key=lambda item: item["due"])

    def pop_due(self):
        """Remove and return every reminder whose time has come."""
        now = datetime.now()
        due = [i for i in self.items if datetime.fromisoformat(i["due"]) <= now]
        if due:
            self.items = [i for i in self.items if i not in due]
            self._save()
        return sorted(due, key=lambda item: item["due"])

    def listing(self):
        if not self.items:
            return "You have no reminders. " + HELP.split("\n")[0]
        now = datetime.now()
        lines = []
        for number, item in enumerate(self._sorted(), 1):
            due = datetime.fromisoformat(item["due"])
            lines.append(
                f"{number}. {item['text']}  -  {due.strftime('%I:%M %p, %a %d %b')} "
                f"({in_words((due - now).total_seconds())})"
            )
        return "Your reminders:\n" + "\n".join(lines)

    def handle(self, text):
        """Return Aira's reply if this is a reminder message, otherwise None."""
        cleaned = text.strip()
        lower = cleaned.lower().strip(" .!?")

        if lower in LIST_WORDS:
            return self.listing()
        if lower in CLEAR_WORDS:
            count = len(self.items)
            self.items = []
            self._save()
            return f"Done. I removed {count} reminder(s)."

        remove = re.match(r"^(?:delete|cancel|remove)\s+reminder\s+(\d+)$", lower)
        if remove:
            ordered = self._sorted()
            position = int(remove.group(1))
            if 1 <= position <= len(ordered):
                gone = ordered[position - 1]
                self.items.remove(gone)
                self._save()
                return f"Removed reminder {position}: {gone['text']}"
            return "There is no reminder with that number. Type 'show reminders' to see them."

        start = START.match(cleaned)
        if not start:
            return None

        label = "timer" if "timer" in start.group(0).lower() else (
            "alarm" if "alarm" in start.group(0).lower() else "reminder"
        )
        now = datetime.now()
        due, rest = parse_when(cleaned[start.end():], now)
        if due is None:
            return "I could not find a time in that.\n" + HELP
        if len(self.items) >= MAX_REMINDERS:
            return "You have too many reminders. Type 'clear reminders' first."

        message = clean_message(rest, label)
        next_id = max([i.get("id", 0) for i in self.items] + [0]) + 1
        self.items.append({"id": next_id, "text": message, "due": due.isoformat(timespec="seconds")})
        self._save()
        return (
            f"Okay! I will remind you: {message}\n"
            f"At {due.strftime('%I:%M %p, %a %d %b')} ({in_words((due - now).total_seconds())}).\n"
            "Keep Aira open (you can minimize it) so I can ring."
        )