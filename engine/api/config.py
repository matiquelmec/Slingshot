from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

# Ruta absoluta al .env — independiente del CWD desde donde se lance el servidor
_ENV_FILE = str(Path(__file__).parent.parent.parent / ".env")

class Settings(BaseSettings):
    # API Configuration
    PROJECT_NAME: str = "Slingshot Engine"
    VERSION: str = "6.0.0"
    API_V1_STR: str = "/api/v1"

    # Binance
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None

    # Gemini AI (LLM Advisor)
    GEMINI_API_KEY: Optional[str] = None

    # Whale Alert
    WHALE_ALERT_API_KEY: Optional[str] = None

    # Removido: REDIS y SUPABASE en entorno local

    # Security
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    SECURITY_API_KEY: str = "SLINGSHOT_INTERNAL_V6"

    # Ollama LLM (Advisor Táctico)
    OLLAMA_MODEL: str = "gemma3:4b"        # gemma3:4b = producción | gemma3:4b = VRAM reducida
    OLLAMA_URL: str = "http://localhost:11434"

    # Strategy Delta Δ: Tiered Priority (v6.0 Trident Audit)
    MASTER_WATCHLIST: list[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "PAXGUSDT"]
    PRIORITY_TIERS: dict[str, float] = {
        "BTCUSDT": 0.5,   # Tier 1: Alta Volatilidad (0.5s)
        "SOLUSDT": 0.5,   # Tier 1
        "ETHUSDT": 1.5,   # Tier 2: Media Volatilidad (1.5s)
        "PAXGUSDT": 5.0,  # Tier 3: Commodities tokenizados (5.0s)
    }
    DEFAULT_PULSE_INTERVAL: float = 2.0

    # Risk Management (leídos desde .env — ya no hardcodeados en el router)
    ACCOUNT_BALANCE: float = 1000.0
    MAX_RISK_PCT: float = 0.02
    MIN_RR: float = 2.5

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

settings = Settings()

# Level-1 Access (Legacy Compatibility)
MASTER_WATCHLIST = settings.MASTER_WATCHLIST
PRIORITY_TIERS   = settings.PRIORITY_TIERS
DEFAULT_PULSE_INTERVAL = settings.DEFAULT_PULSE_INTERVAL

