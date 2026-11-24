"""Тексты кнопок и клавиатуры."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import catalog
import config
import utils

BTN_ORDER = "🛒 Заказ"
BTN_PRICE = "💰 Прайс"
BTN_MY = "📦 Мои заказы"
BTN_ORDERS = "📋 Заказы"
BTN_ARCHIVE = "🗂 Все заказы"
BTN_SHARE_PHONE = "📱 Отправить мой номер"


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu(is_supplier: bool) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=BTN_ORDER), KeyboardButton(text=BTN_PRICE)], [KeyboardButton(text=BTN_MY)]]
    if is_supplier:
        rows.append([KeyboardButton(text=BTN_ORDERS), KeyboardButton(text=BTN_ARCHIVE)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def single_reply(text: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=text)]], resize_keyboard=True, one_time_keyboard=True)


def phone_reply(saved_phone: str | None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=BTN_SHARE_PHONE, request_contact=True)]]
    if saved_phone:
        rows.append([KeyboardButton(text=saved_phone)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


# ---------- корзина ----------

def cart_text(cart: dict, editing: bool = False) -> str:
    head = "Выберите товар из меню 👇"
    if not cart:
        return head + "\n\n🛒 Корзина пуста"
    lines, total = [], 0
    for key, qty in cart.items():
        item = catalog.ITEMS[int(key)]
        lines.append(f"• {item['name']} × {qty} = {utils.money(qty * item['price'])}")
        total += qty * item["price"]
    return f"{head}\n\n🛒 Корзина:\n" + "\n".join(lines) + f"\n\nИтого: {utils.money(total)}"


def cart_kb(cart: dict, editing: bool = False) -> InlineKeyboardMarkup:
    rows, pair = [], []
    for i, item in enumerate(catalog.ITEMS):
        pair.append(_b(f"{item['btn']} · {item['price']} ₽", f"item:{i}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    for key, qty in cart.items():
        rows.append([_b(f"❌ Убрать: {catalog.ITEMS[int(key)]['btn']} × {qty}", f"cartdel:{key}")])
    if cart:
        rows.append([_b("✅ К заказу" if editing else "✅ Далее", "cart:next")])
        rows.append([_b("🗑 Очистить корзину", "cart:clear")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def qty_text(idx: int, qty: int) -> str:
    item = catalog.ITEMS[idx]
    return (
        f"{item['name']}\nЦена: {utils.money(item['price'])} за штуку\n\n"
        f"Количество: {qty}\nСумма: {utils.money(qty * item['price'])}"
    )


def qty_kb(qty: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_b("−", "qty:dec"), _b(str(qty), "qty:noop"), _b("+", "qty:inc")],
            [_b("✏️ Ввести число", "qty:input")],
            [_b("➕ Добавить в заказ", "qty:add")],
            [_b("⬅️ Назад к меню", "qty:back")],
        ]
    )


def qty_input_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b("⬅️ Отмена", "qty:back")]])


# ---------- дата ----------

def date_kb() -> InlineKeyboardMarkup:
    start = utils.min_date()
    from datetime import timedelta

    rows, pair = [], []
    for i in range(config.DATE_BUTTON_DAYS):
        d = start + timedelta(days=i)
        pair.append(_b(utils.date_label(d), f"date:{d.isoformat()}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- подтверждение ----------

def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_b("✏️ Редактировать", "ord:edit"), _b("✅ Готово", "ord:done")]]
    )


def edit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_b("🛒 Товары", "edit:items")],
            [_b("📅 Дата и время", "edit:dt")],
            [_b("👤 ФИО", "edit:name"), _b("📞 Телефон", "edit:phone")],
            [_b("⬅️ Назад", "edit:back")],
        ]
    )


# ---------- заказы ----------

def supplier_status_kb(row) -> InlineKeyboardMarkup | None:
    oid, st = row["id"], row["status"]
    if st == "new":
        return InlineKeyboardMarkup(
            inline_keyboard=[[_b("✅ Подтвердить", f"st:{oid}:confirmed"), _b("❌ Отклонить", f"st:{oid}:cancelled")]]
        )
    if st == "confirmed":
        return InlineKeyboardMarkup(
            inline_keyboard=[[_b("📦 Выполнен", f"st:{oid}:done"), _b("❌ Отменить", f"st:{oid}:cancelled")]]
        )
    return None


def my_orders_kb(rows) -> InlineKeyboardMarkup | None:
    buttons = [[_b(f"❌ Отменить заказ №{r['id']}", f"my:cancel:{r['id']}")] for r in rows if r["status"] == "new"]
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
