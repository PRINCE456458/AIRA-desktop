import json
import os
import subprocess
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

import paths
BASE_DIR = paths.DATA_DIR
DATA_FILE = os.path.join(BASE_DIR, "library.json")

# Folders where Aira saves what it makes. Add your own folder names here.
FOLDERS = ["images", "builds", "plans", "timetables", "expense_reports"]

KINDS = {
    "Images": (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"),
    "Websites": (".html", ".htm"),
    "Documents": (".pdf", ".docx", ".txt", ".md"),
    "Programs": (".py",),
}
BADGE_COLORS = {
    "Images": "#2a9d8f", "Websites": "#e76f51", "Documents": "#3a6ea5", "Programs": "#8a5cc2",
}
TABS = ["Suggested", "Favorites", "Folders", "Images", "All"]
MAX_SHOWN = 80
MAX_GRID = 60
GRID_COLUMNS = 5
THUMB = 56
BIG_THUMB = 120
MAX_COLLECTIONS = 40
OLD_DAYS = 30

WORDS = {
    "library", "my library", "open library", "open my library", "show library",
    "show my library", "my files", "show my files", "my creations", "show my creations",
}


def is_request(text):
    return text.lower().strip(" .!?") in WORDS


# ---------- Finding files ----------
def kind_of(name):
    ext = os.path.splitext(name)[1].lower()
    for kind, extensions in KINDS.items():
        if ext in extensions:
            return kind
    return None


def scan(base_dir=BASE_DIR, folders=FOLDERS):
    """Return everything Aira made, newest first."""
    items = []
    for folder in folders:
        root = os.path.join(base_dir, folder)
        if not os.path.isdir(root):
            continue
        for current, _dirs, files in os.walk(root):
            if current[len(root):].count(os.sep) > 1:   # at most one folder deep
                continue
            for name in files:
                kind = kind_of(name)
                if not kind:
                    continue
                path = os.path.join(current, name)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                items.append({
                    "path": path, "name": name, "kind": kind, "folder": folder,
                    "mtime": stat.st_mtime, "size": stat.st_size,
                })
    items.sort(key=lambda i: i["mtime"], reverse=True)
    return items


def filter_items(items, kind, needle):
    needle = needle.strip().lower()
    result = []
    for item in items:
        if kind not in ("All", "All types") and item["kind"] != kind:
            continue
        if needle and needle not in item["name"].lower():
            continue
        result.append(item)
    return result


def human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def is_inside(path, base_dir=BASE_DIR, folders=FOLDERS):
    """True only for files that live inside one of Aira's own folders."""
    real = os.path.realpath(path)
    for folder in folders:
        root = os.path.realpath(os.path.join(base_dir, folder))
        if real.startswith(root + os.sep):
            return True
    return False


# ---------- Favorites, folders and what you opened ----------
class LibraryData:
    def __init__(self, path=DATA_FILE, base_dir=BASE_DIR):
        self.path = path
        self.base_dir = base_dir
        self.favorites = []
        self.collections = {}   # folder name -> list of files
        self.opens = {}         # file -> {"count": n, "last": time}
        self._load()

    def rel(self, path):
        return os.path.relpath(path, self.base_dir).replace(os.sep, "/")

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.favorites = [x for x in data.get("favorites", []) if isinstance(x, str)]
            self.collections = {
                str(k): [x for x in v if isinstance(x, str)]
                for k, v in data.get("folders", {}).items() if isinstance(v, list)
            }
            self.opens = {
                k: v for k, v in data.get("opens", {}).items()
                if isinstance(v, dict) and "last" in v
            }
        except (FileNotFoundError, json.JSONDecodeError, AttributeError):
            pass

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                {"favorites": self.favorites, "folders": self.collections, "opens": self.opens},
                f, indent=2, ensure_ascii=False,
            )

    # favorites
    def is_favorite(self, path):
        return self.rel(path) in self.favorites

    def toggle_favorite(self, path):
        rel = self.rel(path)
        if rel in self.favorites:
            self.favorites.remove(rel)
        else:
            self.favorites.append(rel)
        self.save()
        return rel in self.favorites

    # folders
    def folder_names(self):
        return sorted(self.collections, key=str.lower)

    def create_folder(self, name):
        name = " ".join(name.split())[:30]
        if not name:
            return None, "Please give the folder a name."
        if len(self.collections) >= MAX_COLLECTIONS:
            return None, f"You can have up to {MAX_COLLECTIONS} folders."
        if any(n.lower() == name.lower() for n in self.collections):
            return None, f"You already have a folder called {name}."
        self.collections[name] = []
        self.save()
        return name, ""

    def rename_folder(self, old, new):
        new = " ".join(new.split())[:30]
        if old not in self.collections or not new:
            return False
        if any(n.lower() == new.lower() and n != old for n in self.collections):
            return False
        self.collections = {(new if k == old else k): v for k, v in self.collections.items()}
        self.save()
        return True

    def delete_folder(self, name):
        self.collections.pop(name, None)   # the files themselves are not touched
        self.save()

    def in_folder(self, name, path):
        return self.rel(path) in self.collections.get(name, [])

    def in_any_folder(self, path):
        rel = self.rel(path)
        return any(rel in files for files in self.collections.values())

    def toggle_in_folder(self, name, path):
        rel = self.rel(path)
        files = self.collections.setdefault(name, [])
        if rel in files:
            files.remove(rel)
        else:
            files.append(rel)
        self.save()

    def folder_count(self, name, existing):
        known = {self.rel(i["path"]) for i in existing}
        return sum(1 for rel in self.collections.get(name, []) if rel in known)

    # opens
    def record_open(self, path):
        rel = self.rel(path)
        info = self.opens.get(rel, {"count": 0, "last": 0})
        self.opens[rel] = {"count": info["count"] + 1, "last": time.time()}
        self.save()

    def forget(self, path):
        """Remove a deleted file from favorites, folders and history."""
        rel = self.rel(path)
        self.favorites = [x for x in self.favorites if x != rel]
        for files in self.collections.values():
            if rel in files:
                files.remove(rel)
        self.opens.pop(rel, None)
        self.save()


