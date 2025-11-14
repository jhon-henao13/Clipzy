# Usa Python 3.12 slim como base
FROM python:3.12-slim

# Evita buffering
ENV PYTHONUNBUFFERED=1

# Instala ffmpeg y dependencias necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Carpeta de trabajo
WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar la versión MÁS RECIENTE de yt-dlp (binario oficial)
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

# Copiar la aplicación
COPY . .

# Crear carpeta de descargas
RUN mkdir -p /app/downloads

# Koyeb usa el puerto 8000
EXPOSE 8000

# Ejecutar con Gunicorn
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 300 --workers 1 --threads 2
