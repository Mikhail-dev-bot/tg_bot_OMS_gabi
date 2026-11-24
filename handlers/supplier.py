"""Сценарий поставщика: список заказов, таблица-картинка, смена статусов."""
import asyncio

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import db
import notify
import table_image
import ui
import utils
from filters import IsSupplier

router = Router()
router.message.filter(IsSupplier())
router.callback_query.filter(IsSupplier())

CLIENT_NOTICES = {
    "confirmed": "✅ Ваш заказ №{id} подтверждён.",
    "done": "📦 Ваш заказ №{id} выполнен. Спасибо!",
    "cancelled": "❌ Заказ №{id} отменён поставщиком. Если это ошибка, свяжитесь с нами.",
}


def _chunk_texts(texts: list[str], limit: int = 3800) -> list[str]:
    parts, cur = [], ""
    for t in texts:
        piece = t if not cur else cur + "\n\n———\n\n" + t
        if len(piece) > limit and cur:
            parts.append(cur)
            cur = t
        else:
            cur = piece
    if cur:
        parts.append(cur)
    return parts


async def send_orders(bot: Bot, chat_id: int, active_only: bool) -> None:
    rows = db.list_orders(active_only=active_only)
    if not rows:
        await bot.send_message(chat_id, "Активных заказов нет." if active_only else "Заказов пока нет.")
        return

    title = "Активные заказы" if active_only else "Все заказы"
    images = await asyncio.to_thread(table_image.render_table, rows, title)
    for i, png in enumerate(images, 1):
        caption = f"{title}: {len(rows)}" if i == 1 else None
        await bot.send_photo(chat_id, BufferedInputFile(png, filename=f"orders_{i}.png"), caption=caption)

    if active_only:
        for r in rows:
            await bot.send_message(
                chat_id, utils.order_text(r, for_supplier=True), reply_markup=ui.supplier_status_kb(r)
            )
    else:
        for part in _chunk_texts([utils.order_text(r, for_supplier=True) for r in rows]):
            await bot.send_message(chat_id, part)


@router.message(F.text == ui.BTN_ORDERS)
async def active_orders(message: Message) -> None:
    await send_orders(message.bot, message.chat.id, active_only=True)


@router.message(F.text == ui.BTN_ARCHIVE)
async def all_orders(message: Message) -> None:
    await send_orders(message.bot, message.chat.id, active_only=False)


@router.callback_query(F.data.startswith("st:"))
async def change_status(cb: CallbackQuery) -> None:
    _, oid_s, new = cb.data.split(":")
    oid = int(oid_s)
    row = db.get_order(oid)
    if not row:
        await cb.answer("Заказ не найден", show_alert=True)
        return

    text_for = lambda r: utils.order_text(r, for_supplier=True)  # noqa: E731

    if new not in utils.TRANSITIONS.get(row["status"], ()):
        # другой поставщик уже поменял статус: обновляем сообщение актуальными данными
        await cb.answer("Статус уже изменён, обновил сообщение", show_alert=True)
        try:
            await cb.message.edit_text(text_for(row), reply_markup=ui.supplier_status_kb(row))
        except TelegramBadRequest:
            pass
        return

    db.set_status(oid, new)
    row = db.get_order(oid)
    try:
        await cb.message.edit_text(text_for(row), reply_markup=ui.supplier_status_kb(row))
    except TelegramBadRequest:
        pass
    await cb.answer("Готово")
    await notify.to_user(cb.bot, row["user_id"], CLIENT_NOTICES[new].format(id=oid))