def suggestions(items, data, now=None):
    """Smart picks, worked out from your own habits. Returns [(title, hint, items)]."""
    now = now or time.time()
    by_rel = {data.rel(i["path"]): i for i in items}
    sections = []
    seen = set()

    cutoff = now - OLD_DAYS * 86400
    old = [
        i for i in items
        if i["mtime"] < cutoff and data.rel(i["path"]) not in data.opens
        and not data.is_favorite(i["path"]) and not data.in_any_folder(i["path"])
    ]
    old.sort(key=lambda i: i["size"], reverse=True)
    old_rels = {data.rel(i["path"]) for i in old[:5]}   # shown in their own section below

    recent = sorted(
        ((info["last"], rel) for rel, info in data.opens.items() if rel in by_rel), reverse=True
    )
    picked = [by_rel[rel] for _, rel in recent[:5]]
    if picked:
        sections.append(("Pick up where you left off", "The files you opened most recently.", picked))
        seen.update(data.rel(i["path"]) for i in picked)

    fresh = [i for i in items if data.rel(i["path"]) not in data.opens and data.rel(i["path"]) not in seen and data.rel(i["path"]) not in old_rels][:4]
    if fresh:
        sections.append(("New, not opened yet", "Things Aira made that you haven't looked at.", fresh))
        seen.update(data.rel(i["path"]) for i in fresh)

    loose = [
        i for i in items
        if data.rel(i["path"]) not in seen and data.rel(i["path"]) not in old_rels
        and not data.in_any_folder(i["path"]) and not data.is_favorite(i["path"])
    ][:5]
    if loose:
        sections.append(("Put these in a folder", "Use + Folder on a file to organize it.", loose))

    if old:
        sections.append((
            "Old and never opened", f"Over {OLD_DAYS} days old. Delete to free space, or star to keep.",
            old[:5],
        ))
    return sections


# ---------- Opening things ----------
def open_path(path):
    try:
        os.startfile(path)
    except Exception:
        pass


def show_in_folder(path):
    try:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    except Exception:
        open_path(os.path.dirname(path))


