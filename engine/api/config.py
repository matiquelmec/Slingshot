from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # API Configuration
    PROJECT_NAME: str = "Slingshot Engine"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Binance
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Security
    CORS_ORIGINS: list[str] = ["*"]
    
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

settings = Settings()
