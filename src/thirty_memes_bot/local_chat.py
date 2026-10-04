from __future__ import annotations

import argparse
from pathlib import Path

from thirty_memes_bot.loader import ModuleLoadError, meme_path
from thirty_memes_bot.registry import Registry
from thirty_memes_bot.session import SessionStore
from thirty_memes_bot.settings import repo_root

QUIT = {"выход", "exit", "quit"}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Локальный диалог без Telegram")
    parser.add_argument(
        "module",
        nargs="?",
        default="demo",
        help="имя папки в algorithms/",
    )
    args = parser.parse_args(argv)
    registry = Registry(repo_root() / "algorithms")
    try:
        loaded = registry.use(args.module)
    except ModuleLoadError as exc:
        raise SystemExit(str(exc)) from exc
    sessions = SessionStore()
    log_path = Path.cwd() / "dialog_log.txt"
    print(f"Модуль {loaded.name}. Реплика, для выхода: выход")
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        text = line.strip()
        if text.lower() in QUIT:
            break
        if not text:
            continue
        history = sessions.push(0, 0, text)
        try:
            name = loaded.choose_meme(history)
        except Exception as exc:
            print(f"ошибка: {type(exc).__name__}: {exc}")
            continue
        path = meme_path(loaded, name)
        if not path.is_file():
            print(f"нет файла {name!r} в memes/")
            continue
        print(name)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"пользователь: {text}\nмем: {name}\n")


if __name__ == "__main__":
    main()
