from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=repo_root() / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str
    admin_user_ids: list[int]

    @property
    def algorithms_dir(self) -> Path:
        return repo_root() / "algorithms"
