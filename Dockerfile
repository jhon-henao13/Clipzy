FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Añadimos tor y ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    build-essential \
    libffi-dev \
    tor \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir curl_cffi
RUN pip install --no-cache-dir --upgrade "yt-dlp[default,impersonate] @ git+https://github.com/yt-dlp/yt-dlp.git"

COPY . .
RUN mkdir -p /app/downloads

# Script para iniciar Tor en segundo plano y luego la app
RUN echo "#!/bin/bash\ntor &\nsleep 5\ngunicorn --bind 0.0.0.0:\${PORT:-8000} app:app --timeout 600 --workers 1 --threads 4" > /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
CMD ["/app/entrypoint.sh"]