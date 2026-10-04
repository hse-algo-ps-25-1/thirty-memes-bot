import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from thirty_memes_bot.registry import Registry
from thirty_memes_bot.session import SessionStore
from thirty_memes_bot.settings import Settings
from thirty_memes_bot.telegram import handlers

logger = logging.getLogger(__name__)


async def _on_started(application: Application) -> None:
    me = await application.bot.get_me()
    module = application.bot_data["registry"].current_name
    logger.info("Бот успешно запущен: @%s, активный модуль %s", me.username, module)


def build_application(settings: Settings) -> Application:
    registry = Registry(settings.algorithms_dir)
    registry.use_default()
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_on_started)
        .build()
    )
    application.bot_data["settings"] = settings
    application.bot_data["registry"] = registry
    application.bot_data["sessions"] = SessionStore()
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("teams", handlers.teams))
    application.add_handler(CommandHandler("who", handlers.who))
    application.add_handler(CommandHandler("use", handlers.use))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
    return application
