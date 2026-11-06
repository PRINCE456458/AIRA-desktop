import os
import re

import customtkinter as ctk
from PIL import Image

import imagegen

# Aira's image replies contain a line like: Saved at: C:\...\images\kite_2026.jpg
IMAGE_LINE = re.compile(
    r"Saved at:\s*(.+\.(?:jpg|jpeg|png|webp|gif))\s*$", re.IGNORECASE | re.MULTILINE
)

def is_in_images_folder(path):
    folder = os.path.abspath(imagegen.OUT_DIR) + os.sep
    return os.path.abspath(path).startswith(folder)


class Bubble:
    """One message: a small caption (who) and a rounded box with the text."""

    def __init__(self, view, role, text, caption):
        theme = view.theme
        self.view = view
        self.role = role
        self.text = text
        self.image_path = None
        self._photo = None  # we must keep this, or the picture disappears
        anchor = {"user": "e", "ai": "w", "note": "center"}[role]

        self.row = ctk.CTkFrame(view, fg_color="transparent")
        self.row.pack(fill="x", pady=4)
        column = ctk.CTkFrame(self.row, fg_color="transparent")
        column.pack(anchor=anchor, padx=6)

        if caption:
            ctk.CTkLabel(
                column, text=caption, text_color=theme["status"], font=("Segoe UI", 11)
            ).pack(anchor=anchor, padx=6)

        if role == "user":
            fill, ink, size = theme["accent"], theme["text"], 15
        elif role == "ai":
            fill, ink, size = theme["panel"], theme["text"], 15
        else:
            fill, ink, size = "transparent", theme["status"], 12

        self.box = ctk.CTkFrame(column, fg_color=fill, corner_radius=16)
        self.box.pack(anchor=anchor)
        self.label = ctk.CTkLabel(
            self.box, text="", text_color=ink, font=("Segoe UI", size),
            justify="left", anchor="w", wraplength=view.max_width(),
        )
        self.label.pack(padx=14, pady=10)
        self.label.bind("<Button-3>", self.copy)  # right-click copies this message
        self.refresh()

    def refresh(self):
        shown = self.text.strip()
        self.label.configure(text=shown or "...")
        self.show_image_if_any()
        self.view.scroll_down()

    def show_image_if_any(self):
        """If this message says where a picture was saved, show the picture below the text."""
        if self.role != "ai" or self.image_path:
            return
        match = IMAGE_LINE.search(self.text)
        if not match:
            return
        path = match.group(1).strip()
        if not os.path.isfile(path) or not is_in_images_folder(path):
            return
        try:
            image = Image.open(path)
            width = min(420, max(240, self.view.max_width() - 40))
            height = max(1, int(image.height * width / image.width))
            self._photo = ctk.CTkImage(light_image=image, dark_image=image, size=(width, height))
            picture = ctk.CTkLabel(self.box, text="", image=self._photo)
            picture.pack(padx=14, pady=(0, 12))
            picture.bind("<Button-1>", lambda event, p=path: self.open_file(p))
            self.image_path = path
        except Exception:
            pass  # if the picture cannot be shown, the text still tells where it is

    @staticmethod
    def open_file(path):
        try:
            os.startfile(path)
        except Exception:
            pass

    def add_text(self, extra):
        self.text += extra
        self.refresh()

    def set_width(self, width):
        self.label.configure(wraplength=width)

    def copy(self, event=None):
        root = self.view.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(self.text.strip())
        root.update()


class ChatView(ctk.CTkScrollableFrame):
    """The scrolling chat area made of bubbles."""

    def __init__(self, master, theme, get_user_name):
        super().__init__(
            master, fg_color=theme["bg"], corner_radius=12,
            scrollbar_button_color=theme["button"],
            scrollbar_button_hover_color=theme["button_hover"],
        )
        self.theme = theme
        self.get_user_name = get_user_name
        self.bubbles = []
        self.live = None             # the Aira bubble that is being written right now
        self.extra = None            # the suggestion cards, shown until the first message
        self._last_width = None
        self._resize_job = None
        self._scroll_pending = False
        self.winfo_toplevel().bind("<Configure>", self._on_resize, add="+")

    def max_width(self):
        width = self.winfo_width()
        if width <= 1:
            width = self.winfo_toplevel().winfo_width() - 280
        return max(260, int(width * 0.72))

    def _on_resize(self, event=None):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self._apply_width)

    def _apply_width(self):
        self._resize_job = None
        width = self.max_width()
        if width == self._last_width:
            return
        self._last_width = width
        for bubble in self.bubbles:
            bubble.set_width(width)

    def set_extra(self, widget):
        """Show one extra widget (the suggestion cards) below the bubbles."""
        self.drop_extra()
        self.extra = widget
        widget.pack(fill="x", pady=6)

    def drop_extra(self):
        if self.extra is not None:
            self.extra.destroy()
            self.extra = None

    def clear(self):
        self.drop_extra()
        for bubble in self.bubbles:
            bubble.row.destroy()
        self.bubbles = []
        self.live = None

    def add(self, role, text, live=False):
        self.drop_extra()
        caption = {"user": self.get_user_name(), "ai": "Aira", "note": ""}[role]
        bubble = Bubble(self, role, text, caption)
        self.bubbles.append(bubble)
        if live:
            self.live = bubble
        self.scroll_down()
        return bubble

    def end_live(self):
        self.live = None

    def append(self, text):
        """Text that arrives while Aira is answering goes into the live bubble.
        Anything else that starts with [ becomes a small note."""
        if self.live is not None:
            self.live.add_text(text)
        elif text.strip():
            if text.strip().startswith("[") or not self.bubbles:
                self.add("note", text.strip())
            else:
                self.bubbles[-1].add_text(text)

    def scroll_down(self):
        if self._scroll_pending:
            return
        self._scroll_pending = True
        self.after(30, self._do_scroll)

    def _do_scroll(self):
        self._scroll_pending = False
        try:
            self._parent_canvas.update_idletasks()
            self._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass