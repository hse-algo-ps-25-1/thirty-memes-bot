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
        # Если множества пересекаются (найдено хотя бы одно совпадение)
        if not lemmas.isdisjoint(keywords):
            return category
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

    #Нормализация
    current_lemmas = set(normalize(current_msg))

    history_lemmas = set()
    for msg in history_msgs:
        history_lemmas.update(normalize(msg))

    #Определение класса
    intent = _match_category(current_lemmas, features.get("classes", {}))

    #Определение контекста
    context = _match_category(history_lemmas, features.get("contexts", {}))

    routing = features.get("routing", {})

    # Ищем блок правил
    intent_rules = routing.get(intent, routing.get("DEFAULT", {}))

    # Ищем картинку. Картинка 30 - заглушка
    meme_file = intent_rules.get(context, intent_rules.get("DEFAULT", "30_fallback.jpg"))

    return meme_file