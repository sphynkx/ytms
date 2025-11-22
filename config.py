import os
import hmac
import hashlib
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    WORK_DIR: str = "/opt/ytms"
    STORAGE_ROOT: str = "/var/www/yurtube/storage"
    WORKERS: int = 1

    GLOBAL_AUTH_TOKEN: str = "dev-secret"

    DEFAULT_TILE_W: int = 160
    DEFAULT_TILE_H: int = 90
    DEFAULT_COLS: int = 10
    DEFAULT_ROWS: int = 10

    PREVIEW_INTERVAL_SHORT: float = 2.0
    PREVIEW_INTERVAL_MEDIUM: float = 4.0
    PREVIEW_INTERVAL_LONG: float = 6.0
    PREVIEW_SHORT_MAX_SEC: int = 15 * 60
    PREVIEW_MEDIUM_MAX_SEC: int = 60 * 60

    MAX_FRAMES: int = 1000
    MIN_INTERVAL_SEC: float = 0.2

    model_config = SettingsConfigDict(
        env_prefix="YTMS_",
        env_file=".env",
        extra="ignore",
    )

    def sign(self, token: str | None, body: bytes) -> str:
        secret = (token or self.GLOBAL_AUTH_TOKEN).encode("utf-8")
        return hmac.new(secret, body, hashlib.sha256).hexdigest()


settings = Settings()