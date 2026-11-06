"""Aira license server.

Run it for testing:     python server.py run
Run it online:          gunicorn server:app   (or any host that runs Flask apps)

Commands:
    python server.py genkeys                make the signing keys (do this once)
    python server.py create EMAIL [DAYS]    make a license by hand (default 31 days)
    python server.py list                   show all licenses
    python server.py revoke KEY             stop a license
    python server.py reset-device KEY       let a license move to another laptop
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import sqlite3
import sys
import time
from collections import defaultdict, deque
from email.message import EmailMessage

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "licenses.db"))
KEY_FILE = os.environ.get("KEY_FILE", os.path.join(BASE_DIR, "private_key.pem"))
GRACE_DAYS = int(os.environ.get("GRACE_DAYS", "7"))      # how long Aira may work offline
PAYMENT_BUFFER_DAYS = 2                                    # slack for a late renewal payment
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"              # no 0/O or 1/I

app = Flask(__name__)
_attempts = defaultdict(lambda: deque(maxlen=30))


# ---------- database ----------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS licenses ("
            "key TEXT PRIMARY KEY, email TEXT, status TEXT NOT NULL, expires_at INTEGER NOT NULL,"
            "subscription_id TEXT, device TEXT, created_at INTEGER NOT NULL)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sub ON licenses(subscription_id)")
        conn.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, seen_at INTEGER)")


def new_key():
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(5)) for _ in range(4)]
    return "Aira-" + "-".join(groups)


def clean_key(text):
    return "".join(str(text).upper().split())


# ---------- signing ----------
def load_private():
    with open(KEY_FILE, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def public_b64(private):
    raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return base64.b64encode(raw).decode()


def sign(payload):
    text = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = load_private().sign(text.encode())
    return {"payload": text, "sig": base64.b64encode(signature).decode()}


# ---------- license rules ----------
def is_valid(row, now):
    return row["status"] in ("active", "cancelled") and row["expires_at"] > now


def token_for(row, device, now):
    return sign({
        "key": row["key"], "plan": "pro", "device": device,
        "expires": row["expires_at"], "issued": now,
        "valid_until": min(row["expires_at"], now + GRACE_DAYS * 86400),
    })


def fail(code, message, status):
    return jsonify({"ok": False, "code": code, "error": message}), status


def too_many():
    now = time.time()
    attempts = _attempts[request.remote_addr or "?"]
    attempts.append(now)
    recent = [t for t in attempts if now - t < 60]
    return len(recent) > 20


def read_request():
    data = request.get_json(silent=True) or {}
    return clean_key(data.get("key", "")), str(data.get("device", ""))[:80]


@app.post("/activate")
def activate():
    if too_many():
        return fail("slow_down", "Too many tries. Wait a minute.", 429)
    key, device = read_request()
    if not key or not device:
        return fail("bad_request", "Please send a license key.", 400)
    now = int(time.time())
    with db() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE key = ?", (key,)).fetchone()
        if not row:
            return fail("unknown_key", "That key was not found. Check it and try again.", 404)
        if not is_valid(row, now):
            return fail("expired", "This subscription has ended. Renew it to use Pro again.", 403)
        if row["device"] and row["device"] != device:
            return fail("other_device", "This key is already used on another laptop. "
                                        "Use 'Remove key' there first, or contact support.", 409)
        if not row["device"]:
            conn.execute("UPDATE licenses SET device = ? WHERE key = ?", (device, key))
    return jsonify({"ok": True, "token": token_for(row, device, now)})


@app.post("/verify")
def verify():
    if too_many():
        return fail("slow_down", "Too many tries. Wait a minute.", 429)
    key, device = read_request()
    now = int(time.time())
    with db() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE key = ?", (key,)).fetchone()
    if not row:
        return fail("unknown_key", "That key was not found.", 404)
    if row["device"] != device:
        return fail("other_device", "This key is used on another laptop.", 409)
    if not is_valid(row, now):
        return fail("expired", "This subscription has ended.", 403)
    return jsonify({"ok": True, "token": token_for(row, device, now)})


@app.post("/deactivate")
def deactivate():
    key, device = read_request()
    with db() as conn:
        conn.execute("UPDATE licenses SET device = NULL WHERE key = ? AND device = ?", (key, device))
    return jsonify({"ok": True})


@app.get("/health")
def health():
    return jsonify({"ok": True})


# ---------- payments (Razorpay) ----------
def send_key_email(email, key):
    """Email the key if SMTP settings exist. Otherwise just print it for you to send."""
    print(f"[license] new key for {email}: {key}", flush=True)
    host = os.environ.get("SMTP_HOST")
    if not host or not email:
        return
    try:
        message = EmailMessage()
        message["Subject"] = "Your Aira Pro license key"
        message["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", ""))
        message["To"] = email
        message.set_content(
            f"Thank you for subscribing to Aira Pro!\n\nYour license key:\n{key}\n\n"
            "Open Aira, click Pro, paste the key and press Activate."
        )
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except Exception as error:
        print(f"[license] could not email {email}: {error}", flush=True)


def as_dict(value):
    return value if isinstance(value, dict) else {}


@app.post("/webhook/razorpay")
def razorpay_webhook():
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret:
        return fail("not_configured", "Webhook secret is not set on the server.", 500)
    raw = request.get_data()
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-Razorpay-Signature", "")):
        return fail("bad_signature", "Signature does not match.", 401)

    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(raw).hexdigest()
    body = as_dict(request.get_json(silent=True))
    event = body.get("event", "")
    payload = as_dict(body.get("payload"))
    sub = as_dict(as_dict(payload.get("subscription")).get("entity"))
    pay = as_dict(as_dict(payload.get("payment")).get("entity"))
    sub_id = sub.get("id")
    now = int(time.time())
    email_to_send = None

    with db() as conn:
        added = conn.execute("INSERT OR IGNORE INTO events VALUES (?, ?)", (event_id, now)).rowcount
        if not added:
            return jsonify({"ok": True, "note": "already handled"})
        if not sub_id:
            return jsonify({"ok": True, "note": "not a subscription event"})
        row = conn.execute("SELECT * FROM licenses WHERE subscription_id = ?", (sub_id,)).fetchone()

        if event in ("subscription.activated", "subscription.charged"):
            period_end = sub.get("current_end")
            period_end = int(period_end) if isinstance(period_end, (int, float)) else now + 31 * 86400
            expires = period_end + PAYMENT_BUFFER_DAYS * 86400
            if row:
                conn.execute(
                    "UPDATE licenses SET status = 'active', expires_at = MAX(expires_at, ?) WHERE key = ?",
                    (expires, row["key"]),
                )
            else:
                email = pay.get("email") or as_dict(sub.get("notes")).get("email") or ""
                key = new_key()
                conn.execute(
                    "INSERT INTO licenses (key, email, status, expires_at, subscription_id, created_at) "
                    "VALUES (?, ?, 'active', ?, ?, ?)", (key, email, expires, sub_id, now),
                )
                email_to_send = (email, key)
        elif event == "subscription.cancelled" and row:
            conn.execute("UPDATE licenses SET status = 'cancelled' WHERE key = ?", (row["key"],))
        elif event in ("subscription.halted", "subscription.completed", "subscription.expired") and row:
            conn.execute(
                "UPDATE licenses SET status = 'expired', expires_at = ? WHERE key = ?", (now, row["key"])
            )

    if email_to_send:
        send_key_email(*email_to_send)
    return jsonify({"ok": True})


# ---------- command line ----------
def cli(argv):
    command = argv[1] if len(argv) > 1 else "run"
    if command == "genkeys":
        if os.path.exists(KEY_FILE):
            print("private_key.pem already exists. Not overwriting it.")
            return
        private = Ed25519PrivateKey.generate()
        with open(KEY_FILE, "wb") as f:
            f.write(private.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
        try:
            os.chmod(KEY_FILE, 0o600)
        except OSError:
            pass
        print("Created private_key.pem. KEEP IT SECRET and back it up.")
        print("Paste this PUBLIC key into pro.py (PUBLIC_KEY):")
        print(public_b64(private))
    elif command == "publickey":
        print(public_b64(load_private()))
    elif command == "create":
        email = argv[2] if len(argv) > 2 else ""
        days = int(argv[3]) if len(argv) > 3 else 31
        key = new_key()
        now = int(time.time())
        with db() as conn:
            conn.execute(
                "INSERT INTO licenses (key, email, status, expires_at, created_at) VALUES (?, ?, 'active', ?, ?)",
                (key, email, now + days * 86400, now),
            )
        print(key)
    elif command == "list":
        with db() as conn:
            for row in conn.execute("SELECT * FROM licenses ORDER BY created_at DESC"):
                ends = time.strftime("%d %b %Y", time.localtime(row["expires_at"]))
                print(f"{row['key']}  {row['status']:<9} ends {ends}  {row['email'] or '-'}  "
                      f"{'in use' if row['device'] else 'free'}")
    elif command == "revoke" and len(argv) > 2:
        with db() as conn:
            conn.execute("UPDATE licenses SET status = 'expired', expires_at = ? WHERE key = ?",
                         (int(time.time()), clean_key(argv[2])))
        print("Revoked.")
    elif command == "reset-device" and len(argv) > 2:
        with db() as conn:
            conn.execute("UPDATE licenses SET device = NULL WHERE key = ?", (clean_key(argv[2]),))
        print("Done. The key can be used on a new laptop.")
    elif command == "run":
        app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
    else:
        print(__doc__)


init_db()

if __name__ == "__main__":
    cli(sys.argv)