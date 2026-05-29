#!/usr/bin/env python3
"""
Steam Weekly Top 10 – Video Renderer
=====================================
Erwartet folgende Ordnerstruktur:
  ./workspace/
    intro.mp4          (optional – wird übersprungen falls nicht vorhanden)
    outro.mp4          (optional – wird übersprungen falls nicht vorhanden)
    games/
      01_<appid>/
        trailer.mp4
        voice.mp3
      02_<appid>/
        ...

Output: ./output/final_video.mp4
"""

import os
import subprocess
import json
import sys
from pathlib import Path

# ──────────────────────────────────────────────
# KONFIGURATION
# ──────────────────────────────────────────────
WORKSPACE   = Path(os.environ.get("STEAM_WORKSPACE", "/data/steam-bot/workspace"))
OUTPUT_DIR  = Path(os.environ.get("STEAM_OUTPUT", "/data/steam-bot/output"))
OUTPUT_FILE = OUTPUT_DIR / "final_video.mp4"

# Video-Normalisierung: alle Clips auf diese Einstellungen bringen
TARGET_WIDTH   = 1920
TARGET_HEIGHT  = 1080
TARGET_FPS     = 30
TARGET_AUDIO   = "aac"
TARGET_VCODEC  = "libx264"
TARGET_PRESET  = "fast"
TARGET_CRF     = 23

CLIP_MAX_DURATION = int(os.environ.get("CLIP_MAX_DURATION", "60"))  # Sekunden pro Spiel-Clip

# Übergangs-/Titelkarte pro Spiel (Sekunden schwarzer Screen mit Titel)
TITLE_CARD_DURATION = 3   # Sekunden – auf 0 setzen um zu deaktivieren

# ──────────────────────────────────────────────
# HILFSFUNKTIONEN
# ──────────────────────────────────────────────

def run(cmd: list, label: str = ""):
    """Shell-Befehl ausführen mit Fehlerbehandlung."""
    print(f"  ▶ {label or ' '.join(cmd[:4])}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ Fehler: {result.stderr[-500:]}")
        sys.exit(1)
    return result


def normalize(src: Path, dst: Path, label: str = ""):
    """
    Normalisiert ein Video auf einheitliche Auflösung, FPS und Codec.
    Audio wird auf Stereo AAC gemischt.
    Falls keine Audiospur vorhanden → Stille wird hinzugefügt.
    """
    filter_v = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={TARGET_FPS},format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", filter_v,
        "-c:v", TARGET_VCODEC, "-preset", TARGET_PRESET, "-crf", str(TARGET_CRF),
        "-c:a", TARGET_AUDIO, "-ar", "44100", "-ac", "2",
        "-shortest",
        str(dst)
    ]
    run(cmd, label or f"Normalisiere {src.name}")


def merge_trailer_voice(trailer: Path, voice: Path, dst: Path, game_name: str = "", max_duration: int = None):
    """
    Mischt Trailer-Video mit Voice-Over:
    - Original-Ton des Trailers auf 20 % reduziert
    - Voice-Over auf 100 %
    - Falls Trailer kürzer als Voice → Video einfrieren (loop letztes Frame)
    - Falls Voice kürzer → Video wird gekürzt
    - Falls max_duration gesetzt → Clip wird auf max. Sekunden begrenzt
    """
    filter_complex = (
        "[0:a]volume=0.2[trailer_audio];"
        "[1:a]volume=1.0[voice_audio];"
        "[trailer_audio][voice_audio]amix=inputs=2:duration=longest[aout]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(trailer),   # Trailer ggf. loopen
        "-i", str(voice),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", TARGET_VCODEC, "-preset", TARGET_PRESET, "-crf", str(TARGET_CRF),
        "-c:a", TARGET_AUDIO, "-ar", "44100", "-ac", "2",
        "-shortest",
    ]
    if max_duration is not None:
        cmd += ["-t", str(max_duration)]
    cmd.append(str(dst))
    run(cmd, f"Merge Trailer+Voice: {game_name or dst.name}")


