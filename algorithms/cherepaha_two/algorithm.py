import json
from pathlib import Path

from thirty_memes_bot.text import normalize

FEATURES_NAME = "features.txt"


def _features_path() -> Path:
    return Path(__file__).resolve().parent / FEATURES_NAME


def _load_features() -> dict:
    """Загружает базу знаний (классы, контексты, маршруты) из JSON-файла."""
    path = _features_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _match_category(lemmas: set[str], categories: dict[str, list[str]]) -> str:
    """
    Находит первую подходящую категорию.
    Возвращает имя категории, если есть пересечение множеств лемм, иначе "DEFAULT".
    """
    for category, keywords in categories.items():
        if category == "DEFAULT":
            continue
        if not lemmas.isdisjoint(keywords):
            return category
    return "DEFAULT"


def _match_context_from_history(
    history_msgs: list[str], contexts: dict[str, list[str]]
) -> str:
    """
    Ищет контекст в предыстории, начиная с самых свежих реплик.
    Как только тема найдена в более новом сообщении, поиск прекращается.
    """
    for msg in reversed(history_msgs):
        msg_lemmas = set(normalize(msg))
        matched = _match_category(msg_lemmas, contexts)
        if matched != "DEFAULT":
            return matched
    return "DEFAULT"


def choose_meme(messages: list[str]) -> str:
    """Выбирает имя файла мема по окну реплик на основе двухуровневой модели.

    messages — реплики по времени, последняя — текущая, список непустой.
    Возвращает имя файла из memes/, например "04_base_case.jpg".
    Детерминировано: одинаковый messages даёт одинаковый файл.
    """
    features = _load_features()

    history_msgs = messages[:-1]
    current_msg = messages[-1]

    # 1. Уровень 1: Определяем класс (интент) по последней реплике
    current_lemmas = set(normalize(current_msg))
    intent = _match_category(current_lemmas, features.get("classes", {}))

    # 2. Уровень 2: Определяем контекст по предыстории (с приоритетом свежих реплик)
    context = _match_context_from_history(messages, features.get("contexts", {}))

    # 3. Маршрутизация по матрице
    routing = features.get("routing", {})

    # Ищем правила для найденного интента.
    fallback_rules = routing.get("DEFAULT", routing.get("QUESTION", {}))
    intent_rules = routing.get(intent, fallback_rules)

    # Выбираем мем по контексту, при отсутствии — берем DEFAULT внутри этой ветки
    meme_file = intent_rules.get(
        context, intent_rules.get("DEFAULT", "30_base_wat.jpg")
    )

    return meme_file