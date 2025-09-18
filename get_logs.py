import os
import logging
from logging.handlers import TimedRotatingFileHandler
from flask import request
from flask_login import current_user

class GetLogs:
    def __init__(self):
        self.logs_path = os.path.join(os.path.dirname(__file__), '..', 'logs')
        
    def get_user_logger(self, user_id):
        logger = logging.getLogger(f"user_{user_id}")
        if not logger.handlers:
            log_dir = self.logs_path
            os.makedirs(log_dir, exist_ok=True)
            handler = TimedRotatingFileHandler(
                os.path.join(log_dir, f"user_{user_id}.log"),
                when="midnight", interval=1, backupCount=30, encoding="utf-8"
            )
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def log_message(self, msg, level='INFO'):
        if current_user.is_authenticated:
            user_id = current_user.id
        else:
            user_id = "Anonymous"
        
        user_logger = self.get_user_logger(user_id)
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        if level == 'DEBUG':
            user_logger.debug(f"[{ip}]: {msg}")
        elif level == 'INFO':       
            user_logger.info(f"[{ip}]: {msg}")
        elif level == 'WARNING':
            user_logger.warning(f"[{ip}]: {msg}")
        elif level == 'ERROR':
            user_logger.error(f"[{ip}]: {msg}")
        elif level == 'CRITICAL':
            user_logger.critical(f"[{ip}]: {msg}")
        
        return