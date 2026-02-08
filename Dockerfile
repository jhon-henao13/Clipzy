FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    curl \
    git \
    build-essential \
    nodejs \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Primero las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalamos yt-dlp directamente desde el repositorio master para tener los últimos fixes
RUN pip install --no-cache-dir --upgrade "yt-dlp[default] @ git+https://github.com/yt-dlp/yt-dlp.git"

COPY . .
RUN mkdir -p /app/downloads

EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 600 --workers 1 --threads 8