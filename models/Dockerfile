# Dockerfile multi-stage pour le module models (ML)
# ===============================================

# Stage 1: Builder
ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}-slim as builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


# Stage 2: Runtime
ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}-slim as runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

# Création des dossiers locaux requis pour l'écriture locale si non montés
RUN mkdir -p data logs reports artifacts mlruns && \
    chown -R app:app /app

USER app
EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

CMD ["python", "-m", "src.main", "--config", "config.yaml", "api", "--host", "0.0.0.0", "--port", "8010"]
