import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# prod/ directory (parent of app/) — env files in prod/.env/
PROD_DIR = Path(__file__).resolve().parent.parent.parent
ENV_DB = PROD_DIR / ".env" / ".env.db"
ENV_API = PROD_DIR / ".env" / ".env.api"

# #region agent log
def _log(d):
    # Get log path from environment variable or use default in project root
    log_path = os.environ.get(
        "CURSOR_DEBUG_LOG_PATH",
        str((PROD_DIR / ".cursor" / "debug.log").resolve())
    )
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as f:
        import time
        d_with_ts = {**d, "timestamp": time.time() * 1000}
        f.write(json.dumps(d_with_ts) + "\n")
_log({"hypothesisId":"A","location":"config.py:paths","message":"ENV paths","data":{"ENV_API":str(ENV_API),"ENV_API_exists":ENV_API.exists(),"PROD_DIR":str(PROD_DIR)}})
# #endregion

# Explicitly load into os.environ so pydantic finds vars
loaded_db = load_dotenv(ENV_DB)
loaded_api = load_dotenv(ENV_API)

# #region agent log
_log({"hypothesisId":"B","location":"config.py:load_dotenv","message":"load_dotenv result","data":{"loaded_db":loaded_db,"loaded_api":loaded_api,"env_has_key":"YOUTUBE_API_KEY" in os.environ,"env_key_len":len(os.environ.get("YOUTUBE_API_KEY","")) if "YOUTUBE_API_KEY" in os.environ else 0}})
# #endregion


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

# #region agent log
_log({"hypothesisId":"C","location":"config.py:ApiSettings","message":"ApiSettings after init","data":{"YOUTUBE_API_KEY_set":bool(api_settings.YOUTUBE_API_KEY),"YOUTUBE_API_KEY_len":len(api_settings.YOUTUBE_API_KEY or "")}})
# #endregion
