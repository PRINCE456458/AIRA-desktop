from datetime import datetime, timedelta
from tkinter import messagebox

import customtkinter as ctk

import tasks

try:
    import winsound
except ImportError:      # not on Windows
    winsound = None


def open_tasks(app, T):
    win = ctk.CTkToplevel(app)
    win.title("Aira tasks")
    win.geometry("700x640")
    win.configure(fg_color=T["bg"])
    win.after(100, win.focus)

    state = {"view": "My tasks" if app.tasks.items else "Suggested"}

    top = ctk.CTkFrame(win, fg_color="transparent")
    top.pack(fill="x", padx=12, pady=(12, 2))
    ctk.CTkLabel(
        top, text="Tasks", text_color=T["text"], font=("Segoe UI", 20, "bold"),
    ).pack(side="left")
    ctk.CTkButton(
        top, text="+ New task", width=110, fg_color=T["accent"], hover_color=T["accent_hover"],
        command=lambda: edit_task(None),
    ).pack(side="right")

    ctk.CTkLabel(
        win,
        text="Give Aira a job to do later, or again and again. It runs while Aira is open, "
             "and the answer appears as a new chat.",
        text_color=T["status"], font=("Segoe UI", 12), wraplength=660, justify="left",
    ).pack(anchor="w", padx=14, pady=(0, 6))

    tabs = ctk.CTkSegmentedButton(
        win, values=["My tasks", "Suggested"], command=lambda value: pick(value),
        selected_color=T["accent"], selected_hover_color=T["accent_hover"],
        unselected_color=T["button"], unselected_hover_color=T["button_hover"],
        text_color=T["text"],
    )
    tabs.set(state["view"])
    tabs.pack(fill="x", padx=12, pady=(0, 6))

    body = ctk.CTkScrollableFrame(win, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    def pick(value):
        state["view"] = value
        render()

    def small(parent, text, command, width=70, danger=False, accent=False):
        fg = T["danger"] if danger else (T["accent"] if accent else T["button"])
        hover = T["danger_hover"] if danger else (T["accent_hover"] if accent else T["button_hover"])
        ctk.CTkButton(
            parent, text=text, width=width, height=28, fg_color=fg, hover_color=hover,
            text_color=T["text"], command=command,
        ).pack(side="left", padx=2)

    def note(text):
        ctk.CTkLabel(body, text=text, text_color=T["status"], wraplength=620).pack(pady=30)

    # ----- My tasks -----
    def show_mine():
        if not app.tasks.items:
            note("No tasks yet. Open the Suggested tab for ideas, or click + New task.")
            return
        for task in app.tasks.items:
            card = ctk.CTkFrame(body, fg_color=T["panel"], corner_radius=10)
            card.pack(fill="x", padx=4, pady=4)
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(
                head, text=task["title"], text_color=T["text"], font=("Segoe UI", 14, "bold"), anchor="w",
            ).pack(side="left")
            switch = ctk.CTkSwitch(
                head, text="On", text_color=T["text"], progress_color=T["accent"], width=60,
                command=lambda i=task["id"]: toggle(i),
            )
            switch.pack(side="right")
            if task.get("enabled"):
                switch.select()
            else:
                switch.deselect()
            ctk.CTkLabel(
                card, text=f"{tasks.describe(task)}   |   {tasks.next_text(task)}",
                text_color=T["status"], font=("Segoe UI", 11), anchor="w",
            ).pack(fill="x", padx=12)
            preview = task["prompt"] if len(task["prompt"]) <= 110 else task["prompt"][:107] + "..."
            ctk.CTkLabel(
                card, text=preview, text_color=T["text"], font=("Segoe UI", 12),
                anchor="w", justify="left", wraplength=620,
            ).pack(fill="x", padx=12, pady=(2, 0))
            ctk.CTkLabel(
                card, text=task.get("status", ""), text_color=T["status"], font=("Segoe UI", 11),
                anchor="w", wraplength=620, justify="left",
            ).pack(fill="x", padx=12)
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=(4, 8))
            small(row, "Run now", lambda i=task["id"]: run_now(i), accent=True)
            small(row, "Edit", lambda t=task: edit_task(t))
            small(row, "Delete", lambda i=task["id"]: delete(i), danger=True)

    def toggle(task_id):
        task = app.tasks.get(task_id)
        ok, message = app.tasks.set_enabled(task_id, not task.get("enabled"))
        if not ok:
            messagebox.showinfo("Tasks", message, parent=win)
        render()

    def run_now(task_id):
        if app.is_busy or app.task_running:
            messagebox.showinfo("Tasks", "Aira is busy right now. Try again in a moment.", parent=win)
            return
        win.destroy()
        app.run_task(task_id, manual=True)

    def delete(task_id):
        task = app.tasks.get(task_id)
        if messagebox.askyesno("Delete task", f"Delete the task '{task['title']}'?", parent=win):
            app.tasks.delete(task_id)
            render()

    # ----- Suggested -----
    def show_suggested():
        have = {t["title"].lower() for t in app.tasks.items}
        for index, idea in enumerate(tasks.SUGGESTIONS):
            card = ctk.CTkFrame(body, fg_color=T["panel"], corner_radius=10)
            card.pack(fill="x", padx=4, pady=4)
            ctk.CTkLabel(
                card, text=idea["title"], text_color=T["text"], font=("Segoe UI", 14, "bold"), anchor="w",
            ).pack(fill="x", padx=12, pady=(8, 0))
            when = dict(idea, weekday=idea.get("day", 0), date=None)
            ctk.CTkLabel(
                card, text=tasks.describe(when), text_color=T["status"], font=("Segoe UI", 11), anchor="w",
            ).pack(fill="x", padx=12)
            ctk.CTkLabel(
                card, text=idea["prompt"], text_color=T["text"], font=("Segoe UI", 12),
                anchor="w", justify="left", wraplength=620,
            ).pack(fill="x", padx=12, pady=(2, 0))
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=(4, 8))
            if idea["title"].lower() in have:
                ctk.CTkLabel(row, text="Added", text_color=T["status"]).pack(side="left", padx=8)
            else:
                small(row, "Add", lambda i=index: add_idea(i), accent=True)
            small(row, "Customize", lambda i=idea: edit_task(None, i), width=90)

    def add_idea(index):
        task, error = app.tasks.add_suggestion(index)
        if error:
            messagebox.showinfo("Tasks", error, parent=win)
        render()

    # ----- Make or change a task -----
    def edit_task(task, idea=None):
        source = task or idea or {}
        box = ctk.CTkToplevel(win)
        box.title("Edit task" if task else "New task")
        box.geometry("520x600")
        box.configure(fg_color=T["bg"])
        box.after(100, box.focus)

        def label(text):
            ctk.CTkLabel(box, text=text, text_color=T["text"], anchor="w").pack(fill="x", padx=18, pady=(10, 2))

        label("Title")
        title = ctk.CTkEntry(box, fg_color=T["panel"], border_color=T["accent"], text_color=T["text"])
        title.pack(fill="x", padx=18)
        title.insert(0, source.get("title", ""))

        label("What should Aira do? (write it like a message to Aira)")
        prompt = ctk.CTkTextbox(box, height=120, fg_color=T["panel"], text_color=T["text"], wrap="word")
        prompt.pack(fill="x", padx=18)
        prompt.insert("1.0", source.get("prompt", ""))

        label("How often?")
        repeat = ctk.CTkOptionMenu(
            box, values=tasks.REPEATS, fg_color=T["button"], button_color=T["button_hover"],
            text_color=T["text"], command=lambda value: layout(),
        )
        repeat.set(source.get("repeat", "Daily"))
        repeat.pack(fill="x", padx=18)

        extra = ctk.CTkFrame(box, fg_color="transparent")
        extra.pack(fill="x", padx=18)
        day_label = ctk.CTkLabel(extra, text="Which day?", text_color=T["text"], anchor="w")
        day_menu = ctk.CTkOptionMenu(
            extra, values=tasks.DAYS, fg_color=T["button"], button_color=T["button_hover"], text_color=T["text"],
        )
        day_menu.set(tasks.DAYS[source.get("weekday", source.get("day", 0)) or 0])
        date_label = ctk.CTkLabel(extra, text="Date (day-month-year, like 25-10-2026)", text_color=T["text"], anchor="w")
        date_entry = ctk.CTkEntry(extra, fg_color=T["panel"], border_color=T["accent"], text_color=T["text"])
        tomorrow = datetime.now() + timedelta(days=1)
        shown_date = source.get("date")
        date_entry.insert(0, datetime.fromisoformat(shown_date).strftime("%d-%m-%Y") if shown_date else tomorrow.strftime("%d-%m-%Y"))

        def layout():
            for widget in (day_label, day_menu, date_label, date_entry):
                widget.pack_forget()
            if repeat.get() == "Weekly":
                day_label.pack(fill="x", pady=(10, 2))
                day_menu.pack(fill="x")
            elif repeat.get() == "Once":
                date_label.pack(fill="x", pady=(10, 2))
                date_entry.pack(fill="x")

        label("What time? (like 8:30 am or 20:15)")
        clock = ctk.CTkEntry(box, fg_color=T["panel"], border_color=T["accent"], text_color=T["text"])
        clock.pack(fill="x", padx=18)
        if source.get("time"):
            clock.insert(0, tasks.nice_time(source["time"]))
        layout()

        def save():
            args = (
                title.get(), prompt.get("1.0", "end"), repeat.get(), clock.get(),
                tasks.DAYS.index(day_menu.get()), date_entry.get(),
            )
            if task:
                result, error = app.tasks.update(task["id"], *args)
            else:
                result, error = app.tasks.add(*args)
            if error:
                messagebox.showinfo("Tasks", error, parent=box)
                return
            box.destroy()
            state["view"] = "My tasks"
            tabs.set("My tasks")
            render()

        ctk.CTkButton(
            box, text="Save task", fg_color=T["accent"], hover_color=T["accent_hover"],
            text_color=T["text"], command=save,
        ).pack(pady=18)

    def render():
        for widget in body.winfo_children():
            widget.destroy()
        (show_mine if state["view"] == "My tasks" else show_suggested)()

    render()


