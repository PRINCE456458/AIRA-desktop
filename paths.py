# One place for everything Aira saves (chats, settings, memory, notes, builds, images...).
# It lives in the user's AppData folder, not next to main.py, because an installed app
# (a Microsoft Store app or a PyInstaller .exe) is not allowed to write into its own folder.
import os


def _make_data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "AiraAI")
    os.makedirs(folder, exist_ok=True)
    return folder


DATA_DIR = _make_data_dir()