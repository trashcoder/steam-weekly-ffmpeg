#!/usr/bin/env python3
"""
Intro & Outro Generator
========================
Erstellt ein professionelles Intro und Outro mit reinem FFmpeg –
kein externes Tool, keine Kosten.

Anpassungen in der KONFIGURATION-Sektion unten.

Usage:
  python3 generate_intro_outro.py

Output:
  ./workspace/intro.mp4
  ./workspace/outro.mp4
"""

import os
import subprocess
import sys
from pathlib import Path

# ──────────────────────────────────────────────
# KONFIGURATION – hier anpassen!
# ──────────────────────────────────────────────

WORKSPACE = Path(os.environ.get("STEAM_WORKSPACE", "/data/steam-bot/workspace"))

# Kanal-Name / Branding
CHANNEL_NAME   = os.environ.get("INTRO_CHANNEL_NAME", "Steam Weekly")
CHANNEL_SLOGAN = os.environ.get("INTRO_CHANNEL_SLOGAN", "Die besten neuen Releases – jede Woche")
SOCIAL_HANDLE  = os.environ.get("INTRO_SOCIAL_HANDLE", "@SteamWeekly")

# Farben (Hex ohne #, für FFmpeg)
BG_COLOR       = os.environ.get("INTRO_BG_COLOR", "0a0a1a")   # Fast schwarz / dunkles Blau
ACCENT_COLOR   = os.environ.get("INTRO_ACCENT_COLOR", "1b9aff")   # Steam-Blau
TEXT_COLOR     = "ffffff"   # Weiß

# Abmessungen
WIDTH  = 1920
HEIGHT = 1080
FPS    = 30

# Dauer
INTRO_DURATION  = 5   # Sekunden
OUTRO_DURATION  = 8   # Sekunden

# ──────────────────────────────────────────────
# HILFSFUNKTIONEN
# ──────────────────────────────────────────────

def run(cmd: list, label: str = ""):
    print(f"  ▶ {label}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ FFmpeg Fehler:\n{result.stderr[-800:]}")
        sys.exit(1)


def hex_to_ffmpeg(hex_color: str) -> str:
    """'1b9aff' → '0x1b9aff'"""
    return f"0x{hex_color}"


# ──────────────────────────────────────────────
# INTRO
# ──────────────────────────────────────────────

def generate_intro():
    """
    Aufbau:
    - Dunkler Hintergrund mit Verlauf
    - Animierter blauer Balken der von links reinschiebt (t=0.5s)
    - Kanal-Name erscheint (Fade-In bei t=1.0s)
    - Slogan erscheint (Fade-In bei t=2.0s)
    """
    out = WORKSPACE / "intro.mp4"

    # Escape-Zeichen für drawtext
    name   = CHANNEL_NAME.replace("'", "\\'").replace(":", "\\:")
    slogan = CHANNEL_SLOGAN.replace("'", "\\'").replace(":", "\\:")

    vf = (
        # Hintergrund
        f"color=c=#{BG_COLOR}:size={WIDTH}x{HEIGHT}:rate={FPS}[bg];"

        # Animierter Balken (schiebt von links rein, t=0.5 bis t=1.2)
        f"[bg]drawbox="
        f"x='if(lt(t,0.5),-(w),if(lt(t,1.2),(t-0.5)/0.7*({WIDTH}//2-80),{WIDTH}//2-80))':"
        f"y={HEIGHT}//2-6:w={WIDTH}//2:h=12:color=#{ACCENT_COLOR}:t=fill[with_bar];"

        # Kanal-Name (Fade-In ab t=1.0)
        f"[with_bar]drawtext="
        f"text='{name}':"
        f"fontcolor=#{TEXT_COLOR}:"
        f"fontsize=90:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2-60:"
        f"alpha='if(lt(t,1.0),0,if(lt(t,1.8),(t-1.0)/0.8,1))'[with_title];"

        # Slogan (Fade-In ab t=2.0)
        f"[with_title]drawtext="
        f"text='{slogan}':"
        f"fontcolor=#{ACCENT_COLOR}:"
        f"fontsize=42:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2+60:"
        f"alpha='if(lt(t,2.0),0,if(lt(t,2.8),(t-2.0)/0.8,1))'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=#{BG_COLOR}:size={WIDTH}x{HEIGHT}:rate={FPS}:duration={INTRO_DURATION}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={INTRO_DURATION}",
        "-filter_complex", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-t", str(INTRO_DURATION),
        str(out)
    ]
    run(cmd, f"Intro generieren → {out}")
    print(f"  ✓ Intro gespeichert: {out}")


