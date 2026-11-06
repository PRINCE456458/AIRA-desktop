# Help & feedback window: a small FAQ, plus a form for feedback or problem reports.
# Aira has no server, so "sending" opens WhatsApp (or email) with the message already
# typed. The person only has to press Send there.
import json
import os
import platform
import time
import urllib.parse
import webbrowser

import customtkinter as ctk

import checks
import storage

APP_VERSION = "1.0"
SUPPORT_WHATSAPP = "917359100656"  # country code + number, no + sign and no spaces
SUPPORT_EMAIL = ""                 # optional: put an email address here to show an email button
CATEGORIES = ["Problem", "Idea", "Compliment"]
MAX_MESSAGE = 1500                 # WhatsApp links break when the text is too long

FAQ = [
    ("Aira says Ollama is not running",
     "Aira needs the free Ollama app. Download it at ollama.com/download, install it, "
     "open it, then restart Aira."),
    ("Aira says a model is not installed",
     "Open Command Prompt and type: ollama pull llama3.2:3b (use the model name shown in "
     "the message). It is a one-time download of a few GB, so you need internet once."),
    ("Replies are slow",
     "The AI runs on your own computer, so speed depends on your PC. Close other big apps, "
     "start a New chat if the old one is very long, or pick a smaller model in All settings."),
    ("Voice does not work",
     "Check that Windows lets apps use the microphone: Settings > Privacy > Microphone. "
     "The first time you use voice, Aira downloads a small speech model, so you need internet once."),
    ("Web search, weather or pictures fail",
     "These features need an internet connection. The free search service may also pause "
     "for a few minutes if you ask for many searches quickly."),
    ("Where are my chats saved?",
     "Only on your computer, in the folder %LOCALAPPDATA%\\AiraAI. Web search words, "
     "weather places and picture descriptions are sent to the online services that do those jobs."),
    ("How do I delete my data?",
     "Close Aira and delete the AiraAI folder inside %LOCALAPPDATA%. "
     "All chats, memory and notes are gone after that."),
]


# ---------- Plain functions (no window needed) ----------
def tech_info(app):
    """Facts that help the developer fix a problem. It never includes chats or notes."""
    try:
        models = ", ".join(checks.list_models()) or "none"
    except Exception:
        models = "Ollama not reachable"
    return "\n".join([
        f"App version: {APP_VERSION}",
        f"Windows: {platform.platform()}",
        f"Python: {platform.python_version()}",
        f"Mode: {app.mode}",
        f"Chat model: {app.settings.get('model', '?')}",
        f"Installed models: {models}",
    ])


def build_message(app, category, rating, text, include_info):
    lines = [f"Aira feedback ({category})", f"Rating: {rating}/5", "", text.strip()]
    if include_info:
        lines += ["", "--- technical info ---", tech_info(app)]
    return "\n".join(lines)


def whatsapp_url(message, number=SUPPORT_WHATSAPP):
    return f"https://wa.me/{number}?text=" + urllib.parse.quote(message[:MAX_MESSAGE])


def email_url(message, address=SUPPORT_EMAIL):
    return f"mailto:{address}?subject=" + urllib.parse.quote("Aira feedback") + \
        "&body=" + urllib.parse.quote(message[:MAX_MESSAGE])


def save_copy(message, category, rating):
    """Keep a copy of what was sent, in feedback.json inside the data folder."""
    path = os.path.join(storage.BASE_DIR, "feedback.json")
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        items = []
    items.append({
        "time": time.strftime("%Y-%m-%d %H:%M"),
        "category": category, "rating": rating, "message": message,
    })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


