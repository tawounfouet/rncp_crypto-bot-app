# Frontend Streamlit - Crypto Bot Spot MVP (Mock-First)

Frontend multipage premium en Streamlit, totalement fonctionnel sur donnees mockees, sans dependance backend/FastAPI/Binance.

## 1. Prerequis
- Python 3.10+
- `pip`

## 2. Installation
Depuis la racine du repo:

```bash
cd frontend
python -m pip install -r requirements.txt
```

Note environnement courant:
- `pydantic` n'est pas resolvable sur l'index pip disponible localement.
- Un shim minimal compatible (`src/pydantic/__init__.py`) est inclus pour conserver une execution locale testable en mode offline.

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
    schemas/
    state/
    utils/
  tests/
    unit/
    integration/
    smoke/
  IMPLEMENTATION_PLAN.md
  PROGRESS.md
  MOCK_SCENARIOS.md
  requirements.txt
  pyproject.toml
```

## 7. Strategie Mock-First
- Separation nette:
  - `pages/`: rendu et interactions Streamlit
  - `services/`: logique metier mockee
  - `mocks/`: generation et scenario de donnees
  - `schemas/`: models types (pydantic-compatible)
  - `state/`: session globale
- Scenarios mockes pilotables depuis la sidebar.
- Delais simules et erreurs forcees possibles par service.
- Substitution backend future:
  - conserver les signatures de `services/*`
  - remplacer la logique interne par appels API sans casser les pages.

## 8. Pages implementees
1. Connexion (`src/app.py`)
2. Inscription
3. Portefeuille Spot
4. Performances Spot
5. Controle Bot Spot
6. Parametrage Bot Spot
7. Gestion de compte
8. Admin

## 9. UX/Design
- Theme dark premium par defaut.
- Tokens de couleur/spacing centralises.
- Composants reutilisables:
  - KPI cards
  - badges de statut
  - feedback success/warning/error/info
  - tableaux homogemes
- Etats loading/empty/error/success sur les ecrans critiques.
