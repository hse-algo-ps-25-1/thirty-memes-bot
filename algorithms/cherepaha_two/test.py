import re
import unittest
from pathlib import Path

from algorithm import choose_meme

MEME_NAME = re.compile(r"^(0[1-9]|[12]\d|30)_[A-Za-z0-9_]+\.(jpg|png)$")
MEMES_DIR = Path(__file__).resolve().parent / "memes"

# Одна последняя фраза, разная история, разные файлы.
HISTORY_A = ["мне тяжело сдать", "да"]
HISTORY_B = ["сдал с первой попытки", "да"]


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
        messages = ["локально зелёные", "Checks красные"]
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


if __name__ == "__main__":
    unittest.main()
