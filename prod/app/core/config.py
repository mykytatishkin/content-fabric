import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# prod/ directory (parent of app/) — env files in prod/.env/
PROD_DIR = Path(__file__).resolve().parent.parent.parent
ENV_DB = PROD_DIR / ".env" / ".env.db"
ENV_API = PROD_DIR / ".env" / ".env.api"
ENV_DLE = PROD_DIR / ".env" / ".env.dle"

# Explicitly load into os.environ so pydantic finds vars
load_dotenv(ENV_DB)
load_dotenv(ENV_API)
load_dotenv(ENV_DLE)


class ApiSettings(BaseSettings):
    """External API keys — loaded only from prod/.env.api"""

    YOUTUBE_API_KEY: str = ""  # YouTube Data API v3 (channel validation)

    # OpenAI (мигрировано из Yii — был захардкожен в 7+ контроллерах)
    OPENAI_API_KEY: str = ""

    # Google API ключи для Yii pipelines (shorts validator + stats collector)
    GOOGLE_API_KEY_SHORTS: str = ""
    GOOGLE_API_KEY_STATS: str = ""

    # Zenrows web-scraping proxy (используется в Sora pipeline)
    ZENROWS_API_KEY: str = ""

    # yt-dlp cookies path (для скачивания YouTube-видео)
    YOUTUBE_COOKIES_PATH: str = "/opt/content-fabric/data/cookies.txt"

    model_config = {
        "env_file": str(ENV_API),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class DleSettings(BaseSettings):
    """7 DLE источников контента — DSN из prod/.env.dle

    Каждый DSN — полная строка SQLAlchemy:
        mysql+pymysql://user:pass@host:port/db?charset=utf8mb4

    Если какой-то источник недоступен — оставляем пустой DSN, парсер должен gracefully skip.
    """

    DLE_KNIGI_AUDIO_DSN: str = ""       # knigi-audio.biz (77.220.213.172)
    DLE_AUDIOKNIGA_DSN: str = ""        # audiokniga-one.com (185.154.15.251:3310)
    DLE_CLUB_BOOKS_DSN: str = ""        # club-books.ru (185.244.217.9:3311)
    DLE_BOOKS_ONLINE_DSN: str = ""      # books-online.info (91.211.251.57)
    DLE_SLUSHAT_DSN: str = ""           # slushat-knigi.com (80.85.141.91:3310)
    DLE_KNIGI_ONLINE_DSN: str = ""      # knigi-online.club (185.224.133.132:3310)
    DLE_BAZAKNIG_DSN: str = ""          # bazaknig.net (185.224.133.132:3310)

    def all_sources(self) -> dict[str, str]:
        """Маппинг slug → DSN для всех источников. Пустые DSN исключаются."""
        return {
            slug: dsn
            for slug, dsn in {
                "knigi_audio_biz": self.DLE_KNIGI_AUDIO_DSN,
                "audiokniga_one_com": self.DLE_AUDIOKNIGA_DSN,
                "club_books_ru": self.DLE_CLUB_BOOKS_DSN,
                "books_online_info": self.DLE_BOOKS_ONLINE_DSN,
                "slushat_knigi_com": self.DLE_SLUSHAT_DSN,
                "knigi_online_club": self.DLE_KNIGI_ONLINE_DSN,
                "bazaknig_net": self.DLE_BAZAKNIG_DSN,
            }.items()
            if dsn
        }

    model_config = {
        "env_file": str(ENV_DLE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class Settings(BaseSettings):
    APP_NAME: str = "FastAPI App"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["http://46.21.250.43"]
    BASE_URL: str = ""  # e.g. "http://46.21.250.43" — used for OAuth redirect_uri

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
dle_settings = DleSettings()
