"""
Тесты для модуля database.py
"""
import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_add_restricted_user(temp_db):
    """Тест добавления пользователя с ограничениями."""
    result = await temp_db.add_restricted_user(
        user_id=12345,
        username="test_user",
        first_name="Test",
        last_name="User"
    )
    
    assert result is True
    assert await temp_db.is_user_restricted(12345) is True


@pytest.mark.asyncio
async def test_add_duplicate_restricted_user(temp_db):
    """Тест попытки добавить пользователя дважды."""
    await temp_db.add_restricted_user(
        user_id=12345,
        username="test_user",
        first_name="Test",
        last_name="User"
    )
    
    # Попытка добавить того же пользователя снова
    result = await temp_db.add_restricted_user(
        user_id=12345,
        username="test_user",
        first_name="Test",
        last_name="User"
    )
    
    assert result is False


@pytest.mark.asyncio
async def test_is_user_restricted_not_found(temp_db):
    """Тест проверки несуществующего пользователя."""
    assert await temp_db.is_user_restricted(99999) is False


@pytest.mark.asyncio
async def test_add_banned_user(temp_db):
    """Тест добавления забаненного пользователя."""
    result = await temp_db.add_banned_user(
        user_id=54321,
        username="spam_user",
        first_name="Spam",
        last_name="Bot",
        reason="Test ban"
    )
    
    assert result is True
    assert await temp_db.is_user_banned(54321) is True


@pytest.mark.asyncio
async def test_is_user_banned_not_found(temp_db):
    """Тест проверки небаненного пользователя."""
    assert await temp_db.is_user_banned(99999) is False


@pytest.mark.asyncio
async def test_remove_restricted_user(temp_db):
    """Тест удаления пользователя из ограниченных."""
    await temp_db.add_restricted_user(
        user_id=12345,
        username="test_user",
        first_name="Test",
        last_name="User"
    )
    
    result = await temp_db.remove_restricted_user(12345)
    assert result is True
    assert await temp_db.is_user_restricted(12345) is False


@pytest.mark.asyncio
async def test_remove_nonexistent_restricted_user(temp_db):
    """Тест удаления несуществующего пользователя."""
    result = await temp_db.remove_restricted_user(99999)
    assert result is False


@pytest.mark.asyncio
async def test_get_expired_restrictions(temp_db):
    """Тест получения пользователей с истекшими ограничениями."""
    # Добавляем пользователя
    await temp_db.add_restricted_user(
        user_id=12345,
        username="old_user",
        first_name="Old",
        last_name="User"
    )
    
    # Изменяем дату ограничения на 31 день назад вручную
    cutoff_date = datetime.utcnow() - timedelta(days=31)
    await temp_db.connection.execute(
        "UPDATE restricted_users SET restricted_at = ? WHERE user_id = ?",
        (cutoff_date, 12345)
    )
    await temp_db.connection.commit()
    
    # Проверяем, что пользователь найден
    expired = await temp_db.get_expired_restrictions(30)
    assert len(expired) == 1
    assert expired[0]['user_id'] == 12345


@pytest.mark.asyncio
async def test_get_expired_restrictions_empty(temp_db):
    """Тест получения пустого списка просроченных ограничений."""
    # Добавляем нового пользователя (сегодня)
    await temp_db.add_restricted_user(
        user_id=12345,
        username="new_user",
        first_name="New",
        last_name="User"
    )
    
    # Проверяем, что список пуст
    expired = await temp_db.get_expired_restrictions(30)
    assert len(expired) == 0


@pytest.mark.asyncio
async def test_get_stats(temp_db):
    """Тест получения статистики."""
    # Добавляем тестовые данные
    await temp_db.add_restricted_user(user_id=1, username="user1")
    await temp_db.add_restricted_user(user_id=2, username="user2")
    await temp_db.add_banned_user(user_id=3, username="banned1")
    
    stats = await temp_db.get_stats()
    
    assert stats['restricted_users'] == 2
    assert stats['banned_users'] == 1


@pytest.mark.asyncio
async def test_workflow_restricted_to_banned(temp_db):
    """Тест полного workflow: ограничение -> бан -> повторное вступление."""
    user_id = 12345
    
    # 1. Добавляем пользователя в ограниченные
    await temp_db.add_restricted_user(
        user_id=user_id,
        username="test_user",
        first_name="Test"
    )
    assert await temp_db.is_user_restricted(user_id) is True
    assert await temp_db.is_user_banned(user_id) is False
    
    # 2. Перемещаем в забаненные
    await temp_db.add_banned_user(
        user_id=user_id,
        username="test_user",
        first_name="Test",
        reason="Expired"
    )
    await temp_db.remove_restricted_user(user_id)
    
    assert await temp_db.is_user_restricted(user_id) is False
    assert await temp_db.is_user_banned(user_id) is True
    
    # 3. Проверяем, что пользователь остается в banned
    assert await temp_db.is_user_banned(user_id) is True
