import hashlib
import json
from pathlib import Path

from thirty_memes_bot.text import normalize

FEATURES_NAME = "features.txt"
SEPARATOR = "\n"
BUCKETS = 30


def _features_path() -> Path:
    return Path(__file__).resolve().parent / FEATURES_NAME


def _load_table() -> dict[int, str]:
    raw = json.loads(_features_path().read_text(encoding="utf-8"))
    return {int(key): value for key, value in raw.items()}


def choose_meme(messages: list[str]) -> str:
    """Выбирает имя файла мема по окну реплик.

    messages — реплики по времени, последняя — текущая, список непустой.
    Возвращает имя файла из memes/, например "04_base_case.jpg".
    Детерминировано: одинаковый messages даёт одинаковый файл.

    :param messages: непустой список текстовых реплик
    :return: имя существующего файла из memes/
    """
    parts = [" ".join(normalize(message)) for message in messages]
    text = SEPARATOR.join(parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    bucket = int(digest, 16) % BUCKETS + 1
    return _load_table()[bucket]
