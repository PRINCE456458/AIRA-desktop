import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

import pro as pro_module


def open_pro(app, T):
    win = ctk.CTkToplevel(app)
    win.title("Aira Pro")
    win.geometry("560x640")
    win.configure(fg_color=T["bg"])
    win.after(100, win.focus)
    state = {"busy": False}

    def label(text, size=12, bold=False, color=None, pad=(2, 0)):
        ctk.CTkLabel(
            win, text=text, text_color=color or T["text"], anchor="w", justify="left",
            font=("Segoe UI", size, "bold" if bold else "normal"), wraplength=500,
        ).pack(fill="x", padx=22, pady=pad)

    header = ctk.CTkLabel(win, text="", font=("Segoe UI", 22, "bold"), text_color=T["text"], anchor="w")
    header.pack(fill="x", padx=22, pady=(20, 0))
    status = ctk.CTkLabel(
        win, text="", text_color=T["status"], anchor="w", justify="left", wraplength=500,
        font=("Segoe UI", 13),
    )
    status.pack(fill="x", padx=22, pady=(2, 10))

    usage = ctk.CTkFrame(win, fg_color=T["panel"], corner_radius=10)
    usage.pack(fill="x", padx=22, pady=(0, 10))
    usage_label = ctk.CTkLabel(usage, text="", text_color=T["text"], anchor="w", justify="left",
                               font=("Segoe UI", 13))
    usage_label.pack(fill="x", padx=14, pady=10)

    label("What Pro gives you", 14, True, T["accent"], (6, 2))
    label(f"- Up to {pro_module.PRO_LIMITS['tasks']} scheduled tasks (Free: {pro_module.FREE_LIMITS['tasks']})")
    label(f"- Up to {pro_module.PRO_LIMITS['projects']} projects (Free: {pro_module.FREE_LIMITS['projects']})")
    label("- Your support helps Aira keep growing", pad=(2, 10))

    buy = ctk.CTkButton(
        win, text="Subscribe to Pro", fg_color=T["accent"], hover_color=T["accent_hover"],
        text_color=T["text"], height=38, command=lambda: webbrowser.open(pro_module.UPGRADE_URL),
    )
    buy.pack(fill="x", padx=22, pady=(4, 12))

    label("Already subscribed? Paste your license key:", 13, True, pad=(4, 2))
    key_entry = ctk.CTkEntry(
        win, placeholder_text="Aira-XXXXX-XXXXX-XXXXX-XXXXX",
        fg_color=T["panel"], border_color=T["accent"], text_color=T["text"],
    )
    key_entry.pack(fill="x", padx=22)

    message = ctk.CTkLabel(
        win, text="", text_color=T["status"], anchor="w", justify="left", wraplength=500,
    )
    message.pack(fill="x", padx=22, pady=(6, 2))

    buttons = ctk.CTkFrame(win, fg_color="transparent")
    buttons.pack(fill="x", padx=18, pady=4)

    def refresh_view():
        pro_on = app.pro.is_pro()
        header.configure(text="Aira Pro" if pro_on else "Aira Free")
        status.configure(text=app.pro.status_text())
        usage_label.configure(text=(
            f"Tasks: {len(app.tasks.items)} of {app.pro.limit('tasks')}\n"
            f"Projects: {len(app.projects.items)} of {app.pro.limit('projects')}"
        ))
        buy.configure(state="disabled" if pro_on else "normal")
        app.apply_plan()

    def work(job):
        """Run a slow server call in the background so the window never freezes."""
        if state["busy"]:
            return
        state["busy"] = True
        message.configure(text="Checking, please wait...")

        def run():
            result = job()
            try:
                win.after(0, finish, result)
            except Exception:
                state["busy"] = False

        def finish(result):
            state["busy"] = False
            ok, text = result
            message.configure(text=text, text_color=T["status"] if ok else T["text"])
            refresh_view()

        threading.Thread(target=run, daemon=True).start()

    def activate():
        key = key_entry.get()
        work(lambda: app.pro.activate(key))

    def check_again():
        if not app.pro.data.get("key"):
            message.configure(text="Paste a license key first.")
            return
        work(app.pro.refresh)

    def remove_key():
        if not app.pro.data.get("key"):
            message.configure(text="There is no key saved.")
            return
        if messagebox.askyesno(
            "Remove key", "Remove the key from this laptop?\n\nYou can then use it on another laptop. "
            "Pro stops working here until you activate again.", parent=win,
        ):
            work(lambda: (app.pro.deactivate() or True, "The key was removed from this laptop."))

    for text, command, accent in (("Activate", activate, True), ("Check again", check_again, False),
                                  ("Remove key", remove_key, False)):
        ctk.CTkButton(
            buttons, text=text, width=120,
            fg_color=T["accent"] if accent else T["button"],
            hover_color=T["accent_hover"] if accent else T["button_hover"],
            text_color=T["text"], command=command,
        ).pack(side="left", padx=4)

    label("Your key is checked online from time to time. If your internet is off, Pro keeps working "
          "for a few days.", 11, color=T["status"], pad=(14, 0))
    refresh_view()