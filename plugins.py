import importlib.util
import os
import re
import threading

import paths

BASE_DIR = paths.DATA_DIR
PLUGIN_DIR = os.path.join(BASE_DIR, "plugins")
TIME_LIMIT = 10  # seconds a plugin may take before Aira gives up waiting

TEMPLATE = '''# Plugin: {name}
# Aira calls handle(text) for every message you type.
# Return a string to answer, or None to say "this message is not for me".

NAME = "{name}"
DESCRIPTION = "Describe what this plugin does."
EXAMPLES = ["{word} something"]
TRIGGERS = ["{word}"]   # only messages that START with one of these reach handle()


def handle(text):
    request = text.strip()
    return f"Plugin {name} got: {{request}}"
'''


class Plugin:
    def __init__(self, filename, module):
        self.filename = filename
        self.module = module
        self.name = str(getattr(module, "NAME", filename[:-3]))
        self.description = str(getattr(module, "DESCRIPTION", "No description."))
        self.examples = list(getattr(module, "EXAMPLES", []))
        self.triggers = [t.lower() for t in getattr(module, "TRIGGERS", [])]

    def wants(self, text):
        if not self.triggers:
            return True
        low = text.lower().strip()
        return any(low == t or low.startswith(t + " ") for t in self.triggers)


class PluginManager:
    def __init__(self):
        os.makedirs(PLUGIN_DIR, exist_ok=True)
        self.plugins = []
        self.errors = []
        self.load_all()

    def load_all(self):
        self.plugins = []
        self.errors = []
        names = sorted(f for f in os.listdir(PLUGIN_DIR) if f.endswith(".py"))
        for filename in names:
            if filename.startswith("_"):
                continue  # a leading underscore means "switched off"
            path = os.path.join(PLUGIN_DIR, filename)
            try:
                spec = importlib.util.spec_from_file_location("Aira_plugin_" + filename[:-3], path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if not callable(getattr(module, "handle", None)):
                    raise ValueError("it has no handle(text) function")
                self.plugins.append(Plugin(filename, module))
            except Exception as error:
                self.errors.append(f"{filename}: {error}")

    def run(self, plugin, text):
        box = {}

        def work():
            try:
                box["result"] = plugin.module.handle(text)
            except Exception as error:
                box["error"] = error

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        thread.join(TIME_LIMIT)
        if thread.is_alive():
            return f"The plugin '{plugin.name}' took longer than {TIME_LIMIT} seconds, so I stopped waiting."
        if "error" in box:
            return f"The plugin '{plugin.name}' had an error: {box['error']}"
        result = box.get("result")
        if result is None:
            return None
        return str(result)

    def handle(self, text):
        low = text.lower().strip()

        if low in ("list plugins", "show plugins", "plugins"):
            return self.describe()
        if low in ("reload plugins", "refresh plugins"):
            self.load_all()
            return "Plugins reloaded.\n" + self.describe()
        match = re.match(r"^plugin help (.+)$", low)
        if match:
            return self.help_for(match.group(1).strip())
        match = re.match(r"^new plugin ([a-z0-9_ -]{1,30})$", low)
        if match:
            return self.create_template(match.group(1).strip())

        for plugin in self.plugins:
            if plugin.wants(text):
                result = self.run(plugin, text)
                if result is not None:
                    return result
        return None

    def describe(self):
        lines = []
        if self.plugins:
            lines.append(f"{len(self.plugins)} plugin(s) loaded:")
            for plugin in self.plugins:
                lines.append(f"- {plugin.name}: {plugin.description}")
            lines.append("Type 'plugin help <name>' to see examples.")
        else:
            lines.append("No plugins yet. Type 'new plugin mytool' to make one.")
        for problem in self.errors:
            lines.append(f"Could not load {problem}")
        lines.append(f"Plugin folder: {PLUGIN_DIR}")
        return "\n".join(lines)

    def help_for(self, name):
        for plugin in self.plugins:
            if name in (plugin.name.lower(), plugin.filename[:-3].lower()):
                text = f"{plugin.name}: {plugin.description}"
                if plugin.examples:
                    text += "\nTry:\n" + "\n".join(f"- {e}" for e in plugin.examples)
                return text
        return f"I don't have a plugin called '{name}'. Type 'list plugins'."

    def create_template(self, raw):
        word = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
        if not word:
            return "Please give the plugin a simple name, like: new plugin weather"
        path = os.path.join(PLUGIN_DIR, word + ".py")
        if os.path.exists(path):
            return f"There is already a plugin file called {word}.py."
        with open(path, "w", encoding="utf-8") as file:
            file.write(TEMPLATE.format(name=word, word=word.replace("_", " ")))
        try:
            os.startfile(path)
        except Exception:
            pass
        self.load_all()
        return (
            f"Created plugins/{word}.py and opened it. Edit the handle() function, save, then type "
            f"'reload plugins'."
        )