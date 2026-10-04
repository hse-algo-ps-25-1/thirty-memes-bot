from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from thirty_memes_bot.loader import ModuleLoadError, meme_path
from thirty_memes_bot.registry import Registry
from thirty_memes_bot.session import SessionStore
from thirty_memes_bot.settings import Settings
from thirty_memes_bot.telegram.errors import format_exception, missing_meme


def _registry(context: ContextTypes.DEFAULT_TYPE) -> Registry:
    return context.application.bot_data["registry"]


def _sessions(context: ContextTypes.DEFAULT_TYPE) -> SessionStore:
    return context.application.bot_data["sessions"]


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    return user is not None and user.id in _settings(context).admin_user_ids


async def _reject_if_not_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if _is_admin(update, context):
        return False
    if update.effective_message:
        await update.effective_message.reply_text("Эта команда доступна только преподавателю.")
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    await update.effective_message.reply_text(
        "Напишите текст — бот ответит мемом активной реализации."
    )


async def teams(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_if_not_admin(update, context) or not update.effective_message:
        return
    registry = _registry(context)
    modules = registry.list_modules()
    if not modules:
        await update.effective_message.reply_text("В algorithms/ нет папок.")
        return
    current = registry.current_name
    lines = []
    for item in modules:
        mark = " (текущая)" if item.name == current else ""
        if item.ready:
            lines.append(f"• {item.name}{mark}")
        else:
            lines.append(f"• {item.name}{mark} — не подключается: {item.detail}")
    await update.effective_message.reply_text("\n".join(lines))


async def who(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_if_not_admin(update, context) or not update.effective_message:
        return
    name = _registry(context).current_name
    if name is None:
        await update.effective_message.reply_text("Активный модуль не выбран.")
        return
    await update.effective_message.reply_text(f"Сейчас: {name}")


async def use(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _reject_if_not_admin(update, context) or not update.effective_message:
        return
    if not context.args:
        await update.effective_message.reply_text("Укажите папку: /use demo")
        return
    name = context.args[0]
    registry = _registry(context)
    if registry.current_name == name:
        await update.effective_message.reply_text(f"Уже активен: {name}")
        return
    try:
        registry.use(name)
    except ModuleLoadError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    _sessions(context).clear_all()
    await update.effective_message.reply_text(f"Сейчас: {name}")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if message is None or user is None or chat is None or not message.text:
        return
    text = message.text.strip()
    if not text:
        return
    registry = _registry(context)
    try:
        loaded = registry.current
    except ModuleLoadError as exc:
        await message.reply_text(str(exc))
        return
    history = _sessions(context).push(chat.id, user.id, text)
    try:
        filename = loaded.choose_meme(history)
    except Exception as exc:
        await message.reply_text(format_exception(exc, loaded.name))
        return
    if not isinstance(filename, str) or not filename:
        await message.reply_text(
            f"Модуль {loaded.name} вернул не имя файла: {filename!r}."
        )
        return
    path = meme_path(loaded, filename)
    if not path.is_file():
        await message.reply_text(missing_meme(loaded.name, filename))
        return
    await message.reply_photo(photo=path, caption=filename)
