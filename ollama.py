"""Client for a local Ollama instance — fallback for messages that aren't a tennis lookup."""
from __future__ import annotations

import os

import requests

SYSTEM_PROMPT = (
    "You are the fallback chat handler for a Discord bot whose main job is looking up "
    "free tennis court slots from matchi.se. You're only shown messages the bot couldn't "
    "parse as a tennis lookup. Answer the user's question directly and concisely — a "
    "sentence or two, Discord-message length. No need to mention tennis unless asked."
)


def ask(question: str) -> str:
    """Send `question` to the local Ollama model and return its reply text."""
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "gemma4:e2b")

    try:
        r = requests.post(
            f"{host.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                "think": False,  # skip the reasoning pass — faster on Pi-class hardware
                "stream": False,
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except requests.RequestException:
        return "(couldn't reach the local model right now)"
    except (KeyError, ValueError):
        return "(got an unexpected response from the local model)"
