from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

# Ruta absoluta al .env — independiente del CWD desde donde se lance el servidor
_ENV_FILE = str(Path(__file__).parent.parent.parent / ".env")

class Settings(BaseSettings):
    # API Configuration
    PROJECT_NAME: str = "Slingshot Engine"
    VERSION: str = "10.0.0"
    API_V1_STR: str = "/api/v1"

    # Binance
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None

    # Bitunix
    BITUNIX_API_KEY: Optional[str] = None
    BITUNIX_SECRET_KEY: Optional[str] = None
    ENABLE_LIVE_TRADING: bool = False
    ALLOW_TEST_SIGNAL_IN_LIVE: bool = False

    # Gemini AI (LLM Advisor)
    GEMINI_API_KEY: Optional[str] = None

    # Groq Cloud AI (LLM Advisor)
    GROQ_API_KEY: Optional[str] = None

    # Whale Alert
    WHALE_ALERT_API_KEY: Optional[str] = None

    # Removido: REDIS y SUPABASE en entorno local

    # Security
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    SECURITY_API_KEY: str = "SLINGSHOT_INTERNAL_V6"
    JWT_SECRET: str = "slingshot_sovereign_local_jwt_secret_v11_apex"

    # Ollama LLM (Advisor Táctico)
    OLLAMA_MODEL: str = "gemma3:4b"        # gemma3:4b = producción | gemma4:latest = alta precisión
    OLLAMA_URL: str = "http://localhost:11434"

    # Strategy Delta Δ: Tiered Priority (Top 10 High-Performance Assets)
    RADAR_ASSETS: str = "BTCUSDT,ETHUSDT,INJUSDT,SUIUSDT,AVAXUSDT,RENDERUSDT,NEARUSDT,FETUSDT,ATOMUSDT,TIAUSDT"
    
    @property
    def MASTER_WATCHLIST(self) -> list[str]:
        return [s.strip() for s in self.RADAR_ASSETS.split(",") if s.strip()]

    PRIORITY_TIERS: dict[str, float] = {
        "BTCUSDT": 0.5,     # Tier 1: Líder Macro (0.5s)
        "ETHUSDT": 0.5,     # Tier 1: Líder Altcoins (0.5s)
        "INJUSDT": 0.8,     # Tier 1: Máxima Expansión (0.8s)
        "SUIUSDT": 0.8,     # Tier 1: Máxima Expansión (0.8s)
        "AVAXUSDT": 1.2,    # Tier 2: Media Volatilidad (1.2s)
        "RENDERUSDT": 1.2,  # Tier 2: Media Volatilidad (1.2s)
        "NEARUSDT": 1.5,    # Tier 2: Estructura (1.5s)
        "FETUSDT": 1.5,     # Tier 2: Momentum (1.5s)
        "ATOMUSDT": 2.0,    # Tier 3: Rango Limpio (2.0s)
        "TIAUSDT": 2.0,     # Tier 3: Rango Limpio (2.0s)
    }
    DEFAULT_PULSE_INTERVAL: float = 1.5

    # Activos SPOT-only: no existen en Binance Futures (fstream).
    # Usar wss://stream.binance.com:9443 para estos símbolos.
    SPOT_ONLY_ASSETS: set = {"PAXGUSDT", "EURUSDT", "USDCUSDT"}

    # Risk Management (leídos desde .env — ya no hardcodeados en el router)
    ACCOUNT_BALANCE: float = 1000.0
    MAX_RISK_PCT: float = 0.02
    MIN_RR: float = 2.5
    INSTITUTIONAL_VOL_THRESHOLD: float = 1.3

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

settings = Settings()

# Level-1 Access (Legacy Compatibility)
MASTER_WATCHLIST = settings.MASTER_WATCHLIST
PRIORITY_TIERS   = settings.PRIORITY_TIERS
DEFAULT_PULSE_INTERVAL = settings.DEFAULT_PULSE_INTERVAL

