import unittest

from thirty_memes_bot.text import lemmatize, normalize, tokenize


class TestText(unittest.TestCase):
    """Нарезка и леммы: подготовка текста, не выбор мема."""

    def test_tokenize_drops_punctuation_and_case(self):
        """Знаки и регистр не порождают отдельные токены."""
        self.assertEqual(tokenize("База, рекурсии!"), ["база", "рекурсии"])

    def test_tokenize_keeps_digits(self):
        """Числа остаются токенами; знак между цифрой и буквой режет."""
        self.assertEqual(tokenize("лекция 2"), ["лекция", "2"])
        self.assertEqual(tokenize("2^n"), ["2", "n"])

    def test_lemmatize_unifies_cases(self):
        """Разные падежи одного слова дают одну лемму."""
        self.assertEqual(lemmatize(["базу", "базы", "база"]), ["база", "база", "база"])

    def test_normalize_joins_both_steps(self):
        """«Забыли базу» и «забыть базы» совпадают после нормализации."""
        self.assertEqual(normalize("Забыли базу!"), normalize("забыть базы"))

    def test_normalize_empty_punctuation(self):
        """Строка из знаков даёт пустой список, не ошибку."""
        self.assertEqual(normalize("..."), [])