# ---------- The window ----------
class HelpCenter(ctk.CTkToplevel):
    def __init__(self, app, T):
        super().__init__(app)
        self.app = app
        self.T = T
        self.title("Aira - Help & feedback")
        self.geometry("720x660")
        self.minsize(600, 540)
        self.configure(fg_color=T["bg"])
        self.after(100, self.focus)

        tabs = ctk.CTkTabview(
            self, fg_color=T["bg"], text_color=T["text"],
            segmented_button_fg_color=T["sidebar"],
            segmented_button_selected_color=T["accent"],
            segmented_button_selected_hover_color=T["accent_hover"],
            segmented_button_unselected_color=T["sidebar"],
            segmented_button_unselected_hover_color=T["button"],
        )
        tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.build_help(tabs.add("Help"))
        self.build_feedback(tabs.add("Send feedback"))

    # ----- Help tab -----
    def build_help(self, tab):
        T = self.T
        page = ctk.CTkScrollableFrame(tab, fg_color=T["bg"], corner_radius=0)
        page.pack(fill="both", expand=True)
        ctk.CTkLabel(
            page, text="Help and support", text_color=T["text"], anchor="w",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            page, text="Click a question to see the answer.", text_color=T["status"], anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 8))
        for question, answer in FAQ:
            self.add_faq(page, question, answer)

        ctk.CTkLabel(
            page, text="Still stuck?", text_color=T["text"], anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(fill="x", padx=8, pady=(18, 4))
        ctk.CTkButton(
            page, text="Message the developer on WhatsApp",
            fg_color=T["accent"], hover_color=T["accent_hover"],
            command=lambda: webbrowser.open(
                whatsapp_url("Hi, I need help with Aira.")),
        ).pack(anchor="w", padx=8, pady=4)

    def add_faq(self, page, question, answer):
        T = self.T
        box = ctk.CTkFrame(page, fg_color=T["panel"], corner_radius=10)
        box.pack(fill="x", padx=8, pady=4)
        answer_label = ctk.CTkLabel(
            box, text=answer, text_color=T["status"], justify="left",
            anchor="w", wraplength=560,
        )
        state = {"open": False}

        def toggle():
            if state["open"]:
                answer_label.pack_forget()
            else:
                answer_label.pack(fill="x", padx=14, pady=(0, 10))
            state["open"] = not state["open"]

        ctk.CTkButton(
            box, text=question, anchor="w", fg_color="transparent",
            hover_color=T["button"], text_color=T["text"], command=toggle,
        ).pack(fill="x")

    # ----- Feedback tab -----
    def build_feedback(self, tab):
        T = self.T
        page = ctk.CTkScrollableFrame(tab, fg_color=T["bg"], corner_radius=0)
        page.pack(fill="both", expand=True)
        ctk.CTkLabel(
            page, text="Send feedback or report a problem", text_color=T["text"],
            anchor="w", font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(fill="x", padx=8, pady=(6, 8))

        self.label(page, "What is it about?")
        self.category = ctk.CTkOptionMenu(
            page, values=CATEGORIES, fg_color=T["button"], button_color=T["button_hover"],
            button_hover_color=T["accent"], text_color=T["text"],
        )
        self.category.pack(anchor="w", padx=8)

        self.label(page, "How do you like Aira? (1 = not at all, 5 = a lot)")
        self.rating = ctk.CTkSegmentedButton(
            page, values=["1", "2", "3", "4", "5"], selected_color=T["accent"],
            selected_hover_color=T["accent_hover"], unselected_color=T["button"],
            unselected_hover_color=T["button_hover"], text_color=T["text"],
        )
        self.rating.set("5")
        self.rating.pack(anchor="w", padx=8)

        self.label(page, "Your message")
        self.box = ctk.CTkTextbox(
            page, height=150, fg_color=T["panel"], border_color=T["accent"],
            border_width=2, text_color=T["text"],
        )
        self.box.pack(fill="x", padx=8)

        self.info_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            page, text="Include technical info (app version, Windows, models). No chats are included.",
            variable=self.info_var, text_color=T["text"], progress_color=T["accent"],
        ).pack(anchor="w", padx=8, pady=(12, 4))

        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=10)
        for text, command in (("Send on WhatsApp", self.send_whatsapp),
                              ("Copy message", self.copy_message),
                              ("Save a copy", self.save_only)):
            ctk.CTkButton(
                row, text=text, fg_color=T["accent"], hover_color=T["accent_hover"],
                command=command,
            ).pack(side="left", padx=(0, 8))
        if SUPPORT_EMAIL:
            ctk.CTkButton(
                row, text="Send by email", fg_color=T["accent"],
                hover_color=T["accent_hover"], command=self.send_email,
            ).pack(side="left", padx=(0, 8))

        self.status = ctk.CTkLabel(page, text="", text_color=T["status"], anchor="w",
                                   wraplength=560, justify="left")
        self.status.pack(fill="x", padx=8)

    def label(self, page, text):
        ctk.CTkLabel(page, text=text, text_color=self.T["text"], anchor="w").pack(
            fill="x", padx=8, pady=(12, 4))

    def say(self, text):
        self.status.configure(text=text)

    def compose(self):
        text = self.box.get("1.0", "end").strip()
        if not text:
            self.say("Please write a short message first.")
            return None
        return build_message(self.app, self.category.get(), self.rating.get(),
                             text, self.info_var.get())

    def send_whatsapp(self):
        message = self.compose()
        if message is None:
            return
        save_copy(message, self.category.get(), self.rating.get())
        webbrowser.open(whatsapp_url(message))
        self.say("WhatsApp opened with your message. Press Send there to finish.")

    def send_email(self):
        message = self.compose()
        if message is None:
            return
        save_copy(message, self.category.get(), self.rating.get())
        webbrowser.open(email_url(message))
        self.say("Your email app opened with your message. Press Send there to finish.")

    def copy_message(self):
        message = self.compose()
        if message is None:
            return
        self.clipboard_clear()
        self.clipboard_append(message)
        self.say("Copied. You can paste it anywhere.")

    def save_only(self):
        message = self.compose()
        if message is None:
            return
        save_copy(message, self.category.get(), self.rating.get())
        self.say("Saved on this computer in feedback.json.")


def open_help(app, T):
    existing = getattr(app, "_help_center", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        existing.focus()
        return
    app._help_center = HelpCenter(app, T)
    