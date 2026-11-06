import base64
import hashlib
import json
import os
import platform
import time
import uuid

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(BASE_DIR, "pro.json")

# ----- Set these three after you set up your server and your payment page -----
SERVER_URL = "http://127.0.0.1:5000"        # your online server address, for example https://Aira-license.example.com
PUBLIC_KEY = "PASTE_PUBLIC_KEY_HERE"        # printed by: python server.py genkeys
UPGRADE_URL = "https://example.com/Aira-pro"  # your Razorpay subscription link or your pricing page
# -------------------------------------------------------------------------------

FREE_LIMITS = {"tasks": 2, "projects": 2}
PRO_LIMITS = {"tasks": 30, "projects": 30}
CHECK_EVERY = 12 * 3600       # ask the server again after this long
RENEW_BEFORE = 2 * 86400      # or when the offline pass has less than this left
TIMEOUT = 12


def device_id():
    seed = f"{platform.node()}|{uuid.getnode()}|{platform.system()}"
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def clean_key(text):
    return "".join(str(text).upper().split())


class ProState:
    def __init__(self, path=FILE, server=None, public_key=None, clock=time.time):
        self.path = path
        self.server = (server or SERVER_URL).rstrip("/")
        self.public_key = public_key or PUBLIC_KEY
        self.clock = clock
        self.device = device_id()
        self.data = {}
        self._load()

    # ----- saved state -----
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.data = data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    # ----- reading the signed pass -----
    def _token(self):
        """Return the pass details if the signature is real, otherwise None."""
        token = self.data.get("token")
        if not isinstance(token, dict):
            return None
        try:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(self.public_key))
            key.verify(base64.b64decode(token["sig"]), token["payload"].encode())
            info = json.loads(token["payload"])
        except (InvalidSignature, ValueError, KeyError, TypeError):
            return None
        if info.get("device") != self.device or info.get("key") != self.data.get("key"):
            return None
        return info

    def clock_ok(self):
        """Turning the laptop clock back must not give free time."""
        seen = self.data.get("seen", 0)
        return self.clock() >= seen - 86400

    def _touch(self):
        now = self.clock()
        if now > self.data.get("seen", 0):
            self.data["seen"] = now
            self._save()

    def is_pro(self):
        info = self._token()
        if not info or not self.clock_ok():
            return False
        ok = self.clock() < info.get("valid_until", 0)
        if ok:
            self._touch()
        return ok

    def plan(self):
        return "pro" if self.is_pro() else "free"

    def limit(self, name):
        return (PRO_LIMITS if self.is_pro() else FREE_LIMITS).get(name, 0)

    def needs_refresh(self):
        if not self.data.get("key"):
            return False
        info = self._token()
        if not info:
            return True
        now = self.clock()
        if info["valid_until"] - now < RENEW_BEFORE:
            return True
        return now - self.data.get("checked", 0) > CHECK_EVERY

    def status_text(self):
        key = self.data.get("key")
        if self.is_pro():
            info = self._token()
            ends = time.strftime("%d %b %Y", time.localtime(info["expires"]))
            return f"Pro is active. Your subscription runs until {ends}."
        if key and not self.clock_ok():
            return "Your laptop clock looks wrong, so Pro is paused. Fix the date and connect to the internet."
        if key and self._token():
            return "Pro is paused because Aira could not check your subscription for a while. Connect to the internet."
        if key:
            return "A key is saved, but Pro is not active. Press 'Check again'."
        return "You are on the Free plan."

    # ----- talking to the server -----
    def _call(self, path, key):
        try:
            reply = requests.post(
                self.server + path, json={"key": key, "device": self.device}, timeout=TIMEOUT,
            )
        except requests.exceptions.RequestException:
            return None, "offline", "Could not reach the license server. Check your internet and try again."
        try:
            body = reply.json()
        except ValueError:
            return None, "bad_reply", "The license server sent something I did not understand."
        if reply.status_code == 200 and body.get("ok"):
            return body["token"], "ok", ""
        return None, body.get("code", "error"), body.get("error", "The server said no.")

    def _accept(self, key, token):
        previous = (self.data.get("key"), self.data.get("token"))
        self.data.update({"key": key, "token": token, "checked": self.clock()})
        if not self._token():
            self.data["key"], self.data["token"] = previous    # a fake or damaged reply
            if previous[0] is None:
                self.data.pop("key", None)
                self.data.pop("token", None)
            return False
        self.data["seen"] = self._token()["issued"]    # the server's clock is the truth
        self._save()
        return True

    def activate(self, key):
        key = clean_key(key)
        if len(key) < 10:
            return False, "Please paste your license key."
        if self.public_key.startswith("PASTE_"):
            return False, "Pro is not set up yet: the PUBLIC_KEY in pro.py is empty."
        token, code, message = self._call("/activate", key)
        if code != "ok":
            return False, message
        if not self._accept(key, token):
            return False, "The server's answer could not be verified. Check PUBLIC_KEY in pro.py."
        return True, "Pro is now active. Thank you!"

    def refresh(self):
        """Ask the server again. Offline is fine, Aira keeps the current pass."""
        key = self.data.get("key")
        if not key:
            return False, "No key saved."
        token, code, message = self._call("/verify", key)
        if code == "ok":
            if self._accept(key, token):
                return True, "Your subscription is active."
            return False, "The server's answer could not be verified."
        if code in ("offline", "bad_reply", "slow_down", "error"):
            return False, message
        self.data.pop("token", None)       # expired, revoked, or moved to another laptop
        self.data["checked"] = self.clock()
        self._save()
        return False, message

    def deactivate(self):
        """Free this key so it can be used on another laptop."""
        key = self.data.get("key")
        if key:
            try:
                requests.post(
                    self.server + "/deactivate", json={"key": key, "device": self.device}, timeout=TIMEOUT,
                )
            except requests.exceptions.RequestException:
                pass
        for name in ("key", "token", "checked"):
            self.data.pop(name, None)
        self._save()