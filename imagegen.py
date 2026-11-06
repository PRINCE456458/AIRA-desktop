import os
import base64
import random
import re
import time
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

import requests
from PIL import Image

import paths

BASE_DIR = paths.DATA_DIR
OUT_DIR = os.path.join(BASE_DIR, "images")
OLLAMA_URL = "http://localhost:11434/api/chat"

# The image engine. To use a different service later, only this part changes.
ENGINE_URL = "https://image.pollinations.ai/prompt/"
MIN_GAP = 16  # the free service allows about one picture every 15 seconds
_last_request = 0.0

NOUNS = "image|picture|photo|illustration|artwork|wallpaper|logo|poster|drawing|painting|sketch|icon"
POLITE = r"(?:please\s+|can you\s+|could you\s+)?"
MAKE = re.compile(r"^" + POLITE + r"(?:generate|create|make|draw|paint|design|produce)\s+(?:me\s+)?(.+)$", re.IGNORECASE)
DRAW = re.compile(r"^" + POLITE + r"draw\s+(?:me\s+)?\S", re.IGNORECASE)
EXPLICIT = re.compile(r"^(?:/image|image:)\s*\S", re.IGNORECASE)
EXCLUDE = re.compile(
    r"\b(?:website|web\s?site|web\s?page|web\s?app|pdf|docx|word\s+(?:document|doc|file)|python)\b",
    re.IGNORECASE,
)

ENHANCE_SYSTEM = (
    "You write prompts for an AI image generator. Rewrite the user's idea as ONE vivid "
    "English prompt of at most 45 words: the subject, the setting, the lighting, the style "
    "and the mood. Keep every detail the user gave, and keep the style they named. Do not "
    "add names of real people, brands, or text inside the image. Reply with the prompt only."
)


def is_request(text):
    """True if the message asks for a picture to be generated."""
    cleaned = text.strip()
    if EXCLUDE.search(cleaned):
        return False
    if EXPLICIT.match(cleaned) or DRAW.match(cleaned):
        return True
    match = MAKE.match(cleaned)
    if match:
        pattern = r"^(?:an?\s+|the\s+)?(?:[\w'-]+\s+){0,2}?(?:" + NOUNS + r")s?\b"
        return re.match(pattern, match.group(1), re.IGNORECASE) is not None
    return False


def extract_prompt(text):
    cleaned = re.sub(r"^(?:/image|image:)\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(
        r"^" + POLITE + r"(?:generate|create|make|draw|paint|design|produce)\s+(?:me\s+)?",
        "", cleaned, flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:an?\s+|the\s+)?(?:image|picture|photo|illustration|drawing|painting|sketch)s?\s+(?:of|about|showing|with)\s+",
        "", cleaned, flags=re.IGNORECASE,
    )
    return cleaned.strip()


def pick_size(prompt):
    lower = prompt.lower()
    if re.search(r"\b(?:wide|landscape|16:9|banner|wallpaper)\b", lower):
        return 1024, 576
    if re.search(r"\b(?:portrait|vertical|9:16|poster|phone)\b", lower):
        return 576, 1024
    return 768, 768


def enhance(prompt, model):
    """Ask the local AI to expand a short idea. If anything goes wrong, use the original."""
    try:
        reply = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": ENHANCE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 120},
            },
            timeout=90,
        )
        reply.raise_for_status()
        text = reply.json()["message"]["content"].strip().strip('"')
        text = re.sub(r"\s+", " ", text)
        if 10 <= len(text) <= 500:
            return text
    except Exception:
        pass
    return prompt


def wait_turn(should_stop):
    global _last_request
    while time.time() - _last_request < MIN_GAP:
        if should_stop():
            return False
        time.sleep(0.5)
    _last_request = time.time()
    return True


def download(prompt, width, height, should_stop):
    """Return (image bytes, None) or (None, a friendly error message)."""
    seed = random.randint(1, 999999)
    url = ENGINE_URL + quote(prompt, safe="")
    for attempt in (1, 2):
        if not wait_turn(should_stop):
            return None, "Stopped. No image was made."
        try:
            response = requests.get(
                url,
                params={"width": width, "height": height, "seed": seed, "nologo": "true"},
                timeout=120,
            )
        except requests.exceptions.ConnectionError:
            return None, "I could not reach the image service. Check your internet connection."
        except requests.exceptions.Timeout:
            return None, "The image service took too long. Try again."
        if response.status_code == 429 and attempt == 1:
            continue  # too many requests: wait one turn and try once more
        if response.status_code != 200:
            return None, (
                f"The image service answered with error {response.status_code}. "
                "It may be busy, or the free service may have changed. Try again in a minute."
            )
        if not response.headers.get("content-type", "").startswith("image/"):
            return None, "The service did not send a picture. Try again with a different description."
        return response.content, None
    return None, "The free service is busy right now. Wait a minute and try again."


