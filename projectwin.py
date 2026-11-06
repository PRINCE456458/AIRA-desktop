from tkinter import filedialog, messagebox

import customtkinter as ctk


def open_projects(app, T):
    win = ctk.CTkToplevel(app)
    win.title("Aira projects")
    win.geometry("640x560")
    win.configure(fg_color=T["bg"])
    win.after(100, win.focus)

    top = ctk.CTkFrame(win, fg_color="transparent")
    top.pack(fill="x", padx=12, pady=(12, 4))
    ctk.CTkLabel(
        top, text="Projects", text_color=T["text"], font=("Segoe UI", 20, "bold"),
    ).pack(side="left")
    ctk.CTkButton(
        top, text="+ New project", width=120, fg_color=T["accent"], hover_color=T["accent_hover"],
        command=lambda: new_project(),
    ).pack(side="right")

    ctk.CTkLabel(
        win,
        text="A project keeps related chats together, with its own instructions and its own documents.",
        text_color=T["status"], font=("Segoe UI", 12), wraplength=600, justify="left",
    ).pack(anchor="w", padx=14, pady=(0, 6))

    body = ctk.CTkScrollableFrame(win, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def small(parent, text, command, danger=False):
        ctk.CTkButton(
            parent, text=text, width=84, height=28,
            fg_color=T["danger"] if danger else T["button"],
            hover_color=T["danger_hover"] if danger else T["button_hover"],
            text_color=T["text"], command=command,
        ).pack(side="left", padx=2)

    def render():
        for widget in body.winfo_children():
            widget.destroy()

        general = sum(1 for c in app.chats if not c.get("project"))
        ctk.CTkButton(
            body, text=f"All chats, no project  ({general} chats)", anchor="w", height=34,
            fg_color=T["button"], hover_color=T["button_hover"], text_color=T["text"],
            command=lambda: go(None),
        ).pack(fill="x", padx=4, pady=(2, 8))

        if not app.projects.items:
            ctk.CTkLabel(
                body, text="No projects yet. Click + New project.", text_color=T["status"],
            ).pack(pady=20)

        for project in app.projects.items:
            pid = project["id"]
            count = sum(1 for c in app.chats if c.get("project") == pid)
            files = len(app.projects.kb_for(pid).sources())
            card = ctk.CTkFrame(body, fg_color=T["panel"], corner_radius=10)
            card.pack(fill="x", padx=4, pady=4)
            ctk.CTkButton(
                card, text=project["name"], anchor="w", height=34,
                fg_color="transparent", hover_color=T["button_hover"], text_color=T["text"],
                font=("Segoe UI", 14, "bold"), command=lambda p=pid: go(p),
            ).pack(fill="x", padx=6, pady=(6, 0))
            note = "has instructions" if project.get("instructions") else "no instructions yet"
            ctk.CTkLabel(
                card, text=f"{count} chats  |  {files} files  |  {note}",
                text_color=T["status"], font=("Segoe UI", 11), anchor="w",
            ).pack(fill="x", padx=14)
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=(4, 8))
            small(row, "Open", lambda p=pid: go(p))
            small(row, "Instructions", lambda p=pid: edit_instructions(p))
            small(row, "Add files", lambda p=pid: add_files(p))
            small(row, "Rename", lambda p=pid: rename(p))
            small(row, "Delete", lambda p=pid: delete(p), danger=True)

    def go(project_id):
        win.destroy()
        app.open_project(project_id)

    def new_project():
        dialog = ctk.CTkInputDialog(text="Project name:", title="New project")
        name = dialog.get_input()
        if not name:
            return
        project, error = app.projects.create(name)
        if error:
            messagebox.showinfo("Projects", error, parent=win)
            return
        render()
        edit_instructions(project["id"])

    def rename(project_id):
        dialog = ctk.CTkInputDialog(text="New name:", title="Rename project")
        name = dialog.get_input()
        if name and not app.projects.rename(project_id, name):
            messagebox.showinfo("Projects", "That name is empty or already used.", parent=win)
        app.refresh_projects_button()
        render()

    def delete(project_id):
        name = app.projects.name_of(project_id)
        if not messagebox.askyesno(
            "Delete project",
            f"Delete the project '{name}'?\n\nIts chats are kept and move to your normal list. "
            "Its documents are removed.",
            parent=win,
        ):
            return
        app.delete_project(project_id)
        render()

    def add_files(project_id):
        win.destroy()
        app.open_project(project_id)
        app.add_document()   # your existing button; it now adds to this project

    def edit_instructions(project_id):
        project = app.projects.get(project_id)
        if not project:
            return
        box = ctk.CTkToplevel(win)
        box.title(f"Instructions: {project['name']}")
        box.geometry("560x420")
        box.configure(fg_color=T["bg"])
        box.after(100, box.focus)
        ctk.CTkLabel(
            box,
            text="Tell Aira how to behave in this project. Example: 'Answer like a patient "
                 "teacher. Keep replies short. Use simple English.'",
            text_color=T["text"], wraplength=520, justify="left",
        ).pack(anchor="w", padx=14, pady=(14, 6))
        text = ctk.CTkTextbox(box, fg_color=T["panel"], text_color=T["text"], wrap="word")
        text.pack(fill="both", expand=True, padx=14, pady=6)
        text.insert("1.0", project.get("instructions", ""))

        def save():
            app.projects.set_instructions(project_id, text.get("1.0", "end"))
            box.destroy()
            render()

        ctk.CTkButton(
            box, text="Save", fg_color=T["accent"], hover_color=T["accent_hover"], command=save,
        ).pack(pady=(4, 14))

    render()