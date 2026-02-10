FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    ca-certificates \
    nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Permisos totales a la carpeta de descargas
RUN mkdir -p /app/downloads && chmod 777 /app/downloads

# USAMOS 1 SOLO WORKER. En Koyeb Free, 2 workers + FFmpeg = Crash instantáneo.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} app:app --timeout 120 --workers 1 --threads 8"]