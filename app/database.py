# app/database.py

MENU = [
    {"name": "Куба Либре",       "price": 15, "ingredients": ["кола", "лёд", "ром"]},
    {"name": "Отвёртка",         "price": 12, "ingredients": ["водка", "сок"]},
    {"name": "Джин-тоник",       "price": 14, "ingredients": ["джин", "лёд", "тоник"]},
    {"name": "Виски-кола",       "price": 13, "ingredients": ["виски", "кола"]},
    {"name": "Текила-санрайз",   "price": 14, "ingredients": ["сок", "текила"]},
    {"name": "Русский",          "price": 10, "ingredients": ["водка", "лёд"]},
    {"name": "Белый русский",    "price": 16, "ingredients": ["водка", "лёд", "молоко"]},
    {"name": "Лонг-Айленд",      "price": 25, "ingredients": ["водка", "джин", "кола", "ром", "текила"]},
]

VALID_INGREDIENTS = {"водка", "ром", "текила", "виски", "джин", "кола", "сок", "тоник", "лёд", "молоко"}

# Ранги по количеству уникальных напитков
RANKS = [
    (8,  "Легенда"),
    (6,  "Эксперт"),
    (4,  "Завсегдатай"),
    (2,  "Любитель"),
    (0,  "Новичок"),
]

def get_rank(unique_count: int) -> str:
    for threshold, name in RANKS:
        if unique_count >= threshold:
            return name
    return "Новичок"


def get_favorite_drink(history: list):
    if not history:
        return None
    counts = {}
    for order in history:
        name = order["drink"]
        counts[name] = counts.get(name, 0) + 1
    return max(counts, key=counts.get)


# In-memory DB
users_db = {}
