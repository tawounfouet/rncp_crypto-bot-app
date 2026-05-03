# PROGRESS - Frontend Streamlit Crypto Bot MVP

## 2026-04-01 - Milestone 1 (en cours)

### Fait
- Audit du workspace: depot vide au niveau `crypto-bot-app`.
- Verification pre-requis: `streamlit`, `pandas`, `plotly`, `pytest` disponibles.
- Detection manquants: `pydantic`, `ruff`, `black`, `mypy` non installes dans l'environnement actuel.
- Creation de l'arborescence frontend de base.
- Redaction de `IMPLEMENTATION_PLAN.md`.

### Fichiers crees/modifies
- `frontend/IMPLEMENTATION_PLAN.md`
- `frontend/PROGRESS.md`
- Structure de dossiers `frontend/*`

### Tests
- Aucun test lance a ce stade (scaffold initial uniquement).

## 2026-04-01 - Milestone 2 (termine) - Fondations

### Fait
- Ajout du socle technique:
  - `pyproject.toml`, `requirements.txt`, `.streamlit/config.toml`
  - schemas types (`schemas/*`)
  - couche mocks (`mocks/scenarios.py`, `mocks/db.py`, `mocks/factories.py`)
  - services metier mockes (`services/*`)
  - state session (`state/session.py`)
  - utilitaires (`utils/*`)
  - shim local `src/pydantic/__init__.py` pour execution offline (absence package `pydantic` dans l'environnement actif).
- Ajout des tests unitaires de base (validators, formatters, selectors, services).

### Tests
- Commande:
  - `pytest tests/unit -q`
- Resultat:
  - `32 passed`

## 2026-04-01 - Milestone 3 a 6 (termine) - Pages et UX complete

### Fait
- Creation des composants UI partagees:
  - `components/alerts.py`
  - `components/badges.py`
  - `components/cards.py`
  - `components/headers.py`
  - `components/navigation.py`
  - `components/tables.py`
  - `theme/tokens.py`
  - `theme/styles.py`
  - `layouts/page_shell.py`
- Implementation des pages du perimetre:
  - `src/app.py` (Connexion)
  - `src/pages/02_Inscription.py`
  - `src/pages/03_Portefeuille_Spot.py`
  - `src/pages/04_Performances_Spot.py`
  - `src/pages/05_Controle_Bot_Spot.py`
  - `src/pages/06_Parametrage_Bot_Spot.py`
  - `src/pages/07_Gestion_de_compte.py`
  - `src/pages/08_Admin.py`
- Ajout des tests integration/smoke:
  - `tests/integration/test_mock_user_journey.py`
  - `tests/smoke/test_pages_smoke.py`
- Ajustements de robustesse:
  - liens de navigation `st.page_link` securises en fallback test
  - fallback Plotly dans pages graphes si module indisponible dans l'interpreteur courant
  - correction BOM config/test.

### Tests
- Commandes:
  - `pytest tests/integration tests/smoke -q`
- Resultats:
  - `9 passed` (1 integration + 8 smoke)

## 2026-04-01 - Milestone 7 (termine) - Finalisation et validation globale

### Fait
- Documentation finale ajoutee:
  - `frontend/README.md`
  - `frontend/MOCK_SCENARIOS.md`
- Verification lancement app:
  - process Streamlit demarre avec `streamlit run src/app.py --server.headless true --server.port 8510` (job en etat `Running`, puis arret manuel).
- Suite complete tests executee et verte.
- Tentatives lint/format executees et journalisees.

### Tests / Commandes finales
- `pytest tests -q` -> `41 passed`
- `streamlit run src/app.py --server.headless true --server.port 8510` -> app lancee (verification process).
- `ruff check src tests` -> echec: outil absent dans environnement.
- `black --check src tests` -> echec: outil absent dans environnement.
- `mypy src` -> echec: outil absent dans environnement.
- `python -m pip install ruff black mypy` -> echec (index package indisponible dans ce contexte).

### Points d'attention environnement
- Warnings `PytestCacheWarning` et cleanup `PermissionError` sur dossiers temporaires Windows hors projet.
- Warnings deprecation `datetime.utcnow()` non bloquants pour les tests; migration `datetime.now(UTC)` possible ensuite.

## 2026-04-01 - Refactor navigation/guards (termine)

### Fait
- Centralisation des regles de navigation/acces dans `src/navigation/rules.py`.
- Sidebar branchee sur ces regles via `components/navigation.py` (public, user, admin).
- Guard d'acces page centralise dans `layouts/page_shell.py` avec `page_key` par page.
- Desactivation de la navigation Streamlit automatique pour supprimer le double menu:
  - `.streamlit/config.toml` -> `showSidebarNavigation = false`.
- Bouton de session harmonise en `Deconnexion` pour utilisateur connecte.

### Tests ajoutes/mis a jour
- `tests/unit/test_navigation_rules.py`
- `tests/unit/test_streamlit_config.py`
- `tests/smoke/test_pages_smoke.py` (cas anonym/user/admin + blocage admin direct + rendu header unique)

### Tests executes incrementalement
- `pytest tests/unit/test_navigation_rules.py -q` -> 5 passed
- `pytest tests/unit/test_navigation_rules.py tests/smoke/test_pages_smoke.py -q` -> 18 passed
- `pytest tests/unit/test_streamlit_config.py tests/smoke/test_pages_smoke.py::test_navigation_header_rendered_once -q` -> 2 passed

## 2026-04-01 - Prerequis Binance centralise (termine)

### Fait
- Ajout d'une abstraction centralisee de prerequis Binance:
  - `src/prerequisites/binance.py` (policy par page, modes `block/disable/read-only`, copie centralisee).
- Ajout d'un composant unique de rendu prerequis + CTA:
  - `src/components/prerequisites.py`
  - CTA unique: `Configurer mes cles Binance` vers `Gestion de compte`.
- Application de la logique centralisee sur pages concernees:
  - `03_Portefeuille_Spot.py`: blocage contenu metier tant que Binance non configure.
  - `04_Performances_Spot.py`: blocage contenu metier tant que Binance non configure.
  - `05_Controle_Bot_Spot.py`: actions Start/Pause/Stop desactivees tant que Binance non configure.
  - `06_Parametrage_Bot_Spot.py`: mode lecture seule (widgets/formulaires desactives) tant que Binance non configure.
- Ajustements produits:
  - `07_Gestion_de_compte.py`: priorisation explicite de la configuration Binance si non configure.
  - `services/auth_service.py`: message inscription succes -> prochaine etape Binance.
  - `08_Admin.py` + `schemas/admin.py` + `services/admin_service.py`: indicateur `Binance configure` (Oui/Non) visible dans la liste.

### Tests ajoutes/mis a jour
- Unitaires:
  - `tests/unit/test_binance_prerequisite.py`
  - `tests/unit/test_auth_service.py` (message inscription)
  - `tests/unit/test_admin_service.py` (presence flag Binance)
- Smoke:
  - `tests/smoke/test_pages_smoke.py`
    - portefeuille/performance en prerequis
    - controle bot actions desactivees
    - parametrage bot lecture seule
    - CTA coherent present
    - compte priorise si Binance non configure
    - admin colonne Binance Oui/Non

### Tests executes incrementalement
- `pytest tests/unit/test_binance_prerequisite.py -q` -> 7 passed
- `pytest tests/unit/test_binance_prerequisite.py tests/smoke/test_pages_smoke.py -q` -> 25 passed
- `pytest tests/unit/test_auth_service.py tests/unit/test_admin_service.py tests/smoke/test_pages_smoke.py -q` -> 26 passed

## 2026-04-01 - Ajustements UX Binance ciblés (termine)

### Fait
- `Controle Bot Spot`:
  - si Binance non configure, la page affiche uniquement la liste des bots disponibles.
  - suppression des statuts/indices d'execution et des actions Start/Pause/Stop dans ce mode.
- `Parametrage Bot Spot`:
  - si Binance non configure, suppression des metadonnees actives (bot selectionne, statut, version, date modif) et du formulaire.
  - affichage limite a l'etat prerequis + liste des bots disponibles.
- `Gestion de compte`:
  - correction de preservation des credentials Binance lors d'un changement d'email profil (migration maps `binance_credentials` et `credential_updated_at`).
  - evite la re-apparition erronee de la priorite Binance apres update profil si Binance est deja configure.

### Tests ajoutes/mis a jour
- `tests/smoke/test_pages_smoke.py`
  - `test_bot_control_shows_only_bot_list_when_binance_not_configured`
  - `test_bot_config_hides_runtime_metadata_when_binance_not_configured`
  - `test_account_page_does_not_show_priority_banner_after_profile_update_with_configured_binance`
- `tests/unit/test_account_service.py`
  - `test_update_profile_preserves_binance_configuration_when_email_changes`

### Tests executes incrementalement
- `pytest tests/smoke/test_pages_smoke.py::test_bot_control_shows_only_bot_list_when_binance_not_configured -q` -> 1 passed
- `pytest tests/smoke/test_pages_smoke.py::test_bot_config_hides_runtime_metadata_when_binance_not_configured -q` -> 1 passed
- `pytest tests/unit/test_account_service.py tests/smoke/test_pages_smoke.py::test_account_page_does_not_show_priority_banner_after_profile_update_with_configured_binance tests/smoke/test_pages_smoke.py::test_account_prioritizes_binance_setup_when_not_configured -q` -> 6 passed

## 2026-04-01 - Durcissement serialisation UI (termine)

### Fait
- Correction centralisee du shim `BaseModel` (`src/pydantic/__init__.py`):
  - exclusion des champs techniques (`__...__`) et `ClassVar` des champs serialisables.
  - conservation de `__field_validators__` sur la classe pour les validateurs internes.
- Ajout d'une couche centralisee de sanitization pour les donnees UI/DataFrame dans `src/utils/selectors.py`:
  - `sanitize_record`, `sanitize_records`, `strip_technical_columns`, `models_to_dataframe`.
  - filtrage systematique de `__field_validators__` avant transformation `pandas.DataFrame`.
- Branchage des pages vers la couche centralisee:
  - `src/pages/03_Portefeuille_Spot.py`
  - `src/pages/04_Performances_Spot.py`
  - `src/pages/08_Admin.py`
- Durcissement du composant de table `src/components/tables.py`:
  - suppression defensive des colonnes techniques juste avant `st.dataframe`.

### Tests ajoutes/mis a jour
- Ajoutes:
  - `tests/unit/test_pydantic_shim.py`
  - `tests/unit/test_tables.py`
- Mis a jour:
  - `tests/unit/test_selectors.py`
  - `tests/smoke/test_pages_smoke.py`

### Tests executes incrementalement
- `pytest tests/unit/test_pydantic_shim.py tests/unit/test_auth_service.py -q` -> 6 passed
- `pytest tests/unit/test_selectors.py tests/unit/test_tables.py tests/smoke/test_pages_smoke.py::test_table_dataframes_do_not_expose_internal_technical_metadata -q` -> 11 passed

## 2026-04-01 - Theming clair/sombre centralise (termine)

### Choix de persistance
- Persistance via `MockStore` en session (`ui_theme_mode`), car l'architecture existante centralise deja l'etat frontend dans `app_store`.
- Pas de changement backend necessaire, propagation automatique entre pages via `setup_page` + sidebar globale.

### Fait
- Ajout d'un moteur de theme centralise:
  - `src/theme/manager.py` pour normalisation/routage `dark|light`.
  - `src/theme/tokens.py` refactorise en palettes semantiques `dark` et `light`.
  - `src/theme/styles.py` refactorise pour generer un CSS global selon le mode actif (surfaces, textes, cartes, bordures, badges, formulaires, sidebar, dataframe).
- Branchage du theme actif dans le shell global:
  - `src/layouts/page_shell.py` applique le CSS du mode courant sur toutes les pages.
- Ajout d'un switch global en sidebar publique/privee:
  - `src/components/navigation.py` avec `st.toggle("Mode clair")` + rerun.
  - `src/state/session.py` expose `get_theme_mode()` / `set_theme_mode()`.
  - `src/mocks/db.py` ajoute `ui_theme_mode` persiste en session.
- Adaptation des graphes au theme actif:
  - `src/theme/plotly.py` (template, couleurs, layout).
  - `src/pages/03_Portefeuille_Spot.py` et `src/pages/04_Performances_Spot.py` bascules sur helpers centraux.
- Theme sombre conserve par defaut:
  - `.streamlit/config.toml` reste `base = "dark"`.

### Tests ajoutes/mis a jour
- Ajoutes:
  - `tests/unit/test_theme_manager.py`
  - `tests/unit/test_theme_styles.py`
  - `tests/unit/test_page_shell_theme.py`
  - `tests/unit/test_theme_plotly.py`
- Mis a jour:
  - `tests/smoke/test_pages_smoke.py` (switch visible, persistance cross-page, rendu des 8 pages en mode clair)
  - `tests/unit/test_streamlit_config.py` (validation theme dark par defaut)

### Tests executes incrementalement
- `pytest tests/unit/test_theme_manager.py tests/unit/test_theme_styles.py -q` -> 5 passed
- `pytest tests/unit/test_theme_manager.py tests/unit/test_page_shell_theme.py tests/smoke/test_pages_smoke.py::test_theme_switch_visible_in_sidebar tests/smoke/test_pages_smoke.py::test_theme_switch_persists_store_mode_across_pages -q` -> 8 passed
- `pytest tests/unit/test_theme_plotly.py tests/unit/test_streamlit_config.py tests/smoke/test_pages_smoke.py::test_pages_render_in_light_theme -q` -> 14 passed

## 2026-04-01 - Theming dual-mode: propagation exhaustive (termine)

### Diagnostic/cause
- La sidebar restait sombre car la surcharge CSS ciblait principalement `div[data-testid=\"stSidebar\"]` alors que Streamlit applique le fond sur `section[data-testid=\"stSidebar\"]` et son conteneur interne.
- Plusieurs widgets conservaient des styles dark (inputs, boutons, labels, dataframe, liens sidebar) car le CSS global ne couvrait pas suffisamment les selecteurs natifs Streamlit.
- Plotly etait seulement partiellement thematise (template/ligne/grille), avec des incoherences residuelles sur axes/hover/legendes.

### Fait
- Renforcement centralise de la couche theme:
  - `src/theme/tokens.py`: ajout de tokens semantiques pour sidebar, boutons, placeholders, alerts et color-scheme natif.
  - `src/theme/styles.py`: surcharge robuste des zones Streamlit critiques (sidebar section+conteneur, nav links, widgets, boutons, alerts, dataframe/glide vars, labels/captions/placeholder, cards).
- Renforcement centralise Plotly:
  - `src/theme/plotly.py`: helpers pour axes, hoverlabels, line/grid/axis styling et legende.
  - `src/pages/04_Performances_Spot.py`: branchement via `themed_axis(...)`.
- Ajout de gardes anti-regression:
  - contraste minimal texte/fond par theme
  - interdiction de couleurs hardcodees dans `src/pages`, `src/components`, `src/layouts`
  - interdiction d'usage direct de templates Plotly hors couche theme
  - smoke explicite de rendu de toutes les pages en dark + light

### Tests ajoutes/mis a jour
- Ajoutes:
  - `tests/unit/test_theme_contrast.py`
  - `tests/unit/test_theme_hardcoded_audit.py`
- Mis a jour:
  - `tests/unit/test_theme_styles.py`
  - `tests/unit/test_theme_plotly.py`
  - `tests/smoke/test_pages_smoke.py` (rendu explicite en dark)

### Tests executes incrementalement
- `pytest tests/unit/test_theme_styles.py tests/unit/test_theme_manager.py tests/smoke/test_pages_smoke.py::test_theme_switch_visible_in_sidebar -q` -> 7 passed
- `pytest tests/unit/test_theme_plotly.py tests/smoke/test_pages_smoke.py::test_pages_render_in_light_theme tests/smoke/test_pages_smoke.py::test_protected_pages_render_with_user_session -q` -> 18 passed
- `pytest tests/unit/test_theme_contrast.py tests/unit/test_theme_hardcoded_audit.py tests/smoke/test_pages_smoke.py::test_pages_render_in_light_theme tests/smoke/test_pages_smoke.py::test_pages_render_in_dark_theme tests/smoke/test_pages_smoke.py::test_theme_switch_persists_store_mode_across_pages -q` -> 23 passed

## 2026-04-01 - Finition visuelle light mode (termine)

### Fait
- Reequilibrage premium du theme clair au niveau central:
  - `src/theme/tokens.py`: surfaces plus nettes, contrastes texte renforces, sidebar/navigations/controls retouches.
  - `src/theme/styles.py`: couverture CSS etendue pour sidebar, header Streamlit, metrics, stepper number inputs, boutons de formulaire, placeholders et alertes.
- Correction exhaustive des tableaux en mode clair:
  - `src/components/tables.py`: rendu centralise en table HTML thematisee en light (suppression du rendu dark residuel), conservation `st.dataframe` en dark.
  - styles centralises `.theme-table*` dans `src/theme/styles.py`.
- Finition graphes light/dark:
  - `src/theme/plotly.py`: ajout `themed_rangeslider`, fonds coherents selon mode, hover/axes harmonises.
  - `src/pages/04_Performances_Spot.py`: branchement complet axes + rangeslider thematiques.

### Tests ajoutes/mis a jour
- Mis a jour:
  - `tests/unit/test_theme_styles.py`
  - `tests/unit/test_tables.py`
  - `tests/unit/test_theme_plotly.py`
  - `tests/smoke/test_pages_smoke.py`
- Ajoutes precedemment et consolides dans cette passe:
  - `tests/unit/test_theme_contrast.py`
  - `tests/unit/test_theme_hardcoded_audit.py`

### Tests executes incrementalement
- `pytest tests/unit/test_theme_styles.py tests/unit/test_theme_contrast.py tests/unit/test_theme_manager.py tests/smoke/test_pages_smoke.py::test_theme_switch_visible_in_sidebar -q` -> 11 passed
- `pytest tests/unit/test_tables.py tests/unit/test_theme_styles.py tests/smoke/test_pages_smoke.py::test_pages_render_in_light_theme tests/smoke/test_pages_smoke.py::test_pages_render_in_dark_theme tests/smoke/test_pages_smoke.py::test_table_dataframes_do_not_expose_internal_technical_metadata -q` -> 24 passed
- `pytest tests/unit/test_theme_plotly.py tests/unit/test_theme_hardcoded_audit.py tests/smoke/test_pages_smoke.py::test_pages_render_in_light_theme tests/smoke/test_pages_smoke.py::test_pages_render_in_dark_theme tests/smoke/test_pages_smoke.py::test_light_theme_tables_use_custom_light_table_renderer tests/smoke/test_pages_smoke.py::test_theme_switch_persists_store_mode_across_pages -q` -> 30 passed

## 2026-04-01 - Fix dropdown selects portal/virtualized (termine)

### Fait
- Completion du theming des selects au-dela du conteneur `div[data-baseweb=\"select\"]`:
  - ajout de tokens dedies dropdown (fond, texte, hover, selected, bordure, ombre) dans `src/theme/tokens.py`.
  - ajout de styles centralises pour menu portal/virtualized dans `src/theme/styles.py`:
    - `div[data-baseweb=\"popover\"]`
    - `[data-testid=\"stSelectboxVirtualDropdown\"]`
    - `role=\"listbox\"`
    - `role=\"option\"` + etat `aria-selected=\"true\"`
  - conservation et durcissement du style existant du conteneur select.
- Verification smoke des pages utilisant des select widgets en `light` et `dark`.

### Tests ajoutes/mis a jour
- Mis a jour:
  - `tests/unit/test_theme_styles.py`
  - `tests/smoke/test_pages_smoke.py`

### Tests executes incrementalement
- `pytest tests/unit/test_theme_styles.py tests/unit/test_theme_manager.py tests/unit/test_theme_hardcoded_audit.py -q` -> 10 passed
- `pytest tests/smoke/test_pages_smoke.py::test_select_pages_render_select_widgets_in_both_themes tests/smoke/test_pages_smoke.py::test_theme_switch_persists_store_mode_across_pages tests/unit/test_theme_styles.py -q` -> 13 passed

## 2026-04-01 - Suppression warning pytest cache (termine)

### Diagnostic
- Warning reproduit:
  - `PytestCacheWarning: could not create cache path ... .pytest_cache\\v\\cache\\nodeids: [WinError 267] Nom de répertoire non valide: '...\\pytest-cache-files-...\\.gitignore'`
- Origine:
  - couche interne `pytest` (`_pytest/cacheprovider.py`) pendant l'initialisation du cache sur ce workspace Windows.
  - creation/cleanup de dossiers temporaires `pytest-cache-files-*` dans le dossier projet, causant l'echec de creation `.pytest_cache`.

### Correction appliquee
- Configuration pytest centralisee pour utiliser un cache dans `%TEMP%` (filesystem stable dans cet environnement):
  - `pyproject.toml` -> `[tool.pytest.ini_options] cache_dir = "%TEMP%/crypto-bot-app-pytest-cache"`
- Pas de filtre global de warning.
- Pas de masquage aveugle: correction par redirection propre du cache vers un emplacement fiable.

### Tests ajoutes/mis a jour
- `tests/unit/test_streamlit_config.py`
  - ajout de `test_pytest_cache_dir_is_configured_to_temp_path`

### Tests executes incrementalement
- `pytest tests/unit/test_streamlit_config.py -q` -> 3 passed

## 2026-04-02 - Documentation complete architecture et migration (termine)

### Fait
- Audit structurel complet du workspace et du frontend:
  - verification des repos presents
  - cartographie des couches UI/services/mocks/state/theme/navigation/tests
  - identification explicite de l'absence du repo `crypto-bot-models` dans le workspace.
- Creation d'un corpus documentaire complet dans `docs/`:
  - `PROJECT_OVERVIEW.md`
  - `FOLDER_AND_FILE_GUIDE.md`
  - `EXTERNAL_HANDOFF_GUIDE.md`
  - `FRONTEND_RUNTIME_FLOW.md`
  - `MOCKED_TO_REAL_GAP_ANALYSIS.md`
  - `REAL_BACKEND_AND_MODELS_INTEGRATION_PLAN.md`
  - `API_CONTRACTS_NEEDED.md`
  - `MODELS_REPO_EXPECTED_INTERFACES.md`
  - `MIGRATION_CHECKLIST.md`
  - `ARCHITECTURE_DIAGRAMS.md`
- Separation explicite dans les livrables entre:
  - faits observes dans le code
  - hypotheses/assumptions
  - propositions d'architecture et de migration.

### Tests
- Aucun test code execute pour cette passe, car modifications limitees a la documentation.
