"""Typed project settings loaded from root ``config.yaml``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectSettings(BaseModel):
    name: str
    version: str
    description: str
    timezone: str = "UTC"
    random_state: int = 42


class DataPaths(BaseModel):
    raw: Path
    processed: Path
    reports: Path
    artifacts: Path


class DataFormats(BaseModel):
    raw_primary: Literal["parquet", "csv", "jsonl"] = "parquet"
    raw_exports: list[Literal["parquet", "csv", "jsonl"]] = Field(default_factory=lambda: ["csv", "jsonl"])
    processed_primary: Literal["parquet", "csv", "jsonl"] = "parquet"
    processed_exports: list[Literal["parquet", "csv", "jsonl"]] = Field(default_factory=lambda: ["csv", "jsonl"])
    sample_export: Literal["json", "jsonl"] = "json"


class CollectionSettings(BaseModel):
    mode: Literal["single", "paginated"] = "single"
    target_rows: int = 26000
    page_size: int = 1000
    page_delay_ms: int = 100


class DataQualitySettings(BaseModel):
    min_valid_candle_ratio: float = Field(ge=0, le=1)
    allow_missing_candles: bool = False
    drop_duplicates: bool = True
    enforce_ohlc_consistency: bool = True


class DataHistorySettings(BaseModel):
    start: str
    end: str | None = None


class SymbolMappingSettings(BaseModel):
    source_symbol: str
    invert_price: bool = False

    @field_validator("source_symbol")
    @classmethod
    def uppercase_source_symbol(cls, value: str) -> str:
        return value.upper()


class DataSettings(BaseModel):
    symbols: list[str]
    symbol_mappings: dict[str, SymbolMappingSettings] = Field(default_factory=dict)
    primary_interval: str
    intervals: list[str]
    history: DataHistorySettings
    paths: DataPaths
    formats: DataFormats
    quality: DataQualitySettings
    collection: CollectionSettings = Field(default_factory=CollectionSettings)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("data.symbols cannot be empty")
        return [symbol.upper() for symbol in value]

    @field_validator("symbol_mappings")
    @classmethod
    def validate_symbol_mappings(
        cls,
        value: dict[str, SymbolMappingSettings],
    ) -> dict[str, SymbolMappingSettings]:
        return {symbol.upper(): mapping for symbol, mapping in value.items()}

    @model_validator(mode="after")
    def validate_primary_interval(self) -> "DataSettings":
        if self.primary_interval not in self.intervals:
            raise ValueError("data.primary_interval must be listed in data.intervals")
        return self


class TechnicalIndicatorsSettings(BaseModel):
    returns: dict
    volatility: dict
    sma: dict
    ema: dict
    rsi: dict
    macd: dict
    bollinger_bands: dict
    volume_sma: dict
    order_flow: dict = Field(default_factory=lambda: {"enabled": False})


class MissingValuesSettings(BaseModel):
    drop_initial_rolling_rows: bool = True
    fill_method: Literal["ffill", "bfill", "none"] = "ffill"


class FeaturesSettings(BaseModel):
    price_columns: list[str]
    volume_column: str
    technical_indicators: TechnicalIndicatorsSettings
    missing_values: MissingValuesSettings


class LabelClasses(BaseModel):
    sell: int
    hold: int
    buy: int


class LabelSettings(BaseModel):
    classes: LabelClasses
    horizon: int = Field(ge=1)
    threshold_mode: Literal["fixed", "volatility"] = "fixed"
    fixed_threshold: float = Field(ge=0)
    volatility_window: int = Field(ge=1)
    volatility_multiplier: float = Field(ge=0)


class SplitSettings(BaseModel):
    method: Literal["temporal"] = "temporal"
    train_ratio: float = Field(gt=0, lt=1)
    validation_ratio: float = Field(gt=0, lt=1)
    test_ratio: float = Field(gt=0, lt=1)
    shuffle: bool = False

    @model_validator(mode="after")
    def validate_ratios(self) -> "SplitSettings":
        total = self.train_ratio + self.validation_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-9:
            raise ValueError("split ratios must sum to 1.0")
        if self.shuffle:
            raise ValueError("MVP split must remain temporal: shuffle=false")
        return self


class PreprocessingSettings(BaseModel):
    scaler: Literal["standard", "minmax", "robust"] = "standard"
    fit_scaler_on: Literal["train"] = "train"
    persist_scaler: bool = True


class RandomForestSettings(BaseModel):
    enabled: bool = True
    n_estimators: int = Field(gt=0)
    max_depth: int | None = Field(default=None, gt=0)
    min_samples_leaf: int = Field(gt=0)
    class_weight: str | None = None
    n_jobs: int = -1
    random_state: int = 42


class LSTMSettings(BaseModel):
    enabled: bool = True
    sequence_length: int = Field(gt=0)
    hidden_size: int = Field(gt=0)
    num_layers: int = Field(gt=0)
    dropout: float = Field(ge=0, lt=1)
    bidirectional: bool = False
    output_size: int = Field(gt=0)


class ModelsSettings(BaseModel):
    random_forest: RandomForestSettings
    lstm: LSTMSettings


class EarlyStoppingSettings(BaseModel):
    patience: int = Field(gt=0)
    min_delta: float = Field(ge=0)
    restore_best_weights: bool = True


class GradientClippingSettings(BaseModel):
    enabled: bool = True
    max_norm: float = Field(gt=0)


class TrainingSettings(BaseModel):
    batch_size: int = Field(gt=0)
    epochs: int = Field(gt=0)
    learning_rate: float = Field(gt=0)
    weight_decay: float = Field(ge=0)
    optimizer: Literal["adam", "adamw", "sgd"] = "adam"
    loss: Literal["cross_entropy", "focal"] = "cross_entropy"
    focal_gamma: float = Field(default=2.0, gt=0)
    use_class_weights: bool = True
    early_stopping: EarlyStoppingSettings
    gradient_clipping: GradientClippingSettings


class EvaluationSettings(BaseModel):
    primary_metric: str
    metrics: list[str]
    export_confusion_matrix: bool = True
    export_feature_importance: bool = True


class MLOpsLogSettings(BaseModel):
    parameters: bool = True
    metrics: bool = True
    artifacts: bool = True
    dataset_profile: bool = True
    git_commit: bool = True
    config_snapshot: bool = True


class ModelCardSettings(BaseModel):
    enabled: bool = True
    output_filename: str = "model_card.md"


class MLOpsSettings(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    enabled: bool = True
    tracking_backend: Literal["mlflow", "local"] = "mlflow"
    tracking_uri: str
    experiment_name: str
    register_best_model: bool = True
    model_registry_path: Path
    run_id_format: str
    log: MLOpsLogSettings
    model_card: ModelCardSettings


class BacktestingSettings(BaseModel):
    enabled: bool = True
    fee_rate: float = Field(default=0.001, ge=0)
    slippage_rate: float = Field(default=0.0001, ge=0)
    allow_short: bool = False


class InferenceSettings(BaseModel):
    default_model: str
    confidence_policy: str
    fallback_signal: Literal["HOLD"] = "HOLD"
    max_data_freshness_seconds: int = Field(gt=0)


class APISettings(BaseModel):
    host: str
    port: int
    reload: bool = False
    latency_target_ms_p95: int = Field(gt=0)
    cors_origins: list[str]


class LoggingSettings(BaseModel):
    level: str = "INFO"
    log_dir: Path
    json_logs: bool = False
    file_logging: bool = True


class AppSettings(BaseModel):
    project: ProjectSettings
    data: DataSettings
    features: FeaturesSettings
    labels: LabelSettings
    split: SplitSettings
    preprocessing: PreprocessingSettings
    models: ModelsSettings
    training: TrainingSettings
    evaluation: EvaluationSettings
    mlops: MLOpsSettings
    backtesting: BacktestingSettings = Field(default_factory=BacktestingSettings)
    inference: InferenceSettings
    api: APISettings
    logging: LoggingSettings

    @property
    def label_to_id(self) -> dict[str, int]:
        return {
            "SELL": self.labels.classes.sell,
            "HOLD": self.labels.classes.hold,
            "BUY": self.labels.classes.buy,
        }

    @property
    def id_to_label(self) -> dict[int, str]:
        return {value: key for key, value in self.label_to_id.items()}
