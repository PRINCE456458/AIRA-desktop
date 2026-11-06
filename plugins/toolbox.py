import os

import customtkinter as ctk

import gallery
import imagegen
import plugins

# Each section is a title and a list of buttons.
# A button is (label, kind, value, hint). Kinds:
#   say    - send the text right away
#   ask    - ask a question in a small box, then send value with {} replaced by the answer
#   fill   - put the text in the message box so you can edit it, then press Send
#   photo  - choose a picture, then fill the message box with value
#   gallery, folder, newplugin, pluginfolder - special actions
SECTIONS = [
    ("Pictures", [
        ("Draw an image", "ask", "generate an image of {}", "Describe the picture you want:"),
        ("Redraw a photo", "photo", "redraw this as a watercolor painting", ""),
        ("Image gallery", "gallery", "", ""),
        ("Open images folder", "folder", "", ""),
    ]),
    ("Make things", [
        ("Build a website", "ask", "build {}", "What website? (for example: a pomodoro timer):"),
        ("Make a PDF", "ask", "make a pdf about {}", "What should the PDF be about?"),
        ("Write a Word file", "ask", "write a word document about {}", "What should the document be about?"),
        ("Write a Python program", "ask", "write a python program that {}", "What should the program do?"),
    ]),
    ("Everyday", [
        ("Set a reminder", "fill", "remind me in 10 minutes to ", ""),
        ("Show reminders", "say", "show reminders", ""),
        ("Add an expense", "fill", "spent 100 on ", ""),
        ("Expense report", "say", "expense report", ""),
    ]),
    ("Plugins", [
        ("List plugins", "say", "list plugins", ""),
        ("Reload plugins", "say", "reload plugins", ""),
        ("New plugin", "newplugin", "", ""),
        ("Open plugins folder", "pluginfolder", "", ""),
    ]),
]


def send(app, text):
    app.entry.delete(0, "end")
    app.entry.insert(0, text)
    app.send_message()


def fill(app, text):
    app.entry.delete(0, "end")
    app.entry.insert(0, text)
    app.entry.focus()


def ask_box(question, title):
    dialog = ctk.CTkInputDialog(text=question, title=title)
    answer = dialog.get_input()
    return (answer or "").strip()


def do_action(app, T, win, kind, value, hint, label):
    if kind in ("ask", "photo", "gallery", "folder", "newplugin", "pluginfolder", "say", "fill"):
        win.destroy()
    if kind == "say":
        send(app, value)
    elif kind == "fill":
        fill(app, value)
    elif kind == "ask":
        answer = ask_box(hint, label)
        if answer:
            send(app, value.replace("{}", answer))
    elif kind == "photo":
        app.pick_image()
        fill(app, value)
    elif kind == "gallery":
        gallery.open_gallery(app, T)
    elif kind == "folder":
        gallery.open_folder()
    elif kind == "newplugin":
        answer = ask_box("Name for your new plugin (simple words, like weather):", label)
        if answer:
            send(app, "new plugin " + answer)
    elif kind == "pluginfolder":
        os.makedirs(plugins.PLUGIN_DIR, exist_ok=True)
        try:
            os.startfile(plugins.PLUGIN_DIR)
        except Exception:
            pass


def open_toolbox(app, T):
    win = ctk.CTkToplevel(app)
    win.title("Aira toolbox")
    win.geometry("420x680")
    win.configure(fg_color=T["bg"])
    win.after(100, win.focus)

    ctk.CTkLabel(
        win, text="Toolbox", text_color=T["text"], font=("Segoe UI", 20, "bold"),
    ).pack(pady=(14, 2))
    ctk.CTkLabel(
        win, text="Click a button. Aira does the rest.", text_color=T["status"],
        font=("Segoe UI", 12),
    ).pack(pady=(0, 8))

    body = ctk.CTkScrollableFrame(win, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def section(title):
        ctk.CTkLabel(
            body, text=title, text_color=T["accent"], font=("Segoe UI", 14, "bold"), anchor="w",
        ).pack(fill="x", padx=6, pady=(12, 4))

    def button(label, command):
        ctk.CTkButton(
            body, text=label, fg_color=T["button"], hover_color=T["button_hover"],
            text_color=T["text"], anchor="w", height=34, command=command,
        ).pack(fill="x", padx=6, pady=3)

    for title, items in SECTIONS:
        section(title)
        for label, kind, value, hint in items:
            button(label, lambda k=kind, v=value, h=hint, l=label: do_action(app, T, win, k, v, h, l))

    # One button for each plugin you have installed.
    manager = getattr(app, "plugins", None)
    if manager and manager.plugins:
        section("Your plugins")
        for plugin in manager.plugins:
            example = plugin.examples[0] if plugin.examples else ""
            button(
                plugin.name,
                lambda e=example, l=plugin.name: do_action(app, T, win, "fill", e, "", l),
            )