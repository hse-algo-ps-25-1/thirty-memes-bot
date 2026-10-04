import logging

from thirty_memes_bot.settings import Settings
from thirty_memes_bot.telegram.app import build_application

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)


def main() -> None:
    settings = Settings()
    if not settings.admin_user_ids:
        raise SystemExit("ADMIN_USER_IDS не должен быть пустым")
    application = build_application(settings)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
