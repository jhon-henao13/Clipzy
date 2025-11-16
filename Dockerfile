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

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements y actualizar yt-dlp a la última versión
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar la app
COPY . .

# Carpeta de descargas
RUN mkdir -p /app/downloads

EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 300 --workers 1 --threads 2
