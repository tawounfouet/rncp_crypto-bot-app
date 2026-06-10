# Spécification — Collecte paginée Binance

**Statut :** À implémenter — itération v1
**Priorité :** Bloquante
**Contexte :** [04-diagnostic-premiers-resultats.md](../analyse/04-diagnostic-premiers-resultats.md) — 1 000 lignes sont insuffisantes pour l'apprentissage ML.

---

## Problème

Le collecteur actuel (`src/data/binance.py`) effectue un appel unique à l'API Binance avec `limit=1000`, soit environ 41 jours d'historique en 1h. Cette quantité est insuffisante pour entraîner un modèle discriminant sur données financières.

Le module `src/data/collect.py` appelle directement `fetch_klines` sans pagination. Aucun paramètre de cible d'historique n'existe dans `config.yaml`.

---

## Objectif

Implémenter une collecte paginée vers l'arrière depuis Binance, permettant d'atteindre un volume cible configurable (default : 26 000 candles ≈ 3 ans en 1h), sans modifier les contrats de sortie existants.

---

## Contrat de la fonction principale

```python
def collect_klines_paginated(
    symbol: str,
    source_symbol: str,
    interval: str,
    target_rows: int,
    invert_price: bool = False,
    end_time: datetime | None = None,
) -> pd.DataFrame:
    """
    Collecte target_rows klines en paginant vers l'arrière depuis end_time.

    Args:
        symbol:        Symbole canonique MVP (ex: "BTCUSDT", "BTCETH").
        source_symbol: Symbole Binance réel (ex: "ETHBTC" pour BTCETH).
        interval:      Intervalle Binance (ex: "1h").
        target_rows:   Nombre de lignes cibles à collecter.
        invert_price:  Si True, inverse les prix OHLC après collecte.
        end_time:      Point de départ de la pagination (default: now UTC).

    Returns:
        DataFrame ordonné ascendant par open_time, colonnes identiques
        au contrat défini dans specs/03-contrats-donnees-api.md.

    Raises:
        BinanceAPIError:  Erreur HTTP non récupérable.
        DataQualityError: Dataset résultant vide après déduplication.
    """
```

---

## Algorithme de pagination

```text
cursor <- end_time (ou now UTC)
frames <- []

boucle:
    df_page <- fetch_klines(source_symbol, interval, end_time=cursor, limit=1000)
    si df_page est vide -> break
    frames.append(df_page)
    cursor <- df_page["open_time"].min() - 1ms
    si sum(rows) >= target_rows -> break

résultat <- concat(frames)
             .drop_duplicates("open_time")
             .sort_values("open_time")
             .tail(target_rows)   # conserver les target_rows les plus récentes
```

Chaque page est loggée :

```text
binance paginated page=1 cursor=2026-06-01 rows_fetched=1000 total=1000
binance paginated page=2 cursor=2025-06-01 rows_fetched=1000 total=2000
...
binance paginated complete symbol=BTCUSDT rows=26000 pages=26 duration_s=12.4
```

---

## Détection des gaps temporels

Après concat, calculer les écarts inter-bougies :

```python
expected_gap = interval_to_timedelta(interval)   # 1h -> timedelta(hours=1)
actual_gaps = df["open_time"].diff().dropna()
gaps = actual_gaps[actual_gaps > expected_gap * 2]
```

Si des gaps sont détectés :
- Logger un WARNING par gap : `gap detected start=... end=... missing_candles=N`
- Inclure le rapport de gaps dans le `quality_report` du meta.json
- Ne pas lever d'exception — la donnée reste utilisable avec des trous documentés

---

## Configuration

Ajouter dans `config.yaml` :

```yaml
data:
  collection:
    mode: paginated          # "single" | "paginated"
    target_rows: 26000       # cible en mode paginated
    page_size: 1000          # limite par appel Binance (max 1000)
    page_delay_ms: 100       # délai entre pages pour éviter rate limit
```

Ajouter dans `src/config/settings.py` :

```python
class CollectionSettings(BaseModel):
    mode: Literal["single", "paginated"] = "single"
    target_rows: int = 26000
    page_size: int = 1000
    page_delay_ms: int = 100
```

Rétrocompatibilité : le mode `single` conserve le comportement actuel (`limit=1000`, un seul appel). Aucune modification de l'interface CLI `collect`.

---

## Interface CLI

La commande `collect` doit résoudre `mode` depuis la config et dispatcher :

