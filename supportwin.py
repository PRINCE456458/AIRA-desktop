import threading
import webbrowser
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

import checks
import support


def open_support(app, T, tab="Help"):
    win = ctk.CTkToplevel(app)
    win.title(f"{support.APP_NAME} help and support")
    win.geometry("640x700")
    win.configure(fg_color=T["bg"])
    win.after(100, win.focus)

    state = {"tab": tab, "rating": 0, "open": set(), "info": "Loading technical info..."}
    frames = {}

    ctk.CTkLabel(
        win, text="Help and support", text_color=T["text"], font=("Segoe UI", 20, "bold"),
    ).pack(anchor="w", padx=16, pady=(14, 6))

    tabs = ctk.CTkSegmentedButton(
        win, values=["Help", "Send feedback", "Contact"], command=lambda value: pick(value),
        selected_color=T["accent"], selected_hover_color=T["accent_hover"],
        unselected_color=T["button"], unselected_hover_color=T["button_hover"],
        text_color=T["text"],
    )
    tabs.pack(fill="x", padx=14, pady=(0, 8))

    holder = ctk.CTkFrame(win, fg_color="transparent")
    holder.pack(fill="both", expand=True)

    def pick(value):
        for name, frame in frames.items():
            frame.pack_forget()
        frames[value].pack(fill="both", expand=True, padx=8, pady=(0, 10))
        state["tab"] = value
        tabs.set(value)

    def small(parent, text, command, width=120, accent=False):
        ctk.CTkButton(
            parent, text=text, width=width, height=30,
            fg_color=T["accent"] if accent else T["button"],
            hover_color=T["accent_hover"] if accent else T["button_hover"],
            text_color=T["text"], command=command,
        ).pack(side="left", padx=4)

    def copy_text(text):
        win.clipboard_clear()
        win.clipboard_append(text)

    # ================= Help =================
    help_frame = ctk.CTkFrame(holder, fg_color="transparent")
    frames["Help"] = help_frame

    top = ctk.CTkFrame(help_frame, fg_color="transparent")
    top.pack(fill="x", padx=6, pady=(0, 4))
    small(top, "Check my setup", lambda: run_check(), width=140, accent=True)
    check_label = ctk.CTkLabel(
        top, text="", text_color=T["status"], anchor="w", justify="left", wraplength=360,
    )
    check_label.pack(side="left", padx=8)

    search = ctk.CTkEntry(
        help_frame, placeholder_text="Search for your problem...",
        fg_color=T["panel"], border_color=T["accent"], text_color=T["text"],
    )
    search.pack(fill="x", padx=6, pady=(4, 6))
    search.bind("<KeyRelease>", lambda event: render_faq())

    faq_body = ctk.CTkScrollableFrame(help_frame, fg_color="transparent")
    faq_body.pack(fill="both", expand=True, padx=2)

    def run_check():
        check_label.configure(text="Checking...")

        def work():
            try:
                problems = checks.find_problems(app.settings)
            except Exception as error:
                problems = [f"The check could not finish: {error}"]
            text = "Everything looks fine." if not problems else "\n".join("- " + p for p in problems)
            try:
                win.after(0, lambda: check_label.configure(text=text))
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def toggle(question):
        if question in state["open"]:
            state["open"].discard(question)
        else:
            state["open"].add(question)
        render_faq()

    def render_faq():
        for widget in faq_body.winfo_children():
            widget.destroy()
        found = support.search_faq(search.get())
        if not found:
            ctk.CTkLabel(
                faq_body, text="No answer found. Press 'Send feedback' and tell us your problem.",
                text_color=T["status"], wraplength=540,
            ).pack(pady=24)
            return
        for question, answer in found:
            card = ctk.CTkFrame(faq_body, fg_color=T["panel"], corner_radius=10)
            card.pack(fill="x", padx=4, pady=3)
            opened = question in state["open"]
            ctk.CTkButton(
                card, text=("▾  " if opened else "▸  ") + question, anchor="w", height=34,
                fg_color="transparent", hover_color=T["button_hover"], text_color=T["text"],
                font=("Segoe UI", 13, "bold"), command=lambda q=question: toggle(q),
            ).pack(fill="x", padx=6, pady=(4, 0 if opened else 4))
            if opened:
                ctk.CTkLabel(
                    card, text=answer, text_color=T["text"], anchor="w", justify="left", wraplength=540,
                    font=("Segoe UI", 12),
                ).pack(fill="x", padx=16, pady=(0, 10))

    # ================= Feedback =================
    fb = ctk.CTkFrame(holder, fg_color="transparent")
    frames["Send feedback"] = fb

    def label(parent, text):
        ctk.CTkLabel(parent, text=text, text_color=T["text"], anchor="w").pack(fill="x", padx=14, pady=(8, 2))

    label(fb, "What kind of message is it?")
    category = ctk.CTkOptionMenu(
        fb, values=support.CATEGORIES, fg_color=T["button"], button_color=T["button_hover"],
        text_color=T["text"],
    )
    category.set("Problem")
    category.pack(anchor="w", padx=14)

    label(fb, "How do you like it so far? (optional)")
    stars_row = ctk.CTkFrame(fb, fg_color="transparent")
    stars_row.pack(anchor="w", padx=10)
    star_buttons = []

    def set_rating(value):
        state["rating"] = 0 if state["rating"] == value else value
        for index, button in enumerate(star_buttons, start=1):
            filled = index <= state["rating"]
            button.configure(text="★" if filled else "☆",
                             fg_color=T["accent"] if filled else T["button"])

    for index in range(1, 6):
        button = ctk.CTkButton(
            stars_row, text="☆", width=40, height=34, fg_color=T["button"],
            hover_color=T["button_hover"], text_color=T["text"], font=("Segoe UI", 18),
            command=lambda v=index: set_rating(v),
        )
        button.pack(side="left", padx=2)
        star_buttons.append(button)

    label(fb, f"Tell us what happened or what you want (up to {support.MAX_TEXT} characters)")
    message = ctk.CTkTextbox(fb, height=130, fg_color=T["panel"], text_color=T["text"], wrap="word")
    message.pack(fill="x", padx=14)

    include = ctk.CTkCheckBox(
        fb, text="Include technical info (helps me fix problems; no chats, name or key)",
        text_color=T["text"], fg_color=T["accent"], hover_color=T["accent_hover"],
        command=lambda: show_info(),
    )
    include.select()
    include.pack(anchor="w", padx=14, pady=(10, 2))
    info_box = ctk.CTkTextbox(fb, height=110, fg_color=T["panel"], text_color=T["status"], wrap="word")
    info_box.pack(fill="x", padx=14)

    def show_info():
        if include.get():
            info_box.pack(fill="x", padx=14)
        else:
            info_box.pack_forget()

    def fill_info():
        info_box.configure(state="normal")
        info_box.delete("1.0", "end")
        info_box.insert("1.0", state["info"])
        info_box.configure(state="disabled")

    status = ctk.CTkLabel(fb, text="", text_color=T["status"], anchor="w", justify="left", wraplength=560)
    status.pack(fill="x", padx=14, pady=(8, 2))

    def current():
        text = message.get("1.0", "end").strip()
        problem = support.check_feedback(category.get(), text)
        if problem:
            status.configure(text=problem)
            return None
        info = state["info"] if include.get() else ""
        return support.build_message(category.get(), state["rating"], text, info), text

    def send_whatsapp():
        made = current()
        if not made:
            return
        full, text = made
        support.save_feedback(category.get(), state["rating"], text, "whatsapp", datetime.now())
        webbrowser.open(support.whatsapp_link(full))
        status.configure(text="WhatsApp is opening with your message. Press Send there to finish. "
                              "If it does not open, use Copy message and paste it into WhatsApp.")

    def copy_message():
        made = current()
        if not made:
            return
        full, text = made
        support.save_feedback(category.get(), state["rating"], text, "copied", datetime.now())
        copy_text(full)
        status.configure(text=f"Copied. Paste it into WhatsApp to {support.phone_text()}.")

    row = ctk.CTkFrame(fb, fg_color="transparent")
    row.pack(fill="x", padx=10, pady=6)
    small(row, "Send on WhatsApp", send_whatsapp, width=160, accent=True)
    small(row, "Copy message", copy_message, width=130)

    # ================= Contact =================
    contact = ctk.CTkFrame(holder, fg_color="transparent")
    frames["Contact"] = contact

    ctk.CTkLabel(
        contact, text="Need help? Talk to us", text_color=T["text"], font=("Segoe UI", 18, "bold"),
    ).pack(anchor="w", padx=16, pady=(14, 2))
    ctk.CTkLabel(
        contact, text="WhatsApp: " + support.phone_text(), text_color=T["accent"],
        font=("Segoe UI", 16, "bold"),
    ).pack(anchor="w", padx=16)
    ctk.CTkLabel(
        contact, text=support.SUPPORT_HOURS, text_color=T["status"], anchor="w",
    ).pack(fill="x", padx=16, pady=(0, 10))

    crow = ctk.CTkFrame(contact, fg_color="transparent")
    crow.pack(fill="x", padx=12, pady=4)
    small(crow, "Chat on WhatsApp", lambda: webbrowser.open(support.whatsapp_link(
        f"Hi, I need help with {support.APP_NAME} {support.APP_VERSION}.")), width=160, accent=True)
    small(crow, "Copy number", lambda: copy_text(support.phone_text()), width=120)
    small(crow, "Report a problem", lambda: (category.set("Problem"), pick("Send feedback")), width=150)

    ctk.CTkLabel(
        contact,
        text=f"{support.APP_NAME} version {support.APP_VERSION}\n\n"
             "Nothing is sent from your laptop on its own. A message is only sent when you press Send in "
             "WhatsApp yourself. A copy of the feedback you write is kept on your laptop in feedback.json.",
        text_color=T["status"], anchor="w", justify="left", wraplength=560,
    ).pack(fill="x", padx=16, pady=(16, 0))

    # ----- start -----
    render_faq()
    fill_info()

    def load_info():
        plan = "free"
        try:
            plan = app.pro.plan()
        except Exception:
            pass
        text = support.tech_info(app.settings, plan)
        state["info"] = text
        try:
            win.after(0, fill_info)
        except Exception:
            pass

    threading.Thread(target=load_info, daemon=True).start()
    pick(state["tab"])