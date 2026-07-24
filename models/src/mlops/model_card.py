"""Model card generation."""

from __future__ import annotations

from pathlib import Path

from src.utils.logger import get_logger


logger = get_logger(__name__)


def write_model_card(
    output_dir: str | Path,
    model_name: str,
    run_id: str,
    metrics: dict,
    dataset_summary: dict | None = None,
) -> Path:
    """Write a concise MVP model card."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary = dataset_summary or {}
    lines = [
        f"# Model Card — {model_name}",
        "",
        f"- Run ID: `{run_id}`",
        "- Intended use: MVP technical trading signal, not financial advice.",
        "- Output: `BUY`, `SELL`, `HOLD`.",
        "",
        "## Metrics",
        "",
    ]
    for key, value in metrics.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Dataset", ""])
    for key, value in summary.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "- No real order execution.",
            "- No guarantee of profit.",
            "- Signal quality depends on data freshness and class distribution.",
        ]
    )
    path = destination / "model_card.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("model card written model=%s run_id=%s path=%s", model_name, run_id, path)
    return path
