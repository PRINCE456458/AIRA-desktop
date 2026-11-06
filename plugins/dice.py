import random
import re

NAME = "Dice"
DESCRIPTION = "Rolls dice and flips coins."
EXAMPLES = ["roll a dice", "roll 3 dice", "flip a coin"]
TRIGGERS = ["roll", "flip"]


def handle(text):
    low = text.lower()
    if "coin" in low:
        return "It's " + random.choice(["heads", "tails"]) + "."
    if "dice" in low or "die" in low:
        match = re.search(r"\b(\d{1,2})\b", low)
        count = min(int(match.group(1)), 20) if match else 1
        rolls = [random.randint(1, 6) for _ in range(max(count, 1))]
        return "You rolled: " + ", ".join(map(str, rolls)) + (f"  (total {sum(rolls)})" if len(rolls) > 1 else "")
    return None