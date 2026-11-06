# Suggested tasks: cards shown in an empty chat, like ChatGPT's starter ideas.
# Each idea is (short title shown on the card, message that is sent when you click it).
# Every mode has its own list. To add an idea, add one more line to a list.
import random

IDEAS = {
    "Normal": [
        ("Explain neural networks simply", "Explain how a neural network learns, in simple words with a small example."),
        ("Plan my study week", "Help me plan a balanced study week for 5 subjects."),
        ("Build a study timer", "build a pomodoro study timer website with start, pause and reset"),
        ("Make a PDF study guide", "make a pdf study guide about operating systems"),
        ("Write a Python program", "write a python program that guesses a number"),
        ("Set a reminder", "remind me in 10 minutes to drink water"),
        ("Draw a picture", "generate an image of a futuristic city at sunset, wide"),
        ("Tell me a space fact", "Tell me an interesting fact about space."),
    ],
    "Study buddy": [
        ("Teach me recursion", "Teach me recursion with a simple example."),
        ("Make an exam plan", "Make a study plan for my exams in 10 days."),
        ("Explain binary search", "Explain binary search with a real-life example."),
        ("AI vs ML vs deep learning", "What is the difference between AI, machine learning and deep learning?"),
        ("Help me remember formulas", "Give me tips to remember formulas for exams."),
        ("Explain pointers", "Help me understand pointers in simple words."),
    ],
    "Quiz me": [
        ("Quiz me on Python basics", "Quiz me on Python basics."),
        ("Quiz me on networks", "Give me 5 questions on computer networks."),
        ("Quiz me on operating systems", "Quiz me on operating systems."),
        ("Test me on the solar system", "Test me on the solar system."),
        ("Quiz me on algebra", "Quiz me on basic algebra."),
        ("Quiz me on data structures", "Quiz me on data structures, one question at a time."),
    ],
    "Code helper": [
        ("Explain Python dictionaries", "Explain what a Python dictionary is with an example."),
        ("Write a prime checker", "Write a function that checks if a number is prime, and explain it."),
        ("Why IndexError?", "Why do I get an IndexError in Python and how do I fix it?"),
        ("Teach me for loops", "Teach me how a for loop works in Python."),
        ("Read a file in Python", "Show me how to read a text file in Python."),
        ("List vs tuple", "What is the difference between a list and a tuple?"),
    ],
    "Project mentor": [
        ("Plan a mini project", "Help me plan a mini project for my AI course."),
        ("Break down a to-do app", "Break down building a to-do app into small steps."),
        ("Beginner project ideas", "Suggest 5 beginner Python project ideas."),
        ("Start a Flask project", "How do I start a project with Flask?"),
        ("Set weekly goals", "How should I split my project into weekly goals?"),
        ("Choose a first-year project", "Help me choose a project idea for my first year."),
    ],
    "Quiz from notes": [
        ("Quiz me on my notes", "Quiz me on my notes."),
        ("Make 5 questions", "Make 5 questions from my notes."),
        ("Test the main points", "Test me on the main points of my document."),
        ("Ask me an easy question", "Ask me one easy question from my notes."),
    ],
    "Agent": [
        ("Check the weather", "What is the weather in Delhi?"),
        ("Latest news", "What is the latest news about ISRO?"),
        ("Do some maths", "What is 15% of 840, and what is today's date?"),
        ("Save a note", "Note down: submit the assignment on Friday"),
        ("Read my notes", "What notes do I have?"),
        ("Make a timetable", "Create a timetable: Mon 9-10 Maths; Tue 9-11 Python lab"),
        ("Look something up", "Tell me about the Eiffel Tower."),
    ],
}


def ideas_for(mode):
    """The list of ideas for a mode (the Normal list if the mode has none)."""
    return IDEAS.get(mode) or IDEAS["Normal"]


def pick(mode, count=4, avoid=()):
    """Choose `count` ideas at random, preferring ones that are not in `avoid`."""
    pool = ideas_for(mode)
    fresh = [idea for idea in pool if idea not in avoid]
    chosen = random.sample(fresh, min(count, len(fresh)))
    if len(chosen) < count:  # not enough new ones, so top up with older ones
        older = [idea for idea in pool if idea not in chosen]
        chosen += random.sample(older, min(count - len(chosen), len(older)))
    return chosen


# The panel needs customtkinter, so it is only created when the app runs.
def make_panel(master, theme, mode, on_pick, count=4):
    import customtkinter as ctk

    class SuggestionPanel(ctk.CTkFrame):
        def __init__(self):
            super().__init__(master, fg_color="transparent")
            self.shown = []
            ctk.CTkLabel(
                self, text="What can I help you with?", text_color=theme["text"],
                font=("Segoe UI", 20, "bold"),
            ).pack(pady=(24, 2))
            ctk.CTkLabel(
                self, text=f"{mode} mode. Pick an idea or type your own.",
                text_color=theme["status"], font=("Segoe UI", 12),
            ).pack(pady=(0, 12))
            self.cards = ctk.CTkFrame(self, fg_color="transparent")
            self.cards.pack(fill="x", padx=10)
            self.cards.grid_columnconfigure((0, 1), weight=1, uniform="cards")
            ctk.CTkButton(
                self, text="Show different ideas", fg_color="transparent",
                text_color=theme["status"], hover_color=theme["button"],
                command=self.shuffle,
            ).pack(pady=(8, 0))
            self.shuffle()

        def shuffle(self):
            for child in self.cards.winfo_children():
                child.destroy()
            self.shown = pick(mode, count, avoid=self.shown)
            for index, (title, prompt) in enumerate(self.shown):
                ctk.CTkButton(
                    self.cards, text=title, height=54, anchor="w", corner_radius=14,
                    fg_color=theme["panel"], hover_color=theme["button"],
                    text_color=theme["text"], font=("Segoe UI", 13),
                    command=lambda p=prompt: on_pick(p),
                ).grid(row=index // 2, column=index % 2, padx=5, pady=5, sticky="ew")

    return SuggestionPanel()