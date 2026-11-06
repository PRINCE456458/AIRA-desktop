import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3.2:3b",
        "prompt": "Say hello in one short sentence.",
        "stream": False,
    },
)

print(response.json()["response"])