"""
Centralised runtime configuration loaded from environment / .env.
All values have safe defaults so the engine can run without a .env for local dev.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")

    reconnect_delay_s: float = Field(1.0,  description="Base reconnect backoff (seconds)")
    reconnect_max_s:   float = Field(60.0, description="Max reconnect backoff")
    # Kraken v2 book channel only accepts depth ∈ {10, 25, 100, 500, 1000};
    # requesting an unsupported value (e.g. 20) gets the subscription silently
    # rejected by Kraken, so book updates never arrive.
    book_depth:        int   = Field(10,   description="L2 levels to request per exchange (Kraken: 10/25/100/500/1000)")
    symbols:           list[str] = Field(
        default=["BTC/USDT", "ETH/USDT"],
        description="Instruments to subscribe across all exchanges",
    )
    max_quote_staleness_s: float = Field(
        1.0,
        description="Max allowed gap between two exchanges' quote receipt "
                     "times for a cross-exchange comparison to count as fresh "
                     "(see ArbitrageDetectorPlugin)",
    )


class ModelConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GNN_", env_file=".env", extra="ignore")

    hidden_channels: int   = Field(64,   description="GNN hidden dimension")
    num_layers:      int   = Field(3,    description="Number of GNN message-passing layers")
    dropout:         float = Field(0.1)
    learning_rate:   float = Field(1e-3)
    checkpoint_dir:  str   = Field("backend/models/checkpoints")


class ExecutionConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EXEC_", env_file=".env", extra="ignore")

    maker_fee:      float = Field(0.001, description="Maker fee as a fraction (0.1%)")
    taker_fee:      float = Field(0.001, description="Taker fee as a fraction (0.1%)")
    slippage_bps:   float = Field(1.0,   description="Assumed slippage in basis points")
    capital_usdt:   float = Field(10_000.0, description="Notional capital for simulation")


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level:   str  = Field("INFO")
    ws_port:     int  = Field(8000, description="Port for the internal WS bridge to frontend")
    metrics_port: int = Field(9090, description="Prometheus scrape endpoint port")

    ingestion:  IngestionConfig  = Field(default_factory=IngestionConfig)
    model:      ModelConfig      = Field(default_factory=ModelConfig)
    execution:  ExecutionConfig  = Field(default_factory=ExecutionConfig)


# Singleton — import and use `settings` everywhere.
settings = AppConfig()
