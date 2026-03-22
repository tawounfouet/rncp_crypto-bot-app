# Crypto-Bot Frontend

Interface utilisateur Streamlit pour le projet de trading automatise de cryptomonnaies.

## Architecture

```
frontend/
├── src/
│   ├── navigation.py            # Point d'entree, routeur de pages
│   ├── auth/                    # Module authentification
│   │   ├── api_client.py        #   Client HTTP pour les endpoints backend
│   │   ├── auth_manager.py      #   Gestion state Streamlit (tokens, login/register)
│   │   ├── config.py            #   Configuration API (URL, headers, timeout)
│   │   └── utils.py             #   Validation email/password, formatage
│   ├── page/                    # Pages Streamlit
│   │   ├── login_page.py        #   Page de connexion
│   │   ├── signup_page.py       #   Page d'inscription
│   │   ├── app.py               #   Page principale (apres authentification)
│   │   └── info_page.py         #   Page d'information (env, version)
│   ├── utils/                   # Utilitaires
│   │   └── init_session.py      #   Initialisation/reset du session state
│   └── data/                    # Images et assets statiques
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── .gitlab-ci.yml
└── README.md
```

## Flux d'authentification

L'authentification passe par l'API REST du backend (`/api/v1/auth/*`). Les tokens JWT sont stockes dans le session state Streamlit.

```
Page Login
  ├─ Login    → POST /auth/login/json → JWT tokens → Page App
  ├─ Sign Up  → Page Signup
  └─ Guest    → Mode invite → Page App (lecture seule)

Page Signup
  ├─ Register → POST /auth/register → JWT tokens → Page App
  └─ Retour   → Page Login

Page App (authentifie)
  ├─ Sidebar  : "Welcome, {username}", bouton Logout, badge env
  ├─ Logout   → POST /auth/logout → reset session → Page Login
  └─ Info     → Page Info (environnement, version)
```

### Session state

| Variable | Type | Description |
|----------|------|-------------|
| `authenticated` | bool | Etat d'authentification |
| `page` | str | Page courante (login, signup, app, info) |
| `guest_mode` | bool | Mode invite |
| `access_token` | str/None | JWT access token (30 min) |
| `refresh_token` | str/None | JWT refresh token (7 jours) |
| `user_data` | dict/None | Infos utilisateur (`/users/me`) |

## Installation locale

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

## Lancement

```bash
# Mode developpement
streamlit run src/navigation.py

# Ou via Docker
docker build -t crypto-bot-frontend .
docker run -p 8501:8501 crypto-bot-frontend
```

## Variables d'environnement

| Variable | Description | Defaut |
|----------|-------------|--------|
| `API_URL` | URL du backend FastAPI | `http://localhost:8009` |
| `ENVIRONMENT` | Environnement (development/staging/production) | development |
| `APP_VERSION` | Version affichee dans l'UI | dev |

## CI/CD et workflow submodule

Ce repo dispose de son propre `.gitlab-ci.yml` qui execute le stage **lint** sur chaque MR et branche feature (flake8 + black).

### Synchronisation automatique avec le repo parent

Lorsqu'une MR est mergee dans `staging`, un job `sync:parent` met a jour automatiquement le pointeur de submodule dans la branche `staging` du repo `crypto-bot`. Le repo parent detecte alors le changement et declenche sa propre CI pour construire les images Docker et deployer.

### Mecanisme anti-boucle

Les commits de synchronisation sont prefixes avec `ci(...)` dans leur message. Le job `sync:parent` est configure pour ne pas se declencher sur ces commits, ce qui evite une boucle infinie entre les deux pipelines.

### Variable CI requise

La variable `GROUP_PAT_TOKEN` (definie au niveau du groupe `dst_crypto`) est necessaire pour que le job `sync:parent` puisse pousser le commit de mise a jour du submodule dans le repo parent.
