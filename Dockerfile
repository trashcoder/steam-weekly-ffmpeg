FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install flask requests --no-cache-dir

WORKDIR /app

COPY server.py .
COPY render_video.py .
COPY generate_intro_outro.py .
COPY generate_music.py .

RUN mkdir -p /data/steam-bot/workspace/games \
             /data/steam-bot/output

EXPOSE 5679

CMD ["python3", "server.py"]
