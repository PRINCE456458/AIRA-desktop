import html
import json
import os
import re
import webbrowser
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(BASE_DIR, "expenses.json")
OUT_DIR = os.path.join(BASE_DIR, "expense_reports")
CURRENCY = "\u20b9"  # the rupee sign

HELP = (
    "To track spending, type for example:\n"
    "- spent 250 on lunch\n"
    "- paid 1200 for wifi bill yesterday\n"
    "Ask: how much did I spend this week?  |  expenses this month  |  show expenses\n"
    "Other commands: set budget 10000, delete last expense, delete expense 2, expense report"
)

# Aira guesses the category from these words. Add your own words freely.
CATEGORIES = {
    "Food": ["lunch", "dinner", "breakfast", "food", "snack", "snacks", "tea", "coffee",
             "pizza", "burger", "biryani", "restaurant", "canteen", "juice", "icecream", "meal"],
    "Groceries": ["grocery", "groceries", "vegetables", "fruits", "milk", "supermarket", "kirana"],
    "Transport": ["bus", "auto", "uber", "ola", "rapido", "taxi", "cab", "petrol", "fuel",
                  "metro", "train", "ticket", "parking", "diesel"],
    "Shopping": ["clothes", "shirt", "shoes", "jeans", "amazon", "flipkart", "myntra", "bag", "watch"],
    "Bills": ["recharge", "rent", "electricity", "wifi", "internet", "bill", "water", "gas", "mobile"],
    "Entertainment": ["movie", "game", "games", "netflix", "party", "concert", "spotify", "trip"],
    "Health": ["medicine", "doctor", "hospital", "pharmacy", "gym", "checkup"],
}

AMOUNT = r"(\d[\d,]*(?:\.\d+)?)"
ADD = re.compile(
    r"^(?:i\s+)?(?:just\s+)?(?:spent|paid|add\s+expense|expense)\s*:?\s*(?:rs\.?|inr|\u20b9)?\s*"
    + AMOUNT + r"\s*(?:rs\.?|rupees|inr|\u20b9)?\s*(?:on|for|at)?\s*(.*)$",
    re.IGNORECASE,
)
TIME_UNITS = re.compile(r"^(?:hours?|hrs?|minutes?|mins?|days?|weeks?|months?|years?)\b", re.IGNORECASE)
BUDGET = re.compile(
    r"^set\s+(?:a\s+|my\s+)?(?:monthly\s+)?budget\s*(?:to|of|:)?\s*(?:rs\.?|inr|\u20b9)?\s*" + AMOUNT,
    re.IGNORECASE,
)
QUERY = re.compile(
    r"^(?:how\s+much\s+(?:did\s+i|have\s+i|do\s+i)\s+spen[dt]|what\s+did\s+i\s+spend"
    r"|(?:my\s+)?(?:expenses?|spending)(?:\s+summary)?\b)",
    re.IGNORECASE,
)
LIST_WORDS = {"show expenses", "my expenses", "list expenses", "recent expenses", "show my expenses"}

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
  p.sub { margin: 0 0 18px; color: var(--muted); }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin-bottom: 14px; }
  .total { font-size: 34px; font-weight: 700; color: var(--accent); }
  .bar { display: flex; align-items: center; gap: 10px; margin: 8px 0; }
  .name { width: 110px; flex: none; }
  .track { flex: 1; background: var(--soft); border-radius: 99px; height: 14px; overflow: hidden; }
  .fill { display: block; height: 100%; border-radius: 99px; }
  .amt { width: 90px; text-align: right; flex: none; font-variant-numeric: tabular-nums; }
  .budget { height: 10px; background: var(--soft); border-radius: 99px; overflow: hidden; margin-top: 8px; }
  .budget span { display: block; height: 100%; background: var(--accent); }
  .over span { background: #d64545; }
  .wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--line); }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  th { color: var(--muted); font-weight: 600; font-size: 13px; }
  footer { text-align: center; color: var(--muted); font-size: 13px; margin-top: 20px; }
