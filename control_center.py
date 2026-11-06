# The "All settings" window: a list of sections on the left, the chosen page on the right.
# Sections with real controls are built by build_... methods below.
# Every other section shows a "coming soon" page until you build it.
import os

import customtkinter as ctk

import checks
import storage
import themes

SECTIONS = [
    "General", "Appearance", "Notifications", "Profile", "Security and login",
    "Account", "Archived chats", "Parental controls", "Safety & wellbeing", "Voice",
    "Storage", "Personalization", "Pets", "Keyboard", "Usage", "Billing",
    "Data controls", "Integrations", "Plugins", "Passwords", "Spending", "Code Review",
]

NO_ACCOUNT = (
    "Aira runs only on your laptop, so there is no account, login or payment to manage yet. "
    "This page is a placeholder for later."
)

COMING_SOON = {
    "Notifications": "Reminders already work (Phase 27). Notification sound and pop-up options will go here.",
    "Security and login": NO_ACCOUNT,
    "Account": NO_ACCOUNT,
    "Archived chats": "Archiving needs an \"archived\" flag on each chat. We can add that as the next step.",
    "Parental controls": "Limits for younger users will go here, such as blocked topics.",
    "Safety & wellbeing": "Break reminders and topic filters will go here.",
    "Pets": "A small pet companion for the chat window. This is a fun idea for later.",
    "Billing": NO_ACCOUNT,
    "Integrations": "Connections to other apps and services will go here.",
    "Plugins": "Plugins are not built yet. This page will list them once they exist.",
    "Passwords": NO_ACCOUNT,
    "Spending": "Your expense tracker (Phase 28) could show its summary here.",
    "Code Review": "A tool that reviews your code files will go here.",
}

SHORTCUTS = [
    ("Ctrl + N", "New chat"),
    ("Ctrl + F", "Search chats"),
    ("Ctrl + L", "Jump to the message box"),
    ("Ctrl + E", "Export chat"),
]

# Files and folders that Aira creates next to main.py (only the ones that exist are shown).
DATA_ITEMS = [
    "chats.json", "settings.json", "memory.json", "knowledge.json", "notes.txt",
    "reminders.json", "expenses.json", "images", "builds", "timetables", "plans",
    "expense_reports",
]


def size_of(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for folder, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(folder, name))
            except OSError:
                pass
    return total


def human(size):
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def open_in_explorer(path):
    try:
        os.startfile(path)  # Windows only
    except Exception:
        pass


