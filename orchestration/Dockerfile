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

# Installation des providers officiels et bibliotheques requises par cryptobot
# NOTE : pyarrow doit être >=17.0 pour être compatible NumPy 2.x.
#        pyarrow <17 a été compilé contre NumPy 1.x → AttributeError: _ARRAY_API not found.
RUN pip install --no-cache-dir \
    apache-airflow==2.8.1 \
    apache-airflow-providers-postgres \
    apache-airflow-providers-mongo \
    apache-airflow-providers-amazon \
    pymongo==4.6.3 \
    pandas==2.2.3 \
    "numpy>=2.0" \
    "pyarrow>=17.0" \
    minio==7.2.20 \
    python-binance==1.0.35
