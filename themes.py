# Every color the app uses, grouped into themes.
# To make your own theme, copy one block and change the colors.
THEMES = {
    "Purple dark": {
        "mode": "dark",
        "bg": "#1a1025", "panel": "#241535", "sidebar": "#150c20",
        "text": "#f0e6ff", "status": "#b794f4",
        "accent": "#7b2cbf", "accent_hover": "#9d4edd",
        "button": "#3a2354", "button_hover": "#51327a",
        "danger": "#4a1d4f", "danger_hover": "#6b2a73",
        "stop": "#c1121f", "stop_hover": "#e5383b",
    },
    "Ocean dark": {
        "mode": "dark",
        "bg": "#0f1b2d", "panel": "#162a45", "sidebar": "#0b1423",
        "text": "#e6f1ff", "status": "#7fb3ff",
        "accent": "#1f7aec", "accent_hover": "#4a9bff",
        "button": "#22406b", "button_hover": "#2f5a95",
        "danger": "#5b2a4a", "danger_hover": "#7a3a63",
        "stop": "#c1121f", "stop_hover": "#e5383b",
    },
    "Light": {
        "mode": "light",
        "bg": "#f4f1fa", "panel": "#ffffff", "sidebar": "#e8e2f3",
        "text": "#1f1535", "status": "#6b3fa0",
        "accent": "#b794f4", "accent_hover": "#9d6ee6",
        "button": "#d9cfee", "button_hover": "#c7b8e6",
        "danger": "#e8b4c8", "danger_hover": "#d99ab5",
        "stop": "#ff8a8a", "stop_hover": "#ff6b6b",
    },
    "Black": {
        "mode": "dark",
        "bg": "#000000", "panel": "#121212", "sidebar": "#0a0a0a",
        "text": "#f5f5f5", "status": "#a6a6a6",
        "accent": "#3d3d3d", "accent_hover": "#5a5a5a",
        "button": "#1f1f1f", "button_hover": "#3a3a3a",
        "danger": "#2e2e2e", "danger_hover": "#474747",
        "stop": "#5c5c5c", "stop_hover": "#7a7a7a",
    },
    "White": {
        "mode": "light",
        "bg": "#ffffff", "panel": "#f2f2f2", "sidebar": "#e9e9e9",
        "text": "#111111", "status": "#555555",
        "accent": "#bdbdbd", "accent_hover": "#a5a5a5",
        "button": "#e0e0e0", "button_hover": "#cccccc",
        "danger": "#c9c9c9", "danger_hover": "#b0b0b0",
        "stop": "#9a9a9a", "stop_hover": "#7f7f7f",
    },
}


def get_theme(name):
    return THEMES.get(name, THEMES["Purple dark"])