"""
Основной модуль телеграм-бота для защиты от спамеров.
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update, ChatMember, ChatPermissions, Chat
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
)
from telegram.error import TelegramError

from .database import Database
from .config import Config

logger = logging.getLogger(__name__)


class SpamRestrictorBot:
    def __init__(self, config: Config, database: Database):
        """
        Инициализация бота.
        
        Args:
            config: объект конфигурации
            database: объект базы данных
        """
        self.config = config
        self.db = database
        self.application: Optional[Application] = None
        self.last_check_time: Optional[datetime] = None
        self.next_check_time: Optional[datetime] = None
        
        # Права для ограниченных пользователей (запрет на отправку сообщений и медиа)
        self.restricted_permissions = ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )
    
    async def notify_admin(self, context: ContextTypes.DEFAULT_TYPE, message: str):
        """
        Отправить уведомление администратору.
        
        Args:
            context: контекст бота
            message: текст уведомления
        """
        if not self.config.admin_user_id:
            return
        
        try:
            await context.bot.send_message(
                chat_id=self.config.admin_user_id,
                text=message,
                parse_mode="HTML"
            )
            logger.debug(f"Уведомление отправлено администратору: {message}")
        except TelegramError as e:
            logger.error(f"Ошибка при отправке уведомления администратору: {e}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status - показать статус бота (только для администратора)."""
        # Проверка прав администратора
        if not self.config.admin_user_id or update.effective_user.id != self.config.admin_user_id:
            return
        # Получаем статистику из БД
        stats = await self.db.get_stats()
        
        # Форматируем время проверок
        if self.last_check_time:
            last_check_str = self.last_check_time.strftime("%d.%m.%Y %H:%M:%S")
        else:
            last_check_str = "еще не проводилась"
        
        if self.next_check_time:
            next_check_str = self.next_check_time.strftime("%d.%m.%Y %H:%M:%S")
            time_until = self.next_check_time - datetime.utcnow()
            minutes_until = int(time_until.total_seconds() / 60)
            next_check_str += f" (через {minutes_until} мин)"
        else:
            next_check_str = "не запланирована"
        
        # Получаем ID чата
        chat_id = update.effective_chat.id
        
        status_text = (
            f"🤖 <b>Статус бота</b>\n\n"
            f"📍 <b>ID текущего чата:</b> <code>{chat_id}</code>\n"
            f"👥 <b>Активных наблюдаемых:</b> {stats['restricted_users']}\n"
            f"🚫 <b>Забанено всего:</b> {stats['banned_users']}\n\n"
            f"🕐 <b>Последняя проверка:</b> {last_check_str}\n"
            f"⏰ <b>Следующая проверка:</b> {next_check_str}\n\n"
            f"⚙️ <b>Период ограничения:</b> {self.config.restriction_period_days} дней\n"
            f"⏱️ <b>Интервал проверок:</b> {self.config.check_interval_seconds // 60} минут"
        )
        
        await update.message.reply_text(status_text, parse_mode="HTML")
    
    async def track_chat_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик изменений статуса участников чата.
        Отслеживает вступление новых участников в группу.
        """
        result = update.chat_member
        
        # Проверяем, что это нужная группа
        if result.chat.id != self.config.group_id:
            return
        
        # Проверяем, что пользователь присоединился к группе
        if result.new_chat_member.status not in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            return
        
        # Игнорируем ботов
        if result.new_chat_member.user.is_bot:
            return
        
        # Проверяем, был ли пользователь ранее забанен
        user = result.new_chat_member.user
        user_id = user.id
        
        logger.info(f"Новый участник: {user_id} ({user.username or user.first_name})")
        
        # Если пользователь был ранее удален - сразу баним
        if await self.db.is_user_banned(user_id):
            logger.warning(f"Пользователь {user_id} был ранее удален, баним повторно")
            try:
                await context.bot.ban_chat_member(
                    chat_id=self.config.group_id,
                    user_id=user_id
                )
                logger.info(f"Пользователь {user_id} успешно забанен")
                
                # Уведомляем администратора
                await self.notify_admin(
                    context,
                    f"🚫 <b>Повторное вступление заблокировано</b>\n\n"
                    f"ID: <code>{user_id}</code>\n"
                    f"Username: @{user.username if user.username else 'отсутствует'}\n"
                    f"Причина: пользователь был ранее удален"
                )
                return
            except TelegramError as e:
                logger.error(f"Ошибка при бане пользователя {user_id}: {e}")
                await self.notify_admin(
                    context,
                    f"❌ <b>Ошибка при бане пользователя</b>\n\n"
                    f"ID: <code>{user_id}</code>\n"
                    f"Ошибка: {e}"
                )
                return
        
        # Получаем информацию о пользователе для логирования
        username = user.username or "без username"
        full_name = user.full_name or user.first_name or "без имени"
        
        # Применяем ограничения ко всем новым пользователям без исключений
        # Реальные комментаторы подписаны на канал, а не на группу
        # Все, кто вступает в группу напрямую - потенциальные спамеры
        logger.info(f"Новый пользователь {user_id} ({username}, {full_name}) вступил в группу, применяем ограничения")
        
        try:
            # Ограничиваем права пользователя
            await context.bot.restrict_chat_member(
                chat_id=self.config.group_id,
                user_id=user_id,
                permissions=self.restricted_permissions
            )
            
            # Добавляем в базу данных
            await self.db.add_restricted_user(
                user_id=user_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            
            logger.info(f"Пользователь {user_id} успешно ограничен и добавлен в БД")
            
            # Отправляем уведомление администратору
            await self.notify_admin(
                context,
                f"🔒 <b>Новый участник ограничен</b>\n\n"
                f"ID: <code>{user_id}</code>\n"
                f"Имя: {full_name}\n"
                f"Username: @{username if user.username else 'отсутствует'}\n"
                f"Удаление через: {self.config.restriction_period_days} дней"
            )
            
        except TelegramError as e:
            logger.error(f"Ошибка при ограничении пользователя {user_id}: {e}")
            await self.notify_admin(
                context,
                f"❌ <b>Ошибка при ограничении пользователя</b>\n\n"
                f"ID: <code>{user_id}</code>\n"
                f"Имя: {full_name}\n"
                f"Ошибка: {e}"
            )
    
    async def check_expired_restrictions(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Периодическая задача для проверки и удаления пользователей с истекшими ограничениями.
        """
        # Обновляем время проверок
        self.last_check_time = datetime.utcnow()
        self.next_check_time = self.last_check_time + timedelta(seconds=self.config.check_interval_seconds)
        
        logger.info("Запуск проверки просроченных ограничений")
        
        try:
            expired_users = await self.db.get_expired_restrictions(
                days=self.config.restriction_period_days
            )
            
            if not expired_users:
                logger.info("Не найдено пользователей с истекшими ограничениями")
                
                # Отправляем отладочное уведомление если включено
                if self.config.notify_no_users:
                    await self.notify_admin(
                        context,
                        "ℹ️ <b>Плановая проверка завершена</b>\n\n"
                        "Новых пользователей для удаления не найдено."
                    )
                return
            
            logger.info(f"Найдено {len(expired_users)} пользователей для удаления")
            
            for user in expired_users:
                user_id = user['user_id']
                username = user['username']
                
                try:
                    # Удаляем пользователя из группы (ban + unban для удаления из группы)
                    await context.bot.ban_chat_member(
                        chat_id=self.config.group_id,
                        user_id=user_id
                    )
                    
                    # Размбаниваем, чтобы пользователь мог вступить снова
                    # (но при вступлении он попадет в banned_users и будет сразу забанен)
                    await context.bot.unban_chat_member(
                        chat_id=self.config.group_id,
                        user_id=user_id
                    )
                    
                    # Перемещаем из restricted в banned
                    await self.db.add_banned_user(
                        user_id=user_id,
                        username=username,
                        first_name=user['first_name'],
                        last_name=user['last_name'],
                        reason="Истек период ограничения"
                    )
                    await self.db.remove_restricted_user(user_id)
                    
                    logger.info(f"Пользователь {user_id} ({username}) удален из группы")
                    
                    # Уведомляем администратора
                    await self.notify_admin(
                        context,
                        f"🗑️ <b>Пользователь удален из группы</b>\n\n"
                        f"ID: <code>{user_id}</code>\n"
                        f"Username: @{username if username else 'отсутствует'}\n"
                        f"Причина: истек период ограничения ({self.config.restriction_period_days} дней)"
                    )
                    
                except TelegramError as e:
                    logger.error(f"Ошибка при удалении пользователя {user_id}: {e}")
                    await self.notify_admin(
                        context,
                        f"❌ <b>Ошибка при удалении пользователя</b>\n\n"
                        f"ID: <code>{user_id}</code>\n"
                        f"Username: @{username if username else 'отсутствует'}\n"
                        f"Ошибка: {e}"
                    )
                    
        except Exception as e:
            logger.error(f"Ошибка в задаче проверки просроченных ограничений: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок."""
        logger.error(f"Ошибка при обработке обновления: {context.error}", exc_info=context.error)
    
    def build_application(self) -> Application:
        """
        Создать и настроить Application бота.
        
        Returns:
            Настроенный объект Application
        """
        # Создаем Application
        application = Application.builder().token(self.config.bot_token).build()
        
        # Регистрируем обработчики команд (только для администратора)
        application.add_handler(CommandHandler("status", self.status_command))
        
        # Регистрируем обработчик изменений статуса участников
        application.add_handler(ChatMemberHandler(
            self.track_chat_member,
            ChatMemberHandler.CHAT_MEMBER
        ))
        
        # Регистрируем обработчик ошибок
        application.add_error_handler(self.error_handler)
        
        # Добавляем периодическую задачу для проверки просроченных ограничений
        job_queue = application.job_queue
        job_queue.run_repeating(
            self.check_expired_restrictions,
            interval=self.config.check_interval_seconds,
            first=10  # Первый запуск через 10 секунд после старта
        )
        
        return application
    
    async def run(self):
        """Запустить бота."""
        logger.info("Запуск бота...")
        
        # Подключаемся к базе данных
        await self.db.connect()
        
        # Создаем Application
        self.application = self.build_application()
        
        logger.info("Бот успешно запущен и готов к работе")
        
        # Используем run_polling который сам управляет lifecycle
        async with self.application:
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=[Update.CHAT_MEMBER, Update.MESSAGE]
            )
            
            # Получаем статистику для уведомления
            stats = await self.db.get_stats()
            
            # Отправляем уведомление администратору о запуске
            if self.config.admin_user_id:
                try:
                    await self.application.bot.send_message(
                        chat_id=self.config.admin_user_id,
                        text=(
                            f"✅ <b>Бот успешно запущен</b>\n\n"
                            f"🏢 <b>Группа ID:</b> <code>{self.config.group_id}</code>\n"
                            f"👥 <b>Активных наблюдаемых:</b> {stats['restricted_users']}\n"
                            f"🚫 <b>Забанено всего:</b> {stats['banned_users']}\n"
                            f"⏱️ <b>Период ограничения:</b> {self.config.restriction_period_days} дней\n"
                            f"🔄 <b>Интервал проверок:</b> {self.config.check_interval_seconds // 60} минут"
                        ),
                        parse_mode="HTML"
                    )
                    logger.info("Уведомление о запуске отправлено администратору")
                except TelegramError as e:
                    logger.error(f"Ошибка при отправке уведомления о запуске: {e}")
            
            # Бесконечное ожидание (пока не будет Ctrl+C)
            import asyncio
            stop_event = asyncio.Event()
            
            try:
                await stop_event.wait()
            except (KeyboardInterrupt, SystemExit):
                logger.info("Получен сигнал остановки")
        
        # Закрываем соединение с БД
        await self.db.close()
        logger.info("Бот остановлен")
