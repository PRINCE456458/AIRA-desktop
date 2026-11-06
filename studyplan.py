import html
import json
import os
import re
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

import paths
import timetable  # reused for subject colors

BASE_DIR = paths.DATA_DIR
OUT_DIR = os.path.join(BASE_DIR, "plans")

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

HELP = (
    "To make a study plan website, type your exams and dates separated by semicolons:\n"
    "study plan: Maths 15 Dec; Physics 18 Dec; Python 20 Dec; 4 hours a day\n"
    "Write the subject, then the date (15 Dec, 15 December 2026 or 2026-12-15). "
    "The part about hours per day is optional (the default is 3)."
)

START = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?"
    r"(?:(?:make|create|build|generate|prepare)\s+(?:me\s+)?(?:a\s+|my\s+)?)?"
    r"(?:(?:study|exam|revision)\s*(?:plan|planner|schedule)|plan\s+my\s+exams?)\b",
    re.IGNORECASE,
)
SKIP = re.compile(r"\b(?:website|web\s?site|web\s?page|web\s?app|pdf|docx|app)\b", re.IGNORECASE)

DATE_PART = (
    r"(?:(\d{4})-(\d{1,2})-(\d{1,2})"
    r"|(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})(?:\s+(\d{4}))?)"
)
ENTRY = re.compile(r"^(.+?)\s+(?:on\s+)?" + DATE_PART + r"\s*$", re.IGNORECASE)
HOURS = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:a|per|each|/)?\s*(?:day|daily)", re.IGNORECASE
)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { --bg:#f4f1fa; --card:#ffffff; --text:#1f1535; --muted:#6b5f85; --line:#e0d8ef; --accent:#7b2cbf; --soft:#ece6f6; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#1a1025; --card:#241535; --text:#f0e6ff; --muted:#b7a6d6; --line:#3a2a52; --accent:#b794f4; --soft:#2f1e47; }
  }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Arial, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px 16px 48px; }
  main { max-width: 760px; margin: 0 auto; }
  h1 { margin: 0 0 4px; }
  p.sub { margin: 0 0 20px; color: var(--muted); }
  .exams { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 20px; }
  .exam { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; }
  .exam .n { font-size: 30px; font-weight: 700; color: var(--accent); }
  .exam .u { color: var(--muted); font-size: 13px; margin-left: 4px; }
  .exam b { display: block; margin-top: 4px; }
  .exam small { color: var(--muted); }
  .progress { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; margin-bottom: 18px; }
  .track { background: var(--soft); border-radius: 99px; height: 10px; margin-top: 8px; overflow: hidden; }
  #bar { background: var(--accent); height: 100%; width: 0; transition: width .3s; }
  .day { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; margin-bottom: 10px; }
  .day h3 { margin: 0 0 6px; font-size: 15px; color: var(--muted); }
  .day.today { border: 2px solid var(--accent); }
  .day.today h3::after { content: "  TODAY"; color: var(--accent); font-weight: 700; }
  .day.past { opacity: .55; }
  .task { display: flex; align-items: center; gap: 10px; padding: 6px 0; flex-wrap: wrap; }
  .task input { width: 18px; height: 18px; accent-color: var(--accent); }
  .chip { color: #1f1535; padding: 3px 10px; border-radius: 99px; font-weight: 600; font-size: 14px; }
  .what { flex: 1; min-width: 140px; }
  .hrs { color: var(--muted); font-size: 13px; }
  .examday { background: var(--accent); color: #fff; border-radius: 8px; padding: 6px 10px; font-weight: 700; margin: 4px 0; }
  .rest { color: var(--muted); padding: 4px 0; }
  footer { text-align: center; color: var(--muted); font-size: 13px; margin-top: 20px; }
</style>
</head>
<body>
<main>
<h1>__TITLE__</h1>
<p class="sub">__SUB__</p>
<div class="exams">__EXAMS__</div>
<div class="progress"><span id="progress"></span><div class="track"><div id="bar"></div></div></div>
__DAYS__
<footer>Made with Aira AI. Ticks are saved in this browser.</footer>
</main>
<script>
  var PLAN_ID = "__ID__";
  function iso(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function startOf(s) { var p = s.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  var now = new Date();
  var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  var todayIso = iso(today);

  document.querySelectorAll(".exam").forEach(function (el) {
    var left = Math.round((startOf(el.dataset.date) - today) / 86400000);
    el.querySelector(".n").textContent = left > 0 ? left : (left === 0 ? "Today" : "Done");
    el.querySelector(".u").textContent = left > 1 ? "days left" : (left === 1 ? "day left" : "");
  });

  document.querySelectorAll(".day").forEach(function (el) {
    if (el.dataset.date === todayIso) { el.classList.add("today"); }
    else if (el.dataset.date < todayIso) { el.classList.add("past"); }
  });

  var saved = {};
  try { saved = JSON.parse(localStorage.getItem("Aira-plan-" + PLAN_ID) || "{}"); } catch (e) {}
  var ticks = document.querySelectorAll(".tick");
  function update() {
    var done = 0;
    ticks.forEach(function (t) { if (t.checked) { done++; } });
    document.getElementById("progress").textContent = done + " of " + ticks.length + " study blocks done";
    document.getElementById("bar").style.width = (ticks.length ? 100 * done / ticks.length : 0) + "%";
  }
  ticks.forEach(function (t) {
    t.checked = !!saved[t.dataset.key];
    t.addEventListener("change", function () {
      saved[t.dataset.key] = t.checked;
      try { localStorage.setItem("Aira-plan-" + PLAN_ID, JSON.stringify(saved)); } catch (e) {}
      update();
    });
  });
  update();
</script>
</body>
</html>
"""


def resolve_date(groups, today):
    iso_y, iso_m, iso_d, day, month_name, year = groups
    try:
        if iso_y:
            return date(int(iso_y), int(iso_m), int(iso_d))
        month = MONTHS.get(month_name.lower()[:3])
        if not month:
            return None
        if year:
            return date(int(year), month, int(day))
        found = date(today.year, month, int(day))
        if found < today:
            found = date(today.year + 1, month, int(day))
        return found
    except ValueError:
        return None


def parse_request(body, today):
    """Return (exams, hours_per_day, skipped). Each exam is {'subject', 'date'}."""
    hours = 3.0
    match = HOURS.search(body)
    if match:
        hours = min(12.0, max(1.0, float(match.group(1))))

    pieces = [p for p in re.split(r"[;\n]+", body) if p.strip()]
    if len(pieces) == 1 and "," in pieces[0]:
        pieces = [p for p in pieces[0].split(",") if p.strip()]

    exams, skipped = [], []
    for piece in pieces:
        entry = ENTRY.match(piece.strip())
        if not entry:
            continue
        subject = entry.group(1).strip(" .,:-")[:40]
        when = resolve_date(entry.groups()[1:], today)
        if not subject or when is None:
            continue
        if when < today:
            skipped.append(f"{subject} ({when.isoformat()})")
            continue
        exams.append({"subject": subject, "date": when})
    return exams, hours, skipped


def describe(left, runway):
    if left == 1:
        return "Final revision, then rest well"
    progress = 1 - left / runway
    if progress < 0.5:
        return "Learn topics and make notes"
    if progress < 0.85:
        return "Practice questions and revise"
    return "Past papers and weak areas"


def allocate(day, exams, hours):
    """Share the day's study blocks (30 minutes each) between the most urgent exams."""
    scored = []
    for exam in exams:
        left = (exam["date"] - day).days
        if left <= 0:
            continue
        weight = 1.0 / left
        if left == 1:
            weight *= 3  # the day before an exam is almost all about that exam
        scored.append((weight, exam, left))
    if not scored:
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    scored = scored[:3]

    blocks = max(1, round(hours * 2))
    total = sum(item[0] for item in scored)
    raw = [item[0] / total * blocks for item in scored]
    given = [int(value) for value in raw]
    by_fraction = sorted(range(len(raw)), key=lambda i: raw[i] - given[i], reverse=True)
    for i in by_fraction[: blocks - sum(given)]:
        given[i] += 1

    tasks = []
    for (weight, exam, left), count in zip(scored, given):
        if count > 0:
            tasks.append({
                "subject": exam["subject"],
                "hours": count / 2,
                "what": describe(left, exam["runway"]),
            })
    return tasks


def build_days(exams, hours, today):
    for exam in exams:
        exam["runway"] = max(1, (exam["date"] - today).days)
    last = max(exam["date"] for exam in exams)
    capped = (last - today).days > 120
    end = today + timedelta(days=120) if capped else last

    days = []
    current = today
    while current <= end:
        days.append({
            "date": current,
            "exams": [e for e in exams if e["date"] == current],
            "tasks": allocate(current, exams, hours),
        })
        current += timedelta(days=1)
    return days, capped


def render_exams(exams):
    cards = []
    for exam in sorted(exams, key=lambda e: e["date"]):
        cards.append(
            f'<div class="exam" data-date="{exam["date"].isoformat()}">'
            f'<span class="n">-</span><span class="u"></span>'
            f'<b>{html.escape(exam["subject"])}</b>'
            f'<small>{exam["date"].strftime("%a %d %b %Y")}</small></div>'
        )
    return "".join(cards)


def render_days(days):
    out = []
    for day in days:
        iso = day["date"].isoformat()
        parts = []
        for exam in day["exams"]:
            parts.append(f'<div class="examday">Exam: {html.escape(exam["subject"])}</div>')
        for task in day["tasks"]:
            key = html.escape(f'{iso}|{task["subject"]}', quote=True)
            parts.append(
                f'<label class="task"><input type="checkbox" class="tick" data-key="{key}">'
                f'<span class="chip" style="background:{timetable.color_for(task["subject"])}">'
                f'{html.escape(task["subject"])}</span>'
                f'<span class="what">{html.escape(task["what"])}</span>'
                f'<span class="hrs">{task["hours"]:g} h</span></label>'
            )
        if not parts:
            parts.append('<div class="rest">Free day</div>')
        out.append(
            f'<section class="day" data-date="{iso}"><h3>{day["date"].strftime("%a %d %b")}</h3>'
            + "".join(parts) + "</section>"
        )
    return "\n".join(out)


def build_and_open(exams, hours, today, title):
    days, capped = build_days(exams, hours, today)
    plan_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    sub = f"About {hours:g} hours of study per day, with more time for the exam that is closest."
    if capped:
        sub += " Showing the next 120 days."
    page = (
        PAGE.replace("__TITLE__", html.escape(title))
        .replace("__SUB__", html.escape(sub))
        .replace("__EXAMS__", render_exams(exams))
        .replace("__DAYS__", render_days(days))
        .replace("__ID__", plan_id)
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"studyplan_{plan_id}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    webbrowser.open(Path(path).as_uri())
    return (
        f"Done! I made your study plan for {len(exams)} exam(s) ({len(days)} days) and "
        f"opened it in your browser.\nSaved at: {path}\n"
        "Tick the blocks as you finish them. To change the plan, type a new study plan "
        "message with the updated dates."
    )


def handle(text, name="You"):
    """Return Aira's reply if this is a study plan request, otherwise None."""
    cleaned = text.strip()
    if SKIP.search(cleaned):
        return None
    if cleaned.lower().strip(" .!?") in ("study plan help", "exam plan help"):
        return HELP
    match = START.match(cleaned)
    if not match:
        return None

    today = date.today()
    exams, hours, skipped = parse_request(cleaned[match.end():].lstrip(" :,-"), today)
    if not exams:
        if skipped:
            return "Those exam dates are already in the past: " + ", ".join(skipped) + "\n" + HELP
        return HELP
    title = "My Study Plan" if name == "You" else f"{name}'s Study Plan"
    reply = build_and_open(exams, hours, today, title)
    if skipped:
        reply += "\nLeft out (date already passed): " + ", ".join(skipped)
    return reply