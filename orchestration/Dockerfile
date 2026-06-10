ARG AIRFLOW_IMAGE
FROM ${AIRFLOW_IMAGE}

USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         build-essential \
         git \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER airflow

# Copier les requirements
COPY --chown=airflow:root jobs/requirements.txt /opt/airflow/jobs/requirements.txt
COPY --chown=airflow:root orchestration/requirements.txt /tmp/requirements.txt

# Installer les dépendances
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

