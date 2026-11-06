import ast
import json
import os
import re
from datetime import datetime

import requests

import builder

try:
    from fpdf import FPDF
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    from docx import Document
    from docx.shared import Pt
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

OUT_DIR = builder.OUT_DIR
OLLAMA_URL = "http://localhost:11434/api/chat"
FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

DOC_SYSTEM = (
    "You are a careful writer helping a student. Write the requested document in "
    "Markdown only. Start with one '# ' title, use '## ' headings, short paragraphs, "
    "'- ' bullet lists and '1. ' numbered lists. Use **bold** sparingly. No tables, "
    "no images, no text before or after the document. Be accurate: never invent "
    "facts, names, dates or statistics. If you are not sure about something, leave it out."
)

PY_SYSTEM = (
    "You are an expert Python teacher who writes small programs for beginners. "
    "Reply with ONE complete Python program inside a single ```python code block and "
    "nothing else. Use only the Python standard library (tkinter is allowed for windows). "
    "The program must run exactly as written, with a short comment on each part, input "
    "checking, and no placeholder code. Never delete files, never run system commands "
    "and never use the internet. Keep it under about 150 lines."
)

VERB = r"(?:please\s+|can you\s+|could you\s+)?(?:build|create|make|generate|write|prepare|design)\s+"
KINDS = [
    ("pdf", re.compile(VERB + r".{0,80}?\bpdf\b", re.IGNORECASE)),
    ("docx", re.compile(VERB + r".{0,80}?\b(?:word\s+(?:document|doc|file)|docx)\b", re.IGNORECASE)),
    (
        "python",
        re.compile(
            VERB + r".{0,80}?\b(?:python\s+(?:app|application|program|script|game|tool|project)|in\s+python)\b",
            re.IGNORECASE,
        ),
    ),
]
KIT_PATTERN = re.compile(
    r"^(?:please\s+)?(?:(?:make|create|build|generate|prepare)\s+)?(?:me\s+)?"
    r"(?:a\s+|my\s+)?study\s*kit\b",
    re.IGNORECASE,
)

KIT_SYSTEM = (
    "You are a careful teacher making a study kit for a first-year engineering student. "
    "Use ONLY facts that appear in the NOTES the student gives you. Never invent facts. "
    "Write Markdown only, with exactly these parts in this order:\n"
    "# Study Kit\n"
    "## Summary  (5 to 8 short bullet points)\n"
    "## Key Terms  (8 bullet points, each 'term: one-line meaning')\n"
    "## Practice Questions  (8 numbered questions, from easy to hard)\n"
    "## Answer Key  (numbered answers that match the questions, one or two sentences each)\n"
    "No text before or after. If the notes do not cover something, leave it out."
)
# If generated Python contains any of these, Aira warns you to read it first.
RISKY_WORDS = [
    "os.remove", "os.unlink", "shutil", "rmtree", "subprocess", "os.system",
    "eval(", "exec(", "socket", "urllib", "requests", "__import__", "ctypes", "winreg",
]


def detect(text):
    """Return 'kit', 'pdf', 'docx' or 'python' if the message asks for one, otherwise None."""
    lower = text.lower().strip()
    if KIT_PATTERN.match(lower):
        return "kit"
    for kind, pattern in KINDS:
        if pattern.match(lower):
            return kind
    return None

def slug(request):
    return re.sub(r"[^a-z0-9]+", "-", request.lower()).strip("-")[:30] or "file"


def stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def open_path(path):
    try:
        os.startfile(path)
    except Exception:
        pass


