from __future__ import annotations

import re
from functools import lru_cache

import pymorphy3

# Буквы (в том числе кириллица) и цифры; знаки и подчёркивание не входят.
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


@lru_cache(maxsize=1)
def _analyzer() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer()


def tokenize(text: str) -> list[str]:
    """Режет текст на слова и приводит их к нижнему регистру.

    Знаки препинания отбрасываются, последовательности цифр остаются токенами.
    Это нарезка, не выбор мема.
    """
    return [match.group(0).casefold() for match in _TOKEN.finditer(text)]


def lemmatize(tokens: list[str]) -> list[str]:
    """Заменяет каждое слово словарной формой (леммой).

    «Базу», «базы» и «база» дают одну лемму. Анализатор один на процесс.
    """
    morph = _analyzer()
    return [morph.parse(token)[0].normal_form for token in tokens]


def normalize(text: str) -> list[str]:
    """Токены, затем леммы: стандартный вид реплики для алгоритма выбора."""
    return lemmatize(tokenize(text))
