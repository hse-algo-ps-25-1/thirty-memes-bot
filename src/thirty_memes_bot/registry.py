from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from thirty_memes_bot.loader import LoadedModule, ModuleLoadError, inspect_module, load_module


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    ready: bool
    detail: str = ""


class Registry:
    def __init__(self, algorithms_dir: Path, default: str = "demo") -> None:
        self.algorithms_dir = algorithms_dir
        self._default = default
        self._current: LoadedModule | None = None

    @property
    def current(self) -> LoadedModule:
        if self._current is None:
            raise ModuleLoadError("активный модуль не выбран")
        return self._current

    @property
    def current_name(self) -> str | None:
        return None if self._current is None else self._current.name

    def list_modules(self) -> list[ModuleInfo]:
        if not self.algorithms_dir.is_dir():
            return []
        items: list[ModuleInfo] = []
        for path in sorted(self.algorithms_dir.iterdir(), key=lambda p: p.name):
            if not path.is_dir() or path.name.startswith("."):
                continue
            reason = inspect_module(path)
            if reason:
                items.append(ModuleInfo(path.name, ready=False, detail=reason))
            else:
                items.append(ModuleInfo(path.name, ready=True))
        return items

    def use(self, name: str) -> LoadedModule:
        root = self.algorithms_dir / name
        if not root.is_dir():
            raise ModuleLoadError(f"модуль {name}: папки нет")
        loaded = load_module(name, root)
        self._current = loaded
        return loaded

    def use_default(self) -> LoadedModule:
        return self.use(self._default)
