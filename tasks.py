import json
import os
import re
import time
from datetime import date, datetime, timedelta

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(BASE_DIR, "tasks.json")
OLLAMA_URL = "http://localhost:11434/api/chat"

REPEATS = ["Once", "Daily", "Weekdays", "Weekly"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MAX_TASKS = 30
MISSED_LIMIT = 6 * 3600     # a repeating task missed by more than 6 hours is skipped
RETRY_MINUTES = 5           # if Ollama is off, try again after this long
MAX_FAILS = 3

WORDS = {"tasks", "my tasks", "open tasks", "show tasks", "task list", "scheduled tasks"}

# Ideas shown in the "Suggested" tab. Add your own freely.
SUGGESTIONS = [
    {"title": "Word of the day", "repeat": "Daily", "time": "09:00",
     "prompt": "Teach me one useful English word. Give its meaning, an example sentence and a tip to remember it."},
    {"title": "Morning motivation", "repeat": "Daily", "time": "08:00",
     "prompt": "Give me one short motivational thought and one small goal I can finish today."},
    {"title": "Python practice", "repeat": "Weekdays", "time": "18:00",
     "prompt": "Give me one small Python practice problem for a beginner. Add a hint, but do not give the answer."},
    {"title": "Fun fact", "repeat": "Daily", "time": "12:00",
     "prompt": "Tell me one surprising fact about science or technology in three sentences."},
    {"title": "Healthy break", "repeat": "Daily", "time": "17:00",
     "prompt": "Give me a quick healthy-break routine: drink water, stretch, and rest my eyes. Keep it under 60 words."},
    {"title": "Plan my week", "repeat": "Weekly", "time": "09:00", "day": 0,
     "prompt": "Help me plan my week. Ask me three short questions about my priorities, then give a simple weekly plan template."},
    {"title": "Evening reflection", "repeat": "Daily", "time": "21:00",
     "prompt": "Ask me three short questions to reflect on my day: what went well, what was hard, and what I will do tomorrow."},
    {"title": "Learn a skill", "repeat": "Weekly", "time": "19:00", "day": 5,
     "prompt": "Pick one useful skill for a first-year engineering student and give me a 20-minute practice plan for it."},
]


def is_request(text):
    return text.lower().strip(" .!?") in WORDS


# ---------- Reading times and dates ----------
def parse_time(text):
    """'8', '8am', '8:30 pm', '20:15' -> 'HH:MM', or None."""
    match = re.match(r"^(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?$", text.strip().lower())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    suffix = (match.group(3) or "").replace(".", "")
    if suffix:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if suffix == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def parse_date(text):
    """'2026-10-25' or '25-10-2026' -> 'YYYY-MM-DD', or None."""
    text = text.strip()
    for pattern, order in ((r"^(\d{4})-(\d{1,2})-(\d{1,2})$", "ymd"), (r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", "dmy")):
        match = re.match(pattern, text)
        if match:
            a, b, c = (int(x) for x in match.groups())
            year, month, day = (a, b, c) if order == "ymd" else (c, b, a)
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return None
    return None


def nice_time(hhmm):
    hour, minute = (int(x) for x in hhmm.split(":"))
    return datetime(2000, 1, 1, hour, minute).strftime("%I:%M %p").lstrip("0")


# ---------- When does a task run? ----------
def matches_day(task, day):
    repeat = task["repeat"]
    if repeat == "Once":
        return day.isoformat() == task.get("date")
    if repeat == "Daily":
        return True
    if repeat == "Weekdays":
        return day.weekday() < 5
    if repeat == "Weekly":
        return day.weekday() == task.get("weekday", 0)
    return False


def next_after(task, now):
    hour, minute = (int(x) for x in task["time"].split(":"))
    for offset in range(0, 15):
        day = now.date() + timedelta(days=offset)
        if matches_day(task, day):
            moment = datetime(day.year, day.month, day.day, hour, minute)
            if moment > now:
                return moment
    return None


def describe(task):
    at = nice_time(task["time"])
    repeat = task["repeat"]
    if repeat == "Once":
        shown = datetime.fromisoformat(task["date"]).strftime("%d %b %Y")
        return f"Once on {shown} at {at}"
    if repeat == "Daily":
        return f"Every day at {at}"
    if repeat == "Weekdays":
        return f"Every weekday at {at}"
    return f"Every {DAYS[task.get('weekday', 0)]} at {at}"


def next_text(task):
    if not task.get("enabled"):
        return "Done" if task["repeat"] == "Once" and task.get("runs") else "Paused"
    if not task.get("next_run"):
        return "Not scheduled"
    return "Next: " + datetime.fromisoformat(task["next_run"]).strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


# ---------- Running a task with the AI ----------
def run_prompt(prompt, model, system):
    try:
        reply = requests.post(
            OLLAMA_URL,
            json={
                "model": model, "stream": False, "options": {"temperature": 0.7},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            },
            timeout=180,
        )
        reply.raise_for_status()
        text = reply.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        return None, "Ollama is not running"
    except Exception as error:
        return None, str(error)[:120]
    if not text:
        return None, "The model sent an empty answer"
    return text, None


# ---------- The saved tasks ----------
class TaskStore:
    def __init__(self):
        self.items = self._load()
        self.limit = MAX_TASKS      # main.py sets this from your plan (Free or Pro)

    def _load(self):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [t for t in data if "id" in t and "prompt" in t and "time" in t and "repeat" in t]
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return []

    def _save(self):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=2, ensure_ascii=False)

    def get(self, task_id):
        for task in self.items:
            if task["id"] == task_id:
                return task
        return None

    def _check(self, title, prompt, repeat, time_text, day_index, date_text, now, ignore=None):
        title = " ".join(title.split())[:40]
        prompt = prompt.strip()[:1500]
        if not title:
            return None, "Please give the task a title."
        if len(prompt) < 8:
            return None, "Please write what Aira should do (a short sentence is enough)."
        if repeat not in REPEATS:
            return None, "Pick how often it should repeat."
        clock = parse_time(time_text)
        if not clock:
            return None, "I could not read the time. Try 8:30 am or 20:15."
        if any(t["title"].lower() == title.lower() and t is not ignore for t in self.items):
            return None, f"You already have a task called {title}."
        fields = {"title": title, "prompt": prompt, "repeat": repeat, "time": clock}
        if repeat == "Weekly":
            fields["weekday"] = day_index if 0 <= day_index <= 6 else 0
        if repeat == "Once":
            day = parse_date(date_text)
            if not day:
                return None, "I could not read the date. Try 25-10-2026."
            fields["date"] = day
        probe = dict(fields)
        if next_after(probe, now) is None:
            return None, "That time has already passed. Pick a time in the future."
        return fields, ""

    def add(self, title, prompt, repeat, time_text, day_index=0, date_text="", now=None):
        now = now or datetime.now()
        if len(self.items) >= self.limit:
            return None, f"Your plan allows {self.limit} tasks. Open Pro to get more."
        fields, error = self._check(title, prompt, repeat, time_text, day_index, date_text, now)
        if error:
            return None, error
        new_id = int(time.time() * 1000)
        while any(t["id"] == str(new_id) for t in self.items):
            new_id += 1
        task = {"id": str(new_id), "enabled": True, "runs": 0, "fails": 0, "last_run": "", "status": "Not run yet"}
        task.update(fields)
        task["next_run"] = next_after(task, now).isoformat()
        self.items.append(task)
        self._save()
        return task, ""

    def update(self, task_id, title, prompt, repeat, time_text, day_index=0, date_text="", now=None):
        now = now or datetime.now()
        task = self.get(task_id)
        if not task:
            return None, "That task no longer exists."
        fields, error = self._check(title, prompt, repeat, time_text, day_index, date_text, now, ignore=task)
        if error:
            return None, error
        for key in ("weekday", "date"):
            task.pop(key, None)
        task.update(fields)
        task["enabled"] = True
        task["fails"] = 0
        task["next_run"] = next_after(task, now).isoformat()
        self._save()
        return task, ""

    def add_suggestion(self, index, now=None):
        idea = SUGGESTIONS[index]
        return self.add(idea["title"], idea["prompt"], idea["repeat"], idea["time"], idea.get("day", 0), now=now)

    def delete(self, task_id):
        self.items = [t for t in self.items if t["id"] != task_id]
        self._save()

    def set_enabled(self, task_id, flag, now=None):
        now = now or datetime.now()
        task = self.get(task_id)
        if not task:
            return False, "That task no longer exists."
        if flag:
            upcoming = next_after(task, now)
            if upcoming is None:
                return False, "The time has passed. Edit the task to pick a new time."
            task["next_run"] = upcoming.isoformat()
            task["fails"] = 0
        task["enabled"] = bool(flag)
        self._save()
        return True, ""

    def due(self, now=None):
        """Tasks whose time has come, oldest first."""
        now = now or datetime.now()
        ready = []
        changed = False
        for task in self.items[: self.limit]:     # tasks over the plan limit stay saved but do not run
            if not task.get("enabled") or not task.get("next_run"):
                continue
            moment = datetime.fromisoformat(task["next_run"])
            if moment > now:
                continue
            late = (now - moment).total_seconds()
            if task["repeat"] != "Once" and late > MISSED_LIMIT and task.get("fails", 0) == 0:
                upcoming = next_after(task, now)      # we were closed too long: skip this one
                task["next_run"] = upcoming.isoformat() if upcoming else None
                task["status"] = "Skipped: Aira was closed at the scheduled time"
                changed = True
                continue
            ready.append((moment, task))
        if changed:
            self._save()
        return [t for _, t in sorted(ready, key=lambda pair: pair[0])]

    def mark_run(self, task_id, ok, note="", now=None):
        now = now or datetime.now()
        task = self.get(task_id)
        if not task:
            return
        stamp = now.strftime("%d %b, %I:%M %p").lstrip("0")
        if ok:
            task["fails"] = 0
            task["runs"] = task.get("runs", 0) + 1
            task["last_run"] = now.isoformat()
            task["status"] = f"Ran on {stamp}"
            self._finish(task, now)
        else:
            task["fails"] = task.get("fails", 0) + 1
            if task["fails"] < MAX_FAILS:
                task["next_run"] = (now + timedelta(minutes=RETRY_MINUTES)).isoformat()
                task["status"] = f"Could not run ({note}). Trying again in {RETRY_MINUTES} minutes"
            else:
                task["fails"] = 0
                task["status"] = f"Could not run on {stamp}: {note}"
                self._finish(task, now)
        self._save()

    def mark_manual(self, task_id, ok, note="", now=None):
        """A 'Run now' click. It never changes the schedule."""
        now = now or datetime.now()
        task = self.get(task_id)
        if not task:
            return
        stamp = now.strftime("%d %b, %I:%M %p").lstrip("0")
        if ok:
            task["runs"] = task.get("runs", 0) + 1
            task["last_run"] = now.isoformat()
            task["status"] = f"Ran on {stamp} (run by you)"
        else:
            task["status"] = f"Could not run on {stamp}: {note}"
        self._save()

    def _finish(self, task, now):
        if task["repeat"] == "Once":
            task["enabled"] = False
            task["next_run"] = None
        else:
            upcoming = next_after(task, now)
            task["next_run"] = upcoming.isoformat() if upcoming else None