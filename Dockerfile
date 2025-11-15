# Usa Python 3.12 slim
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements y actualizar yt-dlp a la última versión
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade --force-reinstall "git+https://github.com/yt-dlp/yt-dlp.git"

# add EJS challenge solver so yt-dlp can solve YouTube signatures
RUN pip install --no-cache-dir yt-dlp-ejs

# Después de pip install yt-dlp
RUN pip install --no-cache-dir "curl_cffi[all]"


# Instalar binario más reciente (opcional)
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

# Copiar la app
COPY . .

# Carpeta de descargas
RUN mkdir -p /app/downloads

EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 300 --workers 1 --threads 2
