#!/usr/bin/env python3
"""
Generiert einen 30s Synthwave-Hintergrundmusik-Clip via OpenRouter Lyria 3 Clip Preview.
Speichert das Ergebnis als gaming_music in STEAM_WORKSPACE.

Umgebungsvariablen:
  OPENROUTER_API_KEY  – OpenRouter API Key (Pflicht)
  STEAM_WORKSPACE     – Workspace-Pfad (Default: /data/steam-bot/workspace)
  MUSIC_PROMPT        – Optionaler eigener Prompt für Lyria
"""

import base64
import json
import os
import sys
from pathlib import Path

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_PROMPT = (
    "Synthwave electronic background music for a gaming YouTube channel. "
    "Energetic retro synths, pulsing bass, driving 80s-inspired beat. "
    "No vocals, purely instrumental. "
    "Perfect as low-volume background music under spoken game reviews. "
    "Build up from a gentle intro, peak energy at 15 seconds, smooth fade-out."
)


def generate(api_key: str, prompt: str, workspace: Path) -> Path:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "google/lyria-3-clip-preview",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }

    print("Generating background music via Lyria 3 Clip...")
    resp = requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=120)
    if not resp.ok:
        sys.exit(f"Lyria API error {resp.status_code}: {resp.text}")

    audio_chunks: list[str] = []
    for raw in resp.iter_lines():
        if not raw or not raw.startswith(b"data: "):
            continue
        data = raw[6:]
        if data == b"[DONE]":
            break
        try:
            chunk = json.loads(data)
            audio = chunk["choices"][0]["delta"].get("audio") or {}
            if audio.get("data"):
                audio_chunks.append(audio["data"])
        except (json.JSONDecodeError, KeyError, IndexError):
            continue

    if not audio_chunks:
        sys.exit("Lyria returned no audio data.")

    audio_bytes = base64.b64decode("".join(audio_chunks))

    # Format aus Datei-Magic ermitteln (RIFF=wav, fLaC=flac, sonst mp3 annehmen)
    magic = audio_bytes[:4]
    ext = "wav" if magic[:4] == b"RIFF" else "flac" if magic[:4] == b"fLaC" else "mp3"

    workspace.mkdir(parents=True, exist_ok=True)
    out = workspace / f"gaming_music.{ext}"
    out.write_bytes(audio_bytes)
    print(f"Music saved: {out} ({len(audio_bytes) // 1024} KB)")
    return out


INTRO_PROMPT = (
    "High-energy Drum and Bass intro for a gaming YouTube channel. "
    "Upbeat dance feel, fast breakbeat drums, punchy bass line. "
    "Explosive start within the first second — no slow build-up. "
    "Euphoric, driving, fun. No vocals, purely instrumental. "
    "Think club-ready DnB with a bright, modern gaming vibe."
)


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        sys.exit("Error: OPENROUTER_API_KEY not set")

    # MUSIC_OUTPUT überschreibt den Standard-Workspace-Pfad (für Intro-Musik)
    custom_output = os.environ.get("MUSIC_OUTPUT")
    if custom_output:
        out_path = Path(custom_output)
        workspace = out_path.parent
        prompt = os.environ.get("MUSIC_PROMPT", INTRO_PROMPT)
    else:
        workspace = Path(os.environ.get("STEAM_WORKSPACE", "/data/steam-bot/workspace"))
        prompt = os.environ.get("MUSIC_PROMPT", DEFAULT_PROMPT)

    result = generate(api_key, prompt, workspace)

    # Bei custom output: Datei zum gewünschten Namen umbenennen
    if custom_output and result != Path(custom_output):
        result.rename(custom_output)


if __name__ == "__main__":
    main()
