"""Отправка сообщений поставщикам и клиентам (ошибки доставки не роняют бота)."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

import config

log = logging.getLogger(__name__)


async def to_suppliers(bot: Bot, text: str, reply_markup=None) -> None:
    for sid in config.SUPPLIER_IDS:
        try:
            await bot.send_message(sid, text, reply_markup=reply_markup)
        except TelegramAPIError as e:
            # например, поставщик ещё не нажал /start у бота
            log.warning("Не удалось отправить сообщение поставщику %s: %s", sid, e)


async def to_user(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except TelegramAPIError as e:
        log.warning("Не удалось отправить сообщение пользователю %s: %s", user_id, e)
