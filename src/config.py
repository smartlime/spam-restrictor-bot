"""
Модуль для загрузки и управления конфигурацией из переменных окружения.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        """
        Загрузить конфигурацию из переменных окружения.
        """
        self._validate_required_vars()
        logger.info("Конфигурация загружена из переменных окружения")
    
    def _validate_required_vars(self):
        """Проверить наличие обязательных переменных окружения."""
        required_vars = ['BOT_TOKEN', 'GROUP_ID']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    @property
    def bot_token(self) -> str:
        """Получить токен бота."""
        return os.getenv('BOT_TOKEN')
    
    @property
    def group_id(self) -> int:
        """Получить ID группы для мониторинга."""
        return int(os.getenv('GROUP_ID'))
    
    @property
    def database_path(self) -> str:
        """Получить путь к базе данных."""
        return os.getenv('DATABASE_PATH', '/app/data/spam_restrictor.db')
    
    @property
    def restriction_period_days(self) -> int:
        """Получить период ограничения в днях."""
        return int(os.getenv('RESTRICTION_PERIOD_DAYS', '30'))
    
    @property
    def check_interval_seconds(self) -> int:
        """Получить интервал проверки в секундах."""
        return int(os.getenv('CHECK_INTERVAL_SECONDS', '3600'))
    
    @property
    def log_level(self) -> str:
        """Получить уровень логирования."""
        return os.getenv('LOG_LEVEL', 'INFO')
    
    @property
    def admin_user_id(self) -> Optional[int]:
        """Получить ID администратора для уведомлений (опционально)."""
        admin_id = os.getenv('ADMIN_USER_ID')
        return int(admin_id) if admin_id else None
    
    @property
    def notify_no_users(self) -> bool:
        """Отправлять ли уведомление когда нет новых пользователей для удаления."""
        return os.getenv('NOTIFY_NO_USERS', '0') == '1'
