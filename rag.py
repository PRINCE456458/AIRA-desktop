import json
import math
import os

import requests
from pypdf import PdfReader

import paths

BASE_DIR = paths.DATA_DIR
KB_FILE = os.path.join(BASE_DIR, "knowledge.json")

EMBED_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 800    # characters per piece
OVERLAP = 150       # pieces overlap so sentences are not cut badly
MIN_SCORE = 0.35    # ignore pieces that are not related to the question


def read_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def split_into_chunks(text):
    text = " ".join(text.split())
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start:start + CHUNK_SIZE].strip()
        if piece:
            chunks.append(piece)
        start += CHUNK_SIZE - OVERLAP
    return chunks


def embed(texts):
    """Turn a list of texts into a list of number-lists (embeddings)."""
    vectors = []
    for i in range(0, len(texts), 16):
        batch = texts[i:i + 16]
        response = requests.post(
            EMBED_URL,
            json={"model": EMBED_MODEL, "input": batch},
            timeout=300,
        )
        response.raise_for_status()
        vectors.extend(response.json()["embeddings"])
    return vectors


def normalize(vector):
    length = math.sqrt(sum(x * x for x in vector))
    return [x / length for x in vector] if length else vector


class KnowledgeBase:
    def __init__(self):
        self.items = self._load()

    def _load(self):
        try:
            with open(KB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self):
        with open(KB_FILE, "w", encoding="utf-8") as f:
            json.dump(self.items, f)

    def sources(self):
        return sorted(set(item["source"] for item in self.items))

    def add_file(self, path):
        """Learn a file. Returns how many pieces were stored."""
        name = os.path.basename(path)
        chunks = split_into_chunks(read_file(path))
        if not chunks:
            return 0
        vectors = embed(["search_document: " + c for c in chunks])
        self.items = [i for i in self.items if i["source"] != name]  # re-adding replaces
        for chunk, vector in zip(chunks, vectors):
            self.items.append(
                {"source": name, "text": chunk, "embedding": normalize(vector)}
            )
        self._save()
        return len(chunks)

    def clear(self):
        self.items = []
        self._save()

    def search(self, question, k=3):
        """Return the k pieces most related to the question."""
        if not self.items:
            return []
        q = normalize(embed(["search_query: " + question])[0])
        scored = [
            (sum(a * b for a, b in zip(q, item["embedding"])), item)
            for item in self.items
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for score, item in scored[:k] if score >= MIN_SCORE]