</style>
</head>
<body>
<main>
<h1>__TITLE__</h1>
<p class="sub">__SUB__</p>
<div class="card"><div class="total">__TOTAL__</div>__BUDGET__</div>
<div class="card"><h3 style="margin-top:0">By category</h3>__BARS__</div>
<div class="card"><h3 style="margin-top:0">All entries</h3>
<div class="wrap"><table>
<tr><th>Date</th><th>What</th><th>Category</th><th class="num">Amount</th></tr>
__ROWS__
</table></div></div>
<footer>Made with Aira AI</footer>
</main>
</body>
</html>
"""


def fmt(value):
    if abs(value - round(value)) < 0.005:
        return f"{CURRENCY}{value:,.0f}"
    return f"{CURRENCY}{value:,.2f}"


def guess_category(note):
    words = set(re.findall(r"[a-z]+", note.lower()))
    for category, keywords in CATEGORIES.items():
        if words.intersection(keywords):
            return category
    return "Other"


def color_for(category):
    hue = sum(ord(c) for c in category.lower()) * 7 % 360
    return f"hsl({hue}, 65%, 55%)"


def period_range(text, today):
    """Return (start date, end date, label) for words like 'this week'."""
    lower = text.lower()
    if "last month" in lower:
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end, "last month"
    if "this month" in lower:
        return today.replace(day=1), today, "this month"
    if "this week" in lower:
        return today - timedelta(days=today.weekday()), today, "this week"
    if "yesterday" in lower:
        day = today - timedelta(days=1)
        return day, day, "yesterday"
    if "today" in lower:
        return today, today, "today"
    return None, None, "in total"


class ExpenseStore:
    def __init__(self):
        self.items = []
        self.budget = 0
        self._load()

    def _load(self):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.items = [i for i in data.get("items", []) if "amount" in i and "date" in i]
            self.budget = float(data.get("budget", 0) or 0)
        except (FileNotFoundError, json.JSONDecodeError, AttributeError, ValueError):
            self.items, self.budget = [], 0

    def _save(self):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump({"budget": self.budget, "items": self.items}, f, indent=2, ensure_ascii=False)

    def _in_range(self, start, end):
        if start is None:
            return list(self.items)
        return [i for i in self.items if start <= date.fromisoformat(i["date"]) <= end]

    def _newest_first(self):
        return sorted(self.items, key=lambda i: (i["date"], i["id"]), reverse=True)

    def month_total(self):
        today = date.today()
        return sum(i["amount"] for i in self._in_range(today.replace(day=1), today))

    # ----- replies -----
    def add(self, amount, note, when):
        category = guess_category(note)
        next_id = max([i["id"] for i in self.items] + [0]) + 1
        self.items.append({
            "id": next_id, "amount": amount, "note": note or "Expense",
            "category": category, "date": when.isoformat(),
        })
        self._save()
        reply = f"Saved: {fmt(amount)} for {note or 'Expense'} ({category}, {when.strftime('%a %d %b')})."
        if self.budget:
            left = self.budget - self.month_total()
            reply += (
                f"\nBudget left this month: {fmt(left)}." if left >= 0
                else f"\nYou are over this month's budget by {fmt(-left)}."
            )
        return reply

    def summary(self, text):
        today = date.today()
        start, end, label = period_range(text, today)
        rows = self._in_range(start, end)
        if not rows:
            return f"No expenses recorded {label}. " + HELP.split("\n")[0]
        total = sum(i["amount"] for i in rows)
        by_category = {}
        for item in rows:
            by_category[item["category"]] = by_category.get(item["category"], 0) + item["amount"]
        lines = [f"Spending {label}: {fmt(total)} in {len(rows)} entries"]
        for category, amount in sorted(by_category.items(), key=lambda pair: -pair[1]):
            bar = "\u2588" * max(1, round(10 * amount / total))
            lines.append(f"- {category}: {fmt(amount)} ({round(100 * amount / total)}%) {bar}")
        if self.budget and label == "this month":
            left = self.budget - total
            lines.append(
                f"Budget {fmt(self.budget)}: {fmt(left)} left." if left >= 0
                else f"Budget {fmt(self.budget)}: over by {fmt(-left)}."
            )
        return "\n".join(lines)

    def listing(self):
        recent = self._newest_first()[:10]
        if not recent:
            return "No expenses yet. " + HELP.split("\n")[0]
        lines = ["Your last expenses (newest first):"]
        for number, item in enumerate(recent, 1):
            when = date.fromisoformat(item["date"]).strftime("%d %b")
            lines.append(f"{number}. {when}  {fmt(item['amount'])}  {item['note']}  ({item['category']})")
        return "\n".join(lines)

    def report(self, text):
        today = date.today()
        start, end, label = period_range(text, today)
        if start is None:
            start, end, label = today.replace(day=1), today, "this month"
        rows = self._in_range(start, end)
        if not rows:
            return f"No expenses recorded {label}, so there is nothing to report yet."

        total = sum(i["amount"] for i in rows)
        by_category = {}
        for item in rows:
            by_category[item["category"]] = by_category.get(item["category"], 0) + item["amount"]
        top = max(by_category.values())

        bars = "".join(
            f'<div class="bar"><span class="name">{html.escape(c)}</span>'
            f'<span class="track"><span class="fill" style="width:{100 * a / top:.0f}%;background:{color_for(c)}"></span></span>'
            f'<span class="amt">{fmt(a)}</span></div>'
            for c, a in sorted(by_category.items(), key=lambda pair: -pair[1])
        )
        table = "\n".join(
            f'<tr><td>{date.fromisoformat(i["date"]).strftime("%d %b")}</td>'
            f'<td>{html.escape(i["note"])}</td><td>{html.escape(i["category"])}</td>'
            f'<td class="num">{fmt(i["amount"])}</td></tr>'
            for i in sorted(rows, key=lambda i: (i["date"], i["id"]), reverse=True)
        )

        budget_html = ""
        if self.budget and label == "this month":
            used = min(100, 100 * total / self.budget)
            over = " over" if total > self.budget else ""
            left = self.budget - total
            note = f"{fmt(left)} left of {fmt(self.budget)}" if left >= 0 else f"over {fmt(self.budget)} by {fmt(-left)}"
            budget_html = f'<div class="budget{over}"><span style="width:{used:.0f}%"></span></div><p class="sub">{note}</p>'

        title = f"Expense Report ({label})"
        page = (
            PAGE.replace("__TITLE__", html.escape(title))
            .replace("__SUB__", f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}, {len(rows)} entries")
            .replace("__TOTAL__", fmt(total))
            .replace("__BUDGET__", budget_html)
            .replace("__BARS__", bars)
            .replace("__ROWS__", table)
        )
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, f"report_{today.isoformat()}_{label.replace(' ', '-')}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        webbrowser.open(Path(path).as_uri())
        return f"Done! I opened your expense report for {label}.\nSaved at: {path}"

    def handle(self, text):
        """Return Aira's reply if this is an expense message, otherwise None."""
        cleaned = text.strip()
        lower = cleaned.lower().strip(" .!?")

        if re.match(r"^(?:make\s+(?:me\s+)?(?:an?\s+)?|show\s+(?:me\s+)?(?:my\s+)?|open\s+(?:my\s+)?)?expense\s+report\b", lower):
            return self.report(lower)
        if lower in LIST_WORDS:
            return self.listing()
        if lower in ("show budget", "my budget", "budget"):
            if not self.budget:
                return "You have no budget yet. Type: set budget 10000"
            left = self.budget - self.month_total()
            return f"Monthly budget: {fmt(self.budget)}. " + (
                f"Left this month: {fmt(left)}." if left >= 0 else f"Over by {fmt(-left)}."
            )

        if lower in ("delete last expense", "undo expense", "remove last expense"):
            if not self.items:
                return "There are no expenses to delete."
            newest = max(self.items, key=lambda i: i["id"])
            self.items.remove(newest)
            self._save()
            return f"Removed your last entry: {fmt(newest['amount'])} for {newest['note']}."
        remove = re.match(r"^(?:delete|remove)\s+expense\s+(\d+)$", lower)
        if remove:
            recent = self._newest_first()[:10]
            number = int(remove.group(1))
            if 1 <= number <= len(recent):
                gone = recent[number - 1]
                self.items.remove(gone)
                self._save()
                return f"Removed: {fmt(gone['amount'])} for {gone['note']}."
            return "There is no expense with that number. Type 'show expenses' to see the list."
        if lower == "clear expenses":
            return "This deletes ALL your expenses. If you are sure, type: clear expenses confirm"
        if lower == "clear expenses confirm":
            count = len(self.items)
            self.items = []
            self._save()
            return f"Done. I removed {count} expense(s)."

        budget = BUDGET.match(cleaned)
        if budget:
            value = float(budget.group(1).replace(",", ""))
            if value <= 0:
                return "A budget must be more than zero."
            self.budget = value
            self._save()
            return f"Monthly budget set to {fmt(value)}. I will show how much is left when you add expenses."

        add = ADD.match(cleaned)
        if add:
            rest = add.group(2).strip()
            if TIME_UNITS.match(rest):
                return None  # for example "spent 3 hours on this", which is not money
            try:
                amount = float(add.group(1).replace(",", ""))
            except ValueError:
                return None
            if amount <= 0 or amount > 10_000_000:
                return "That amount does not look right. Please check it."
            when = date.today()
            if re.search(r"\byesterday\b", rest, re.IGNORECASE):
                when -= timedelta(days=1)
            note = re.sub(r"\b(?:yesterday|today)\b", " ", rest, flags=re.IGNORECASE)
            note = re.sub(r"\s+", " ", note).strip(" ,.:;-")
            return self.add(amount, note[:60], when)

        if QUERY.match(cleaned):
            return self.summary(lower)
        return None