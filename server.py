#!/usr/bin/env python3
"""
FFmpeg API Server
=================
Nimmt Render-Jobs von N8N entgegen und führt render_video.py aus.

Endpoints:
  GET  /health              → Health-Check
  POST /render              → Render-Job starten (async)
  GET  /status/<job_id>     → Job-Status abfragen
  POST /intro-outro         → Intro & Outro neu generieren
"""

import os
import json
import uuid
import threading
import subprocess
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

DATA_DIR    = Path("/data/steam-bot")
SCRIPTS_DIR = Path("/app")

# Job-Status im Memory
jobs: dict = {}


# ── Health ─────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        ffmpeg = r.stdout.split("\n")[0]
    except Exception:
        ffmpeg = "nicht gefunden"
    return jsonify({"status": "ok", "ffmpeg": ffmpeg})


# ── Render starten ─────────────────────────────────────────────────────

@app.route("/render", methods=["POST"])
def start_render():
    body   = request.get_json(silent=True) or {}
    job_id = str(uuid.uuid4())[:8]

    workspace = body.get("workspace", str(DATA_DIR / "workspace"))
    output    = body.get("output",    str(DATA_DIR / "output"))

    jobs[job_id] = {"status": "running", "log": ""}

    threading.Thread(
        target=_run_render,
        args=(job_id, workspace, output),
        daemon=True
    ).start()

    return jsonify({"job_id": job_id, "status": "running"}), 202


@app.route("/render-sync", methods=["POST"])
def render_sync():
    body      = request.get_json(silent=True) or {}
    workspace = body.get("workspace", str(DATA_DIR / "workspace"))
    output    = body.get("output",    str(DATA_DIR / "output"))

    env = os.environ.copy()
    env["STEAM_WORKSPACE"] = workspace
    env["STEAM_OUTPUT"]    = output
    try:
        r = subprocess.run(
            ["python3", str(SCRIPTS_DIR / "render_video.py")],
            capture_output=True, text=True, env=env, cwd=str(SCRIPTS_DIR),
            timeout=3600
        )
        if r.returncode == 0:
            return jsonify({
                "success": True,
                "output_file": str(Path(output) / "final_video.mp4"),
                "log": r.stdout[-2000:]
            })
        else:
            return jsonify({
                "success": False,
                "error": r.stderr[-2000:],
                "exit_code": r.returncode
            }), 500
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Render timed out after 3600s"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _run_render(job_id: str, workspace: str, output: str):
    env = os.environ.copy()
    env["STEAM_WORKSPACE"] = workspace
    env["STEAM_OUTPUT"]    = output
    try:
        r = subprocess.run(
            ["python3", str(SCRIPTS_DIR / "render_video.py")],
            capture_output=True, text=True, env=env, cwd=str(SCRIPTS_DIR)
        )
        if r.returncode == 0:
            jobs[job_id] = {
                "status":      "done",
                "output_file": str(Path(output) / "final_video.mp4"),
                "log":         r.stdout[-2000:]
            }
        else:
            jobs[job_id] = {"status": "error", "log": r.stderr[-2000:]}
    except Exception as e:
        jobs[job_id] = {"status": "error", "log": str(e)}


# ── Status abfragen ────────────────────────────────────────────────────

@app.route("/status/<job_id>", methods=["GET"])
def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job nicht gefunden"}), 404
    return jsonify({"job_id": job_id, **job})


# ── Intro / Outro ──────────────────────────────────────────────────────

@app.route("/intro-outro", methods=["POST"])
def generate_intro_outro():
    body = request.get_json(silent=True) or {}
    env  = os.environ.copy()
    env["STEAM_WORKSPACE"] = str(DATA_DIR / "workspace")

    mapping = {
        "channel_name":   "INTRO_CHANNEL_NAME",
        "channel_slogan": "INTRO_CHANNEL_SLOGAN",
        "social_handle":  "INTRO_SOCIAL_HANDLE",
        "bg_color":       "INTRO_BG_COLOR",
        "accent_color":   "INTRO_ACCENT_COLOR",
    }
    for key, env_key in mapping.items():
        if key in body:
            env[env_key] = body[key]

    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "generate_intro_outro.py")],
        capture_output=True, text=True, env=env, cwd=str(SCRIPTS_DIR)
    )
    if r.returncode == 0:
        return jsonify({
            "status": "done",
            "intro":  str(DATA_DIR / "workspace/intro.mp4"),
            "outro":  str(DATA_DIR / "workspace/outro.mp4"),
        })
    return jsonify({"status": "error", "log": r.stderr}), 500


# ── Metadaten speichern ─────────────────────────────────────────────────

@app.route("/metadata", methods=["POST"])
def save_metadata():
    body = request.get_json(silent=True) or {}
    workspace = Path(body.get("workspace", str(DATA_DIR / "workspace")))
    meta = body.get("meta", body)

    workspace.mkdir(parents=True, exist_ok=True)
    meta_file = workspace / "games_meta.json"
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({"status": "done", "file": str(meta_file), "count": len(meta)})


# ── File Download ────────────────────────────────────────────────────────

@app.route("/output/<filename>", methods=["GET"])
def download_output(filename: str):
    output_dir = str(DATA_DIR / "output")
    return send_from_directory(output_dir, filename, as_attachment=False)


# ── Start ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🎬 FFmpeg API Server startet auf Port 5679...")
    app.run(host="0.0.0.0", port=5679, debug=False)
