import os
from thirty_memes_bot.text import normalize

def load_features_and_threshold():
    """
    Парсит features.txt.
    Возвращает:
        threshold (float): минимальный скор для срабатывания.
        meme_data (dict): словарь вида {имя_файла: множество_токенов}.
    """
    current_dir = os.path.dirname(__file__)
    features_path = os.path.join(current_dir, 'features.txt')

    threshold = 0.1  # Дефолтное значение, если не найдено в файле
    meme_data = {}

    if not os.path.exists(features_path):
        # Если файла нет, возвращаем пустые структуры (для отказоустойчивости)
        return threshold, meme_data

    with open(features_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Пропускаем пустые строки и комментарии
            if not line or line.startswith('#'):
                continue

            # Парсим строку мема (разделитель '|')
            if '|' in line:
                parts = line.split('|')
                filename = parts[0].strip()
                if filename == "порог":
                    threshold = float(parts[1].strip())
                    continue
                # Собираем все слова после черты в одно множество токенов
                keywords = set(parts[1].strip().lower().split())
                meme_data[filename] = keywords

    return threshold, meme_data


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """
    Вычисляет коэффициент Жаккара между двумя множествами строк.
    Возвращает число от 0.0 до 1.0.
    """
    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))

    return float(intersection) / union


def find_leader(words, meme_data):
    best_name = None
    best = -1
    second = -1

    for name, keywords in meme_data.items():
        s = jaccard_similarity(words, keywords)

        if s > best:
            second = best
            best = s
            best_name = name
        elif s > second:
            second = s

    return best_name, best, second


def choose_meme(messages):
    # 1. Загрузка порога и данных мемов
    threshold, meme_data = load_features_and_threshold()

    # 2. Слова последней реплики
    last = set(normalize(messages[-1]))

    # 3. Поиск лидера по последней реплике
    name, best, second = find_leader(last, meme_data)

    # 4. Проверка уверенного лидера
    if best > 0 and (best - second) > threshold:
        return name

    # 5. Иначе собираем контекст («общая коробка»)
    window = set()
    for m in messages:
        window |= set(normalize(m))

    # 6. Повторный поиск лидера по всему окну контекста
    name, best, second = find_leader(window, meme_data)

    # 7. Если совпадений вообще нет
    if best == 0:
        return "30_confused.jpg"

    # 8. Возврат имени мема во всех остальных случаях
    return name
