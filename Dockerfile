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


# Crea carpeta de trabajo
WORKDIR /app

# Copia requirements.txt e instala dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    # Instalar yt-dlp usando el binario oficial (siempre la versión más reciente)
    RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
        && chmod +x /usr/local/bin/yt-dlp \
        && pip install --no-cache-dir gunicorn


# Copia la aplicación completa
COPY . .

# Crea carpeta de descargas
RUN mkdir -p /app/downloads

# Koyeb usa el puerto 8000 para el health check
EXPOSE 8000


# Comando de ejecución (compatible con Koyeb y Render)
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 300 --workers 1 --threads 2
