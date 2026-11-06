import re
import secrets
import string

NAME = "Password maker"
DESCRIPTION = "Makes a strong random password on your laptop. Nothing goes online."
EXAMPLES = ["make a password", "generate password 20"]
TRIGGERS = ["make a password", "generate password", "generate a password"]


def handle(text):
    match = re.search(r"\b(\d{1,2})\b", text)
    length = min(max(int(match.group(1)), 8), 64) if match else 16
    letters = string.ascii_letters + string.digits + "!@#$%&*?"
    while True:
        password = "".join(secrets.choice(letters) for _ in range(length))
        if (any(c.islower() for c in password) and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password) and any(c in "!@#$%&*?" for c in password)):
            break
    return f"Your {length}-character password:\n{password}\nCopy it now. I do not save it."