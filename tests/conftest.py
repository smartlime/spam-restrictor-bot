"""
Конфигурация pytest и общие фикстуры для тестов.
"""
import pytest
import tempfile
import os
from pathlib import Path

from src.database import Database
from src.config import Config


@pytest.fixture
async def temp_db():
    """
    Создать временную базу данных для тестов.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = Database(db_path)
    await db.connect()
    
    yield db
    
    await db.close()
    os.unlink(db_path)


@pytest.fixture
def temp_config(monkeypatch):
    """
    Создать временную конфигурацию для тестов через переменные окружения.
    """
    # Устанавливаем тестовые переменные окружения
    monkeypatch.setenv('BOT_TOKEN', 'test_bot_token_123456')
    monkeypatch.setenv('GROUP_ID', '-1001234567890')
    monkeypatch.setenv('DATABASE_PATH', '/tmp/test.db')
    monkeypatch.setenv('RESTRICTION_PERIOD_DAYS', '30')
    monkeypatch.setenv('CHECK_INTERVAL_SECONDS', '3600')
    monkeypatch.setenv('LOG_LEVEL', 'INFO')
    
    config = Config()
    
    yield config
