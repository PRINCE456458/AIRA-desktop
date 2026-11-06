import os

import customtkinter as ctk
from PIL import Image

import imagegen

EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
COLUMNS = 3
THUMB = 180
MAX_IMAGES = 60


def list_images():
    """Your pictures, newest first."""
    if not os.path.isdir(imagegen.OUT_DIR):
        return []
    paths = [
        os.path.join(imagegen.OUT_DIR, name)
        for name in os.listdir(imagegen.OUT_DIR)
        if name.lower().endswith(EXTENSIONS)
    ]
    paths.sort(key=os.path.getmtime, reverse=True)
    return paths[:MAX_IMAGES]


def open_path(path):
    try:
        os.startfile(path)
    except Exception:
        pass


def open_folder():
    os.makedirs(imagegen.OUT_DIR, exist_ok=True)
    open_path(imagegen.OUT_DIR)


def open_gallery(parent, T):
    win = ctk.CTkToplevel(parent)
    win.title("Aira image gallery")
    win.geometry("640x560")
    win.configure(fg_color=T["bg"])
    win.after(100, win.focus)
    win._photos = []  # keep the thumbnails alive, or they vanish

    top = ctk.CTkFrame(win, fg_color="transparent")
    top.pack(fill="x", padx=12, pady=(12, 4))
    ctk.CTkLabel(
        top, text="Your images", font=("Segoe UI", 16, "bold"), text_color=T["text"]
    ).pack(side="left")
    ctk.CTkButton(
        top, text="Open folder", width=110,
        fg_color=T["button"], hover_color=T["button_hover"], command=open_folder,
    ).pack(side="right")

    area = ctk.CTkScrollableFrame(win, fg_color=T["panel"])
    area.pack(fill="both", expand=True, padx=12, pady=8)

    paths = list_images()
    if not paths:
        ctk.CTkLabel(
            area, text="No images yet.\nTry: draw a red kite flying over green hills",
            text_color=T["status"], font=("Segoe UI", 14),
        ).pack(pady=40)
        return

    shown = 0
    for path in paths:
        try:
            image = Image.open(path)
            image.thumbnail((THUMB, THUMB))
            photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        except Exception:
            continue  # skip a damaged file
        win._photos.append(photo)

        cell = ctk.CTkFrame(area, fg_color="transparent")
        cell.grid(row=shown // COLUMNS, column=shown % COLUMNS, padx=8, pady=8)
        ctk.CTkButton(
            cell, text="", image=photo, width=THUMB, height=THUMB,
            fg_color="transparent", hover_color=T["button_hover"],
            command=lambda p=path: open_path(p),
        ).pack()
        name = os.path.basename(path)
        short = name if len(name) <= 24 else name[:21] + "..."
        ctk.CTkLabel(cell, text=short, font=("Segoe UI", 11), text_color=T["status"]).pack()
        shown += 1