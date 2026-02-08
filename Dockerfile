FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# INSTALACIÓN MAESTRA: yt-dlp con soporte de personificación de navegador
RUN pip install --no-cache-dir --upgrade "yt-dlp[default,impersonate] @ git+https://github.com/yt-dlp/yt-dlp.git"

COPY . .
RUN mkdir -p /app/downloads

EXPOSE 8000
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 600 --workers 1 --threads 4