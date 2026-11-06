import base64
import io

from PIL import Image


def image_to_base64(path, max_size=1024):
    """Open an image, shrink it, and turn it into text the AI can receive."""
    image = Image.open(path)
    image = image.convert("RGB")          # makes PNG/WEBP work too
    image.thumbnail((max_size, max_size))  # big photos become smaller and faster
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")