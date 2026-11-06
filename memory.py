import json
import os

import paths

BASE_DIR = paths.DATA_DIR
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")


class MemoryStore:
    def __init__(self):
        self.facts = self._load()

    def _load(self):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.facts, f, indent=2, ensure_ascii=False)

    def add(self, fact):
        fact = fact.strip()
        if fact and fact not in self.facts:
            self.facts.append(fact)
            self._save()

    def forget(self, word):
        """Delete every fact that contains the word. Returns how many were deleted."""
        word = word.lower()
        kept = [f for f in self.facts if word not in f.lower()]
        removed = len(self.facts) - len(kept)
        self.facts = kept
        self._save()
        return removed

    def clear(self):
        self.facts = []
        self._save()

    def as_prompt(self):
        """Text added to the AI's instructions so it knows the facts."""
        if not self.facts:
            return ""
        lines = "\n".join(f"- {fact}" for fact in self.facts)
        return (
            "\n\nFacts the user asked you to remember, in their own words "
            "('my' and 'I' mean the user). Use them naturally when relevant, "
            "and do not repeat them unprompted:\n" + lines
        )

    def handle(self, text):
        """Return Aira's reply if this is a memory command, otherwise None."""
        cleaned = text.strip()
        lower = cleaned.lower().rstrip(".!?")

        if lower in ("forget everything", "clear memory", "clear my memory"):
            self.clear()
            return "Done. I have forgotten everything."

        if lower in ("what do you remember", "what do you know about me",
                     "show memory", "show my memory"):
            if not self.facts:
                return "I don't remember anything yet. Say 'remember ...' to teach me."
            numbered = "\n".join(f"{i}. {fact}" for i, fact in enumerate(self.facts, 1))
            return "Here is what I remember:\n" + numbered

        if lower.startswith("forget "):
            word = lower[len("forget "):].strip()
            if word:
                removed = self.forget(word)
                if removed:
                    return f"Okay, I forgot {removed} thing(s) about '{word}'."
                return f"I had nothing saved about '{word}'."

        for prefix in ("remember that ", "remember: ", "remember "):
            if lower.startswith(prefix):
                fact = cleaned[len(prefix):].strip().rstrip(".!")
                if fact:
                    self.add(fact)
                    return f"Got it. I will remember: {fact}"

        return None