# ──────────────────────────────────────────────
# OUTRO
# ──────────────────────────────────────────────

def generate_outro():
    """
    Aufbau:
    - Gleicher Hintergrund wie Intro
    - "Danke fürs Zuschauen!" (Fade-In t=0.5)
    - Social Handle (Fade-In t=1.5)
    - "Nächste Woche wieder!" (Fade-In t=3.0)
    - Fade-Out des gesamten Videos in letzten 1.5s
    """
    out = WORKSPACE / "outro.mp4"

    thanks  = "Danke fürs Zuschauen!".replace("'", "\\'")
    handle  = SOCIAL_HANDLE.replace("'", "\\'")
    next_wk = "Naechste Woche wieder!".replace("'", "\\'")  # Umlaute vermeiden
    d       = OUTRO_DURATION

    fade_start = d - 1.5   # Fade-Out beginnt

    vf = (
        f"color=c=#{BG_COLOR}:size={WIDTH}x{HEIGHT}:rate={FPS}[bg];"

        # "Danke"-Text
        f"[bg]drawtext=text='{thanks}':"
        f"fontcolor=#{TEXT_COLOR}:fontsize=80:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-100:"
        f"alpha='if(lt(t,0.5),0,if(lt(t,1.3),(t-0.5)/0.8,if(gt(t,{fade_start}),(({d}-t)/1.5),1)))'[t1];"

        # Social Handle
        f"[t1]drawtext=text='{handle}':"
        f"fontcolor=#{ACCENT_COLOR}:fontsize=54:"
        f"x=(w-text_w)/2:y=(h-text_h)/2+10:"
        f"alpha='if(lt(t,1.5),0,if(lt(t,2.3),(t-1.5)/0.8,if(gt(t,{fade_start}),(({d}-t)/1.5),1)))'[t2];"

        # "Nächste Woche"
        f"[t2]drawtext=text='{next_wk}':"
        f"fontcolor=#{TEXT_COLOR}:fontsize=40:"
        f"x=(w-text_w)/2:y=(h-text_h)/2+110:"
        f"alpha='if(lt(t,3.0),0,if(lt(t,3.8),(t-3.0)/0.8,if(gt(t,{fade_start}),(({d}-t)/1.5),1)))'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=#{BG_COLOR}:size={WIDTH}x{HEIGHT}:rate={FPS}:duration={d}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={d}",
        "-filter_complex", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-t", str(d),
        str(out)
    ]
    run(cmd, f"Outro generieren → {out}")
    print(f"  ✓ Outro gespeichert: {out}")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    print("\n🎬 Intro generieren...")
    generate_intro()

    print("\n🎬 Outro generieren...")
    generate_outro()

    print("\n✅ Fertig!")
    print(f"   Intro → {(WORKSPACE / 'intro.mp4').resolve()}")
    print(f"   Outro → {(WORKSPACE / 'outro.mp4').resolve()}")
    print("\n💡 Tipp: Ersetze intro.mp4 / outro.mp4 jederzeit mit")
    print("         eigenen fertigen Videos – render_video.py")
    print("         erkennt sie automatisch.")


if __name__ == "__main__":
    main()
