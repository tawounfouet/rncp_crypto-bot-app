#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  SELECT 'CREATE DATABASE airflow'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec

  SELECT 'CREATE DATABASE mlflow'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow')\gexec

  SELECT 'CREATE DATABASE crypto_bot_db'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'crypto_bot_db')\gexec
EOSQL
