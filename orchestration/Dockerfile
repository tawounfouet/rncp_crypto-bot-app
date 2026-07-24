# check=skip=InvalidDefaultArgInFrom
# AIRFLOW_IMAGE n'a volontairement pas de défaut : la version est définie une
# seule fois dans versions.env et injectée par docker-compose (build.args).
# Invocation : docker build -f orchestration/Dockerfile --target runtime .
ARG AIRFLOW_IMAGE
FROM ${AIRFLOW_IMAGE} AS runtime

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

# Code applicatif : bind-monte en dev (cf. docker-compose.yml x-airflow-common),
# copie en dur ici pour que l'image soit autonome en staging/production (pas de
# checkout du repo sur la cible qui la fait tourner).
COPY --chown=airflow:root orchestration/dags/ /opt/airflow/dags/
COPY --chown=airflow:root orchestration/plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root jobs/ /opt/airflow/jobs/
COPY --chown=airflow:root models/ /opt/airflow/models/
COPY --chown=airflow:root utils/ /opt/airflow/utils/