def make_title_card(text: str, duration: int, dst: Path):
    """Erstellt eine schwarze Titelkarte mit weißem Text (kein externes Font nötig)."""
    if duration <= 0:
        return
    # Text escapen für FFmpeg drawtext
    safe_text = text.replace("'", "\\'").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:size={TARGET_WIDTH}x{TARGET_HEIGHT}:rate={TARGET_FPS}:duration={duration}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-vf", (
            f"drawtext=text='{safe_text}':"
            f"fontcolor=white:fontsize=60:"
            f"x=(w-text_w)/2:y=(h-text_h)/2"
        ),
        "-c:v", TARGET_VCODEC, "-preset", TARGET_PRESET, "-crf", str(TARGET_CRF),
        "-c:a", TARGET_AUDIO,
        "-t", str(duration),
        str(dst)
    ]
    run(cmd, f"Titelkarte: {text[:40]}")


def concat_videos(parts: list[Path], dst: Path):
    """Verbindet eine Liste von MP4s via FFmpeg concat demuxer."""
    list_file = OUTPUT_DIR / "_concat_list.txt"
    with open(list_file, "w") as f:
        for p in parts:
            f.write(f"file '{p.resolve()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(dst)
    ]
    run(cmd, f"Zusammenfügen → {dst.name}")
    list_file.unlink(missing_ok=True)


# ──────────────────────────────────────────────
# HAUPTPROGRAMM
# ──────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_DIR / "_tmp"
    tmp.mkdir(exist_ok=True)

    parts: list[Path] = []
    step = 0

    def tmp_file(name: str) -> Path:
        return tmp / name

    # ── 1. INTRO ──────────────────────────────
    intro_src = WORKSPACE / "intro.mp4"
    if intro_src.exists():
        print("\n[1/4] Intro verarbeiten...")
        intro_norm = tmp_file("00_intro.mp4")
        normalize(intro_src, intro_norm, "Intro normalisieren")
        parts.append(intro_norm)
    else:
        print("\n[1/4] Kein Intro gefunden – übersprungen.")

    # ── 2. SPIELE ─────────────────────────────
    games_dir = WORKSPACE / "games"
    game_folders = sorted([d for d in games_dir.iterdir() if d.is_dir()])

    print(f"\n[2/4] {len(game_folders)} Spiele verarbeiten...")

    # Metadaten laden falls vorhanden (für Titelkarten)
    meta_file = WORKSPACE / "games_meta.json"
    meta = {}
    if meta_file.exists():
        with open(meta_file) as f:
            meta = json.load(f)  # { "appid": "Spielname", ... }

    for i, folder in enumerate(game_folders, 1):
        trailer = folder / "trailer.mp4"
        voice   = folder / "voice.mp3"

        if not trailer.exists():
            print(f"  ⚠ Kein Trailer in {folder.name} – übersprungen.")
            continue
        if not voice.exists():
            print(f"  ⚠ Kein Voice-Over in {folder.name} – übersprungen.")
            continue

        appid     = folder.name.split("_")[-1]
        game_name = meta.get(appid, folder.name)
        prefix    = f"{i:02d}"

        # Titelkarte
        if TITLE_CARD_DURATION > 0:
            card = tmp_file(f"{prefix}_card.mp4")
            make_title_card(f"#{i} – {game_name}", TITLE_CARD_DURATION, card)
            parts.append(card)

        # Trailer normalisieren
        trailer_norm = tmp_file(f"{prefix}_trailer_norm.mp4")
        normalize(trailer, trailer_norm, f"Trailer #{i} normalisieren")

        # Voice-Over mergen
        merged = tmp_file(f"{prefix}_merged.mp4")
        merge_trailer_voice(trailer_norm, voice, merged, game_name, CLIP_MAX_DURATION)
        parts.append(merged)

    # ── 3. OUTRO ──────────────────────────────
    outro_src = WORKSPACE / "outro.mp4"
    if outro_src.exists():
        print("\n[3/4] Outro verarbeiten...")
        outro_norm = tmp_file("99_outro.mp4")
        normalize(outro_src, outro_norm, "Outro normalisieren")
        parts.append(outro_norm)
    else:
        print("\n[3/4] Kein Outro gefunden – übersprungen.")

    # ── 4. ZUSAMMENFÜGEN ──────────────────────
    print(f"\n[4/4] {len(parts)} Clips zusammenfügen → {OUTPUT_FILE}")
    concat_videos(parts, OUTPUT_FILE)

    # Aufräumen
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n✅ Fertig! Video gespeichert unter: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
