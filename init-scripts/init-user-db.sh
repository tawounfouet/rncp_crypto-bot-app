#!/bin/bash
set -e


# -d "$POSTGRES_DB" explicite : sans lui, psql se connecte par defaut a une base
# portant le MEME NOM que l'utilisateur (comportement libpq standard, rien a voir avec
# POSTGRES_DB) -- si POSTGRES_USER ne vaut pas un nom d'utilisateur classique (ex. une
# valeur generee mise par erreur dans la mauvaise variable), la connexion echoue avec
# "database <POSTGRES_USER> does not exist", observe en conditions reelles le
# 2026-08-29. $POSTGRES_DB est deja cree par le bootstrap de l'image officielle
# postgres, avant l'execution des scripts de /docker-entrypoint-initdb.d/.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
  SELECT 'CREATE DATABASE airflow'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec

  SELECT 'CREATE DATABASE mlflow'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow')\gexec

  SELECT 'CREATE DATABASE crypto_bot_db'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'crypto_bot_db')\gexec
EOSQL
