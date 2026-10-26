"""Shared value pools for every holdout domain.

Held here rather than taken from Faker so that the output does not move when
Faker's own data files are updated. A locale upgrade silently changing a frozen
set is the same class of bug as a shifting "today", and the set is hashed.

Country-neutral by the decision of 20.10.2026: the product is global, so the
names, cities and currencies read as international and carry no national
identifier formats or local legislation. The difficulty of a domain has to come
from its schema, not from locale trivia a model either memorised or did not.
"""
from __future__ import annotations

FIRST = ("Anna", "Mark", "Elena", "Pavel", "Irina", "Victor", "Olga", "Daniel",
         "Sofia", "Timur", "Vera", "Igor", "Alina", "Boris", "Nina", "Artem")
LAST = ("Kovach", "Reiner", "Almeida", "Bauer", "Novak", "Linde", "Marek",
        "Soto", "Hale", "Varga", "Petran", "Oduya", "Kristof", "Benali")
CITY = ("Northport", "Eastvale", "Marden", "Lowick", "Thorne", "Avelin")


def person(rng) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"
