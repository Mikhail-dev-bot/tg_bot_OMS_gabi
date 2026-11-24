"""Рисует таблицу заказов картинкой (PNG), чтобы поставщик видел её как скриншот."""
import io
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

import config
import utils

# (заголовок, ширина колонки)
COLUMNS = [
    ("№", 60),
    ("Получение", 190),
    ("ФИО", 250),
    ("Телефон", 250),
    ("Заказ", 430),
    ("Сумма", 120),
    ("Статус", 190),
]
PAD = 12
FONT_SIZE = 20
ROWS_PER_IMAGE = 12

BG = (255, 255, 255)
HEAD_BG = (101, 67, 51)
HEAD_FG = (255, 255, 255)
ZEBRA = (248, 243, 238)
GRID = (214, 200, 190)
TEXT = (40, 30, 25)
STATUS_COLORS = {
    "new": (0, 102, 204),
    "confirmed": (200, 120, 0),
    "done": (30, 130, 60),
    "cancelled": (180, 40, 40),
}


def _wrap(font, text: str, max_w: float) -> list[str]:
    lines: list[str] = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = word if not cur else cur + " " + word
            if font.getlength(cand) <= max_w:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            # слишком длинное слово режем по символам
            while font.getlength(word) > max_w:
                cut = len(word)
                while cut > 1 and font.getlength(word[:cut]) > max_w:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            cur = word
        lines.append(cur)
    return lines or [""]


def _render_chunk(rows, title: str, page_info: str) -> bytes:
    font = ImageFont.truetype(str(config.FONT_REGULAR), FONT_SIZE)
    bold = ImageFont.truetype(str(config.FONT_BOLD), FONT_SIZE)
    title_font = ImageFont.truetype(str(config.FONT_BOLD), FONT_SIZE + 6)
    line_h = FONT_SIZE + 8
    width = sum(w for _, w in COLUMNS)

    # содержимое ячеек
    table = []
    for r in rows:
        items = utils.order_items(r)
        cells = [
            f"{r['id']}",
            utils.fmt_pickup(r["pickup"]).replace(" ", "\n"),
            r["full_name"],
            r["phone"],
            "\n".join(f"{n} × {q}" for n, q, _ in items),
            utils.money(r["total"]),
            utils.STATUS_PLAIN[r["status"]],
        ]
        wrapped = [_wrap(font, c, w - 2 * PAD) for c, (_, w) in zip(cells, COLUMNS)]
        h = max(len(w) for w in wrapped) * line_h + 2 * PAD - 8
        table.append((r, wrapped, h))

    title_h = 56
    head_h = line_h + 2 * PAD - 8
    height = title_h + head_h + sum(h for _, _, h in table) + 1
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    d.text((PAD, 14), f"{title}  {page_info}".strip(), font=title_font, fill=TEXT)
    y = title_h
    d.rectangle([0, y, width, y + head_h], fill=HEAD_BG)
    x = 0
    for name, w in COLUMNS:
        d.text((x + PAD, y + PAD - 4), name, font=bold, fill=HEAD_FG)
        x += w
    y += head_h

    for i, (r, wrapped, h) in enumerate(table):
        if i % 2 == 1:
            d.rectangle([0, y, width, y + h], fill=ZEBRA)
        x = 0
        for ci, (lines, (_, w)) in enumerate(zip(wrapped, COLUMNS)):
            color = STATUS_COLORS[r["status"]] if ci == len(COLUMNS) - 1 else TEXT
            f = bold if ci in (0, len(COLUMNS) - 1) else font
            ty = y + PAD - 4
            for ln in lines:
                d.text((x + PAD, ty), ln, font=f, fill=color)
                ty += line_h
            x += w
        d.line([0, y + h, width, y + h], fill=GRID, width=1)
        y += h

    x = 0
    for _, w in COLUMNS:
        d.line([x, title_h, x, height], fill=GRID, width=1)
        x += w
    d.line([width - 1, title_h, width - 1, height], fill=GRID, width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_table(rows, title: str) -> list[bytes]:
    """Возвращает список PNG: по ROWS_PER_IMAGE заказов на картинку."""
    stamp = datetime.now().strftime("%d.%m.%Y")
    chunks = [rows[i : i + ROWS_PER_IMAGE] for i in range(0, len(rows), ROWS_PER_IMAGE)]
    out = []
    for n, chunk in enumerate(chunks, 1):
        info = f"({n}/{len(chunks)})" if len(chunks) > 1 else ""
        out.append(_render_chunk(chunk, f"{title} · {stamp}", info))
    return out
