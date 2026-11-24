from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

import config


class IsSupplier(BaseFilter):
    """Пропускает только поставщиков (Telegram ID из SUPPLIER_IDS)."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user is not None and event.from_user.id in config.SUPPLIER_IDS
