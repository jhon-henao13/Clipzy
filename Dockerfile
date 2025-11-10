# Etapa 1: Builder (instala dependencias Python)
FROM python:3.12-slim AS builder

WORKDIR /app

# Copia requirements primero para cache de layers
COPY requirements.txt .
RUN python -m venv venv
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install -r requirements.txt

# Etapa 2: Runtime (instala ffmpeg y copia todo)
FROM python:3.12-slim AS runner

# Instala ffmpeg (paquete del sistema)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia el venv del builder
COPY --from=builder /app/venv venv
ENV VIRTUAL_ENV=/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copia el código de tu app
COPY . .

# Expone el puerto (ajusta si usas otro, e.g., 5000)
EXPOSE 8080

# Comando de run (ajusta si usas gunicorn o flask run)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]  # Reemplaza "app:app" con tu entrypoint Flask