"""Job de backfill OHLCV : télécharge l'historique complet Binance → MinIO → PostgreSQL.

Gère la pagination automatique par chunks de 1 000 bougies (limite API Binance)
pour couvrir des plages de plusieurs années, de façon idempotente.

Chaque chunk est stocké sous une clé MinIO unique et upserted en base :
    raw/ohlcv/<SYMBOL>/<interval>/backfill/<YYYY-MM-DDTHHMMSS>.parquet

Usage CLI :
    # 2 ans d'historique par défaut
    python backfill_ohlcv.py --symbol BTCUSDC --interval 1h

    # Plage explicite
    python backfill_ohlcv.py --symbol BTCUSDC --interval 1h \\
        --start-date 2024-06-01 --end-date 2026-06-01

    # Simuler sans écriture (dry-run)
    python backfill_ohlcv.py --symbol BTCUSDC --interval 1h --dry-run

Variables d'environnement : identiques à collect_ohlcv.py et load_ohlcv.py
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import UTC, datetime, timedelta

import pandas as pd

# ---------------------------------------------------------------------------
# Chemin vers les autres jobs (ingest, transform)
# ---------------------------------------------------------------------------

_JOBS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _JOBS_ROOT not in sys.path:
    sys.path.insert(0, _JOBS_ROOT)

from ingest.collect_ohlcv import (  # noqa: E402
    MINIO_BUCKET,
    _ensure_bucket,
    _get_minio_client,
    fetch_klines,
    upload_dataframe_parquet,
)
from transform.load_ohlcv import run_loading  # noqa: E402

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("backfill.backfill_ohlcv")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Millisecondes par intervalle — sert à calculer les bornes de chunk
INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
}

BINANCE_KLINES_LIMIT = 1000  # maximum par appel API Binance
API_SLEEP_S = 0.25  # pause entre deux appels pour respecter les rate limits Binance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dt_to_ms(dt: datetime) -> int:
    """Convertit un datetime UTC en timestamp milliseconde."""
    return int(dt.timestamp() * 1000)


def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


# ---------------------------------------------------------------------------
# Logique principale
# ---------------------------------------------------------------------------


def run_backfill(
    symbol: str,
    interval: str,
    start_dt: datetime,
    end_dt: datetime,
    bucket: str = MINIO_BUCKET,
    dry_run: bool = False,
) -> dict:
    """Télécharge l'historique OHLCV complet sur la plage [start_dt, end_dt).

    Pagine automatiquement par chunks de 1 000 bougies.
    Chaque chunk est uploadé dans MinIO puis upserted dans PostgreSQL.
    L'opération est idempotente grâce à l'upsert sur la contrainte unique
    (symbol, exchange, interval_timeframe, open_time).

    Args:
        symbol:    Paire de trading (ex: BTCUSDC)
        interval:  Intervalle temporel (ex: 1h, 4h, 1d)
        start_dt:  Début de la plage, timezone-aware UTC
        end_dt:    Fin de la plage (exclusive), timezone-aware UTC
        bucket:    Bucket MinIO cible
        dry_run:   Si True, collecte les données sans écrire dans MinIO ni PostgreSQL

    Returns:
        Dict de statistiques :
            symbol, interval, start_date, end_date,
            total_rows, chunks_processed, chunks_failed, duration_s
    """
    if interval not in INTERVAL_MS:
        raise ValueError(f"Intervalle inconnu: {interval!r}. Valeurs supportées: {sorted(INTERVAL_MS)}")

    interval_ms = INTERVAL_MS[interval]
    chunk_ms = BINANCE_KLINES_LIMIT * interval_ms

    # Estimation du nombre de chunks pour les logs
    total_candles_expected = max(
        1,
        int((end_dt - start_dt).total_seconds() * 1000 / interval_ms),
    )
    total_chunks_est = (total_candles_expected + BINANCE_KLINES_LIMIT - 1) // BINANCE_KLINES_LIMIT

    logger.info(
        "backfill start  symbol=%s interval=%s  range=[%s → %s]  expected_candles~%s  chunks~%s  dry_run=%s",
        symbol.upper(),
        interval,
        start_dt.strftime("%Y-%m-%d"),
        end_dt.strftime("%Y-%m-%d"),
        total_candles_expected,
        total_chunks_est,
        dry_run,
    )

    minio_client = None
    if not dry_run:
        minio_client = _get_minio_client()
        _ensure_bucket(minio_client, bucket)

    stats: dict = {
        "symbol": symbol.upper(),
        "interval": interval,
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "total_rows": 0,
        "chunks_processed": 0,
        "chunks_failed": 0,
        "object_keys": [],
    }

    t0 = time.monotonic()
    chunk_start_ms = _dt_to_ms(start_dt)
    end_ms = _dt_to_ms(end_dt)
    chunk_idx = 0

    while chunk_start_ms < end_ms:
        chunk_end_ms = min(chunk_start_ms + chunk_ms, end_ms)
        chunk_idx += 1
        chunk_start_dt = _ms_to_dt(chunk_start_ms)

        logger.info(
            "chunk %s/%s  symbol=%s  from=%s",
            chunk_idx,
            total_chunks_est,
            symbol.upper(),
            chunk_start_dt.strftime("%Y-%m-%d %H:%M"),
        )

        # --- Fetch ---
        try:
            rows = fetch_klines(
                symbol=symbol,
                interval=interval,
                limit=BINANCE_KLINES_LIMIT,
                start_time_ms=chunk_start_ms,
                end_time_ms=chunk_end_ms - 1,  # endTime est inclusif côté Binance
            )
        except Exception as exc:
            logger.error("fetch failed  chunk=%s: %s", chunk_idx, exc)
            stats["chunks_failed"] += 1
            chunk_start_ms = chunk_end_ms
            time.sleep(API_SLEEP_S * 4)  # back-off plus long sur erreur
            continue

        if not rows:
            logger.warning("empty chunk=%s (pas de données pour cette fenêtre), skip", chunk_idx)
            chunk_start_ms = chunk_end_ms
            continue

        stats["total_rows"] += len(rows)

        # --- Upload MinIO + Load PostgreSQL ---
        if not dry_run:
            df = pd.DataFrame(rows)
            ts_label = chunk_start_dt.strftime("%Y-%m-%dT%H%M%S")
            object_key = f"raw/ohlcv/{symbol.upper()}/{interval}/backfill/{ts_label}.parquet"
            try:
                upload_dataframe_parquet(minio_client, df, object_key, bucket)
                run_loading(object_key=object_key, bucket=bucket)
                stats["object_keys"].append(object_key)
                stats["chunks_processed"] += 1
            except Exception as exc:
                logger.error("store/load failed  chunk=%s  key=%s: %s", chunk_idx, object_key, exc)
                stats["chunks_failed"] += 1
        else:
            stats["chunks_processed"] += 1

        # Avancer au prochain chunk à partir du open_time de la dernière bougie reçue
        last_open_ms = int(rows[-1]["open_time"].timestamp() * 1000)
        chunk_start_ms = last_open_ms + interval_ms

        time.sleep(API_SLEEP_S)

    stats["duration_s"] = round(time.monotonic() - t0, 1)
    logger.info(
        "backfill done  symbol=%s  rows=%s  chunks_ok=%s  chunks_fail=%s  duration=%ss",
        symbol.upper(),
        stats["total_rows"],
        stats["chunks_processed"],
        stats["chunks_failed"],
        stats["duration_s"],
    )
    return stats


# ---------------------------------------------------------------------------
# Point d'entrée CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill historique OHLCV depuis Binance → MinIO → PostgreSQL.\n"
            "Par défaut : 2 ans d'historique à partir d'aujourd'hui."
        )
    )
    parser.add_argument("--symbol", required=True, help="Paire ex: BTCUSDC, ETHUSDC")
    parser.add_argument("--interval", required=True, help="Intervalle ex: 1h, 4h, 1d")
    parser.add_argument(
        "--start-date",
        help="Date de début ISO (ex: 2024-06-01). Prioritaire sur --years.",
    )
    parser.add_argument(
        "--end-date",
        help="Date de fin ISO (ex: 2026-06-12). Défaut : heure courante tronquée.",
    )
    parser.add_argument(
        "--years",
        type=float,
        default=2.0,
        help="Nombre d'années d'historique à remonter (défaut: 2).",
    )
    parser.add_argument("--bucket", default=MINIO_BUCKET, help="Bucket MinIO cible.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collecte uniquement — pas d'écriture dans MinIO ni PostgreSQL.",
    )
    args = parser.parse_args()

    # Borne supérieure : heure courante tronquée à la minute 0
    end_dt = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    if args.end_date:
        end_dt = datetime.fromisoformat(args.end_date).replace(tzinfo=UTC)

    # Borne inférieure
    if args.start_date:
        start_dt = datetime.fromisoformat(args.start_date).replace(tzinfo=UTC)
    else:
        start_dt = end_dt - timedelta(days=365 * args.years)

    try:
        stats = run_backfill(
            symbol=args.symbol,
            interval=args.interval,
            start_dt=start_dt,
            end_dt=end_dt,
            bucket=args.bucket,
            dry_run=args.dry_run,
        )
        mode = "[DRY-RUN] " if args.dry_run else ""
        print(
            f"{mode}✓ Backfill terminé : "
            f"{stats['total_rows']:,} bougies — "
            f"{stats['chunks_processed']} chunks OK — "
            f"{stats['duration_s']}s"
        )
        if stats["chunks_failed"]:
            print(
                f"⚠  {stats['chunks_failed']} chunk(s) en échec. Relancez le job pour récupérer les données manquantes."
            )
            sys.exit(2)
    except Exception as exc:
        logger.error("backfill failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
