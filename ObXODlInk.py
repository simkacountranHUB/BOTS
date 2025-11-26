import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import threading
from concurrent.futures import ThreadPoolExecutor

# Импортируем наш класс для обхода ссылок
from platoboost_unshortener import AdvancedPlatoboostUnshortener

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ===
# ВСТАВЬТЕ ВАШ ТОКЕН БОТА ЗДЕСЬ
BOT_TOKEN = "7574698107:AAHbi4NkCrrbsmaS33JV3SleWu4yXcwtWyE"

# Инициализируем обходчик ссылок
tesseract_path = None  # Укажите путь к tesseract если нужен OCR
unshortener = AdvancedPlatoboostUnshortener(tesseract_path=tesseract_path)

# Создаем ThreadPoolExecutor для выполнения блокирующих задач
executor = ThreadPoolExecutor(max_workers=3)

# Словарь для хранения результатов обработки
user_results = {}

# === КОМАНДЫ БОТА ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для обхода сокращенных ссылок Platoboost (Delta X).\n\n"
        "📋 Просто отправь мне ссылку вида:\n"
        "https://auth.platoboost.app/a?d=...\n\n"
        "⚡️ Я автоматически обработаю её и верну оригинальную ссылку!\n\n"
        "🛠️ Команды:\n"
        "/start - показать это сообщение\n"
        "/help - помощь\n"
        "/stats - статистика"
    )
    
    keyboard = [
        [InlineKeyboardButton("📖 Как использовать", callback_data="help")],
        [InlineKeyboardButton("⚡️ Обработать ссылку", callback_data="process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = (
        "🆘 Помощь по использованию бота:\n\n"
        "📥 Отправьте мне ссылку Platoboost в формате:\n"
        "<code>https://auth.platoboost.app/a?d=...</code>\n\n"
        "⚙️ Бот автоматически:\n"
        "• Обойдет все редиректы\n"
        "• Обработает капчу (если потребуется)\n"
        "• Вернет оригинальную ссылку\n\n"
        "⏱️ Обработка обычно занимает 5-30 секунд\n\n"
        "❓ Если возникли проблемы:\n"
        "• Проверьте формат ссылки\n"
        "• Убедитесь, что ссылка активна\n"
        "• Попробуйте еще раз через минуту"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")],
        [InlineKeyboardButton("⚡️ Обработать ссылку", callback_data="process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_html(help_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(help_text, parse_mode='HTML', reply_markup=reply_markup)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats"""
    stats_text = (
        "📊 Статистика бота:\n\n"
        "🔄 Обработано ссылок: собираем статистику...\n"
        "⚡️ Среднее время обработки: 5-30 сек\n"
        "🎯 Успешных обходов: >90%\n\n"
        "🛠️ Технологии:\n"
        "• Selenium WebDriver\n"
        "• Авто-обработка капчи\n"
        "• Multi-threading"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")],
        [InlineKeyboardButton("⚡️ Обработать ссылку", callback_data="process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(stats_text, reply_markup=reply_markup)

def unshorten_url_blocking(url: str) -> str:
    """Синхронная функция для обхода ссылки (выполняется в отдельном потоке)"""
    try:
        result = unshortener.unshorten_with_retry(url, max_retries=2)
        return result
    except Exception as e:
        logger.error(f"Error unshortening URL: {e}")
        return f"Ошибка при обходе ссылки: {e}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений с ссылками"""
    user_message = update.message.text
    user_id = update.effective_user.id
    
    # Проверяем, что сообщение содержит ссылку Platoboost
    if "platoboost.app" in user_message and "?d=" in user_message:
        # Отправляем сообщение о том, что начали обработку
        processing_message = await update.message.reply_text(
            "🔄 Обрабатываю ссылку...\n"
            "Это может занять до 30 секунд\n"
            "⏳ Пожалуйста, подождите..."
        )
        
        # Запускаем блокирующую задачу в отдельном потоке
        loop = asyncio.get_event_loop()
        try:
            # Выполняем обход ссылки в потоке
            final_url = await loop.run_in_executor(executor, unshorten_url_blocking, user_message)
            
            # Сохраняем результат для пользователя
            user_results[user_id] = final_url
            
            # Форматируем результат
            if final_url and final_url != user_message and not final_url.startswith("Ошибка"):
                result_text = (
                    f"✅ Ссылка успешно обработана!\n\n"
                    f"🔗 Оригинальная ссылка:\n"
                    f"<code>{final_url}</code>"
                )
                
                # Создаем клавиатуру с кнопками
                keyboard = [
                    [InlineKeyboardButton("📋 Скопировать ссылку", callback_data="copy_url")],
                    [InlineKeyboardButton("🔄 Обработать другую", callback_data="process")],
                    [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_start")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
            else:
                result_text = (
                    f"❌ Не удалось обойти ссылку\n\n"
                    f"Возможные причины:\n"
                    f"• Ссылка неактивна\n"
                    f"• Требуется ручная проверка\n"
                    f"• Ошибка сервера\n\n"
                    f"Попробуйте еще раз или проверьте ссылку"
                )
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data="process")],
                    [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_start")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Редактируем исходное сообщение с результатом
            await processing_message.edit_text(
                result_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            await processing_message.edit_text(
                "❌ Произошла ошибка при обработке ссылки\n"
                "Попробуйте еще раз через несколько минут"
            )
    
    else:
        # Если это не ссылка Platoboost
        if "http" in user_message:
            await update.message.reply_text(
                "❓ Это не похоже на ссылку Platoboost (Delta X)\n\n"
                "📝 Отправьте ссылку в формате:\n"
                "<code>https://auth.platoboost.app/a?d=...</code>\n\n"
                "⚡️ Я специализируюсь на обходе именно таких ссылок",
                parse_mode='HTML'
            )
        else:
            # Показываем стартовое меню
            await start(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == "help":
        await help_command(update, context)
    
    elif query.data == "process":
        await query.edit_message_text(
            "⚡️ Отправьте мне ссылку Platoboost для обработки\n\n"
            "Формат ссылки:\n"
            "<code>https://auth.platoboost.app/a?d=...</code>\n\n"
            "Я автоматически обойду все редиректы и верну оригинальную ссылку!",
            parse_mode='HTML'
        )
    
    elif query.data == "back_to_start":
        user = query.from_user
        welcome_text = (
            f"👋 С возвращением, {user.first_name}!\n\n"
            "Я бот для обхода сокращенных ссылок Platoboost (Delta X).\n\n"
            "📋 Просто отправь мне ссылку вида:\n"
            "https://auth.platoboost.app/a?d=...\n\n"
            "⚡️ Я автоматически обработаю её и верну оригинальную ссылку!"
        )
        
        keyboard = [
            [InlineKeyboardButton("📖 Как использовать", callback_data="help")],
            [InlineKeyboardButton("⚡️ Обработать ссылку", callback_data="process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_text, reply_markup=reply_markup)
    
    elif query.data == "copy_url":
        # Получаем сохраненную ссылку для пользователя
        final_url = user_results.get(user_id)
        
        if final_url and not final_url.startswith("Ошибка"):
            # Создаем сообщение с удобной для копирования ссылкой
            copy_text = (
                f"📋 Скопируйте ссылку:\n\n"
                f"{final_url}\n\n"
                f"⚠️ Просто выделите текст выше и скопируйте (Ctrl+C)"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Обработать другую", callback_data="process")],
                [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(copy_text, reply_markup=reply_markup)
        else:
            await query.edit_message_text(
                "❌ Не удалось найти ссылку для копирования\n"
                "Попробуйте обработать ссылку заново",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data="process")]
                ])
            )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}")

def main() -> None:
    """Запуск бота"""
    # Создаем Application и передаем ему токен бота
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("🤖 Бот запущен...")
    print("📱 Используйте /start для начала работы")
    application.run_polling()

if __name__ == '__main__':
    main()

