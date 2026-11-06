import json
import os
import random
import threading
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
import requests

import builder
import pro
import support
import supportwin
import prowin
import checks
import help_center
import projects
import projectwin
import control_center
import creator
import chatview
import library
import internet
import commands
import gallery
import imagegen
import suggestions
import expenses
import memory
import modes
import plugins
import rag
import reminders
import storage
import tasks
import taskwin
import suggestions
import themes
import toolbox
import timetable
import tools
import vision
import voice
import websearch

OLLAMA_URL = "http://localhost:11434/api/chat"

T = themes.get_theme(storage.load_settings().get("theme", "Purple dark"))
ctk.set_appearance_mode(T["mode"])
if T["mode"] == "light":
    for widget in ("CTkButton", "CTkOptionMenu", "CTkSegmentedButton"):
        ctk.ThemeManager.theme.get(widget, {})["text_color"] = ["#111111", "#111111"]


class AiraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Aira AI")
        self.geometry("1000x760")
        self.after(0, lambda: self.state("zoomed"))
        self.configure(fg_color=T["bg"])

        self.kb = rag.KnowledgeBase()
        self.projects = projects.ProjectStore(self.kb)
        self.project_id = None
        self.tasks = tasks.TaskStore()
        self.task_running = False
        self.pro = pro.ProState()
        self.memory = memory.MemoryStore()
        self.reminders = reminders.ReminderStore()
        self.expenses = expenses.ExpenseStore()
        self.plugins = plugins.PluginManager()
        self.quiz_chunks = []
        self.builds = {}
        self.restyle_job = None
        self.settings = storage.load_settings()
        self.chats = storage.load_chats()
        if not self.chats:
            self.chats = [storage.new_chat()]
        self.current = self.chats[0]
        self.is_busy = False
        self.stop_requested = False
        self.thinking = False
        self.recording = False
        self.pending_image = None  # path of the picture waiting to be sent

        self.speaker = voice.Speaker()
        self.speaker.rate = self.settings["voice_rate"]
        self.listener = voice.Listener() if voice.STT_AVAILABLE else None

        self.mode = self.settings.get("mode", "Normal")
        if self.mode not in modes.MODES:
            self.mode = "Normal"


        self.build_sidebar()
        self.build_chat_area()
        self.refresh_sidebar()
        self.render_chat()
        self.project_id = self.current.get("project")
        self.apply_project()
        self.refresh_sidebar()
        self.apply_project()
        self.after(500, self.startup_check)
        self.after(1500, self.check_reminders)
        self.bind("<Control-n>", lambda event: self.new_chat())
        self.bind("<Control-f>", lambda event: self.search_entry.focus())
        self.bind("<Control-l>", lambda event: self.entry.focus())
        self.bind("<Control-t>", lambda event: toolbox.open_toolbox(self, T))
        self.after(8000, self.check_tasks)
        self.bind("<Control-e>", lambda event: self.export_chat())
        self.bind("<Escape>", lambda event: self.speaker.stop())
        self.entry.focus()
        self.apply_plan()
        self.after(4000, self.pro_check)
           
           
    def open_help(self):
        help_center.open_help(self, T)

    # ---------- Building the screen ----------
    def build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=230, fg_color=T["sidebar"], corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkButton(
            self.sidebar, text="+ New chat",
            fg_color=T["accent"], hover_color=T["accent_hover"],
            command=self.new_chat,
        ).pack(fill="x", padx=12, pady=(12, 8))

        self.projects_button = ctk.CTkButton(
            self.sidebar, text="Projects",
            fg_color=T["accent"], hover_color=T["accent_hover"],
            command=lambda: projectwin.open_projects(self, T),
        )
        ctk.CTkButton(
            self.sidebar, text="Help and feedback",
            fg_color=T["button"], hover_color=T["button_hover"],
            command=lambda: supportwin.open_support(self, T),
        ).pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkButton(
            self.sidebar, text="Library",
            fg_color=T["accent"], hover_color=T["accent_hover"],
            command=lambda: library.open_library(self, T),
        ).pack(fill="x", padx=12, pady=(0, 8))
        self.projects_button.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkButton(
            self.sidebar, text="Tasks",
            fg_color=T["accent"], hover_color=T["accent_hover"],
            command=lambda: taskwin.open_tasks(self, T),
        ).pack(fill="x", padx=12, pady=(0, 8))
        self.pro_button = ctk.CTkButton(
            self.sidebar, text="Upgrade to Pro",
            fg_color=T["accent"], hover_color=T["accent_hover"],
            command=lambda: prowin.open_pro(self, T),
        )
        self.pro_button.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkButton(
            self.sidebar, text="All settings",
            fg_color=T["button"], hover_color=T["button_hover"],
            command=self.open_control_center,
        ).pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(
            self.sidebar, text="Help & feedback",
            fg_color=T["button"], hover_color=T["button_hover"],
            command=self.open_help,
        ).pack(fill="x", padx=12, pady=4)

        self.mode_menu = ctk.CTkOptionMenu(
            self.sidebar, values=list(modes.MODES.keys()),
            fg_color=T["button"], button_color="#030106", button_hover_color=T["accent"],
            command=self.change_mode,
        )
        self.mode_menu.set(self.mode)
        self.mode_menu.pack(fill="x", padx=12, pady=(0, 8))
        self.search_entry = ctk.CTkEntry(
            self.sidebar, placeholder_text="Search chats...",
            fg_color=T["panel"], border_color=T["accent"], text_color=T["text"],
        )
        self.search_entry.pack(fill="x", padx=12, pady=(0, 8))
        self.search_entry.bind("<KeyRelease>", lambda event: self.refresh_sidebar())

        self.chat_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.chat_list.pack(fill="both", expand=True, padx=4)

        
        ctk.CTkButton(
            self.sidebar, text="Toolbox",
            fg_color=T["accent"], hover_color=T["accent_hover"],
            command=lambda: toolbox.open_toolbox(self, T),
        ).pack(fill="x", padx=12, pady=(4, 8))

       

        ctk.CTkButton(
            self.sidebar, text="Stop voice",
            fg_color=T["button"], hover_color=T["button_hover"],
            command=self.speaker.stop,
        ).pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkButton(
            self.sidebar, text="Rename chat",
            fg_color=T["button"], hover_color=T["button_hover"],
            command=self.rename_chat,
        ).pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(
            self.sidebar, text="Delete this chat",
            fg_color=T["danger"], hover_color=T["danger_hover"],
            command=self.delete_chat,
        ).pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(
            self.sidebar, text="Settings",
            fg_color=T["button"], hover_color=T["button_hover"],
            command=self.open_settings,
        ).pack(fill="x", padx=12, pady=(4, 12))

    def build_chat_area(self):
        area = ctk.CTkFrame(self, fg_color="transparent")
        area.pack(side="right", fill="both", expand=True)

        self.header = ctk.CTkLabel(
            area, text=self.header_text(), text_color=T["text"],
            font=("Segoe UI", 16, "bold"), anchor="w",
        )
        self.header.pack(fill="x", padx=22, pady=(14, 0))

        self.view = chatview.ChatView(area, T, lambda: self.settings["user_name"])
        self.view.pack(fill="both", expand=True, padx=15, pady=(8, 8))
        self.status_label = ctk.CTkLabel(
            area, text="", text_color=T["status"], anchor="w"
        )
        self.status_label.pack(fill="x", padx=22)

        # Small bar that shows the attached image (hidden until you pick one)
        self.attach_bar = ctk.CTkFrame(area, fg_color=T["panel"], corner_radius=8)
        self.attach_label = ctk.CTkLabel(self.attach_bar, text="", text_color=T["text"])
        self.attach_label.pack(side="left", padx=10, pady=4)
        ctk.CTkButton(
            self.attach_bar, text="Remove", width=70, height=26,
            fg_color=T["danger"], hover_color=T["danger_hover"],
            command=self.clear_image,
        ).pack(side="right", padx=8, pady=4)

        self.bottom = ctk.CTkFrame(area, fg_color="transparent")
        self.bottom.pack(fill="x", padx=15, pady=(0, 15))

        self.send_btn = ctk.CTkButton(
            self.bottom, text="Send", width=90, height=42,
            fg_color=T["accent"], hover_color=T["accent_hover"],
            command=self.on_send_click,
        )
        self.send_btn.pack(side="right")

        self.mic_btn = ctk.CTkButton(
            self.bottom, text="Mic", width=70, height=42,
            fg_color=T["button"], hover_color=T["button_hover"],
            command=self.toggle_mic,
        )
        self.mic_btn.pack(side="right", padx=(0, 8))

        self.image_btn = ctk.CTkButton(
            self.bottom, text="Image", width=70, height=42,
            fg_color=T["button"], hover_color=T["button_hover"],
            command=self.pick_image,
        )
        self.image_btn.pack(side="right", padx=(0, 8))

        self.entry = ctk.CTkEntry(
            self.bottom, placeholder_text="Type your message and press Enter...",
            height=42, fg_color=T["panel"], border_color=T["accent"],
            text_color=T["text"],
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry.bind("<Return>", lambda event: self.send_message())

    # ---------- Sidebar and chat switching ----------
    def refresh_sidebar(self):
        for widget in self.chat_list.winfo_children():
            widget.destroy()
        needle = self.search_entry.get().strip().lower()
        for chat in self.chats:
            if chat.get("project") != self.project_id:
                continue
            if needle:
                in_title = needle in chat["title"].lower()
                in_text = any(needle in m["content"].lower() for m in chat["messages"])
                if not (in_title or in_text):
                    continue
            active = chat is self.current
            ctk.CTkButton(
                self.chat_list, text=chat["title"], anchor="w",
                fg_color=T["accent"] if active else "transparent",
                hover_color=T["button_hover"], text_color=T["text"],
                command=lambda c=chat: self.open_chat(c),
            ).pack(fill="x", pady=2)

    def open_chat(self, chat):
        if self.is_busy:
            return
        self.current = chat
        self.refresh_sidebar()
        self.render_chat()

    def new_chat(self):
        if self.is_busy or not self.current["messages"]:
            return
        chat = storage.new_chat()
        chat["project"] = self.project_id
        self.chats.insert(0, chat)
        self.current = chat
        storage.save_chats(self.chats)
        self.refresh_sidebar()
        self.render_chat()

    def delete_chat(self):
        if self.is_busy:
            return
        self.chats.remove(self.current)
        same = [c for c in self.chats if c.get("project") == self.project_id]
        if not same:
            fresh = storage.new_chat()
            fresh["project"] = self.project_id
            self.chats.insert(0, fresh)
            same = [fresh]
        self.current = same[0]
        self.apply_project()
        storage.save_chats(self.chats)
        self.refresh_sidebar()
        self.render_chat()

    # ---------- Showing messages ----------
    def append_text(self, text):
        self.view.append(text)

    def render_chat(self):
        self.view.clear()
        self.view.add("ai", "Hi! I'm Aira AI. Ask me anything, or attach an image.")
        for message in self.current["messages"]:
            role = "user" if message["role"] == "user" else "ai"
            self.view.add(role, message["content"])
        if not self.current["messages"]:
            self.show_suggestions()

    def header_text(self):
        return f"Aira AI    |    {self.mode} mode"
    # ---------- Images ----------
    def pick_image(self):
        if self.is_busy:
            return
        path = filedialog.askopenfilename(
            title="Choose an image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")],
        )
        if path:
            self.pending_image = path
            self.attach_label.configure(text=f"Image attached: {os.path.basename(path)}")
            self.attach_bar.pack(fill="x", padx=15, pady=(0, 8), before=self.bottom)

    def clear_image(self):
        self.pending_image = None
        self.attach_bar.pack_forget()

    # ---------- Sending and receiving ----------
    def send_message(self):
        text = self.entry.get().strip()
        image_path = self.pending_image
        if (not text and not image_path) or self.is_busy:
            return

        image_b64 = None
        question = text
        if image_path:
            try:
                image_b64 = vision.image_to_base64(image_path)
            except Exception as error:
                self.append_text(f"[Could not open the image: {error}]\n\n")
                return
            if result is None and support.is_request(text):
                supportwin.open_support(self, T)
                result = "Opening help and support."
            if not question:
                question = "Describe this image in detail."
            text = f"[Image: {os.path.basename(image_path)}] {question}"
            self.clear_image()
            text = f"[Image: {os.path.basename(image_path)}] {question}"
            self.clear_image()
            if imagegen.is_restyle_request(question):
                self.restyle_job = (image_b64, question)
                self.start_build(text, "restyle")
                return
        if not image_b64:
            result = self.memory.handle(text)
            if result is None:
                result = self.reminders.handle(text)
            if result is None:
                result = self.expenses.handle(text) 
            if result is None:
                result = self.plugins.handle(text)
            if result is None and imagegen.is_gallery_request(text):
                gallery.open_gallery(self, T)
                result = "Opening your image gallery."
            if result is None and library.is_request(text):
                library.open_library(self, T)
                result = "Opening your library."
            if result is None:
                result = commands.try_command(text)   
            if result is None:
                result = commands.try_command(text)
            if result is None:
                result = timetable.handle(text, self.settings["user_name"])
            if result is None:
                result = builder.quick_reply(text)
            if result is not None:
                self.run_local_command(text, result)
                return
            if imagegen.is_request(text):
                self.start_build(text, "image")
                return
            kind = creator.detect(text)
            if kind:
                self.start_build(text, kind)
                return
            kind = creator.detect(text)
            if kind:
                self.start_build(text, kind)
                return
            if builder.is_request(text, self.current["id"] in self.builds):
                self.start_build(text)
                return
        if self.mode == "Quiz from notes" and not self.kb.items and not image_b64:
            self.append_text(
                "[Quiz from notes needs a document first. Click Add document, then type 'start'.]\n\n"
            )
            return

        self.speaker.stop()
        self.speaker.stop()
        self.entry.delete(0, "end")
        self.is_busy = True
        self.stop_requested = False
        self.send_btn.configure(text="Stop", fg_color=T["stop"], hover_color=T["stop_hover"])

        chat = self.current
        if not chat["messages"]:
            chat["title"] = text[:24]
            self.refresh_sidebar()

        chat["messages"].append({"role": "user", "content": text})
        self.view.add("user", text)
        self.view.add("ai", "", live=True)

        threading.Thread(
            target=self.get_reply, args=(chat, question, image_b64), daemon=True
        ).start()
        self.start_thinking()


        
    def get_reply(self, chat, question, image_b64):
        sources = []
        if image_b64:
            # Vision: send only this question + the picture to the vision model
            model = self.settings["vision_model"]
            payload_messages = [
                {"role": "user", "content": question, "images": [image_b64]}
            ]
        else:
            model = self.settings["model"]
            system_text = (
                modes.build_system_prompt(self.mode, self.settings["system_prompt"])
                + self.memory.as_prompt()
                + self.projects.prompt_for(chat.get("project"))
            )
            payload_messages = [
                {"role": "system", "content": system_text}
            ] + list(chat["messages"])

            notes = ""
            topic = websearch.extract_topic(question)
            if topic:
                self.after(0, self.append_text, f"[Looking up '{topic}' on Wikipedia...]\n")
                try:
                    page = websearch.wikipedia_lookup(topic)
                except Exception:
                    page = None
                if page:
                    notes = f"[Wikipedia: {page['title']}] {page['text']}"
                    sources = [f"Wikipedia - {page['title']} {page['url']}".strip()]
                else:
                    self.after(
                        0, self.append_text,
                        "[Could not reach Wikipedia or found nothing. Answering from my own knowledge, so it may be wrong.]\n",
                    )
            else:
                try:
                    hits = self.kb.search(question)
                except Exception:
                    hits = []  # if searching fails, just chat normally
                if hits:
                    notes = "\n\n".join(f"[{h['source']}] {h['text']}" for h in hits)
                    sources = sorted(set(h["source"] for h in hits))

            if notes:
                payload_messages[-1] = {
                    "role": "user",
                    "content": (
                        "Here are notes from a reliable source. Use them to answer the "
                        "question in your own words. If the notes do not cover it, say so "
                        "instead of guessing.\n\n"
                        f"NOTES:\n{notes}\n\nQUESTION: {question}"
                    ),
                }
        try:
            with requests.post(
                OLLAMA_URL,
            json={
                    "model": model,
                    "messages": payload_messages,
                    "stream": True,
                    "options": {"temperature": self.settings["temperature"]},
                },
                stream=True,
                timeout=300,
            ) as response:
                response.raise_for_status()
                reply = ""
                for line in response.iter_lines():
                    if self.stop_requested:
                        self.after(0, self.append_text, " [stopped]")
                        break
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk and not reply:
                        self.after(0, self.stop_thinking)
                    reply += chunk
                    self.after(0, self.append_text, chunk)
                    if data.get("done"):
                        break
            chat["messages"].append({"role": "assistant", "content": reply})
            if sources:
                self.after(0, self.append_text, f"\n[Sources: {', '.join(sources)}]")
            if self.settings["speak_replies"] and reply and not self.stop_requested:
                self.after(0, self.speaker.speak, reply)
        except requests.exceptions.ConnectionError:
            chat["messages"].pop()
            self.after(0, self.append_text, "[Ollama is not running. Open the Ollama app and try again.]")
        except Exception as error:
            chat["messages"].pop()
            self.after(0, self.append_text, f"[Error: {error}. If the model is missing, run: ollama pull {model}]")
        finally:
            self.after(0, self.append_text, "\n\n")
            self.after(0, self.finish)

    def finish(self):
        self.view.end_live()
        self.is_busy = False
        self.stop_requested = False
        self.stop_thinking()
        self.send_btn.configure(
            state="normal", text="Send", fg_color=T["accent"], hover_color=T["accent_hover"]
        )
        storage.save_chats(self.chats)
        self.refresh_sidebar()
    def run_local_command(self, text, result):
        self.speaker.stop()
        self.entry.delete(0, "end")
        chat = self.current
        if not chat["messages"]:
            chat["title"] = text[:24]
        chat["messages"].append({"role": "user", "content": text})
        chat["messages"].append({"role": "assistant", "content": result})
        self.view.add("user", text)
        self.view.add("ai", result)
        if self.settings["speak_replies"]:
            self.speaker.speak(result)
        storage.save_chats(self.chats)
        self.refresh_sidebar()


    def rename_chat(self):
        if self.is_busy:
            return
        dialog = ctk.CTkInputDialog(text="New name for this chat:", title="Rename chat")
        name = dialog.get_input()
        if name and name.strip():
            self.current["title"] = name.strip()[:40]
            storage.save_chats(self.chats)
            self.refresh_sidebar()

        # ---------- Thinking indicator and Stop ----------
    def on_send_click(self):
        if self.is_busy:
            self.stop_requested = True
        else:
            self.send_message()

    def start_thinking(self):
        self.thinking = True
        self.animate_thinking(0)

    def animate_thinking(self, step):
        if not self.thinking:
            return
        self.status_label.configure(text="Aira is thinking" + "." * (step % 4))
        self.after(400, self.animate_thinking, step + 1)

    def stop_thinking(self):
        self.thinking = False
        self.status_label.configure(text="")    


            # ---------- Agent mode ----------
    def run_agent(self, payload_messages):
        """Let the AI ask for tools, run them, and add the results to the conversation."""
        for _ in range(3):  # at most 3 rounds, so it can never loop forever
            if self.stop_requested:
                return
            try:
                response = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": self.settings["model"],
                        "messages": payload_messages,
                        "tools": tools.TOOLS,
                        "stream": False,
                        "options": {"temperature": 0.2},
                    },
                    timeout=300,
                )
                response.raise_for_status()
            except requests.exceptions.ConnectionError:
                return  # the normal request below shows the friendly error
            except Exception:
                self.after(
                    0, self.append_text,
                    "[This model cannot use tools. Answering normally.]\n",
                )
                return

            message = response.json().get("message", {})
            calls = message.get("tool_calls") or []
            if not calls:
                return  # the AI needs no tool

            payload_messages.append(message)
            for call in calls:
                function = call.get("function", {})
                name = function.get("name", "")
                args = function.get("arguments") or {}
                self.after(0, self.append_text, f"[Using tool: {name} {args}]\n")
                result = tools.run_tool(name, args, self.kb, self.memory)
                payload_messages.append(
                    {"role": "tool", "tool_name": name, "content": result}
                )    

    # ---------- Website and app builder ----------
    def start_build(self, text, kind="web"):
        self.speaker.stop()
        self.entry.delete(0, "end")
        chat = self.current
        if not chat["messages"]:
            chat["title"] = text[:24]
            self.refresh_sidebar()
        chat["messages"].append({"role": "user", "content": text})
        waiting = {
            "web": "Building your page. This can take 1 to 3 minutes, please wait...",
            "pdf": "Writing your PDF. This can take a minute, please wait...",
            "docx": "Writing your Word document. This can take a minute, please wait...",
            "python": "Writing your Python program. This can take a minute, please wait...",
            "kit": "Reading your notes and writing your study kit. This can take 1 to 2 minutes, please wait...",
            "image": "Painting your image. This can take 20 to 60 seconds, please wait...",
            "restyle": "Looking at your picture and painting a new version. This can take a minute or two, please wait...",
        }[kind]
        self.view.add("user", text)
        self.view.add("ai", waiting, live=True)
        self.is_busy = True
        self.stop_requested = False
        self.send_btn.configure(text="Stop", fg_color=T["stop"], hover_color=T["stop_hover"])
        self.start_thinking()
        threading.Thread(target=self.do_build, args=(chat, text, kind), daemon=True).start()

    def do_build(self, chat, text, kind):
        model = self.settings["model"]
        try:
            if kind == "web":
                result = builder.build(
                    text, model, self.builds.get(chat["id"]), lambda: self.stop_requested
                )
                if result["html"]:
                    self.builds[chat["id"]] = result["html"]
                message = result["message"]
            elif kind == "image":
                message = imagegen.create(text, model, lambda: self.stop_requested)
            elif kind == "restyle":
                image_b64, request = self.restyle_job
                message = imagegen.restyle(
                    image_b64, request, self.settings["vision_model"], lambda: self.stop_requested
                )
            else:
                message = creator.create(
                    kind, text, model, self.kb, lambda: self.stop_requested
                )
        except requests.exceptions.ConnectionError:
            message = "[Ollama is not running. Open the Ollama app and try again.]"
        except Exception as error:
            message = f"[Build error: {error}. If the model is missing, run: ollama pull {model}]"
        chat["messages"].append({"role": "assistant", "content": message})
        self.after(0, self.append_text, message + "\n\n")
        self.after(0, self.finish)

    # ---------- Reminders ----------
    def check_reminders(self):
        """Runs every 15 seconds and rings any reminder whose time has come."""
        try:
            for item in self.reminders.pop_due():
                self.show_reminder(item)
        except Exception as error:
            print("Reminder error:", error)
        self.after(15000, self.check_reminders)

    def show_reminder(self, item):
        text = item["text"]
        due = datetime.fromisoformat(item["due"])
        late = ""
        if (datetime.now() - due).total_seconds() > 90:
            late = f"(was due at {due.strftime('%I:%M %p, %d %b')})"

        try:
            import winsound
            winsound.MessageBeep()
        except Exception:
            pass
        if self.settings["speak_replies"]:
            self.speaker.speak("Reminder. " + text)
        if not self.is_busy:
            self.append_text(f"[Reminder: {text} {late}]\n\n")

        win = ctk.CTkToplevel(self)
        win.title("Aira reminder")
        win.geometry("380x210")
        win.configure(fg_color=T["bg"])
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="Reminder", font=("Segoe UI", 13), text_color=T["status"]).pack(pady=(18, 2))
        ctk.CTkLabel(
            win, text=text, font=("Segoe UI", 18, "bold"),
            text_color=T["text"], wraplength=330,
        ).pack(padx=16)
        if late:
            ctk.CTkLabel(win, text=late, text_color=T["status"]).pack(pady=(4, 0))
        ctk.CTkButton(
            win, text="OK", fg_color=T["accent"], hover_color=T["accent_hover"],
            command=win.destroy,
        ).pack(pady=16)
        win.after(200, win.focus)
            # ---------- Projects ----------
    def apply_project(self):
        self.kb = self.projects.kb_for(self.current.get("project"))
        self.refresh_projects_button()

    def refresh_projects_button(self):
        name = self.projects.name_of(self.project_id)
        self.projects_button.configure(text=f"Project: {name}" if name else "Projects")

    def open_project(self, project_id):
        if self.is_busy:
            return
        self.project_id = project_id
        same = [c for c in self.chats if c.get("project") == project_id]
        if not same:
            chat = storage.new_chat()
            chat["project"] = project_id
            self.chats.insert(0, chat)
            same = [chat]
        self.current = same[0]
        storage.save_chats(self.chats)
        self.apply_project()
        self.refresh_sidebar()
        self.render_chat()

    def delete_project(self, project_id):
        if self.is_busy:
            return
        # empty chats of the project are dropped, chats with messages move to the normal list
        self.chats[:] = [
            c for c in self.chats if not (c.get("project") == project_id and not c["messages"])
        ]
        if not self.chats:
            self.chats.append(storage.new_chat())
        self.projects.delete(project_id, self.chats)
        if self.project_id == project_id:
            self.open_project(None)
        else:
            storage.save_chats(self.chats)
            self.refresh_sidebar()
    # ---------- Suggested tasks ----------
    def show_suggestions(self):
        import suggestions
        panel = suggestions.make_panel(self.view, T, self.mode, self.use_suggestion)
        self.view.set_extra(panel)

    def use_suggestion(self, prompt):
        if self.is_busy:
            return
        self.entry.delete(0, "end")
        self.entry.insert(0, prompt)
        self.send_message()

            # ---------- Tasks ----------
    def check_tasks(self):
        try:
            if not self.is_busy and not self.task_running:
                due = self.tasks.due()
                if due:
                    self.run_task(due[0]["id"])
        except Exception:
            pass
        self.after(30000, self.check_tasks)

    def run_task(self, task_id, manual=False):
        task = self.tasks.get(task_id)
        if not task or self.task_running:
            return False
        self.task_running = True
        threading.Thread(target=self.do_task, args=(task_id, manual), daemon=True).start()
        return True

    def do_task(self, task_id, manual):
        task = self.tasks.get(task_id)
        system = (
            self.settings["system_prompt"]
            + "\n\nThis is a scheduled task you were asked to do. Answer directly, in short "
            "plain text. Do not ask questions unless the task says to."
        )
        text, error = tasks.run_prompt(task["prompt"], self.settings["model"], system)
        self.after(0, self.finish_task, task_id, manual, text, error)

    def finish_task(self, task_id, manual, text, error):
        self.task_running = False
        task = self.tasks.get(task_id)
        if not task:
            return
        record = self.tasks.mark_manual if manual else self.tasks.mark_run
        if error:
            record(task_id, False, error)
            if manual:
                taskwin.show_done(self, T, task["title"], None, error)
            return
        chat = storage.new_chat()
        chat["title"] = ("Task: " + task["title"])[:40]
        chat["messages"] = [
            {"role": "user", "content": task["prompt"]},
            {"role": "assistant", "content": text},
        ]
        self.chats.insert(0, chat)
        storage.save_chats(self.chats)
        record(task_id, True)
        self.refresh_sidebar()
        taskwin.show_done(self, T, task["title"], chat)

    def open_task_chat(self, chat):
        if self.is_busy:
            return
        if getattr(self, "project_id", None) is not None:
            self.open_project(None)
        self.open_chat(chat)

            # ---------- Pro plan ----------
    def apply_plan(self):
        self.tasks.limit = self.pro.limit("tasks")
        self.projects.limit = self.pro.limit("projects")
        self.pro_button.configure(text="Aira Pro" if self.pro.is_pro() else "Upgrade to Pro")

    def pro_check(self):
        if self.pro.needs_refresh():
            def job():
                self.pro.refresh()
                self.after(0, self.apply_plan)
            threading.Thread(target=job, daemon=True).start()
        else:
            self.apply_plan()
        self.after(30 * 60 * 1000, self.pro_check)
             # ---------- Modes ----------
    def change_mode(self, choice):
        self.mode = choice
        self.quiz_chunks = []
        self.settings["mode"] = choice
        storage.save_settings(self.settings)
        self.append_text(f"[Mode changed to: {choice}]\n\n")
        self.header.configure(text=self.header_text())
        if not self.current["messages"]:
            self.show_suggestions()


    def get_reply(self, chat, question, image_b64):
        sources = []
        if image_b64:
            # Vision: send only this question + the picture to the vision model
            model = self.settings["vision_model"]
            payload_messages = [
                {"role": "user", "content": question, "images": [image_b64]}
            ]
        else:
            model = self.settings["model"]
            system_text = (
                modes.build_system_prompt(self.mode, self.settings["system_prompt"])
                + self.memory.as_prompt()
            )
            payload_messages = [
                {"role": "system", "content": system_text}
            ] + list(chat["messages"])

            quiz = self.mode == "Quiz from notes"
            agent = self.mode == "Agent"
            notes = ""
            topic = websearch.extract_topic(question)
            if agent:
                self.run_agent(payload_messages)
            elif quiz:
                notes, sources = self.quiz_notes(question)
            elif topic:
                self.after(0, self.append_text, f"[Looking up '{topic}' on Wikipedia...]\n")
                try:
                    page = websearch.wikipedia_lookup(topic)
                except Exception:
                    page = None
                if page:
                    notes = f"[Wikipedia: {page['title']}] {page['text']}"
                    sources = [f"Wikipedia - {page['title']} {page['url']}".strip()]
                else:
                    self.after(
                        0, self.append_text,
                        "[Could not reach Wikipedia or found nothing. Answering from my own knowledge, so it may be wrong.]\n",
                    )
            else:
                try:
                    hits = self.kb.search(question)
                except Exception:
                    hits = []  # if searching fails, just chat normally
                if hits:
                    notes = "\n\n".join(f"[{h['source']}] {h['text']}" for h in hits)
                    sources = sorted(set(h["source"] for h in hits))

            if notes and quiz:
                payload_messages[-1] = {
                    "role": "user",
                    "content": f"NOTES:\n{notes}\n\nUSER MESSAGE: {question}",
                }
            elif notes:
                payload_messages[-1] = {
                    "role": "user",
                    "content": (
                        "Here are notes from a reliable source. Use them to answer the "
                        "question in your own words. If the notes do not cover it, say so "
                        "instead of guessing.\n\n"
                        f"NOTES:\n{notes}\n\nQUESTION: {question}"
                    ),
                }
        try:
            with requests.post(
                OLLAMA_URL,
                json={"model": model, "messages": payload_messages, "stream": True},
                stream=True,
                timeout=300,
            ) as response:
                response.raise_for_status()
                reply = ""
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    reply += chunk
                    self.after(0, self.append_text, chunk)
                    if data.get("done"):
                        break
            chat["messages"].append({"role": "assistant", "content": reply})
            if sources:
                self.after(0, self.append_text, f"\n[Sources: {', '.join(sources)}]")
            if self.settings["speak_replies"]:
                self.after(0, self.speaker.speak, reply)
        except requests.exceptions.ConnectionError:
            chat["messages"].pop()
            self.after(0, self.append_text, "[Ollama is not running. Open the Ollama app and try again.]")
        except Exception as error:
            chat["messages"].pop()
            self.after(0, self.append_text, f"[Error: {error}. If the model is missing, run: ollama pull {model}]")
        finally:
            self.after(0, self.append_text, "\n\n")
            self.after(0, self.finish)



            # ---------- Copy and export ----------
    def copy_last_answer(self):
        if self.is_busy:
            return
        for message in reversed(self.current["messages"]):
            if message["role"] == "assistant":
                self.clipboard_clear()
                self.clipboard_append(message["content"])
                self.update()  # keeps the text on the clipboard
                self.append_text("[Copied the last answer to the clipboard.]\n\n")
                return
        self.append_text("[There is no answer to copy yet.]\n\n")

    def export_chat(self):
        if self.is_busy:
            return
        if not self.current["messages"]:
            self.append_text("[This chat is empty, so there is nothing to export.]\n\n")
            return

        safe_title = "".join(
            c for c in self.current["title"] if c.isalnum() or c in " _-"
        ).strip() or "chat"
        path = filedialog.asksaveasfilename(
            title="Export chat",
            defaultextension=".txt",
            initialfile=safe_title,
            filetypes=[("Text file", "*.txt"), ("Markdown file", "*.md")],
        )
        if not path:
            return

        user = self.settings["user_name"]
        lines = [f"Aira AI chat: {self.current['title']}", ""]
        for message in self.current["messages"]:
            who = user if message["role"] == "user" else "Aira"
            lines.append(f"{who}: {message['content']}")
            lines.append("")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.append_text(f"[Chat saved to {path}]\n\n")
        except Exception as error:
            self.append_text(f"[Could not save the file: {error}]\n\n")



    # ---------- Voice input ----------
    def toggle_mic(self):
        if not voice.STT_AVAILABLE:
            self.append_text(
                "[Voice input is not installed. Run: "
                "python -m pip install sounddevice numpy faster-whisper]\n\n"
            )
            return
        if self.is_busy and not self.recording:
            return

        if not self.recording:
            try:
                self.listener.start()
            except Exception as error:
                self.append_text(f"[Microphone error: {error}]\n\n")
                return
            self.recording = True
            self.speaker.stop()
            self.mic_btn.configure(text="Stop", fg_color=T["stop"], hover_color=T["stop_hover"])
        else:
            self.recording = False
            self.mic_btn.configure(text="...", state="disabled")
            threading.Thread(target=self.transcribe, daemon=True).start()

    def transcribe(self):
        text = ""
        try:
            text = self.listener.stop_and_transcribe()
        except Exception as error:
            self.after(0, self.append_text, f"[Voice error: {error}]\n\n")
        self.after(0, self.mic_done, text)

    def mic_done(self, text):
        self.mic_btn.configure(
            text="Mic", state="normal", fg_color=T["button"], hover_color=T["button_hover"]
        )
        if text:
            self.entry.insert(0, text)
            self.send_message()

         # ---------- Startup check ----------
    def startup_check(self):
        def work():
            problems = checks.find_problems(self.settings)
            if problems:
                message = "[Setup check]\n" + "\n".join(f"- {p}" for p in problems) + "\n\n"
                self.after(0, self.append_text, message)

        threading.Thread(target=work, daemon=True).start()       
    def open_control_center(self):
        control_center.open_control_center(self, T)

    # ---------- Settings window ----------
    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("450x860")
        win.configure(fg_color=T["bg"])
        win.after(100, win.focus)

        label_style = {"text_color": T["text"], "anchor": "w"}

        ctk.CTkLabel(win, text="Your name", **label_style).pack(fill="x", padx=20, pady=(20, 4))
        name_entry = ctk.CTkEntry(win, fg_color=T["panel"], border_color=T["accent"])
        name_entry.insert(0, self.settings["user_name"])
        name_entry.pack(fill="x", padx=20)

        ctk.CTkLabel(win, text="Chat model (installed in Ollama)", **label_style).pack(fill="x", padx=20, pady=(16, 4))
        installed = checks.list_models()
        if self.settings["model"] not in installed:
            installed.insert(0, self.settings["model"])
        model_menu = ctk.CTkOptionMenu(
            win, values=installed,
            fg_color=T["button"], button_color=T["button_hover"], button_hover_color=T["accent"],
        )
        model_menu.set(self.settings["model"])
        model_menu.pack(fill="x", padx=20)

        ctk.CTkLabel(win, text="Vision model (for images)", **label_style).pack(fill="x", padx=20, pady=(16, 4))
        vision_entry = ctk.CTkEntry(win, fg_color=T["panel"], border_color=T["accent"])
        vision_entry.insert(0, self.settings["vision_model"])
        vision_entry.pack(fill="x", padx=20)

        ctk.CTkLabel(win, text="Aira's personality (system prompt)", **label_style).pack(fill="x", padx=20, pady=(16, 4))
        prompt_box = ctk.CTkTextbox(win, height=120, fg_color=T["panel"], border_color=T["accent"], border_width=2)
        prompt_box.insert("1.0", self.settings["system_prompt"])
        prompt_box.pack(fill="x", padx=20)

        speak_var = ctk.BooleanVar(value=self.settings["speak_replies"])
        ctk.CTkSwitch(
            win, text="Speak replies out loud", variable=speak_var,
            text_color=T["text"], progress_color=T["accent"],
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(win, text="Speech speed", **label_style).pack(fill="x", padx=20, pady=(8, 4))
        rate_slider = ctk.CTkSlider(win, from_=120, to=250, button_color=T["accent_hover"], progress_color=T["accent"])
        rate_slider.set(self.settings["voice_rate"])
        rate_slider.pack(fill="x", padx=20)

        ctk.CTkLabel(win, text="Creativity (low = precise, high = creative)", **label_style).pack(fill="x", padx=20, pady=(16, 4))
        temp_slider = ctk.CTkSlider(win, from_=0.0, to=1.5, button_color=T["accent_hover"], progress_color=T["accent"])
        temp_slider.set(self.settings["temperature"])
        temp_slider.pack(fill="x", padx=20)

        ctk.CTkLabel(win, text="Theme (restart Aira to apply)", **label_style).pack(fill="x", padx=20, pady=(16, 4))
        theme_menu = ctk.CTkOptionMenu(
            win, values=list(themes.THEMES.keys()),
            fg_color=T["button"], button_color=T["button_hover"], button_hover_color=T["accent"],
        )
        theme_menu.set(self.settings["theme"])
        theme_menu.pack(fill="x", padx=20)

        def save():
            self.settings["user_name"] = name_entry.get().strip() or "You"
            self.settings["model"] = model_menu.get()
            self.settings["theme"] = theme_menu.get()
            self.settings["temperature"] = round(temp_slider.get(), 1)
            self.settings["vision_model"] = vision_entry.get().strip() or "moondream"
            self.settings["system_prompt"] = prompt_box.get("1.0", "end").strip()
            self.settings["speak_replies"] = bool(speak_var.get())
            self.settings["voice_rate"] = int(rate_slider.get())
            self.speaker.rate = self.settings["voice_rate"]
            storage.save_settings(self.settings)
            if not self.is_busy:
                self.render_chat()
            win.destroy()

        ctk.CTkButton(
            win, text="Save", fg_color=T["accent"], hover_color=T["accent_hover"], command=save,
        ).pack(pady=20)


if __name__ == "__main__":
    app = AiraApp()
    app.mainloop()