def make_thumbnail(path, size):
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            side = min(img.size)
            left, top = (img.width - side) // 2, (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side)).resize((size, size))
            return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except Exception:
        return None


# ---------- The window ----------
def open_library(app, T):
    win = ctk.CTkToplevel(app)
    win.title("Aira library")
    win.geometry("840x680")
    win.configure(fg_color=T["bg"])
    win.after(100, win.focus)

    data = LibraryData()
    state = {"items": scan(), "tab": "All", "type": "All types", "folder": None}
    thumbs = {}   # keeps thumbnails alive and avoids redrawing them

    def thumb(item, size):
        key = (item["path"], size, item["mtime"])
        if key not in thumbs:
            thumbs[key] = make_thumbnail(item["path"], size)
        return thumbs[key]

    # --- top bar ---
    top = ctk.CTkFrame(win, fg_color="transparent")
    top.pack(fill="x", padx=12, pady=(12, 4))
    ctk.CTkLabel(
        top, text="Library", text_color=T["text"], font=("Segoe UI", 20, "bold"),
    ).pack(side="left")
    count_label = ctk.CTkLabel(top, text="", text_color=T["status"], font=("Segoe UI", 12))
    count_label.pack(side="left", padx=12)
    ctk.CTkButton(
        top, text="Refresh", width=80, fg_color=T["button"], hover_color=T["button_hover"],
        text_color=T["text"], command=lambda: reload(),
    ).pack(side="right")
    type_menu = ctk.CTkOptionMenu(
        top, values=["All types"] + list(KINDS), width=120,
        fg_color=T["button"], button_color=T["button_hover"], text_color=T["text"],
        command=lambda value: set_type(value),
    )
    type_menu.set("All types")
    type_menu.pack(side="right", padx=8)

    search = ctk.CTkEntry(
        win, placeholder_text="Search by file name...",
        fg_color=T["panel"], border_color=T["accent"], text_color=T["text"],
    )
    search.pack(fill="x", padx=12, pady=(4, 6))
    search.bind("<KeyRelease>", lambda event: render())

    tabs = ctk.CTkSegmentedButton(
        win, values=TABS, command=lambda value: pick(value),
        selected_color=T["accent"], selected_hover_color=T["accent_hover"],
        unselected_color=T["button"], unselected_hover_color=T["button_hover"],
        text_color=T["text"],
    )
    tabs.set("All")
    tabs.pack(fill="x", padx=12, pady=(0, 6))

    body = ctk.CTkScrollableFrame(win, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    # --- actions ---
    def pick(value):
        state["tab"] = value
        state["folder"] = None
        render()

    def set_type(value):
        state["type"] = value
        render()

    def reload():
        state["items"] = scan()
        render()

    def open_item(item):
        data.record_open(item["path"])
        open_path(item["path"])

    def toggle_star(item):
        data.toggle_favorite(item["path"])
        render()

    def remove(item):
        if not is_inside(item["path"]):
            return
        if not messagebox.askyesno(
            "Delete file", f"Delete {item['name']}?\n\nThis cannot be undone.", parent=win,
        ):
            return
        try:
            os.remove(item["path"])
        except OSError as error:
            messagebox.showinfo("Library", f"Could not delete it: {error}", parent=win)
            return
        data.forget(item["path"])
        reload()

    def ask_name(question, title):
        dialog = ctk.CTkInputDialog(text=question, title=title)
        return (dialog.get_input() or "").strip()

    def new_folder(then_add=None):
        name = ask_name("Folder name:", "New folder")
        if not name:
            return
        created, error = data.create_folder(name)
        if error:
            messagebox.showinfo("Library", error, parent=win)
            return
        if then_add:
            data.toggle_in_folder(created, then_add["path"])
        render()

    def folder_menu(item):
        menu = tk.Menu(win, tearoff=0)
        for name in data.folder_names():
            if data.in_folder(name, item["path"]):
                label = f"Remove from '{name}'"
            else:
                label = f"Add to '{name}'"
            menu.add_command(
                label=label,
                command=lambda n=name: (data.toggle_in_folder(n, item["path"]), render()),
            )
        if data.folder_names():
            menu.add_separator()
        menu.add_command(label="New folder...", command=lambda: new_folder(item))
        try:
            menu.tk_popup(win.winfo_pointerx(), win.winfo_pointery())
        finally:
            menu.grab_release()

    def rename_folder(name):
        new = ask_name("New name:", "Rename folder")
        if new and data.rename_folder(name, new):
            state["folder"] = new
        elif new:
            messagebox.showinfo("Library", "That name is empty or already used.", parent=win)
        render()

    def delete_folder(name):
        if messagebox.askyesno(
            "Delete folder",
            f"Delete the folder '{name}'?\n\nThe files inside are NOT deleted.", parent=win,
        ):
            data.delete_folder(name)
            state["folder"] = None
            render()

    # --- building blocks ---
    def small(parent, text, command, width=64, danger=False, accent=False):
        fg = T["danger"] if danger else (T["accent"] if accent else T["button"])
        hover = T["danger_hover"] if danger else (T["accent_hover"] if accent else T["button_hover"])
        ctk.CTkButton(
            parent, text=text, width=width, height=26, fg_color=fg, hover_color=hover,
            text_color=T["text"], command=command,
        ).pack(side="left", padx=2)

    def title_line(text, hint=""):
        ctk.CTkLabel(
            body, text=text, text_color=T["accent"], font=("Segoe UI", 14, "bold"), anchor="w",
        ).pack(fill="x", padx=8, pady=(10, 0))
        if hint:
            ctk.CTkLabel(
                body, text=hint, text_color=T["status"], font=("Segoe UI", 11), anchor="w",
            ).pack(fill="x", padx=8, pady=(0, 2))

    def note(text):
        ctk.CTkLabel(body, text=text, text_color=T["status"], wraplength=700).pack(pady=30)

    def file_row(item):
        row = ctk.CTkFrame(body, fg_color=T["panel"], corner_radius=10)
        row.pack(fill="x", padx=4, pady=3)

        picture = thumb(item, THUMB) if item["kind"] == "Images" else None
        if picture:
            ctk.CTkLabel(row, text="", image=picture).pack(side="left", padx=8, pady=6)
        else:
            ext = os.path.splitext(item["name"])[1].upper().lstrip(".")
            ctk.CTkLabel(
                row, text=ext, width=THUMB, height=THUMB, corner_radius=8,
                fg_color=BADGE_COLORS[item["kind"]], text_color="#ffffff",
                font=("Segoe UI", 13, "bold"),
            ).pack(side="left", padx=8, pady=6)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        name = item["name"] if len(item["name"]) <= 30 else item["name"][:27] + "..."
        ctk.CTkLabel(
            info, text=name, text_color=T["text"], font=("Segoe UI", 13, "bold"), anchor="w",
        ).pack(fill="x")
        when = datetime.fromtimestamp(item["mtime"]).strftime("%d %b %Y, %I:%M %p")
        ctk.CTkLabel(
            info, text=f"{item['kind']}  |  {human_size(item['size'])}  |  {when}",
            text_color=T["status"], font=("Segoe UI", 11), anchor="w",
        ).pack(fill="x")

        buttons = ctk.CTkFrame(row, fg_color="transparent")
        buttons.pack(side="right", padx=6)
        starred = data.is_favorite(item["path"])
        small(buttons, "★" if starred else "☆", lambda i=item: toggle_star(i),
              width=32, accent=starred)
        small(buttons, "+ Folder", lambda i=item: folder_menu(i), width=70)
        small(buttons, "Open", lambda i=item: open_item(i), width=52)
        small(buttons, "Explorer", lambda i=item: show_in_folder(i["path"]), width=68)
        small(buttons, "Delete", lambda i=item: remove(i), width=56, danger=True)

    def file_list(found):
        for item in found[:MAX_SHOWN]:
            file_row(item)
        if len(found) > MAX_SHOWN:
            note(f"Showing the newest {MAX_SHOWN}. Use the search box to find older ones.")

    # --- the five tabs ---
    def show_all():
        found = filter_items(state["items"], state["type"], search.get())
        count_label.configure(text=f"{len(found)} item(s)")
        if not found:
            note("Nothing here yet. Ask Aira to draw, build or write something.")
        file_list(found)

    def show_suggested():
        sections = suggestions(state["items"], data)
        count_label.configure(text="")
        if not sections:
            note("No suggestions yet. Make something, open some files, and I will learn what you use.")
        for title, hint, found in sections:
            title_line(title, hint)
            for item in found:
                file_row(item)

    def show_favorites():
        found = [i for i in state["items"] if data.is_favorite(i["path"])]
        found = filter_items(found, state["type"], search.get())
        count_label.configure(text=f"{len(found)} favorite(s)")
        if not found:
            note("No favorites yet. Click the star next to a file to keep it here.")
        file_list(found)

    def show_images():
        found = filter_items(state["items"], "Images", search.get())
        count_label.configure(text=f"{len(found)} image(s)")
        if not found:
            note("No images yet. Type: draw a red fox in the snow")
            return
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x", padx=4, pady=4)
        for index, item in enumerate(found[:MAX_GRID]):
            cell = ctk.CTkFrame(grid, fg_color=T["panel"], corner_radius=10)
            cell.grid(row=index // GRID_COLUMNS, column=index % GRID_COLUMNS, padx=4, pady=4)
            picture = thumb(item, BIG_THUMB)
            ctk.CTkButton(
                cell, text="" if picture else "IMG", image=picture, width=BIG_THUMB, height=BIG_THUMB,
                fg_color="transparent", hover_color=T["button_hover"],
                command=lambda i=item: open_item(i),
            ).pack(padx=4, pady=(4, 2))
            bar = ctk.CTkFrame(cell, fg_color="transparent")
            bar.pack(pady=(0, 4))
            starred = data.is_favorite(item["path"])
            small(bar, "★" if starred else "☆", lambda i=item: toggle_star(i),
                  width=34, accent=starred)
            small(bar, "+ Folder", lambda i=item: folder_menu(i), width=60)
            small(bar, "Delete", lambda i=item: remove(i), width=48, danger=True)
        if len(found) > MAX_GRID:
            note(f"Showing the newest {MAX_GRID}. Use the search box to find older ones.")

    def show_folders():
        count_label.configure(text="")
        name = state["folder"]
        if name and name not in data.collections:
            state["folder"] = name = None
        if name is None:
            bar = ctk.CTkFrame(body, fg_color="transparent")
            bar.pack(fill="x", padx=4, pady=(4, 6))
            small(bar, "+ New folder", lambda: new_folder(), width=110, accent=True)
            if not data.folder_names():
                note("No folders yet. Click + New folder, or use + Folder on any file.")
            for folder in data.folder_names():
                total = data.folder_count(folder, state["items"])
                ctk.CTkButton(
                    body, text=f"\U0001F4C1  {folder}   ({total} files)", anchor="w", height=40,
                    fg_color=T["panel"], hover_color=T["button_hover"], text_color=T["text"],
                    font=("Segoe UI", 14, "bold"),
                    command=lambda f=folder: (state.update(folder=f), render()),
                ).pack(fill="x", padx=4, pady=3)
            return
        bar = ctk.CTkFrame(body, fg_color="transparent")
        bar.pack(fill="x", padx=4, pady=(4, 6))
        small(bar, "< Back", lambda: (state.update(folder=None), render()), width=70)
        ctk.CTkLabel(
            bar, text=f"  {name}", text_color=T["text"], font=("Segoe UI", 16, "bold"),
        ).pack(side="left")
        small(bar, "Delete folder", lambda: delete_folder(name), width=100, danger=True)
        small(bar, "Rename", lambda: rename_folder(name), width=70)
        inside = [i for i in state["items"] if data.in_folder(name, i["path"])]
        inside = filter_items(inside, state["type"], search.get())
        if not inside:
            note("This folder is empty. Use + Folder on a file to add it here.")
        file_list(inside)

    def render():
        for widget in body.winfo_children():
            widget.destroy()
        {
            "All": show_all, "Suggested": show_suggested, "Favorites": show_favorites,
            "Folders": show_folders, "Images": show_images,
        }[state["tab"]]()

    render()