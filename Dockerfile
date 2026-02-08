FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libavcodec-extra curl git build-essential nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Instalar yt-dlp desde GitHub (extractores al día)
RUN pip install --no-cache-dir --upgrade "yt-dlp @ git+https://github.com/yt-dlp/yt-dlp.git"

COPY . .
RUN mkdir -p /app/downloads

EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 600 --workers 1 --threads 8