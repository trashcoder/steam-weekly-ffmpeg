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
import subprocess
import sys
from pathlib import Path

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_PROMPT = (
    "Uplifting electronic pop drum and bass for a gaming YouTube channel. "
    "Fast breakbeat drums, punchy bassline, bright euphoric synths. "
    "High energy, positive feel — think club-ready DnB with a pop sensibility. "
    "No vocals, purely instrumental. "
    "Consistent driving energy throughout, suitable as background under spoken commentary."
)


def generate(api_key: str, prompt: str, workspace: Path) -> Path:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "google/lyria-3-pro-preview",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }

    print("Generating background music via Lyria 3 Clip...")
    resp = requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=120)
    if not resp.ok:
        raise RuntimeError(f"Lyria API error {resp.status_code}: {resp.text}")

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
        raise RuntimeError("Lyria returned no audio data.")

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


def generate_long_music(api_key: str, prompt: str, workspace: Path, clips: int = 3) -> Path:
    """Generiert mehrere Clips und fügt sie zu einem langen Track zusammen.
    Wiederholt fehlgeschlagene Versuche bis zu clips*2 Gesamtversuchen."""
    clip_paths = []
    attempt = 0
    max_attempts = clips * 2
    while len(clip_paths) < clips and attempt < max_attempts:
        attempt += 1
        print(f"Generating music clip {len(clip_paths) + 1}/{clips} (Versuch {attempt}/{max_attempts})...")
        try:
            clip = generate(api_key, prompt, workspace)
        except RuntimeError as e:
            print(f"WARNING: Versuch {attempt} fehlgeschlagen, wiederhole: {e}", file=sys.stderr)
            continue
        numbered = workspace / f"gaming_music_part{len(clip_paths) + 1}{clip.suffix}"
        clip.rename(numbered)
        clip_paths.append(numbered)

    if not clip_paths:
        sys.exit("Fehler: Kein einziger Musik-Clip erfolgreich generiert.")
    if len(clip_paths) < clips:
        print(f"WARNING: Nur {len(clip_paths)}/{clips} Clips generiert — Musik wird häufiger geloopt.", file=sys.stderr)
    else:
        print(f"Alle {clips} Clips erfolgreich generiert.")

    out = workspace / "gaming_music.mp3"
    list_file = workspace / "_music_concat.txt"
    with open(list_file, "w") as f:
        for cp in clip_paths:
            f.write(f"file '{cp.resolve()}'\n")

    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c:a", "libmp3lame", "-q:a", "2", str(out)],
        capture_output=True, text=True
    )
    list_file.unlink(missing_ok=True)
    for cp in clip_paths:
        cp.unlink(missing_ok=True)

    if r.returncode != 0:
        sys.exit(f"FFmpeg concat error: {r.stderr}")

    print(f"Long music track saved: {out} ({out.stat().st_size // 1024} KB)")
    return out


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

    if custom_output:
        # Intro-Musik: einzelner Clip reicht
        try:
            result = generate(api_key, prompt, workspace)
        except RuntimeError as e:
            sys.exit(f"Fehler bei Intro-Musikgenerierung: {e}")
        if result != Path(custom_output):
            result.rename(custom_output)
    else:
        # Hintergrundmusik: mehrere Clips zu einem langen Track zusammensetzen
        generate_long_music(api_key, prompt, workspace)


if __name__ == "__main__":
    main()
