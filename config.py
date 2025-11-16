import os
import hmac
import hashlib
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # General
    WORK_DIR: str = "/opt/ytms"
    STORAGE_ROOT: str = "/var/www/storage"  # it is default, but app will send this path - out_base_path
    WORKERS: int = 1  # number of workers

    # Security for callback signature
    # If no job.payload.auth_token then fallback here (optionally)
    GLOBAL_AUTH_TOKEN: str = "dev-secret"

    # Limits
    DEFAULT_TILE_W: int = 160
    DEFAULT_TILE_H: int = 90
    DEFAULT_COLS: int = 10
    DEFAULT_ROWS: int = 10

    # Adaptive intervals
    PREVIEW_INTERVAL_SHORT: float = 2.0      # < 15 min
    PREVIEW_INTERVAL_MEDIUM: float = 4.0     # < 60 min
    PREVIEW_INTERVAL_LONG: float = 6.0       # > 60 min
    PREVIEW_SHORT_MAX_SEC: int = 15 * 60
    PREVIEW_MEDIUM_MAX_SEC: int = 60 * 60

    model_config = SettingsConfigDict(env_prefix="YTMS_", env_file=".env", extra="ignore")

    def sign(self, token: str, body: bytes) -> str:
        secret = (token or self.GLOBAL_AUTH_TOKEN).encode("utf-8")
        return hmac.new(secret, body, hashlib.sha256).hexdigest()

settings = Settings()