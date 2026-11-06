from datetime import date
import re

NAME = "Countdown"
DESCRIPTION = "Counts the days until a date (day-month-year)."
EXAMPLES = ["days until 25-12-2026", "countdown 01-01-2027"]
TRIGGERS = ["days until", "countdown"]


def handle(text):
    match = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", text)
    if not match:
        return "Give a date like: days until 25-12-2026"
    try:
        target = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return "That date doesn't exist. Use day-month-year, like 25-12-2026."
    days = (target - date.today()).days
    if days > 0:
        return f"{days} days until {target.strftime('%d %B %Y')}."
    if days == 0:
        return "That date is today!"
    return f"{-days} days have passed since {target.strftime('%d %B %Y')}."