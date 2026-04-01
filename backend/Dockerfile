# Dockerfile multi-stage pour le backend FastAPI
# ===============================================

# Stage 1: Builder
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim as builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Installer les dependances de build
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Creer et activer un environnement virtuel
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copier et installer les requirements
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


# Stage 2: Runtime
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim as runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

# Installer les dependances runtime et appliquer les patchs securite
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Creer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash app

# Copier l'environnement virtuel du builder
COPY --from=builder /opt/venv /opt/venv

# Definir le repertoire de travail
WORKDIR /app

# Copier le code source
COPY --chown=app:app . .

# Creer les repertoires necessaires
RUN mkdir -p logs data && \
    chown -R app:app /app

# Changer vers l'utilisateur non-root
USER app

# Exposer le port
EXPOSE 8009

# Verification de sante
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8009/health || exit 1

# Commande par defaut
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8009"]
