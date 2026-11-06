import json
import os
import time

import rag

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(BASE_DIR, "projects.json")
DATA_DIR = os.path.join(BASE_DIR, "projects_data")
MAX_PROJECTS = 30


class ProjectKB(rag.KnowledgeBase):
    """The same document memory as rag.KnowledgeBase, but stored in its own file."""

    def __init__(self, path):
        self.path = path
        super().__init__()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.items, f)


class ProjectStore:
    def __init__(self, global_kb):
        self.global_kb = global_kb      # documents used outside any project
        self.limit = MAX_PROJECTS       # main.py sets this from your plan (Free or Pro)
        self.items = self._load()
        self._kbs = {}

    def _load(self):
        try:
            with open(FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [p for p in data if "id" in p and "name" in p]
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return []

    def _save(self):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=2, ensure_ascii=False)

    def get(self, project_id):
        for project in self.items:
            if project["id"] == project_id:
                return project
        return None

    def name_of(self, project_id):
        project = self.get(project_id)
        return project["name"] if project else ""

    def create(self, name, instructions=""):
        name = " ".join(name.split())[:40]
        if not name:
            return None, "Please give the project a name."
        if len(self.items) >= self.limit:
            return None, f"Your plan allows {self.limit} projects. Open Pro to get more."
        if any(p["name"].lower() == name.lower() for p in self.items):
            return None, f"You already have a project called {name}."
        new_id = int(time.time() * 1000)
        while any(p["id"] == str(new_id) for p in self.items):
            new_id += 1   # two projects made in the same millisecond still get different ids
        project = {
            "id": str(new_id),
            "name": name,
            "instructions": instructions.strip(),
        }
        self.items.append(project)
        self._save()
        return project, ""

    def rename(self, project_id, name):
        project = self.get(project_id)
        name = " ".join(name.split())[:40]
        if not project or not name:
            return False
        if any(p["name"].lower() == name.lower() and p is not project for p in self.items):
            return False
        project["name"] = name
        self._save()
        return True

    def set_instructions(self, project_id, text):
        project = self.get(project_id)
        if project:
            project["instructions"] = text.strip()[:3000]
            self._save()

    def delete(self, project_id, chats):
        """Remove the project. Its chats are kept and move back to the normal list."""
        self.items = [p for p in self.items if p["id"] != project_id]
        self._save()
        for chat in chats:
            if chat.get("project") == project_id:
                chat["project"] = None
        self._kbs.pop(project_id, None)
        try:
            os.remove(self._kb_path(project_id))
        except OSError:
            pass

    def _kb_path(self, project_id):
        return os.path.join(DATA_DIR, f"{project_id}_knowledge.json")

    def kb_for(self, project_id):
        if not self.get(project_id):
            return self.global_kb
        if project_id not in self._kbs:
            self._kbs[project_id] = ProjectKB(self._kb_path(project_id))
        return self._kbs[project_id]

    def prompt_for(self, project_id):
        project = self.get(project_id)
        if not project or not project.get("instructions", "").strip():
            return ""
        return (
            f"\n\nYou are working inside the project '{project['name']}'. "
            f"Follow these project instructions in every reply: {project['instructions'][:3000]}"
        )