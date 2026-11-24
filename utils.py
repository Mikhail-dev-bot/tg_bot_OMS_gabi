"""Вспомогательные функции: форматирование и проверка ввода."""
import json
import re
from datetime import date, datetime, timedelta

import config
import db

STATUS_LABELS = {
    "new": "🆕 Новый",
    "confirmed": "✅ Подтверждён",
    "done": "📦 Выполнен",
    "cancelled": "❌ Отменён",
}
# Для таблицы-картинки (в шрифте нет эмодзи)
STATUS_PLAIN = {
    "new": "Новый",
    "confirmed": "Подтверждён",
    "done": "Выполнен",
    "cancelled": "Отменён",
}
# Допустимые переходы статусов
TRANSITIONS = {
    "new": ("confirmed", "cancelled"),
    "confirmed": ("done", "cancelled"),
}

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


class InputError(Exception):
    """Ошибка пользовательского ввода: текст показывается пользователю."""


# ---------- форматирование ----------

def money(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " ₽"


def prepay_amount(total: int) -> int:
    return (total * config.PREPAY_PERCENT + 99) // 100


def fmt_pickup(pickup: str) -> str:
    d = datetime.strptime(pickup, "%Y-%m-%d %H:%M")
    return d.strftime("%d.%m.%Y %H:%M")


def fmt_created(created: str) -> str:
    return datetime.strptime(created, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")


def order_items(row) -> list:
    return json.loads(row["items_json"])


def items_lines(items) -> str:
    return "\n".join(f"• {n} × {q} = {money(q * p)}" for n, q, p in items)


def order_text(row, for_supplier: bool = False) -> str:
    items = order_items(row)
    lines = [
        f"📦 Заказ №{row['id']} · {STATUS_LABELS[row['status']]}",
        items_lines(items),
        f"Итого: {money(row['total'])}",
        f"📅 Получение: {fmt_pickup(row['pickup'])}",
        f"👤 {row['full_name']}",
        f"📞 {row['phone']}",
    ]
    if for_supplier:
        lines.insert(3, f"Предоплата {config.PREPAY_PERCENT}%: {money(prepay_amount(row['total']))}")
        if row["username"]:
            lines.append(f"✉️ @{row['username']}")
        lines.append(f"🕒 Создан: {fmt_created(row['created_at'])}")
    return "\n".join(lines)


def prepay_block(total: int) -> str:
    return (
        f"Предоплата {config.PREPAY_PERCENT}% на банковскую карту по:\n"
        f"{config.PAY_PHONE} - {config.PAY_BANK}\n"
        f"Сумма: {money(total)}\n"
        f"Предоплата: {money(prepay_amount(total))}"
    )


# ---------- даты ----------

def min_date() -> date:
    return db.now_local().date() + timedelta(days=config.MIN_DAYS_AHEAD)


def date_label(d: date) -> str:
    return f"{d:%d.%m} ({WEEKDAYS[d.weekday()]})"


def parse_date(text: str) -> date:
    m = re.fullmatch(r"\s*(\d{1,2})[./\-](\d{1,2})(?:[./\-](\d{2}|\d{4}))?\s*", text or "")
    if not m:
        raise InputError("Не понял дату. Напишите в формате ДД.ММ или ДД.ММ.ГГГГ, например 25.11")
    day, month = int(m.group(1)), int(m.group(2))
    today = db.now_local().date()
    year_s = m.group(3)
    try:
        if year_s:
            year = int(year_s) + (2000 if len(year_s) == 2 else 0)
            d = date(year, month, day)
        else:
            d = date(today.year, month, day)
            if d < today:
                d = date(today.year + 1, month, day)
    except ValueError:
        raise InputError("Такой даты не существует. Проверьте и напишите ещё раз.")
    low = min_date()
    if d < low:
        raise InputError(
            f"Заказ можно оформить не раньше чем через {config.MIN_DAYS_AHEAD} дня. "
            f"Самая ранняя дата: {low:%d.%m.%Y}."
        )
    return d


def parse_time(text: str) -> str:
    m = re.fullmatch(r"\s*(\d{1,2})\s*[:.\-]?\s*(\d{2})\s*", text or "")
    if not m:
        raise InputError("Не понял время. Напишите в формате ЧЧ:ММ, например 14:30")
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise InputError("Такого времени не бывает. Напишите в формате ЧЧ:ММ, например 14:30")
    return f"{h:02d}:{mi:02d}"


# ---------- контакты ----------

_NAME_RE = re.compile(r"[A-Za-zА-Яа-яЁё\-\.' ]+")


def parse_name(text: str) -> str:
    name = " ".join((text or "").split())
    if len(name) > 60 or not _NAME_RE.fullmatch(name):
        raise InputError("Напишите фамилию и имя буквами, например: Иванов Иван")
    if len(name.split()) < 2:
        raise InputError("Нужны фамилия и имя, например: Иванов Иван")
    return name


def parse_phone(text: str) -> str:
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    elif len(digits) != 10:
        raise InputError("Не понял номер. Напишите в формате +7 999 123-45-67")
    return f"+7 ({digits[:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:]}"


def parse_qty(text: str) -> int:
    t = (text or "").strip()
    if not t.isdigit() or not (1 <= int(t) <= config.MAX_QTY):
        raise InputError(f"Нужно целое число от 1 до {config.MAX_QTY}.")
    return int(t)
