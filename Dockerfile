FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Instalamos ffmpeg (vital) y dependencias básicas
# ELIMINAMOS tor y nodejs (ya no es estrictamente necesario si usamos impersonate, pero ffmpeg sí)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    libffi-dev \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar y e instalar requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código
COPY . .
RUN mkdir -p /app/downloads

# Exponer puerto
EXPOSE 8000

# Ejecutar Gunicorn directamente sin sleeps ni scripts de entrada complejos
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} app:app --timeout 120 --workers 2 --threads 4