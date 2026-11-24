"""Сценарий клиента: прайс, оформление заказа, мои заказы."""
from datetime import date

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message, ReplyKeyboardRemove

import catalog
import config
import db
import notify
import ui
import utils

router = Router()


class OrderFSM(StatesGroup):
    browsing = State()
    qty_input = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


# ---------- общие помощники ----------

def _is_supplier(user_id: int) -> bool:
    return user_id in config.SUPPLIER_IDS


def _msg(target: Message | CallbackQuery) -> Message:
    return target.message if isinstance(target, CallbackQuery) else target


async def render(target: Message | CallbackQuery, text: str, kb=None) -> None:
    """Для кнопки правит текущее сообщение, для текста присылает новое."""
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                await target.message.answer(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def _error(message: Message, text: str) -> None:
    await message.answer("⚠️ " + text)


# ---------- меню, прайс ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    is_sup = _is_supplier(message.from_user.id)
    text = (
        "Здравствуйте! 👋\n"
        "Здесь можно посмотреть прайс и оформить заказ.\n\n"
        f"{ui.BTN_ORDER}: собрать заказ\n"
        f"{ui.BTN_PRICE}: посмотреть цены\n"
        f"{ui.BTN_MY}: ваши заказы"
    )
    if is_sup:
        text += f"\n\nВы вошли как поставщик.\n{ui.BTN_ORDERS}: активные заказы\n{ui.BTN_ARCHIVE}: все заказы"
    await message.answer(text, reply_markup=ui.main_menu(is_sup))


@router.message(F.text == ui.BTN_PRICE)
async def show_price(message: Message) -> None:
    if config.PRICE_IMAGE.exists():
        await message.answer_photo(FSInputFile(config.PRICE_IMAGE), caption="Прайс")
    else:
        lines = [f"• {i['name']}: {utils.money(i['price'])}" for i in catalog.ITEMS]
        await message.answer("Прайс:\n" + "\n".join(lines))


@router.message(F.text == ui.BTN_MY)
async def my_orders(message: Message) -> None:
    await show_my_orders(message, message.from_user.id)


# ---------- корзина ----------

async def show_cart(target: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    cart, editing = data.get("cart", {}), data.get("editing", False)
    await state.set_state(OrderFSM.browsing)
    await render(target, ui.cart_text(cart, editing), ui.cart_kb(cart, editing))


@router.message(F.text == ui.BTN_ORDER)
async def start_order(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(cart={}, editing=False)
    await show_cart(message, state)


@router.callback_query(F.data.startswith("item:"))
async def pick_item(cb: CallbackQuery, state: FSMContext) -> None:
    idx = int(cb.data.split(":")[1])
    cart = (await state.get_data()).get("cart", {})
    qty = cart.get(str(idx), 1)
    await state.update_data(cur_item=idx, cur_qty=qty)
    await state.set_state(OrderFSM.browsing)
    await render(cb, ui.qty_text(idx, qty), ui.qty_kb(qty))
    await cb.answer()


@router.callback_query(F.data.in_({"qty:inc", "qty:dec"}))
async def change_qty(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    idx = data.get("cur_item")
    if idx is None:
        await cb.answer("Откройте меню заказа заново", show_alert=True)
        return
    qty = data.get("cur_qty", 1)
    qty = min(qty + 1, config.MAX_QTY) if cb.data == "qty:inc" else max(qty - 1, 1)
    await state.update_data(cur_qty=qty)
    await render(cb, ui.qty_text(idx, qty), ui.qty_kb(qty))
    await cb.answer()


@router.callback_query(F.data == "qty:noop")
async def qty_noop(cb: CallbackQuery) -> None:
    await cb.answer()


@router.callback_query(F.data == "qty:input")
async def qty_input_start(cb: CallbackQuery, state: FSMContext) -> None:
    idx = (await state.get_data()).get("cur_item")
    if idx is None:
        await cb.answer("Откройте меню заказа заново", show_alert=True)
        return
    await state.set_state(OrderFSM.qty_input)
    await render(
        cb,
        f"{catalog.ITEMS[idx]['name']}\n\nНапишите количество числом (от 1 до {config.MAX_QTY}):",
        ui.qty_input_kb(),
    )
    await cb.answer()


@router.message(OrderFSM.qty_input, F.text)
async def qty_input_done(message: Message, state: FSMContext) -> None:
    try:
        qty = utils.parse_qty(message.text)
    except utils.InputError as e:
        await _error(message, str(e))
        return
    data = await state.get_data()
    cart = dict(data.get("cart", {}))
    cart[str(data["cur_item"])] = qty
    await state.update_data(cart=cart)
    await show_cart(message, state)


@router.callback_query(F.data == "qty:add")
async def qty_add(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    idx = data.get("cur_item")
    if idx is None:
        await cb.answer("Откройте меню заказа заново", show_alert=True)
        return
    cart = dict(data.get("cart", {}))
    cart[str(idx)] = data.get("cur_qty", 1)
    await state.update_data(cart=cart)
    await show_cart(cb, state)
    await cb.answer("Добавлено ✅")


@router.callback_query(F.data == "qty:back")
async def qty_back(cb: CallbackQuery, state: FSMContext) -> None:
    await show_cart(cb, state)
    await cb.answer()


@router.callback_query(F.data.startswith("cartdel:"))
async def cart_del(cb: CallbackQuery, state: FSMContext) -> None:
    key = cb.data.split(":")[1]
    cart = dict((await state.get_data()).get("cart", {}))
    cart.pop(key, None)
    await state.update_data(cart=cart)
    await show_cart(cb, state)
    await cb.answer()


@router.callback_query(F.data == "cart:clear")
async def cart_clear(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(cart={})
    await show_cart(cb, state)
    await cb.answer("Корзина очищена")


@router.callback_query(F.data == "cart:next")
async def cart_next(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("cart"):
        await cb.answer("Корзина пуста", show_alert=True)
        return
    await cb.answer()
    if data.get("editing"):
        await show_confirm(cb, state)
    else:
        await ask_date(cb, state)


# ---------- дата и время ----------

async def ask_date(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderFSM.date)
    low = utils.min_date()
    await render(
        target,
        f"📅 Выберите дату получения кнопкой или напишите её (ДД.ММ).\n"
        f"Самая ранняя дата: {low:%d.%m.%Y}",
        ui.date_kb(),
    )


async def _set_date(target: Message | CallbackQuery, state: FSMContext, d: date) -> None:
    await state.update_data(date=d.isoformat())
    await state.set_state(OrderFSM.time)
    await render(
        target,
        f"Дата: {d:%d.%m.%Y}\n\n🕒 Напишите время получения в формате ЧЧ:ММ, например 14:30",
    )


@router.callback_query(F.data.startswith("date:"))
async def pick_date(cb: CallbackQuery, state: FSMContext) -> None:
    try:
        d = date.fromisoformat(cb.data.split(":", 1)[1])
    except ValueError:
        await cb.answer()
        return
    if d < utils.min_date():
        await cb.answer("Эта дата уже недоступна, выберите другую", show_alert=True)
        await ask_date(cb, state)
        return
    await cb.answer()
    await _set_date(cb, state, d)


@router.message(OrderFSM.date, F.text)
async def type_date(message: Message, state: FSMContext) -> None:
    try:
        d = utils.parse_date(message.text)
    except utils.InputError as e:
        await _error(message, str(e))
        return
    await _set_date(message, state, d)


@router.message(OrderFSM.time, F.text)
async def type_time(message: Message, state: FSMContext) -> None:
    try:
        t = utils.parse_time(message.text)
    except utils.InputError as e:
        await _error(message, str(e))
        return
    await state.update_data(time=t)
    if (await state.get_data()).get("editing"):
        await show_confirm(message, state)
    else:
        await ask_name(message, state)


# ---------- ФИО и телефон ----------

async def ask_name(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderFSM.name)
    saved = db.get_user(target.from_user.id)
    saved_name = saved["full_name"] if saved and saved["full_name"] else None
    await _msg(target).answer(
        "👤 Напишите фамилию и имя, например: Иванов Иван",
        reply_markup=ui.single_reply(saved_name) if saved_name else None,
    )


@router.message(OrderFSM.name, F.text)
async def type_name(message: Message, state: FSMContext) -> None:
    try:
        name = utils.parse_name(message.text)
    except utils.InputError as e:
        await _error(message, str(e))
        return
    await state.update_data(name=name)
    if (await state.get_data()).get("editing"):
        await message.answer("Принято ✅", reply_markup=ui.main_menu(_is_supplier(message.from_user.id)))
        await show_confirm(message, state)
    else:
        await ask_phone(message, state)


async def ask_phone(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderFSM.phone)
    saved = db.get_user(target.from_user.id)
    saved_phone = saved["phone"] if saved and saved["phone"] else None
    await _msg(target).answer(
        "📞 Отправьте номер телефона кнопкой ниже или напишите его, например +7 999 123-45-67",
        reply_markup=ui.phone_reply(saved_phone),
    )


async def _phone_done(message: Message, state: FSMContext, raw: str) -> None:
    try:
        phone = utils.parse_phone(raw)
    except utils.InputError as e:
        await _error(message, str(e))
        return
    await state.update_data(phone=phone)
    await message.answer("Принято ✅", reply_markup=ui.main_menu(_is_supplier(message.from_user.id)))
    await show_confirm(message, state)


@router.message(OrderFSM.phone, F.contact)
async def phone_contact(message: Message, state: FSMContext) -> None:
    await _phone_done(message, state, message.contact.phone_number)


@router.message(OrderFSM.phone, F.text)
async def phone_text(message: Message, state: FSMContext) -> None:
    await _phone_done(message, state, message.text)


# ---------- подтверждение ----------

def _summary(data: dict) -> str:
    cart = data["cart"]
    items = [(catalog.ITEMS[int(k)]["name"], q, catalog.ITEMS[int(k)]["price"]) for k, q in cart.items()]
    total = sum(q * p for _, q, p in items)
    d = date.fromisoformat(data["date"])
    return (
        "📝 Проверьте заказ\n\n"
        f"{utils.items_lines(items)}\n"
        f"Итого: {utils.money(total)}\n\n"
        f"📅 Получение: {d:%d.%m.%Y} в {data['time']}\n"
        f"👤 {data['name']}\n"
        f"📞 {data['phone']}"
    )


async def show_confirm(target: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    missing = [k for k in ("cart", "date", "time", "name", "phone") if not data.get(k)]
    if missing:
        # не хватает данных: продолжаем с первого незаполненного шага
        await state.update_data(editing=False)
        if missing[0] == "cart":
            await show_cart(target, state)
        elif missing[0] in ("date", "time"):
            await ask_date(target, state)
        elif missing[0] == "name":
            await ask_name(target, state)
        else:
            await ask_phone(target, state)
        return
    await state.update_data(editing=False)
    await state.set_state(OrderFSM.confirm)
    await render(target, _summary(data), ui.confirm_kb())


@router.callback_query(F.data == "ord:edit")
async def order_edit(cb: CallbackQuery) -> None:
    await render(cb, "Что изменить?", ui.edit_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("edit:"))
async def edit_choice(cb: CallbackQuery, state: FSMContext) -> None:
    what = cb.data.split(":")[1]
    await cb.answer()
    if what == "back":
        await show_confirm(cb, state)
        return
    await state.update_data(editing=True)
    if what == "items":
        await show_cart(cb, state)
    elif what == "dt":
        await ask_date(cb, state)
    elif what == "name":
        await ask_name(cb, state)
    elif what == "phone":
        await ask_phone(cb, state)


@router.callback_query(F.data == "ord:done")
async def order_done(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not all(data.get(k) for k in ("cart", "date", "time", "name", "phone")):
        await cb.answer("Заказ не найден. Нажмите «🛒 Заказ» и оформите заново.", show_alert=True)
        return
    d = date.fromisoformat(data["date"])
    if d < utils.min_date():
        await cb.answer("Выбранная дата уже недоступна, выберите новую.", show_alert=True)
        await state.update_data(editing=True)
        await ask_date(cb, state)
        return

    items = [
        [catalog.ITEMS[int(k)]["name"], q, catalog.ITEMS[int(k)]["price"]] for k, q in data["cart"].items()
    ]
    total = sum(q * p for _, q, p in items)
    user = cb.from_user
    order_id = db.create_order(
        user.id, user.username, items, total, f"{d.isoformat()} {data['time']}", data["name"], data["phone"]
    )
    db.save_user(user.id, data["name"], data["phone"])
    await state.clear()

    row = db.get_order(order_id)
    await cb.answer("Заказ оформлен ✅")
    await render(cb, utils.order_text(row) + "\n\n" + utils.prepay_block(total))
    await notify.to_suppliers(
        cb.bot, "🆕 Новый заказ!\n\n" + utils.order_text(row, for_supplier=True), ui.supplier_status_kb(row)
    )


# ---------- мои заказы ----------

async def show_my_orders(target: Message | CallbackQuery, user_id: int) -> None:
    rows = db.list_orders(user_id=user_id, limit=8, newest_first=True)
    if not rows:
        await render(target, "У вас пока нет заказов.")
        return
    text = "📦 Ваши заказы (последние):\n\n" + "\n\n———\n\n".join(utils.order_text(r) for r in rows)
    await render(target, text, ui.my_orders_kb(rows))


@router.callback_query(F.data.startswith("my:cancel:"))
async def my_cancel(cb: CallbackQuery) -> None:
    oid = int(cb.data.split(":")[2])
    row = db.get_order(oid)
    if not row or row["user_id"] != cb.from_user.id:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    if row["status"] != "new":
        await cb.answer("Этот заказ уже нельзя отменить. Свяжитесь с поставщиком.", show_alert=True)
        await show_my_orders(cb, cb.from_user.id)
        return
    db.set_status(oid, "cancelled")
    await cb.answer("Заказ отменён")
    await show_my_orders(cb, cb.from_user.id)
    await notify.to_suppliers(cb.bot, f"❌ Клиент отменил заказ №{oid}\n\n" + utils.order_text(db.get_order(oid), True))
