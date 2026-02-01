"""
Тесты для модуля config.py
"""
import pytest
import os


def test_config_loads_successfully(temp_config):
    """Тест успешной загрузки конфигурации из переменных окружения."""
    assert temp_config.bot_token == "test_bot_token_123456"
    assert temp_config.group_id == -1001234567890
    assert temp_config.database_path == "/tmp/test.db"
    assert temp_config.restriction_period_days == 30
    assert temp_config.check_interval_seconds == 3600
    assert temp_config.log_level == "INFO"


def test_config_properties(temp_config):
    """Тест доступа к свойствам конфигурации."""
    config = temp_config
    
    # Проверяем все свойства
    assert isinstance(config.bot_token, str)
    assert isinstance(config.group_id, int)
    assert isinstance(config.database_path, str)
    assert isinstance(config.restriction_period_days, int)
    assert isinstance(config.check_interval_seconds, int)
    assert isinstance(config.log_level, str)


def test_config_missing_required_vars(monkeypatch):
    """Тест обработки отсутствующих обязательных переменных окружения."""
    from src.config import Config
    
    # Очищаем переменные окружения
    monkeypatch.delenv('BOT_TOKEN', raising=False)
    monkeypatch.delenv('GROUP_ID', raising=False)
    
    with pytest.raises(ValueError) as exc_info:
        Config()
    
    assert "обязательные переменные окружения" in str(exc_info.value).lower()


def test_config_default_values(monkeypatch):
    """Тест использования значений по умолчанию для опциональных параметров."""
    from src.config import Config
    
    # Устанавливаем только обязательные переменные
    monkeypatch.setenv('BOT_TOKEN', 'test_token')
    monkeypatch.setenv('GROUP_ID', '-100123')
    
    # Удаляем опциональные переменные
    monkeypatch.delenv('DATABASE_PATH', raising=False)
    monkeypatch.delenv('RESTRICTION_PERIOD_DAYS', raising=False)
    monkeypatch.delenv('CHECK_INTERVAL_SECONDS', raising=False)
    monkeypatch.delenv('LOG_LEVEL', raising=False)
    
    config = Config()
    
    # Проверяем значения по умолчанию
    assert config.database_path == '/app/data/spam_restrictor.db'
    assert config.restriction_period_days == 30
    assert config.check_interval_seconds == 3600
    assert config.log_level == 'INFO'
