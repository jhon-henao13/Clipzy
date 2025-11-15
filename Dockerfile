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

WORKDIR /app

# Copiar requirements y actualizar yt-dlp a la última versión
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade yt-dlp

# Después de pip install yt-dlp
RUN pip install --no-cache-dir "curl_cffi"


# La instalación de EJS está bien, pero falta **node** (runtime JS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://github.com/yt-dlp/yt-dlp-ejs/releases/latest/download/yt-dlp-ejs.tar.gz \
    | tar -xz -C /usr/local/lib/node_modules \
 && ln -s /usr/local/lib/node_modules/yt-dlp-ejs/bin/yt-dlp-ejs /usr/local/bin/yt-dlp-ejs \
 && echo 'export PATH="/usr/local/bin:$PATH"' >> /etc/profile \
 && echo 'export NODE_PATH="/usr/local/lib/node_modules"' >> /etc/profile

# ← AGREGA ESTO:
ENV PATH="/usr/local/bin:$PATH"
ENV NODE_PATH="/usr/local/lib/node_modules"

# Instalar binario más reciente (opcional)
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

# Copiar la app
COPY . .

# Carpeta de descargas
RUN mkdir -p /app/downloads

EXPOSE 8000

CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 300 --workers 1 --threads 2