```python
if settings.data.collection.mode == "paginated":
    df = collect_klines_paginated(symbol=..., target_rows=settings.data.collection.target_rows)
else:
    df = collect_klines_single(symbol=..., limit=1000)   # comportement actuel
```

Aucun nouveau argument CLI requis — le mode est déclaratif dans la config.

---

## Contrats de sortie inchangés

La collecte paginée doit produire exactement les mêmes fichiers que la collecte actuelle :

```text
data/raw/{symbol}/{interval}.parquet
data/raw/{symbol}/{interval}.parquet.meta.json
data/raw/{symbol}/{interval}.csv
data/raw/{symbol}/{interval}.csv.meta.json
data/raw/{symbol}/{interval}.jsonl
data/raw/{symbol}/{interval}.jsonl.meta.json
reports/data_quality/{symbol}_{interval}.json
```

Le schéma des colonnes est identique à `specs/03-contrats-donnees-api.md`. Seul `row_count` augmente dans les meta.json.

Le rapport qualité doit inclure deux champs supplémentaires :

```json
{
  "collection_mode": "paginated",
  "pages_fetched": 26,
  "gaps_detected": 0,
  "gap_details": []
}
```

---

## Gestion du rate limiting Binance

L'API publique Binance (sans clé) est limitée à 1 200 requêtes/minute sur le endpoint `/api/v3/klines`.

Pour 26 pages avec `page_delay_ms=100` : 26 appels × 100ms = 2,6s de délai total. Largement en dessous du rate limit.

Si une réponse HTTP 429 est reçue :
- Attendre `Retry-After` secondes si présent dans l'en-tête
- Sinon attendre 60s et relancer
- Logger : `binance rate_limit hit page=N waiting_s=60`
- Maximum 3 tentatives par page, puis lever `BinanceAPIError`

---

## Tests à ajouter

### Test unitaire — pagination sans réseau

```python
def test_collect_klines_paginated_concatenates_pages(mock_fetch_klines):
    """Vérifie que N pages sont bien concaténées et triées."""
    mock_fetch_klines.side_effect = [make_klines(1000, start=T0 - 2000h),
                                     make_klines(1000, start=T0 - 1000h),
                                     make_klines(1000, start=T0)]
    df = collect_klines_paginated("BTCUSDT", "BTCUSDT", "1h", target_rows=2500)
    assert len(df) == 2500
    assert df["open_time"].is_monotonic_increasing
```

### Test unitaire — détection de gaps

```python
def test_gap_detection_reports_missing_candles(make_df_with_gap):
    """Un gap de 3h dans un dataset 1h doit produire un warning."""
    report = validate_klines(make_df_with_gap(gap_hours=3), interval="1h")
    assert len(report["gap_details"]) == 1
    assert report["gap_details"][0]["missing_candles"] == 2
```

### Test intégration locale

```python
def test_collect_paginated_writes_meta_json(tmp_path, mock_binance):
    """Le meta.json doit contenir collection_mode=paginated et pages_fetched."""
    collect_symbol("BTCUSDT", "1h", output_dir=tmp_path, mode="paginated", target_rows=2000)
    meta = json.loads((tmp_path / "BTCUSDT/1h.parquet.meta.json").read_text())
    assert meta["collection_mode"] == "paginated"
    assert meta["pages_fetched"] >= 2
```

---

## Makefile

```makefile
collect:
    $(PYTHON) -m src.main --config config.yaml collect \
        --symbols BTCUSDT BTCETH --interval 1h

collect-dry:
    $(PYTHON) -m src.main --config config.yaml collect \
        --symbols BTCUSDT --interval 1h --dry-run
```

Le flag `--dry-run` (optionnel) logue combien de pages seraient nécessaires sans écrire de fichiers.

---

## Définition of Done

- [ ] `config.yaml` contient `data.collection.mode` et `data.collection.target_rows`
- [ ] `src/data/binance.py` expose `fetch_klines_paginated`
- [ ] `src/data/collect.py` dispatche sur le mode configuré
- [ ] Tests unitaires pagination et gaps passants
- [ ] `make collect` produit ≥ 26 000 lignes par symbole en mode `paginated`
- [ ] `data/raw/BTCUSDT/1h.parquet.meta.json` contient `pages_fetched` et `gaps_detected`
- [ ] Aucune régression sur les tests existants en mode `single`
