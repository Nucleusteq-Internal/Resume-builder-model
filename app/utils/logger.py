import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    os.makedirs('logs', exist_ok=True)
    handler = RotatingFileHandler(
        f'logs/{name}.log',
        maxBytes=1000000,
        backupCount=5
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = setup_logger('resume_builder')