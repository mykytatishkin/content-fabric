from pathlib import Path

from pydantic_settings import BaseSettings

# prod/ directory (parent of app/)
PROD_DIR = Path(__file__).resolve().parent.parent.parent
ENV_DB = PROD_DIR / ".env.db"
ENV_API = PROD_DIR / ".env.api"


class ApiSettings(BaseSettings):
    """External API keys — loaded only from prod/.env.api"""

    YOUTUBE_API_KEY: str = ""  # YouTube Data API v3 (channel validation)

    model_config = {
        "env_file": str(ENV_API),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class Settings(BaseSettings):
    APP_NAME: str = "FastAPI App"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {
        "env_file": [".env", str(ENV_DB)],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
api_settings = ApiSettings()
