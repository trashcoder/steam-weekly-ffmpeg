# Steam Weekly – FFmpeg API

FFmpeg-Microservice für den Steam Weekly Top 10 YouTube-Bot.
Wird als Docker-Container via Portainer deployed und kommuniziert
mit einem bestehenden N8N-Container über das `n8n_default` Netzwerk.

---

## Repo-Struktur

```
├── ffmpeg-api/
│   ├── Dockerfile
│   ├── server.py               ← Flask API (Port 5679)
│   ├── render_video.py         ← FFmpeg Render-Logic
│   └── generate_intro_outro.py ← Intro/Outro Generator
├── portainer-stack.yml         ← In Portainer einfügen
└── .gitignore
```

---

## Portainer Setup

### 1. Repo URL kopieren
```
https://github.com/DEIN-USER/DEIN-REPO.git
```

### 2. Portainer → Stacks → Add Stack
- **Name:** `ffmpeg-api`
- **Build method:** Web editor
- Inhalt von `portainer-stack.yml` einfügen
- Zwei Werte anpassen:
  - `context:` → deine GitHub Repo URL
  - `device:` → absoluter Pfad zu `steam-bot-data` auf deinem Host

### 3. Deploy the Stack

### 4. Health-Check
```
http://localhost:5679/health
```

---

## API Endpoints

| Method | Endpoint | Beschreibung |
|---|---|---|
| GET | `/health` | FFmpeg-Version + Status |
| POST | `/render` | Render-Job starten |
| GET | `/status/<job_id>` | Job-Status abfragen |
| POST | `/intro-outro` | Intro & Outro generieren |

---

## Intro/Outro generieren

```bash
curl -X POST http://localhost:5679/intro-outro \
  -H "Content-Type: application/json" \
  -d '{
    "channel_name":   "Steam Weekly",
    "channel_slogan": "Die besten neuen Releases",
    "social_handle":  "@SteamWeekly",
    "accent_color":   "1b9aff"
  }'
```

---

## Updates deployen

Nach einem `git push` in Portainer:
**Stacks → ffmpeg-api → Editor → Update the Stack**
→ Portainer pullt automatisch den neuen Code und baut das Image neu.
