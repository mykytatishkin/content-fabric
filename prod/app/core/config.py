import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# prod/ directory (parent of app/) — env files in prod/.env/
PROD_DIR = Path(__file__).resolve().parent.parent.parent
ENV_DB = PROD_DIR / ".env" / ".env.db"
ENV_API = PROD_DIR / ".env" / ".env.api"

# Explicitly load into os.environ so pydantic finds vars
load_dotenv(ENV_DB)
load_dotenv(ENV_API)


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

    # MySQL (loaded from prod/.env/.env.db only)
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_DATABASE: str
    MYSQL_USER: str
    MYSQL_PASSWORD: str

    model_config = {
        "env_file": [".env", str(ENV_DB)],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
api_settings = ApiSettings()
