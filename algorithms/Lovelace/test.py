import re
import unittest
import json
from pathlib import Path

from algorithm import choose_meme
from thirty_memes_bot.text import normalize

MEME_NAME = re.compile(r"^(0[1-9]|[12]\d|30)_[A-Za-z0-9_]+\.(jpg|png)$")
MEMES_DIR = Path(__file__).resolve().parent / "memes"

# Одна последняя фраза, разная история, разные файлы.
HISTORY_A = ["хочу спать", "скучная лекция", "да"]
HISTORY_B = ["скоро дедлайн", "всё горит", "да"]


def _meme_names() -> set[str]:
    """Имена jpg/png в memes/ этой папки."""
    return {
        path.name
        for path in MEMES_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".png"}
    }


class TestChooseMeme(unittest.TestCase):
    """Контракт демо: форма имени, файл на диске, детерминизм, разные истории."""

    def test_filename_matches_required_pattern(self):
        """Возврат — строка вида NN_латиница.jpg или .png."""
        name = choose_meme(["база рекурсии"])
        self.assertIsInstance(name, str)
        self.assertRegex(name, MEME_NAME)

    def test_deterministic_on_repeated_call(self):
        """Одинаковое окно на двух вызовах даёт одно и то же имя."""
        messages = ["готовлюсь к сессии", "устал"]
        self.assertEqual(choose_meme(messages), choose_meme(list(messages)))

    def test_returned_file_exists_when_memes_present(self):
        """Выбранное имя есть среди файлов в memes/; пустой каталог — пропуск."""
        names = _meme_names()
        if not names:
            self.skipTest("в memes/ ещё нет картинок")
        name = choose_meme(["контрпример"])
        self.assertIn(name, names)

    def test_returns_meme_filename(self):
        """На непустом окне функция возвращает имя в договорённом формате."""
        name = choose_meme(["забыли базу"])
        self.assertIsInstance(name, str)
        self.assertRegex(name, MEME_NAME)

    def test_same_messages_same_file(self):
        """Один и тот же список реплик не меняет выбранный файл."""
        messages = ["уже считали"]
        self.assertEqual(choose_meme(messages), choose_meme(messages))

    def test_history_changes_choice(self):
        """Одно «да» после разных предысторий даёт разные файлы (HISTORY_A и HISTORY_B)."""
        self.assertGreaterEqual(len(HISTORY_A), 2)
        self.assertGreaterEqual(len(HISTORY_B), 2)
        self.assertEqual(HISTORY_A[-1], HISTORY_B[-1])
        self.assertNotEqual(HISTORY_A[:-1], HISTORY_B[:-1])
        self.assertNotEqual(choose_meme(HISTORY_A), choose_meme(HISTORY_B))


_RAW = json.loads(
    (Path(__file__).resolve().parent / "features.txt").read_text(encoding="utf-8")
)
FEATURES = {int(key): value for key, value in _RAW["memes"].items()}
META = _RAW["meta"]
FALLBACK = META["fallback"]

NO_WORDS = ["!!!???", "@#()[]{}%", "😂🔥👍", "xyzzy"]


def _words():
    """Все слова из features.txt, без повторов."""
    return sorted({word for entry in FEATURES.values() for word in entry.get("tokens", {})})


class TestFeaturesFile(unittest.TestCase):
    """features.txt согласован с memes/ и с нормализацией текста."""

    def test_features_match_memes(self):
        """В memes/ ровно 30 картинок; каждое имя из features.txt есть на диске и не повторяется."""
        self.assertEqual(len(_meme_names()), 30)
        names = [entry["name"] for entry in FEATURES.values()]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(set(names) <= _meme_names())

    def test_feature_words_are_lemmas(self):
        """Слова в features.txt записаны так, как их выдаёт normalize, иначе они никогда не совпадут."""
        bad = {word: normalize(word) for word in _words() if normalize(word) != [word]}
        self.assertEqual(bad, {}, f"слова не в форме леммы: {bad}")

    def test_every_meme_reachable(self):
        """У каждого мема, кроме заглушки, есть своё слово, на котором выбирается именно он."""
        unreachable = [
            entry["name"]
            for entry in FEATURES.values()
            if entry.get("tokens")
            and not any(choose_meme([word]) == entry["name"] for word in entry["tokens"])
        ]
        self.assertEqual(unreachable, [])


class TestChoiceRules(unittest.TestCase):
    """Правила выбора: максимум счёта, ничья, заглушка, окно истории."""

    def test_single_word_picks_max_weight_smaller_number_on_tie(self):
        """Для каждого слова словаря: выигрывает мем с наибольшим весом этого слова, при равенстве — с меньшим номером."""
        for word in _words():
            weights = {
                number: entry["tokens"][word]
                for number, entry in FEATURES.items()
                if word in entry.get("tokens", {})
            }
            best = max(weights.values())
            expected = FEATURES[min(n for n, w in weights.items() if w == best)]["name"]
            with self.subTest(word=word):
                self.assertEqual(choose_meme([word]), expected)

    def test_no_words_gives_fallback(self):
        """Знаки препинания, смайлики и незнакомое слово без истории дают заглушку."""
        for text in NO_WORDS:
            with self.subTest(text=text):
                self.assertEqual(choose_meme([text]), FALLBACK)

    def test_history_window(self):
        """Реплика без слов отвечает по истории; реплика, вышедшая за окно из пяти, уже не влияет."""
        for word in _words():
            alone = choose_meme([word])
            if alone == FALLBACK:
                continue
            with self.subTest(word=word):
                self.assertEqual(choose_meme([word, "!!!"]), alone)
                self.assertEqual(choose_meme([word] + ["!!!"] * 5), FALLBACK)


if __name__ == "__main__":
    unittest.main()
