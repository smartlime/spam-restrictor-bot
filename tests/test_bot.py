"""
Тесты для модуля bot.py (без реальной работы с Telegram API).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot import SpamRestrictorBot


@pytest.mark.asyncio
async def test_bot_initialization(temp_config, temp_db):
    """Тест инициализации бота."""
    bot = SpamRestrictorBot(temp_config, temp_db)
    
    assert bot.config == temp_config
    assert bot.db == temp_db
    assert bot.application is None
    assert bot.last_check_time is None
    assert bot.next_check_time is None
    assert bot.restricted_permissions.can_send_messages is False


@pytest.mark.asyncio
async def test_bot_build_application(temp_config, temp_db):
    """Тест создания Application."""
    bot = SpamRestrictorBot(temp_config, temp_db)
    
    with patch('src.bot.Application.builder') as mock_builder:
        mock_app = MagicMock()
        mock_builder.return_value.token.return_value.build.return_value = mock_app
        mock_app.job_queue = MagicMock()
        
        application = bot.build_application()
        
        # Проверяем, что Application был создан
        assert application is not None


@pytest.mark.asyncio
async def test_restricted_permissions(temp_config, temp_db):
    """Тест настройки ограниченных прав."""
    bot = SpamRestrictorBot(temp_config, temp_db)
    permissions = bot.restricted_permissions
    
    # Проверяем, что все права запрещены
    assert permissions.can_send_messages is False
    assert permissions.can_send_audios is False
    assert permissions.can_send_documents is False
    assert permissions.can_send_photos is False
    assert permissions.can_send_videos is False
    assert permissions.can_send_polls is False


@pytest.mark.asyncio
async def test_check_expired_restrictions_empty(temp_config, temp_db):
    """Тест проверки просроченных ограничений с пустой базой."""
    bot = SpamRestrictorBot(temp_config, temp_db)
    # temp_db уже подключен через фикстуру
    
    # Создаем mock контекст
    mock_context = MagicMock()
    mock_context.bot = AsyncMock()
    
    # Не должно быть ошибок при пустой базе
    await bot.check_expired_restrictions(mock_context)
    # Не закрываем вручную - фикстура сама закроет


@pytest.mark.asyncio
async def test_stats_computation(temp_db):
    """Тест вычисления статистики."""
    # temp_db уже подключен через фикстуру
    
    # Добавляем тестовые данные
    await temp_db.add_restricted_user(user_id=1, username="user1")
    await temp_db.add_restricted_user(user_id=2, username="user2")
    await temp_db.add_banned_user(user_id=3, username="banned1")
    await temp_db.add_banned_user(user_id=4, username="banned2")
    await temp_db.add_banned_user(user_id=5, username="banned3")
    
    stats = await temp_db.get_stats()
    
    assert stats['restricted_users'] == 2
    assert stats['banned_users'] == 3
    # Не закрываем вручную - фикстура сама закроет
