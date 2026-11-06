import json
import os
import time

import paths

BASE_DIR = paths.DATA_DIR
CHATS_FILE = os.path.join(BASE_DIR, "chats.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "user_name": "You",
    "model": "llama3.2:3b",
    "vision_model": "moondream",
    "system_prompt": "You are Aira, a friendly and helpful AI assistant. Keep answers clear and simple.",
    "speak_replies": True,
    "theme": "Purple dark",
    "voice_rate": 175,
    "temperature": 0.7,
}


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_settings():
    settings = DEFAULT_SETTINGS.copy()
    settings.update(_load_json(SETTINGS_FILE, {}))
    return settings


def save_settings(settings):
    _save_json(SETTINGS_FILE, settings)


def load_chats():
    return _load_json(CHATS_FILE, [])


def save_chats(chats):
    _save_json(CHATS_FILE, chats)


def new_chat():
    return {"id": str(int(time.time() * 1000)), "title": "New chat", "messages": []}