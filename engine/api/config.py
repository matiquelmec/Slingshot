from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

# Ruta absoluta al .env — independiente del CWD desde donde se lance el servidor
_ENV_FILE = str(Path(__file__).parent.parent.parent / ".env")

class Settings(BaseSettings):
    # API Configuration
    PROJECT_NAME: str = "Slingshot Engine"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    # Binance
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None

    # Gemini AI (LLM Advisor)
    GEMINI_API_KEY: Optional[str] = None

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # 🗄️ Supabase (DB + Auth)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None               # anon/public key
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None  # service_role (solo backend)

    # Security
    CORS_ORIGINS: list[str] = ["*"]

    # Risk Management (leídos desde .env — ya no hardcodeados en el router)
    ACCOUNT_BALANCE: float = 1000.0
    MAX_RISK_PCT: float = 0.01
    MIN_RR: float = 3.0

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

settings = Settings()