def ask_ai(model, system, user, should_stop, temperature=0.4):
    """Ask Ollama and collect the whole answer. Returns None if the user pressed Stop."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "options": {"temperature": temperature, "num_ctx": 8192, "num_predict": 3072},
    }
    text = ""
    with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=600) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if should_stop():
                return None
            if not line:
                continue
            data = json.loads(line)
            text += data.get("message", {}).get("content", "")
            if data.get("done"):
                break
    return text


def notes_for(request, kb):
    """If the request mentions 'my notes' and documents were added, return relevant pieces."""
    if not kb.items:
        return ""
    if not re.search(r"\b(?:my|the)\s+(?:notes|documents?|files?|syllabus|pdf|material)\b", request.lower()):
        return ""
    try:
        hits = kb.search(request, k=5)
    except Exception:
        return ""
    return "\n\n".join(hit["text"] for hit in hits)


def strip_fence(text):
    text = text.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:markdown|md)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
    return text


def strip_inline(text):
    return re.sub(r"\*+|`", "", text)


def parse_markdown(text):
    """Turn simple Markdown into blocks: ('h', text, level), ('p', text, 0),
    ('bullet', text, 0), ('number', text, n)."""
    blocks = []
    paragraph = []

    def flush():
        if paragraph:
            blocks.append(("p", " ".join(paragraph), 0))
            paragraph.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if re.match(r"^[-*_]{3,}$", line):
            flush()
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)", line)
        bullet = re.match(r"^[-*\u2022]\s+(.*)", line)
        number = re.match(r"^(\d+)[.)]\s+(.*)", line)
        if heading:
            flush()
            blocks.append(("h", heading.group(2), len(heading.group(1))))
        elif bullet:
            flush()
            blocks.append(("bullet", bullet.group(1), 0))
        elif number:
            flush()
            blocks.append(("number", number.group(2), int(number.group(1))))
        else:
            paragraph.append(line)
    flush()
    return blocks


def setup_fonts(pdf):
    """Use Arial from Windows when available, so more characters work."""
    regular = os.path.join(FONT_DIR, "arial.ttf")
    bold = os.path.join(FONT_DIR, "arialbd.ttf")
    if os.path.exists(regular) and os.path.exists(bold):
        try:
            pdf.add_font("Body", "", regular)
            pdf.add_font("Body", "B", bold)
            return "Body", True
        except Exception:
            pass
    return "Helvetica", False


def write_pdf(path, blocks):
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    family, unicode_ok = setup_fonts(pdf)
    bullet = "\u2022" if unicode_ok else "-"

    def fix(text):
        text = strip_inline(text)
        return text if unicode_ok else text.encode("latin-1", "replace").decode("latin-1")

    sizes = {1: 22, 2: 16, 3: 13}
    for kind, text, level in blocks:
        if kind == "h":
            if level > 1:
                pdf.ln(3)
            pdf.set_font(family, "B", sizes[level])
            pdf.multi_cell(w=0, h=sizes[level] * 0.55, text=fix(text), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif kind == "p":
            pdf.set_font(family, "", 11)
            pdf.multi_cell(w=0, h=6, text=fix(text), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        else:
            marker = bullet if kind == "bullet" else f"{level}."
            pdf.set_font(family, "", 11)
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(w=0, h=6, text=fix(f"{marker} {text}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    pdf.output(path)


def add_runs(paragraph, text):
    """Add text to a Word paragraph, turning **bold** parts into bold runs."""
    for part in re.split(r"(\*\*.+?\*\*)", text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            paragraph.add_run(strip_inline(part[2:-2])).bold = True
        elif part:
            paragraph.add_run(strip_inline(part))


def write_docx(path, blocks):
    doc = Document()
    for kind, text, level in blocks:
        if kind == "h":
            doc.add_heading(strip_inline(text), level=level - 1)
        elif kind == "p":
            add_runs(doc.add_paragraph(), text)
        elif kind == "bullet":
            add_runs(doc.add_paragraph(style="List Bullet"), text)
        else:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.left_indent = Pt(18)
            add_runs(paragraph, f"{level}. {text}")
    doc.save(path)


def make_document(kind, request, default_model, kb, should_stop):
    notes = notes_for(request, kb)
    user = f"Write this document: {request}"
    if notes:
        user += "\n\nUse ONLY facts from these notes from the student's own material:\n" + notes

    text = ask_ai(default_model, DOC_SYSTEM, user, should_stop)
    if text is None:
        return "Stopped. No file was made."

    blocks = parse_markdown(strip_fence(text))
    if not blocks:
        return "I could not write the document this time. Try a simpler request."

    os.makedirs(OUT_DIR, exist_ok=True)
    extension = "pdf" if kind == "pdf" else "docx"
    path = os.path.join(OUT_DIR, f"{slug(request)}_{stamp()}.{extension}")
    try:
        if kind == "pdf":
            write_pdf(path, blocks)
        else:
            write_docx(path, blocks)
    except Exception as error:
        return f"I wrote the text but could not save the file: {error}"

    open_path(path)
    source = " using your notes" if notes else ""
    return (
        f"Done! I wrote your {extension.upper()}{source} and opened it.\n"
        f"Saved at: {path}\n"
        "Read it and check the facts before you submit or share it. "
        "A small AI model can make mistakes."
    )


def extract_python(text):
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    partial = re.search(r"```(?:python|py)?\s*\n(.*)", text, re.DOTALL | re.IGNORECASE)
    if partial:
        return partial.group(1).strip()
    return None


def make_python(request, default_model, should_stop):
    model = builder.pick_model(default_model)
    text = ask_ai(model, PY_SYSTEM, f"Write this program: {request}", should_stop, temperature=0.2)
    if text is None:
        return "Stopped. No file was made."

    code = extract_python(text)
    if not code:
        return (
            "I could not write the program this time. Try a simpler description, or "
            "install the coding model: ollama pull qwen2.5-coder:3b"
        )

    notes = []
    try:
        ast.parse(code)
    except SyntaxError as error:
        notes.append(
            f"Warning: the code has a mistake on line {error.lineno}. Ask again, "
            "or fix it with Code helper mode."
        )
    found = [word for word in RISKY_WORDS if word in code]
    if found:
        notes.append(
            "Careful: the code uses " + ", ".join(found) + ". Read it before you run it."
        )

    os.makedirs(OUT_DIR, exist_ok=True)
    name = f"{slug(request)}_{stamp()}.py"
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code + "\n")
    open_path(OUT_DIR)

    message = (
        f"Done! I wrote your Python program with {model}. I did NOT run it.\n"
        f"Saved at: {path}\n"
        "Open it in VS Code and read it first. To run it, use the VS Code terminal "
        "(with (venv) showing):\n"
        "python builds\\" + name
    )
    if notes:
        message += "\n" + "\n".join(notes)
    return message

def pick_chunks(kb, request, limit_chars=6500):
    """Choose pieces of the notes that fit the small model's memory, spread over the whole text."""
    items = kb.items
    lower = request.lower()
    named = [
        item for item in items
        if os.path.splitext(item["source"])[0].lower() in lower
    ]
    if named:
        items = named
    total = sum(len(item["text"]) for item in items)
    average = max(1, total // max(1, len(items)))
    count = max(1, limit_chars // average)
    if count >= len(items):
        return items
    return [items[int(i * len(items) / count)] for i in range(count)]


def save_blocks(kind, name, blocks):
    """Write parsed Markdown blocks to a PDF or Word file inside the builds folder."""
    os.makedirs(OUT_DIR, exist_ok=True)
    extension = "pdf" if kind == "pdf" else "docx"
    path = os.path.join(OUT_DIR, f"{slug(name)}_{stamp()}.{extension}")
    if kind == "pdf":
        write_pdf(path, blocks)
    else:
        write_docx(path, blocks)
    return path


def make_study_kit(request, default_model, kb, should_stop):
    if not kb.items:
        return (
            "I need your notes first. Click Add document, choose a PDF or text file "
            "of your notes, then type: study kit"
        )
    wants_word = re.search(r"\b(?:word|docx)\b", request.lower()) is not None
    kind = "docx" if wants_word else "pdf"
    if kind == "pdf" and not PDF_OK:
        return "PDF needs a library. Run: python -m pip install fpdf2"
    if kind == "docx" and not DOCX_OK:
        return "Word files need a library. Run: python -m pip install python-docx"

    chunks = pick_chunks(kb, request)
    notes = "\n\n".join(chunk["text"] for chunk in chunks)
    sources = sorted(set(chunk["source"] for chunk in chunks))

    text = ask_ai(
        default_model, KIT_SYSTEM, f"NOTES:\n{notes}\n\nMake the study kit now.",
        should_stop, temperature=0.3,
    )
    if text is None:
        return "Stopped. No file was made."

    blocks = parse_markdown(strip_fence(text))
    if len(blocks) < 4:
        return "I could not write the study kit this time. Try again, or add a shorter document."

    try:
        path = save_blocks(kind, "study kit " + sources[0], blocks)
    except Exception as error:
        return f"I wrote the text but could not save the file: {error}"

    open_path(path)
    return (
        f"Done! I made your study kit from {', '.join(sources)} and opened it.\n"
        f"Saved at: {path}\n"
        "Very long documents are sampled, so the kit covers a spread of your notes, not "
        "every page. Check the answer key against your notes before you rely on it. "
        "A small AI model can make mistakes."
    )

def create(kind, request, default_model, kb, should_stop):
    if kind == "kit":
        return make_study_kit(request, default_model, kb, should_stop)
    if kind == "pdf" and not PDF_OK:
        return "PDF needs a library. Run: python -m pip install fpdf2"
    if kind == "docx" and not DOCX_OK:
        return "Word files need a library. Run: python -m pip install python-docx"
    if kind == "python":
        return make_python(request, default_model, should_stop)
    return make_document(kind, request, default_model, kb, should_stop)