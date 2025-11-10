# Dockerfile
FROM python:3.12-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1

# Instala dependencias del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia requirements e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia la app
COPY . .

# Crea la carpeta de descargas
RUN mkdir -p /app/downloads

# Expone el puerto que asigna Render
EXPOSE 10000  # Render reemplaza con $PORT automáticamente

# Comando
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app", "--timeout", "120"]

