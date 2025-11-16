# Usa Python 3.12 slim
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    curl \
    build-essential \
    git \
    quickjs \
    && rm -rf /var/lib/apt/lists/*


# Dependencias Playwright (FALTABAN)
RUN apt-get update && apt-get install -y \
    libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*


RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements y actualizar yt-dlp a la última versión
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir "yt-dlp @ git+https://github.com/yt-dlp/yt-dlp.git"
RUN pip install --no-cache-dir yt-dlp-ejs
RUN pip install --no-cache-dir -r requirements.txt

# Instalar dependencias para Playwright y Chromium
RUN apt-get update && apt-get install -y wget gnupg ca-certificates

# Instalar Playwright
RUN pip install playwright
RUN playwright install chromium

# Copiar la app
COPY . .

# Carpeta de descargas
RUN mkdir -p /app/downloads

EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 300 --workers 1 --threads 2