class ControlCenter(ctk.CTkToplevel):
    def __init__(self, app, T):
        super().__init__(app)
        self.app = app
        self.T = T
        self.title("Aira - All settings")
        self.geometry("900x620")
        self.minsize(760, 520)
        self.configure(fg_color=T["bg"])
        self.after(100, self.focus)

        self.status = ctk.CTkLabel(self, text="", text_color=T["status"], anchor="e")
        self.status.pack(side="bottom", fill="x", padx=16, pady=6)

        self.nav = ctk.CTkScrollableFrame(self, width=200, fg_color=T["sidebar"], corner_radius=0)
        self.nav.pack(side="left", fill="y")
        self.content = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        self.builders = {
            "General": self.build_general,
            "Appearance": self.build_appearance,
            "Profile": self.build_profile,
            "Voice": self.build_voice,
            "Storage": self.build_storage,
            "Personalization": self.build_personalization,
            "Keyboard": self.build_keyboard,
            "Usage": self.build_usage,
            "Data controls": self.build_data_controls,
        }

        self.buttons = {}
        for name in SECTIONS:
            button = ctk.CTkButton(
                self.nav, text=name, anchor="w", height=32,
                fg_color="transparent", text_color=T["text"], hover_color=T["button"],
                command=lambda n=name: self.show(n),
            )
            button.pack(fill="x", padx=6, pady=2)
            self.buttons[name] = button

        self.show("General")

    # ---------- Page switching ----------
    def show(self, name):
        T = self.T
        for section, button in self.buttons.items():
            button.configure(fg_color=T["accent"] if section == name else "transparent")
        for child in self.content.winfo_children():
            child.destroy()
        self.say("")

        page = ctk.CTkScrollableFrame(self.content, fg_color=T["bg"], corner_radius=0)
        page.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(
            page, text=name, text_color=T["text"], anchor="w",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(fill="x", padx=20, pady=(10, 6))

        builder = self.builders.get(name)
        if builder:
            builder(page)
        else:
            self.note(page, COMING_SOON.get(name, "Coming soon."))

    # ---------- Small building blocks ----------
    def say(self, text):
        self.status.configure(text=text)
        if text:
            self.after(3000, lambda: self.status.configure(text=""))

    def label(self, page, text):
        ctk.CTkLabel(page, text=text, text_color=self.T["text"], anchor="w").pack(
            fill="x", padx=20, pady=(14, 4))

    def note(self, page, text):
        ctk.CTkLabel(
            page, text=text, text_color=self.T["status"], anchor="w",
            justify="left", wraplength=560,
        ).pack(fill="x", padx=20, pady=(4, 8))

    def entry(self, page, value):
        box = ctk.CTkEntry(page, fg_color=self.T["panel"], border_color=self.T["accent"],
                           text_color=self.T["text"])
        box.insert(0, value)
        box.pack(fill="x", padx=20)
        return box

    def row(self, page, left, right):
        frame = ctk.CTkFrame(page, fg_color=self.T["panel"])
        frame.pack(fill="x", padx=20, pady=3)
        ctk.CTkLabel(frame, text=left, text_color=self.T["text"], anchor="w").pack(
            side="left", padx=12, pady=6)
        ctk.CTkLabel(frame, text=right, text_color=self.T["status"], anchor="e").pack(
            side="right", padx=12, pady=6)

    def button(self, page, text, command):
        ctk.CTkButton(
            page, text=text, fg_color=self.T["accent"], hover_color=self.T["accent_hover"],
            command=command,
        ).pack(anchor="w", padx=20, pady=16)

    def save(self, **changes):
        app = self.app
        app.settings.update(changes)
        storage.save_settings(app.settings)
        if "voice_rate" in changes:
            app.speaker.rate = app.settings["voice_rate"]
        if not app.is_busy:
            app.render_chat()
        self.say("Saved")

    # ---------- Sections ----------
    def build_general(self, page):
        T = self.T
        self.label(page, "Chat model (installed in Ollama)")
        installed = checks.list_models()
        current = self.app.settings["model"]
        if current not in installed:
            installed.insert(0, current)
        model_menu = ctk.CTkOptionMenu(
            page, values=installed, fg_color=T["button"], button_color=T["button_hover"],
            button_hover_color=T["accent"], text_color=T["text"],
        )
        model_menu.set(current)
        model_menu.pack(fill="x", padx=20)

        self.label(page, "Vision model (for pictures)")
        vision_entry = self.entry(page, self.app.settings["vision_model"])

        self.button(page, "Save", lambda: self.save(
            model=model_menu.get(),
            vision_model=vision_entry.get().strip() or "moondream",
        ))

    def build_appearance(self, page):
        T = self.T
        self.label(page, "Theme")
        theme_menu = ctk.CTkOptionMenu(
            page, values=list(themes.THEMES.keys()), fg_color=T["button"],
            button_color=T["button_hover"], button_hover_color=T["accent"],
            text_color=T["text"],
        )
        theme_menu.set(self.app.settings["theme"])
        theme_menu.pack(fill="x", padx=20)
        self.note(page, "Close and reopen Aira to see the new theme.")
        self.button(page, "Save", lambda: self.save(theme=theme_menu.get()))

    def build_profile(self, page):
        self.label(page, "Your name (shown in the chat)")
        name_entry = self.entry(page, self.app.settings["user_name"])
        self.button(page, "Save", lambda: self.save(
            user_name=name_entry.get().strip() or "You"))

    def build_voice(self, page):
        T = self.T
        speak_var = ctk.BooleanVar(value=self.app.settings["speak_replies"])
        ctk.CTkSwitch(
            page, text="Speak replies out loud", variable=speak_var,
            text_color=T["text"], progress_color=T["accent"],
        ).pack(anchor="w", padx=20, pady=(16, 4))

        self.label(page, "Speech speed")
        rate_slider = ctk.CTkSlider(page, from_=120, to=250, button_color=T["accent_hover"],
                                    progress_color=T["accent"])
        rate_slider.set(self.app.settings["voice_rate"])
        rate_slider.pack(fill="x", padx=20)

        self.button(page, "Save", lambda: self.save(
            speak_replies=bool(speak_var.get()), voice_rate=int(rate_slider.get())))

    def build_personalization(self, page):
        T = self.T
        self.label(page, "Aira's personality (system prompt)")
        prompt_box = ctk.CTkTextbox(page, height=140, fg_color=T["panel"],
                                    border_color=T["accent"], border_width=2,
                                    text_color=T["text"])
        prompt_box.insert("1.0", self.app.settings["system_prompt"])
        prompt_box.pack(fill="x", padx=20)

        self.label(page, "Creativity (low = precise, high = creative)")
        temp_slider = ctk.CTkSlider(page, from_=0.0, to=1.5, button_color=T["accent_hover"],
                                    progress_color=T["accent"])
        temp_slider.set(self.app.settings["temperature"])
        temp_slider.pack(fill="x", padx=20)

        self.button(page, "Save", lambda: self.save(
            system_prompt=prompt_box.get("1.0", "end").strip(),
            temperature=round(temp_slider.get(), 1),
        ))

    def build_storage(self, page):
        self.note(page, "Everything Aira saves lives next to main.py on your laptop.")
        total = 0
        for name in DATA_ITEMS:
            path = os.path.join(storage.BASE_DIR, name)
            if os.path.exists(path):
                size = size_of(path)
                total += size
                self.row(page, name, human(size))
        self.row(page, "Total", human(total))
        self.button(page, "Open project folder", lambda: open_in_explorer(storage.BASE_DIR))

    def build_keyboard(self, page):
        for keys, action in SHORTCUTS:
            self.row(page, action, keys)

    def build_usage(self, page):
        chats = storage.load_chats()
        messages = [m for chat in chats for m in chat.get("messages", [])]
        sent = sum(1 for m in messages if m.get("role") == "user")
        replies = sum(1 for m in messages if m.get("role") == "assistant")
        self.row(page, "Saved chats", str(len(chats)))
        self.row(page, "Messages you sent", str(sent))
        self.row(page, "Replies from Aira", str(replies))
        self.row(page, "Chat model in use", self.app.settings["model"])

    def build_data_controls(self, page):
        self.note(page, "Your data stays on this laptop. Nothing is sent anywhere except to "
                        "Ollama, which also runs on your laptop.")
        self.button(page, "Export all chats to a text file", self.export_all_chats)

    def export_all_chats(self):
        chats = storage.load_chats()
        path = os.path.join(storage.BASE_DIR, "all_chats_export.txt")
        you = self.app.settings["user_name"]
        with open(path, "w", encoding="utf-8") as f:
            for chat in chats:
                f.write(f"=== {chat.get('title', 'Chat')} ===\n")
                for m in chat.get("messages", []):
                    who = you if m.get("role") == "user" else "Aira"
                    f.write(f"{who}: {m.get('content', '')}\n\n")
                f.write("\n")
        self.say(f"Saved {len(chats)} chats to all_chats_export.txt")
        open_in_explorer(storage.BASE_DIR)


def open_control_center(app, T):
    existing = getattr(app, "_control_center", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        existing.focus()
        return
    app._control_center = ControlCenter(app, T)