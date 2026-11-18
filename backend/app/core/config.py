from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    blackswan_env: str = "development"
    database_url: str = "sqlite:///./data/blackswan.db"
    blackswan_data_dir: str = "./data"
    blackswan_default_risk_free_rate: float = 0.065
    blackswan_trading_days_per_year: int = 252
    blackswan_backend_port: int = 8787
    model_version: str = "1.0.0"

    @field_validator("database_url", mode="before")
    @classmethod
    def sanitize_database_url(cls, v: object) -> str:
        if isinstance(v, str) and "://" in v.strip():
            return v.strip()
        return "sqlite:///./data/blackswan.db"

    @field_validator("blackswan_env", mode="before")
    @classmethod
    def sanitize_env(cls, v: object) -> str:
        if isinstance(v, str) and v.strip().lower() in {"development", "production", "test", "staging"}:
            return v.strip().lower()
        return "development"

    @field_validator("blackswan_data_dir", mode="before")
    @classmethod
    def sanitize_data_dir(cls, v: object) -> str:
        if isinstance(v, str):
            cleaned = v.strip()
            if cleaned and not cleaned.isdigit():
                return cleaned
        return "./data"

    @field_validator("blackswan_default_risk_free_rate", mode="before")
    @classmethod
    def sanitize_rfr(cls, v: object) -> float:
        try:
            val = float(v)  # type: ignore[arg-type]
            if 0.0 <= val <= 0.5:
                return val
        except (TypeError, ValueError):
            pass
        return 0.065

    @field_validator("blackswan_trading_days_per_year", mode="before")
    @classmethod
    def sanitize_trading_days(cls, v: object) -> int:
        try:
            val = int(v)  # type: ignore[arg-type]
            if 200 <= val <= 366:
                return val
        except (TypeError, ValueError):
            pass
        return 252

    @field_validator("blackswan_backend_port", mode="before")
    @classmethod
    def sanitize_backend_port(cls, v: object) -> int:
        try:
            val = int(v)  # type: ignore[arg-type]
            if 1025 <= val <= 65535 and val != 8000:
                return val
        except (TypeError, ValueError):
            pass
        return 8787

    @property
    def data_dir(self) -> Path:
        path = Path(self.blackswan_data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def raw_data_dir(self) -> Path:
        path = self.data_dir / "raw"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def processed_data_dir(self) -> Path:
        path = self.data_dir / "processed"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
