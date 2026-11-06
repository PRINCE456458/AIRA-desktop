import html
import os
import re
import webbrowser
import paths
from datetime import datetime
from pathlib import Path

BASE_DIR = paths.DATA_DIR
OUT_DIR = os.path.join(BASE_DIR, "timetables")

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
    "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
}

HELP = (
    "To make a timetable website, type your lessons separated by semicolons, like this:\n"
    "create timetable: Mon 9-10 Maths; Mon 10-11 Physics; Tue 9-11 Python lab; Fri 2-3 English\n"
    "Write the day (Mon, Tue...), the start and end time, then the subject. "
    "Times from 1 to 7 count as afternoon unless you write am or pm."
)

TIME = r"(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm)\b)?"
ENTRY = re.compile(
    r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?\s+"
    + TIME + r"\s*(?:-|–|to)\s*" + TIME + r"\s+(.+)",
    re.IGNORECASE,
)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  body { font-family: "Segoe UI", Arial, sans-serif; background: #f4f1fa; color: #1f1535; margin: 0; padding: 24px; }
  h1 { text-align: center; margin: 0 0 4px; }
  p.sub { text-align: center; margin: 0 0 20px; color: #6b3fa0; }
  .wrap { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; min-width: 640px; background: #fff; border-radius: 12px; overflow: hidden; }
  th, td { border: 1px solid #e0d8ef; padding: 12px 10px; text-align: center; }
  th { background: #7b2cbf; color: #fff; }
  th.time { background: #ece6f6; color: #1f1535; white-space: nowrap; }
  td.empty { background: #fafafa; }
  th.today { background: #4a148c; }
  td.today { box-shadow: inset 0 0 0 3px #7b2cbf; font-weight: 600; }
  footer { text-align: center; margin-top: 18px; font-size: 13px; color: #7a6a99; }
  @media print { body { background: #fff; padding: 0; } footer { display: none; } }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<p class="sub">Today's column is highlighted</p>
<div class="wrap">
<table>
<thead><tr><th>Time</th>__HEAD__</tr></thead>
<tbody>
__ROWS__
</tbody>
</table>
</div>
<footer>Made with Aira AI</footer>
<script>
  var names = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  var today = names[new Date().getDay()];
  document.querySelectorAll('[data-day="' + today + '"]').forEach(function (el) {
    el.classList.add("today");
  });
</script>
</body>
</html>
"""


def to_minutes(hour, minute, ampm):
    hour = int(hour)
    minute = int(minute or 0)
    if hour > 23 or minute > 59:
        return None
    if ampm:
        hour = hour % 12
        if ampm.lower() == "pm":
            hour += 12
    elif 1 <= hour <= 7:
        hour += 12  # "2" with no am/pm means 2 in the afternoon
    return hour * 60 + minute


def parse_schedule(text):
    """Turn 'Mon 9-10 Maths; Tue 10-11 Physics' into a list of lessons."""
    entries = []
    for piece in re.split(r"[;\n]+", text):
        match = ENTRY.search(piece)
        if not match:
            continue
        day = match.group(1).lower()
        start = to_minutes(match.group(2), match.group(3), match.group(4))
        end = to_minutes(match.group(5), match.group(6), match.group(7))
        subject = match.group(8).strip(" .,!")
        if start is None or end is None or not subject:
            continue
        if end <= start:
            end = start + 60
        entries.append(
            {"day": day, "start": start, "end": end, "subject": subject[:60]}
        )
    return entries


def fmt(minutes):
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{minute:02d} {suffix}"


def color_for(subject):
    """The same subject always gets the same soft color."""
    hue = sum(ord(c) for c in subject.lower()) * 7 % 360
    return f"hsl({hue}, 70%, 86%)"


def build_html(title, entries):
    used = {e["day"] for e in entries}
    days = [d for d in DAY_ORDER if d in used or d in DAY_ORDER[:5]]
    slots = sorted({(e["start"], e["end"]) for e in entries})

    cells = {}
    for e in entries:
        cells.setdefault((e["start"], e["end"], e["day"]), []).append(e["subject"])

    head = "".join(f'<th data-day="{d}">{DAY_NAMES[d]}</th>' for d in days)

    rows = []
    for start, end in slots:
        tds = []
        for d in days:
            subjects = cells.get((start, end, d))
            if subjects:
                inner = "<br>".join(html.escape(s) for s in subjects)
                tds.append(
                    f'<td data-day="{d}" style="background:{color_for(subjects[0])}">{inner}</td>'
                )
            else:
                tds.append(f'<td data-day="{d}" class="empty"></td>')
        time_cell = f'<th class="time">{fmt(start)} - {fmt(end)}</th>'
        rows.append("<tr>" + time_cell + "".join(tds) + "</tr>")

    return (
        PAGE.replace("__TITLE__", html.escape(title))
        .replace("__HEAD__", head)
        .replace("__ROWS__", "\n".join(rows))
    )


def build_and_open(entries, title="My Timetable"):
    page = build_html(title, entries)
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUT_DIR, f"timetable_{stamp}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    webbrowser.open(Path(path).as_uri())
    return (
        f"Done! I made your timetable website with {len(entries)} lessons and opened it "
        f"in your browser. The file is saved at: {path}"
    )


def handle(text, name="You"):
    """Return Aira's reply if this is a timetable request, otherwise None."""
    lower = text.lower().strip(" .!?")
    if lower in ("timetable help", "help timetable", "help with timetable"):
        return HELP
    if "timetable" not in lower:
        return None
    entries = parse_schedule(text)
    if not entries:
        return None  # not a lesson list, so the AI answers normally
    title = "My Timetable" if name == "You" else f"{name}'s Timetable"
    return build_and_open(entries, title)