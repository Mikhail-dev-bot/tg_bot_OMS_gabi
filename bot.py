"""Точка входа: запускает бота (long polling) и маленький HTTP-сервер для Render."""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiohttp import web

import config
import db
from handlers import client, supplier

log = logging.getLogger("bot")


async def start_health_server() -> web.AppRunner | None:
    """Render для Web Service ждёт открытый порт. Отвечаем «ok» на GET /."""
    port = os.getenv("PORT")
    if not port:
        return None

    async def ok(_request):
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", ok)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(port)).start()
    log.info("Health-сервер запущен на порту %s", port)
    return runner


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Укажите его в .env или в переменных окружения.")
    if not config.SUPPLIER_IDS:
        log.warning("SUPPLIER_IDS пуст: никто не получит заказы. Укажите Telegram ID поставщиков.")

    db.init()
    bot = Bot(config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    # Поставщик первым: его кнопки обрабатываются раньше клиентских
    dp.include_routers(supplier.router, client.router)

    await bot.set_my_commands([BotCommand(command="start", description="Главное меню")])
    runner = await start_health_server()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        if runner:
            await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
