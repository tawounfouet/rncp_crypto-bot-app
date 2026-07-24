# Dockerfile multi-stage pour le module models (ML)
# ===============================================
# Contexte de build = racine du repo (pas ./models) : necessaire pour COPY utils/,
# le package multi-exchange partage avec backend/jobs/orchestration (cf. issue #10).
# Invocation : docker build -f models/Dockerfile --target <stage> .

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

COPY models/requirements.txt .
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
        gosu \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app models/ .
COPY --chown=app:app utils/ ./utils
COPY models/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Création des dossiers locaux requis pour l'écriture locale si non montés
RUN mkdir -p data logs reports artifacts mlruns && \
    chown -R app:app /app

# Pas de USER ici : l'entrypoint demarre en root pour pouvoir chown les dossiers
# bind-montes (ex. logs/artifacts crees en root:root par Docker sur l'hote), puis
# bascule lui-meme vers "app" avant d'executer la commande (cf. docker-entrypoint.sh).
EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "src.main", "--config", "config.yaml", "api", "--host", "0.0.0.0", "--port", "8010"]
