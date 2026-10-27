#!/usr/bin/env python3
"""Generate the favicon and the link preview images.

    python scripts/make_images.py

Generated rather than drawn by hand so that a change to the wordmark or the
tagline cannot leave a stale picture behind. Everything stays in the brand's
monochrome: navy ground, white wordmark, hairline rule, no accent colour.

The link preview matters more than it looks. A product that spreads by someone
pasting a link into a chat is judged on that card before the page is opened.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "site" / "assets"
FONTS = ASSETS / "fonts"

GROUND = (11, 16, 38)          # #0B1026
WHITE = (255, 255, 255)
TEXT = (156, 163, 175)         # #9CA3AF
HAIR = (41, 47, 71)

CARDS = {
    "og.png": {
        "lang": "en",
        "tagline": "Ask your database a question.",
        "line2": "Get the table and the query behind it.",
        "foot": "The model runs on your machine  ·  besk.tech",
    },
    "og-ru.png": {
        "lang": "ru",
        "tagline": "Спросите свою базу данных словами.",
        "line2": "Получите таблицу и запрос.",
        "foot": "Модель работает на вашем компьютере  ·  besk.tech",
    },
}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def make_card(path: Path, tagline: str, line2: str, foot: str) -> None:
    # 1200x630 is what the link unfurlers crop to; anything important stays
    # well inside the edges because some of them crop further.
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), GROUND)
    d = ImageDraw.Draw(img)

    # a soft pool of light behind the wordmark, the only "effect" the brand allows
    glow = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glow)
    for i in range(70, 0, -1):
        gd.ellipse(
            [w * 0.5 - i * 9, h * 0.34 - i * 5, w * 0.5 + i * 9, h * 0.34 + i * 5],
            fill=int(16 * (1 - i / 70)),
        )
    img = Image.composite(Image.new("RGB", (w, h), (24, 32, 62)), img, glow)
    d = ImageDraw.Draw(img)

    pad = 72
    d.text((pad, 96), "ASKBASE", font=font("Inter-900.ttf", 108), fill=WHITE)
    d.line([(pad, 252), (w - pad, 252)], fill=HAIR, width=1)

    d.text((pad, 300), tagline, font=font("Inter-900.ttf", 44), fill=WHITE)
    d.text((pad, 362), line2, font=font("Inter-900.ttf", 44), fill=WHITE)

    d.line([(pad, h - 132), (w - pad, h - 132)], fill=HAIR, width=1)
    d.text((pad, h - 104), foot, font=font("Inter-400.ttf", 26), fill=TEXT)

    img.save(path, "PNG", optimize=True)
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} КБ")


# The mark: rows of a result with a cursor on the first one. Same drawing as the
# one in the site header, so the tab icon and the logo are one thing.
ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28">
  <rect width="28" height="28" rx="7" fill="#0B1026"/>
  <path d="M7 10.5h8.4" stroke="#fff" stroke-width="1.9" stroke-linecap="round"/>
  <path d="M7 14.5h12" stroke="#fff" stroke-opacity=".72" stroke-width="1.9" stroke-linecap="round"/>
  <path d="M7 18.5h5.6" stroke="#fff" stroke-opacity=".42" stroke-width="1.9" stroke-linecap="round"/>
  <rect x="17.7" y="8.7" width="1.7" height="3.6" rx=".85" fill="#fff"/>
</svg>
"""


def make_icons() -> None:
    (ASSETS / "icon.svg").write_text(ICON, encoding="utf-8")
    print("site/assets/icon.svg")
    # PNG fallbacks: Safari's pinned tabs and older Android ignore SVG icons.
    for size in (32, 180, 512):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        r = round(size * 0.25)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=GROUND)
        k = size / 28
        bar = max(1, round(1.9 * k))
        for y, alpha, length in ((10.5, 255, 8.4), (14.5, 184, 12), (18.5, 107, 5.6)):
            d.line([(7 * k, y * k), ((7 + length) * k, y * k)],
                   fill=(255, 255, 255, alpha), width=bar)
        d.rounded_rectangle([17.7 * k, 8.7 * k, 19.4 * k, 12.3 * k],
                            radius=max(1, round(0.85 * k)), fill=WHITE)
        name = {32: "favicon-32.png", 180: "apple-touch-icon.png", 512: "icon-512.png"}[size]
        img.save(ASSETS / name, "PNG", optimize=True)
        print(f"site/assets/{name}")


if __name__ == "__main__":
    make_icons()
    for name, w in CARDS.items():
        make_card(ASSETS / name, w["tagline"], w["line2"], w["foot"])
