import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from thirty_memes_bot.loader import ModuleLoadError, inspect_module, load_module, meme_path


class TestLoader(unittest.TestCase):
    """Проверка каркаса папки и загрузка algorithm.py по пути."""

    def test_inspect_missing_algorithm(self):
        """Без algorithm.py инспекция возвращает причину, а не молчаливый успех."""
        with TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "memes").mkdir()
            self.assertEqual(inspect_module(root), "нет algorithm.py")

    def test_load_without_choose_meme(self):
        """Файл есть, функции choose_meme нет — загрузка отвергается."""
        with TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "algorithm.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "memes").mkdir()
            with self.assertRaises(ModuleLoadError):
                load_module("x", root)

    def test_meme_path(self):
        """Имя файла из choose_meme склеивается с memes/ этой папки, не с чужой."""
        with TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "algorithm.py").write_text(
                "def choose_meme(messages):\n    return '01_a.jpg'\n",
                encoding="utf-8",
            )
            (root / "memes").mkdir()
            loaded = load_module("x", root)
            self.assertEqual(meme_path(loaded, "01_a.jpg"), root / "memes" / "01_a.jpg")
