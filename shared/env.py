"""Load environment variables from project .env files."""

from pathlib import Path

from dotenv import load_dotenv

_prod_dir = Path(__file__).resolve().parent.parent

load_dotenv(_prod_dir / ".env" / ".env.db")
load_dotenv(_prod_dir / ".env" / ".env.api")
load_dotenv(_prod_dir.parent / ".env")  # root .env (Telegram, Redis, JWT, etc.)
