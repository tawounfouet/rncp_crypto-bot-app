# IMPLEMENTATION PLAN - Frontend Streamlit Crypto Bot MVP

## 1) Objectif
Construire un frontend Streamlit multipage premium, autonome et testable avec une couche de mocks complète, sans dépendance backend/FastAPI/Binance.

## 2) Arborescence cible
```text
frontend/
  .streamlit/
    config.toml
  assets/
  src/
    app.py
    pages/
      01_Connexion.py
      02_Inscription.py
      03_Portefeuille_Spot.py
      04_Performances_Spot.py
      05_Controle_Bot_Spot.py
      06_Parametrage_Bot_Spot.py
      07_Gestion_de_compte.py
      08_Admin.py
    components/
      alerts.py
      badges.py
      cards.py
      headers.py
      navigation.py
      tables.py
    layouts/
      page_shell.py
    theme/
      tokens.py
      styles.py
    services/
      base.py
      auth_service.py
      portfolio_service.py
      performance_service.py
      bot_control_service.py
      bot_config_service.py
      account_service.py
      admin_service.py
    mocks/
      scenarios.py
      db.py
      factories.py
    schemas/
      common.py
      auth.py
      portfolio.py
      performance.py
      bot.py
      account.py
      admin.py
    state/
      session.py
    utils/
      constants.py
      formatters.py
      validators.py
      guards.py
      selectors.py
  tests/
    unit/
    integration/
    smoke/
  README.md
  PROGRESS.md
  requirements.txt
  pyproject.toml
```

## 3) Conventions
- Langue UI: francais.
- Separation stricte: `pages` (rendu) / `services` (logique) / `mocks` (data) / `schemas` (typing).
- Donnees mockees strictement typees avec `pydantic`.
- Session state centralise dans `state/session.py`.
- Composants visuels reutilisables dans `components/`.
- Helpers de formatage/validation dans `utils/`.
- Code style: `black`, `ruff`, typage raisonnable.

## 4) Dependances
- Runtime: `streamlit`, `plotly`, `pandas`, `pydantic`.
- Qualite: `pytest`, `streamlit.testing.v1`, `ruff`, `black`, `mypy` (optionnel strict modere).

## 5) Pages a implementer
1. Connexion
2. Inscription
3. Portefeuille Spot
4. Performances Spot
5. Controle Bot Spot
6. Parametrage Bot Spot
7. Gestion de compte
8. Admin

## 6) Design system interne
- Tokens: couleur, spacing, radius, ombres.
- Theme dark elegant par defaut.
- Composants: KPI cards, badges statuts, alertes feedback, headers de section, tableaux coherents.
- Formatters: devise, pourcentages, datetime, masquage secrets.

## 7) Couche mock
- Scenarios requis:
  - utilisateur normal
  - admin
  - Binance non configure
  - portefeuille vide
  - portefeuille riche
  - bot en erreur
  - bot en execution
  - performances fortes
  - performances degradees
- Latence simulee configurable.
- Erreurs simulees controlables.
- Services decouples pour remplacer les mocks par API plus tard.

## 8) Strategie de tests incrementale
- Unitaires (prioritaires): utils, validators, services, transitions et validations critiques.
- Integration: enchainements fonctionnels mockes (auth -> actions bot -> update config).
- Smoke UI: rendu minimal des pages principales avec `streamlit.testing.v1` si environnement compatible.
- Regle d'execution: tests lances apres chaque bloc majeur, corrections immediates.

## 9) Milestones
1. Scaffold + tooling + plan
2. Fondations (theme + schemas + mocks + services + state + tests unitaires de base)
3. Pages Connexion/Inscription + tests
4. Pages Portefeuille/Performances + tests
5. Pages Controle/Parametrage bot + tests
6. Pages Compte/Admin + tests
7. Documentation finale + suite complete tests/lint/format

## 10) Checklist d'acceptation
- [x] Toutes les pages du perimetre existent et sont branchees
- [x] Navigation fluide et coherence UX
- [x] Design premium homogene (dark elegant, lisibilite forte)
- [x] Donnees mockees realistes + scenarios requis
- [x] Etats loading/empty/error/success pris en charge
- [x] Actions mockees explicites (pas de faux boutons)
- [x] Tests unitaires/integration/smoke pertinents
- [x] Tests au vert
- [x] README frontend complet
- [x] PROGRESS a jour
