from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class ModuleLoadError(Exception):
    pass


@dataclass(frozen=True)
class LoadedModule:
    name: str
    root: Path
    memes_dir: Path
    choose_meme: Callable[[list[str]], str]


def inspect_module(root: Path) -> str | None:
    """Возвращает причину, почему папку нельзя подключить, либо None."""
    if not (root / "algorithm.py").is_file():
        return "нет algorithm.py"
    if not (root / "memes").is_dir():
        return "нет каталога memes/"
    return None


def load_module(name: str, root: Path) -> LoadedModule:
    reason = inspect_module(root)
    if reason:
        raise ModuleLoadError(f"модуль {name}: {reason}")

    path = root / "algorithm.py"
    spec = importlib.util.spec_from_file_location(f"thirty_memes_impl_{name}", path)
    if spec is None or spec.loader is None:
        raise ModuleLoadError(f"модуль {name}: не удалось прочитать algorithm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    choose = getattr(module, "choose_meme", None)
    if not callable(choose):
        raise ModuleLoadError(f"модуль {name}: нет функции choose_meme")
    return LoadedModule(
        name=name,
        root=root,
        memes_dir=root / "memes",
        choose_meme=choose,
    )


def meme_path(loaded: LoadedModule, filename: str) -> Path:
    return loaded.memes_dir / filename
