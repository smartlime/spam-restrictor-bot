"""
Модуль для работы с базой данных SQLite.
Хранит информацию о пользователях с ограничениями и удаленных пользователях.
"""
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        """
        Инициализация подключения к базе данных.
        
        Args:
            db_path: путь к файлу базы данных SQLite
        """
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Установить соединение с базой данных."""
        self.connection = await aiosqlite.connect(self.db_path)
        await self._create_tables()
        logger.info(f"Подключение к базе данных установлено: {self.db_path}")
    
    async def close(self):
        """Закрыть соединение с базой данных."""
        if self.connection:
            await self.connection.close()
            logger.info("Соединение с базой данных закрыто")
    
    async def _create_tables(self):
        """Создать необходимые таблицы, если они не существуют."""
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS restricted_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP NOT NULL,
                restricted_at TIMESTAMP NOT NULL
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                banned_at TIMESTAMP NOT NULL,
                reason TEXT
            )
        """)
        
        await self.connection.commit()
        logger.info("Таблицы базы данных созданы или уже существуют")
    
    async def add_restricted_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> bool:
        """
        Добавить пользователя с ограничениями.
        
        Args:
            user_id: ID пользователя Telegram
            username: имя пользователя (без @)
            first_name: имя
            last_name: фамилия
            
        Returns:
            True если пользователь успешно добавлен, False если уже существует
        """
        try:
            now = datetime.utcnow()
            await self.connection.execute("""
                INSERT INTO restricted_users (user_id, username, first_name, last_name, joined_at, restricted_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, now, now))
            await self.connection.commit()
            logger.info(f"Пользователь {user_id} ({username}) добавлен в ограниченные")
            return True
        except aiosqlite.IntegrityError:
            logger.warning(f"Пользователь {user_id} уже существует в ограниченных")
            return False
    
    async def is_user_restricted(self, user_id: int) -> bool:
        """
        Проверить, находится ли пользователь в списке ограниченных.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            True если пользователь ограничен
        """
        cursor = await self.connection.execute(
            "SELECT 1 FROM restricted_users WHERE user_id = ?",
            (user_id,)
        )
        result = await cursor.fetchone()
        return result is not None
    
    async def add_banned_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        reason: str = "Expired restriction period"
    ) -> bool:
        """
        Добавить пользователя в список забаненных (удаленных).
        
        Args:
            user_id: ID пользователя Telegram
            username: имя пользователя (без @)
            first_name: имя
            last_name: фамилия
            reason: причина бана
            
        Returns:
            True если пользователь успешно добавлен
        """
        try:
            now = datetime.utcnow()
            await self.connection.execute("""
                INSERT OR REPLACE INTO banned_users (user_id, username, first_name, last_name, banned_at, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, now, reason))
            await self.connection.commit()
            logger.info(f"Пользователь {user_id} ({username}) добавлен в забаненные: {reason}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя в banned: {e}")
            return False
    
    async def is_user_banned(self, user_id: int) -> bool:
        """
        Проверить, находится ли пользователь в списке забаненных.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            True если пользователь забанен
        """
        cursor = await self.connection.execute(
            "SELECT 1 FROM banned_users WHERE user_id = ?",
            (user_id,)
        )
        result = await cursor.fetchone()
        return result is not None
    
    async def remove_restricted_user(self, user_id: int) -> bool:
        """
        Удалить пользователя из списка ограниченных.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            True если пользователь был удален
        """
        cursor = await self.connection.execute(
            "DELETE FROM restricted_users WHERE user_id = ?",
            (user_id,)
        )
        await self.connection.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Пользователь {user_id} удален из ограниченных")
        return deleted
    
    async def get_expired_restrictions(self, days: int) -> List[Dict]:
        """
        Получить список пользователей, у которых истек срок ограничений.
        
        Args:
            days: количество дней для проверки истечения ограничений
            
        Returns:
            Список словарей с информацией о пользователях
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cursor = await self.connection.execute("""
            SELECT user_id, username, first_name, last_name, restricted_at
            FROM restricted_users
            WHERE restricted_at <= ?
        """, (cutoff_date,))
        
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'restricted_at': row[4]
            })
        
        logger.info(f"Найдено {len(results)} пользователей с истекшими ограничениями")
        return results
    
    async def get_stats(self) -> Dict:
        """
        Получить статистику по базе данных.
        
        Returns:
            Словарь со статистикой
        """
        cursor = await self.connection.execute("SELECT COUNT(*) FROM restricted_users")
        restricted_count = (await cursor.fetchone())[0]
        
        cursor = await self.connection.execute("SELECT COUNT(*) FROM banned_users")
        banned_count = (await cursor.fetchone())[0]
        
        return {
            'restricted_users': restricted_count,
            'banned_users': banned_count
        }
