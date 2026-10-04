from __future__ import annotations

import traceback


def format_exception(exc: BaseException, module_name: str) -> str:
    text = "".join(traceback.format_exception(exc))
    return f"Ошибка модуля {module_name}:\n{type(exc).__name__}: {exc}\n\n{text}"


def missing_meme(module_name: str, filename: str) -> str:
    return (
        f"Модуль {module_name} вернул имя, которого нет в memes/: {filename!r}. "
        "Картинку не отправляю."
    )