def create(text, default_model, should_stop):
    prompt = extract_prompt(text)
    if len(prompt) < 3:
        return "Tell me what to draw, for example: draw a red kite flying over green hills"
    width, height = pick_size(prompt)

    exact = len(prompt) > 2 and prompt[0] in "\"'" and prompt[-1] == prompt[0]
    if exact:
        final = prompt.strip("\"'")[:400]
    elif len(prompt.split()) < 25:
        final = enhance(prompt[:300], default_model)
    else:
        final = prompt[:400]

    data, error = download(final, width, height, should_stop)
    if error:
        return error

    try:
        Image.open(BytesIO(data)).verify()
        shape = (Image.open(BytesIO(data)).format or "JPEG").lower()
    except Exception:
        return "The service sent something that is not a real picture. Please try again."

    extension = "jpg" if shape == "jpeg" else shape
    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:30] or "image"
    path = os.path.join(OUT_DIR, f"{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}")
    with open(path, "wb") as f:
        f.write(data)
    try:
        os.startfile(path)
    except Exception:
        pass

    return (
        f"Done! I made your image ({width}x{height}) and opened it.\n"
        f"Prompt I used: {final}\n"
        f"Saved at: {path}\n"
        "Put your own prompt in quotes to use your exact words. This uses a free online "
        "service, so your description leaves your laptop. Do not include private details."
    )
GALLERY_WORDS = {
    "image gallery", "picture gallery", "my gallery", "open gallery", "show gallery",
    "my images", "show my images", "show images", "my pictures", "show my pictures",
}


def is_gallery_request(text):
    return text.lower().strip(" .!?") in GALLERY_WORDS
RESTYLE = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?(?:"
    r"(?:redraw|re-draw|restyle|repaint|recreate|reimagine)\b"
    r"|(?:turn|convert|transform|change)\s+(?:this|it|that|the\s+(?:picture|image|photo))\s+(?:in)?to\b"
    r"|make\s+(?:this|it|that|the\s+(?:picture|image|photo))\s+(?:look\s+like|into)\b"
    r"|(?:draw|paint)\s+(?:this|it|that)\b)",
    re.IGNORECASE,
)

DESCRIBE_PROMPT = (
    "Describe this picture in one detailed sentence: the main subject, the colors, "
    "the setting and the mood. Describe only what you can see."
)


def is_restyle_request(question):
    """True if the words ask to redraw an attached picture in another style."""
    return RESTYLE.match(question.strip()) is not None


def extract_style(question):
    text = question.strip()
    match = RESTYLE.match(text)
    rest = text[match.end():] if match else text
    rest = re.sub(
        r"^\s*(?:this|it|that|the\s+(?:picture|image|photo)|my\s+(?:picture|image|photo))\b",
        "", rest, flags=re.IGNORECASE,
    )
    rest = re.sub(r"^\s*(?:as|in|into|to|like)\b\s*", "", rest, flags=re.IGNORECASE)
    return rest.strip(" ,.:;")


def size_like(image_b64):
    """Pick an output shape that matches the photo: wide, tall or square."""
    try:
        image = Image.open(BytesIO(base64.b64decode(image_b64)))
        ratio = image.width / image.height
    except Exception:
        return 768, 768
    if ratio > 1.3:
        return 1024, 576
    if ratio < 0.77:
        return 576, 1024
    return 768, 768


def store_image(data, hint):
    """Check that the bytes are a real picture, save it in the images folder, and open it."""
    try:
        Image.open(BytesIO(data)).verify()
        shape = (Image.open(BytesIO(data)).format or "JPEG").lower()
    except Exception:
        return None, "The service sent something that is not a real picture. Please try again."
    extension = "jpg" if shape == "jpeg" else shape
    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", hint.lower()).strip("-")[:30] or "image"
    path = os.path.join(OUT_DIR, f"{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}")
    with open(path, "wb") as f:
        f.write(data)
    try:
        os.startfile(path)
    except Exception:
        pass
    return path, None


def restyle(image_b64, request, vision_model, should_stop):
    style = extract_style(request) or "digital painting, vivid colors"

    # Step 1: the local vision model describes the photo. Nothing leaves your laptop here.
    try:
        reply = requests.post(
            OLLAMA_URL,
            json={
                "model": vision_model,
                "messages": [{"role": "user", "content": DESCRIBE_PROMPT, "images": [image_b64]}],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 120},
            },
            timeout=300,
        )
        reply.raise_for_status()
        description = re.sub(r"\s+", " ", reply.json()["message"]["content"]).strip()
    except requests.exceptions.ConnectionError:
        raise  # the app shows its normal "Ollama is not running" message
    except Exception as error:
        return f"I could not look at the picture: {error}. If the model is missing, run: ollama pull {vision_model}"
    if len(description) < 15:
        return "I could not understand the picture. Try a clearer photo."
    if should_stop():
        return "Stopped. No image was made."

    # Step 2 and 3: add the style, then paint a new picture from the words.
    final = f"{description[:300]} Style: {style[:100]}."
    width, height = size_like(image_b64)
    data, error = download(final, width, height, should_stop)
    if error:
        return error
    path, error = store_image(data, "restyle " + style)
    if error:
        return error

    return (
        f"Done! I made a new picture in your style ({width}x{height}) and opened it.\n"
        f"What I saw in your photo: {description}\n"
        f"Prompt I used: {final}\n"
        f"Saved at: {path}\n"
        "This is a NEW picture painted from a description, not an edit of your photo, so "
        "details and faces will differ. Your photo stayed on your laptop; only the "
        "description and style words went to the online service."
    )