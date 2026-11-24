"""Настройки бота. Всё секретное берётся из переменных окружения (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Токен от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Telegram ID поставщиков через запятую, например: 123456789,987654321
# Узнать свой ID можно у бота @userinfobot
SUPPLIER_IDS = {
    int(x) for x in os.getenv("SUPPLIER_IDS", "").replace(" ", "").split(",") if x.isdigit()
}

# Реквизиты для предоплаты (показываются клиенту после заказа)
PAY_PHONE = os.getenv("PAY_PHONE", "+7 000 000-00-00")
PAY_BANK = os.getenv("PAY_BANK", "Банк")
PREPAY_PERCENT = int(os.getenv("PREPAY_PERCENT", "50"))

# Путь к базе SQLite. На Render укажите путь на постоянном диске, например /var/data/orders.db
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "orders.db"))

# Часовой пояс, по которому считаются даты заказа
TZ = os.getenv("TZ_NAME", "Europe/Moscow")

# Заказ можно оформить не раньше чем через N дней
MIN_DAYS_AHEAD = int(os.getenv("MIN_DAYS_AHEAD", "2"))
# Сколько ближайших дат показывать кнопками
DATE_BUTTON_DAYS = int(os.getenv("DATE_BUTTON_DAYS", "8"))

MAX_QTY = 100

PRICE_IMAGE = BASE_DIR / "assets" / "price.jpg"
FONT_REGULAR = BASE_DIR / "fonts" / "DejaVuSans.ttf"
FONT_BOLD = BASE_DIR / "fonts" / "DejaVuSans-Bold.ttf"
