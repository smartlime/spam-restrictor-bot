"""
Точка входа для запуска бота.
"""
import asyncio
import logging
import sys
from pathlib import Path

from .config import Config
from .database import Database
from .bot import SpamRestrictorBot


def setup_logging(level: str = "INFO"):
    """
    Настроить логирование.
    
    Args:
        level: уровень логирования
    """
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=getattr(logging, level.upper()),
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


async def main():
    """Главная функция запуска бота."""
    # Загружаем конфигурацию из переменных окружения
    try:
        config = Config()
    except ValueError as e:
        print(f"❌ ОШИБКА: {e}")
        print("\nУбедитесь, что установлены следующие переменные окружения:")
        print("  - BOT_TOKEN: токен бота от @BotFather")
        print("  - GROUP_ID: ID группы для мониторинга")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ОШИБКА при загрузке конфигурации: {e}")
        sys.exit(1)
    
    # Настраиваем логирование
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 50)
    logger.info("Запуск Spam Restrictor Bot")
    logger.info("=" * 50)
    logger.info(f"Группа ID: {config.group_id}")
    logger.info(f"База данных: {config.database_path}")
    logger.info(f"Период ограничения: {config.restriction_period_days} дней")
    logger.info(f"Интервал проверки: {config.check_interval_seconds} сек")
    
    # Создаем директорию для базы данных, если её нет
    db_path = Path(config.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Создаем объекты базы данных и бота
    database = Database(config.database_path)
    bot = SpamRestrictorBot(config, database)
    
    # Запускаем бота
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
