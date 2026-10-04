import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from thirty_memes_bot.loader import ModuleLoadError
from thirty_memes_bot.registry import Registry


def _write(path: Path, name: str, text: str) -> None:
    """Пишет файл в временную папку модуля."""
    target = path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


class TestRegistry(unittest.TestCase):
    """Список папок в algorithms/ и переключение активного модуля."""

    def test_lists_ready_and_broken(self):
        """Готовая папка помечается ready, папка без algorithm.py — нет."""
        with TemporaryDirectory() as raw:
            root = Path(raw)
            ready = root / "alpha"
            _write(ready, "algorithm.py", "def choose_meme(messages):\n    return '01_a.jpg'\n")
            (ready / "memes").mkdir()
            broken = root / "beta"
            broken.mkdir()
            registry = Registry(root)
            names = {item.name: item for item in registry.list_modules()}
            self.assertTrue(names["alpha"].ready)
            self.assertFalse(names["beta"].ready)

    def test_use_missing_folder(self):
        """Запрос несуществующей папки поднимает ModuleLoadError."""
        with TemporaryDirectory() as raw:
            registry = Registry(Path(raw))
            with self.assertRaises(ModuleLoadError):
                registry.use("nope")

    def test_use_loads_function(self):
        """use загружает choose_meme из папки и запоминает её как текущую."""
        with TemporaryDirectory() as raw:
            root = Path(raw)
            demo = root / "demo"
            _write(
                demo,
                "algorithm.py",
                "def choose_meme(messages):\n    return '01_a.jpg'\n",
            )
            (demo / "memes").mkdir()
            (demo / "memes" / "01_a.jpg").write_bytes(b"x")
            registry = Registry(root)
            loaded = registry.use("demo")
            self.assertEqual(loaded.choose_meme(["привет"]), "01_a.jpg")
            self.assertEqual(registry.current_name, "demo")
