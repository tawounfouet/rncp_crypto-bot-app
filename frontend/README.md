# Frontend Streamlit - Crypto Bot Spot MVP

Statut: référence
Derniere revision: 2026-07-28

Frontend multipage premium en Streamlit, connecte au backend FastAPI reel (auth, marche, portefeuille, trading, strategies). Un mode mock (`mocks/`) reste disponible pour le developpement et les tests hors backend.

## 1. Prerequis
- Python 3.10+
- `pip`

## 2. Installation
Depuis la racine du repo:

```bash
cd frontend
python -m pip install -r requirements.txt
```

`pydantic>=2.8,<3.0` est une dependance normale (`requirements.txt`), installee sans contournement particulier. Un shim local (`src/pydantic/__init__.py`) existe encore dans le code pour l'execution hors-ligne ; comme `PYTHONPATH=/app/src` le place avant le vrai paquet installe, c'est lui qui est effectivement utilise en conteneur. À nettoyer si le vrai paquet couvre desormais tous les usages.

## 3. Lancer l'application
```bash
cd frontend
streamlit run src/app.py
```

## 4. Lancer les tests
```bash
cd frontend
pytest tests/unit -q
pytest tests/integration tests/smoke -q
pytest tests -q
```

## 5. Lint / Format
Si les outils sont disponibles:

```bash
cd frontend
ruff check src tests
black src tests
```

Si `ruff`/`black` ne sont pas installes dans votre environnement, installez-les via `requirements.txt` (ou via un environnement Python qui a acces aux packages requis).

## 6. Arborescence
```text
frontend/
  .streamlit/config.toml
  src/
    app.py
    pages/
      01_Marche.py
      02_Inscription.py
      03_Portefeuille_Spot.py
      04_Performances_Spot.py
      05_Controle_Bot_Spot.py
      06_Parametrage_Bot_Spot.py
      07_Gestion_de_compte.py
      08_Admin.py
    components/
    layouts/
    theme/
    services/
    mocks/
    navigation/
    prerequisites/
    schemas/
    state/
    utils/
  tests/
    unit/
    integration/
    smoke/
  MOCK_SCENARIOS.md
  requirements.txt
  pyproject.toml
```

## 7. Architecture services / mocks

- `pages/`: rendu et interactions Streamlit
- `services/`: logique metier, connectee au backend reel via `BackendApiClient`/`AuthApiClient` par defaut (voir en-tete de chaque fichier `services/*.py`, ex. `"connecte au backend reel"`)
- `mocks/`: `MockStore` + scenarios de donnees, utilises par les tests (`tests/unit`, `tests/integration`, `tests/smoke`) et disponibles en developpement local sans backend
- `schemas/`: models types (pydantic-compatible)
- `state/`: session globale
- `navigation/`: regles d'acces aux pages selon l'etat de connexion/role
- `prerequisites/`: verification des prerequis (ex. configuration d'un exchange) avant certaines pages

Scenarios mockes pilotables depuis la sidebar (voir `MOCK_SCENARIOS.md`) ; delais simules et erreurs forcees possibles via `services/base.py` (`simulate_latency`, `raise_if_forced_error`) — ces utilitaires ne s'appliquent qu'au chemin `MockStore`, pas aux appels reels au backend.

## 8. Pages implementees
1. Marche (`pages/01_Marche.py`, accessible connecte ou non)
2. Connexion (`src/app.py`)
3. Inscription
4. Portefeuille Spot
5. Performances Spot
6. Controle Bot Spot
7. Parametrage Bot Spot
8. Gestion de compte
9. Admin

## 9. UX/Design
- Theme dark premium par defaut.
- Tokens de couleur/spacing centralises.
- Composants reutilisables:
  - KPI cards
  - badges de statut
  - feedback success/warning/error/info
  - tableaux homogemes
- Etats loading/empty/error/success sur les ecrans critiques.

## 10. CI/CD

Le frontend fait partie du monorepo `Crypto-bot-app`. La CI est definie dans `.gitlab-ci.yml` a la racine.

Le lint Python (ruff check + ruff format) couvre backend et frontend dans un seul job `lint:python`.
