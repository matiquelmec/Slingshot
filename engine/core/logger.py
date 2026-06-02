import logging
from logging.handlers import RotatingFileHandler
import os

class SecretRedactingFilter(logging.Filter):
    """
    Scrubs sensitive API keys and secrets from log messages.
    """
    def filter(self, record):
        if not isinstance(record.msg, str):
            return True
            
        msg = record.msg
        try:
            from engine.api.config import settings
            secrets = []
            if getattr(settings, "BINANCE_API_KEY", None):
                secrets.append(settings.BINANCE_API_KEY)
            if getattr(settings, "BINANCE_API_SECRET", None):
                secrets.append(settings.BINANCE_API_SECRET)
            if getattr(settings, "GEMINI_API_KEY", None):
                secrets.append(settings.GEMINI_API_KEY)
            if getattr(settings, "TELEGRAM_BOT_TOKEN", None):
                secrets.append(settings.TELEGRAM_BOT_TOKEN)
                
            for secret in secrets:
                if secret and len(secret) > 4 and secret in msg:
                    msg = msg.replace(secret, f"{secret[:4]}...[REDACTED]")
        except Exception:
            pass
        
        record.msg = msg
        return True

def setup_logger():
    # Only setup once
    logger = logging.getLogger("slingshot")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Ensure log directory exists within tmp/ to keep root clean
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "tmp", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Rotating File Handler: Max 10MB per file, keep 5 backups
        file_handler = RotatingFileHandler(
            filename=os.path.join(log_dir, "slingshot.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # Stream Handler for console output
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Apply secret scrubbing filter
        redact_filter = SecretRedactingFilter()
        file_handler.addFilter(redact_filter)
        console_handler.addFilter(redact_filter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

# Global logger instance
logger = setup_logger()
