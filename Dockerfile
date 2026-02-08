FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Añadimos build-essential para que curl_cffi se instale correctamente
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    build-essential \
    libffi-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalamos curl_cffi explícitamente antes de yt-dlp
RUN pip install --no-cache-dir curl_cffi

# Instalación de yt-dlp desde master
RUN pip install --no-cache-dir --upgrade "yt-dlp[default,impersonate] @ git+https://github.com/yt-dlp/yt-dlp.git"

COPY . .
RUN mkdir -p /app/downloads

EXPOSE 8000
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 600 --workers 1 --threads 4