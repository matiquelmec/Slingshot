# ═══════════════════════════════════════════════════════════════
# Slingshot Trading Engine v4.3.5 — Backend Dockerfile
# ═══════════════════════════════════════════════════════════════

FROM python:3.11-slim

WORKDIR /app

# Dependencias de sistema para compilaciones nativas (numpy, pandas, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl && \
    rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY engine/ ./engine/
COPY main.py ./
COPY .env* ./

# Crear directorios necesarios
RUN mkdir -p /app/tmp /app/logs

# Puerto de la API
EXPOSE 8000

# Healthcheck integrado
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Punto de entrada
CMD ["python", "-m", "uvicorn", "engine.api.main_router:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
