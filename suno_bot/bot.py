"""Telegram-бот для генерации музыки через SunoAPI."""

import asyncio
import logging
from contextlib import asynccontextmanager

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config
from suno_api import SunoAPI, SunoAPIError, GenerationResult

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Хранилище режима instrumental по user_id (в проде лучше Redis/БД)
user_instrumental: dict[int, bool] = {}


def get_instrumental(user_id: int) -> bool:
    return user_instrumental.get(user_id, False)


def set_instrumental(user_id: int, value: bool) -> None:
    user_instrumental[user_id] = value


@asynccontextmanager
async def lifespan(app: Application):
    """Graceful startup/shutdown."""
    logger.info("Bot starting...")
    yield
    logger.info("Bot shutting down...")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик /start."""
    text = """
🎵 *Привет! Я бот для генерации музыки через Suno AI.*

*Как пользоваться:*
Просто отправь текстовое описание песни. Например:
• «грустная песня про расставание в стиле инди-рок»
• «весёлый джаз про утро в Париже»
• «эпичный саундтрек для фэнтези-игры»

Генерация занимает ~1–2 минуты. Я пришлю готовые треки.

*Команды:*
/balance — остаток кредитов
/instrumental — переключить режим без вокала (инструментал)
"""
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик /balance."""
    config: Config = context.bot_data["config"]
    api = SunoAPI(config.suno_api_key, config.suno_base_url)

    try:
        balance = await api.get_balance()
        await update.message.reply_text(f"💰 Остаток кредитов: *{balance}*", parse_mode="Markdown")
    except SunoAPIError as e:
        logger.exception("Balance check failed")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def cmd_instrumental(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик /instrumental — переключить режим без вокала."""
    user_id = update.effective_user.id if update.effective_user else 0
    new_val = not get_instrumental(user_id)
    set_instrumental(user_id, new_val)

    status = "включён (без вокала)" if new_val else "выключен (с вокалом)"
    await update.message.reply_text(f"🎹 Режим instrumental: *{status}*", parse_mode="Markdown")


async def poll_until_complete(
    api: SunoAPI,
    task_id: str,
    poll_interval: int,
    timeout: int,
) -> GenerationResult:
    """Поллить статус до завершения или таймаута."""
    elapsed = 0
    while elapsed < timeout:
        result = await api.get_status(task_id)
        if result.status == "SUCCESS":
            return result
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError("Генерация превысила 5 минут")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений — генерация песни."""
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Отправь описание песни текстом.")
        return

    config: Config = context.bot_data["config"]
    api = SunoAPI(config.suno_api_key, config.suno_base_url)
    user_id = update.effective_user.id if update.effective_user else 0
    instrumental = get_instrumental(user_id)

    status_msg = await update.message.reply_text(
        "⏳ Генерирую песню, подождите ~1–2 минуты..."
    )

    try:
        task_id = await api.generate(
            prompt=text,
            title="Generated",
            instrumental=instrumental,
        )
    except SunoAPIError as e:
        logger.exception("Generate failed")
        await status_msg.edit_text(f"❌ Ошибка генерации: {e}")
        return

    try:
        result = await poll_until_complete(
            api,
            task_id,
            config.poll_interval_sec,
            config.generation_timeout_sec,
        )
    except TimeoutError as e:
        await status_msg.edit_text(f"⏱ {e}. Попробуйте позже.")
        return
    except SunoAPIError as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")
        return

    # Отправляем каждую песню
    for song in result.songs:
        if not song.audio_url:
            continue
        caption_parts = [f"🎵 *{song.title}*"]
        if song.prompt:
            caption_parts.append(f"\n{song.prompt[:500]}")
        caption = "\n".join(caption_parts)

        try:
            await update.message.reply_audio(
                audio=song.audio_url,
                title=song.title,
                caption=caption[:1024],
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning("Failed to send audio, trying as document: %s", e)
            try:
                await update.message.reply_document(
                    document=song.audio_url,
                    caption=caption[:1024],
                )
            except Exception as e2:
                logger.exception("Failed to send: %s", e2)
                await update.message.reply_text(
                    f"Не удалось отправить аудио. Ссылка: {song.audio_url}"
                )

    await status_msg.delete()


def main() -> None:
    """Запуск бота."""
    config = Config.from_env()

    app = (
        Application.builder()
        .token(config.telegram_bot_token)
        .post_init(lambda app: app.bot_data.update({"config": config}))
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("instrumental", cmd_instrumental))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
