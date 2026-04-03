import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger():
    # Only setup once
    logger = logging.getLogger("slingshot")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
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
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

# Global logger instance
logger = setup_logger()
