"""Работа с базой SQLite: пользователи и заказы."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id   INTEGER PRIMARY KEY,
    full_name TEXT,
    phone     TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    user_id    INTEGER NOT NULL,
    username   TEXT,
    items_json TEXT NOT NULL,
    total      INTEGER NOT NULL,
    pickup     TEXT NOT NULL,          -- 'YYYY-MM-DD HH:MM'
    full_name  TEXT NOT NULL,
    phone      TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'new'
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
"""

ACTIVE_STATUSES = ("new", "confirmed")


@contextmanager
def _conn():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init() -> None:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.executescript(SCHEMA)


def now_local() -> datetime:
    return datetime.now(ZoneInfo(config.TZ))


def get_user(user_id: int):
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def save_user(user_id: int, full_name: str, phone: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO users (user_id, full_name, phone) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET full_name = excluded.full_name, phone = excluded.phone",
            (user_id, full_name, phone),
        )


def create_order(user_id, username, items, total, pickup, full_name, phone) -> int:
    """items: список [название, количество, цена за штуку]."""
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO orders (created_at, user_id, username, items_json, total, pickup, full_name, phone) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                now_local().strftime("%Y-%m-%d %H:%M:%S"),
                user_id,
                username,
                json.dumps(items, ensure_ascii=False),
                total,
                pickup,
                full_name,
                phone,
            ),
        )
        return cur.lastrowid


def get_order(order_id: int):
    with _conn() as c:
        return c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def list_orders(active_only=False, user_id=None, limit=None, newest_first=False):
    sql = "SELECT * FROM orders WHERE 1=1"
    params: list = []
    if active_only:
        sql += " AND status IN (%s)" % ",".join("?" * len(ACTIVE_STATUSES))
        params += list(ACTIVE_STATUSES)
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY id " + ("DESC" if newest_first else "ASC")
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    with _conn() as c:
        return c.execute(sql, params).fetchall()


def set_status(order_id: int, status: str) -> None:
    with _conn() as c:
        c.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
