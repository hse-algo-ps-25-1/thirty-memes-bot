import json
from pathlib import Path

from thirty_memes_bot.text import normalize

FEATURES_NAME = "features.txt"


def _features_path() -> Path:
    return Path(__file__).resolve().parent / FEATURES_NAME


def _load_features() -> dict[int, dict]:
    """ Читает JSON-файл с признаками мемов.
    Возвращает словарь вида: {1: {"name": "01.jpg", "tokens": {...}}, ...}
    """
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
    if not messages:
        return "30_einstein.jpg"
    
    normalized_history = [normalize(message) for message in messages]

    recency_weights = [1.0, 0.6, 0.4, 0.2, 0.1]
    features = _load_features()
    best_meme_filename = "30_einstein.jpg"
    max_score = 0.0

    for meme_id, data in features.items():
        meme_tokens = data.get("tokens", {})
        if not meme_tokens:
            continue
        current_score = 0.0
        for i, msg_tokens in enumerate(reversed(normalized_history)):
            if i >= len(recency_weights):
                break
            weight = recency_weights[i]

            for token in set(msg_tokens):
                if token in meme_tokens:
                    current_score += weight * meme_tokens[token]
        if current_score > max_score:
            max_score = current_score
            best_meme_filename = data["name"]

    return best_meme_filename