def show_done(app, T, title, chat, error=None):
    """A small window that says a task finished (or could not run)."""
    if winsound:
        try:
            winsound.MessageBeep()
        except Exception:
            pass
    win = ctk.CTkToplevel(app)
    win.title("Task finished" if not error else "Task could not run")
    win.geometry("380x190")
    win.configure(fg_color=T["bg"])
    win.attributes("-topmost", True)
    ctk.CTkLabel(
        win, text="Task finished" if not error else "Task could not run",
        text_color=T["status"], font=("Segoe UI", 12),
    ).pack(pady=(16, 0))
    ctk.CTkLabel(
        win, text=title, text_color=T["text"], font=("Segoe UI", 16, "bold"), wraplength=340,
    ).pack(pady=(2, 6))
    if error:
        ctk.CTkLabel(
            win, text=error, text_color=T["text"], font=("Segoe UI", 12), wraplength=340,
        ).pack(pady=(0, 8))
    row = ctk.CTkFrame(win, fg_color="transparent")
    row.pack()
    if not error:
        ctk.CTkButton(
            row, text="Open the answer", fg_color=T["accent"], hover_color=T["accent_hover"],
            text_color=T["text"], command=lambda: (win.destroy(), app.open_task_chat(chat)),
        ).pack(side="left", padx=4)
    ctk.CTkButton(
        row, text="Later" if not error else "OK", fg_color=T["button"], hover_color=T["button_hover"],
        text_color=T["text"], command=win.destroy,
    ).pack(side="left", padx=4)