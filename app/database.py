# app/database.py
import sqlite3
import json
import os

DB_PATH = os.getenv("DB_PATH", "/tmp/bar.db")

MENU = [
    {"name": "Куба Либре",     "price": 15, "ingredients": ["кола", "лёд", "ром"]},
    {"name": "Отвёртка",       "price": 12, "ingredients": ["водка", "сок"]},
    {"name": "Джин-тоник",     "price": 14, "ingredients": ["джин", "лёд", "тоник"]},
    {"name": "Виски-кола",     "price": 13, "ingredients": ["виски", "кола"]},
    {"name": "Текила-санрайз", "price": 14, "ingredients": ["сок", "текила"]},
    {"name": "Русский",        "price": 10, "ingredients": ["водка", "лёд"]},
    {"name": "Белый русский",  "price": 16, "ingredients": ["водка", "лёд", "молоко"]},
    {"name": "Лонг-Айленд",   "price": 25, "ingredients": ["водка", "джин", "кола", "ром", "текила"]},
]

VALID_INGREDIENTS = {
    "водка", "ром", "текила", "виски", "джин",
    "кола", "сок", "тоник", "лёд", "молоко"
}

RANKS = [
    (8, "Легенда"),
    (6, "Эксперт"),
    (4, "Завсегдатай"),
    (2, "Любитель"),
    (0, "Новичок"),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                token          TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                balance        INTEGER NOT NULL DEFAULT 100,
                mood           TEXT NOT NULL DEFAULT 'normal',
                history        TEXT NOT NULL DEFAULT '[]',
                unique_set     TEXT NOT NULL DEFAULT '[]',
                total_tips     REAL NOT NULL DEFAULT 0,
                failed_recipes INTEGER NOT NULL DEFAULT 0,
                used_promos    TEXT NOT NULL DEFAULT '[]'
            )
        """)
        conn.commit()


def _row_to_user(row) -> dict | None:
    if row is None:
        return None
    return {
        "token":          row["token"],
        "id":             row["user_id"],
        "balance":        row["balance"],
        "mood":           row["mood"],
        "history":        json.loads(row["history"]),
        "unique":         set(json.loads(row["unique_set"])),
        "total_tips":     row["total_tips"],
        "failed_recipes": row["failed_recipes"],
        "used_promos":    set(json.loads(row["used_promos"])),
    }


def get_user(token: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE token = ?", (token,)
        ).fetchone()
    return _row_to_user(row)


def save_user(token: str, user: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users
                (token, user_id, balance, mood, history, unique_set,
                 total_tips, failed_recipes, used_promos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                balance        = excluded.balance,
                mood           = excluded.mood,
                history        = excluded.history,
                unique_set     = excluded.unique_set,
                total_tips     = excluded.total_tips,
                failed_recipes = excluded.failed_recipes,
                used_promos    = excluded.used_promos
        """, (
            token,
            user["id"],
            user["balance"],
            user["mood"],
            json.dumps(user["history"], ensure_ascii=False),
            json.dumps(list(user["unique"]), ensure_ascii=False),
            user["total_tips"],
            user["failed_recipes"],
            json.dumps(list(user["used_promos"]), ensure_ascii=False),
        ))
        conn.commit()


def count_users() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def all_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users").fetchall()
    return [_row_to_user(r) for r in rows]


def make_user(user_id: str) -> dict:
    return {
        "id":             user_id,
        "balance":        100,
        "mood":           "normal",
        "history":        [],
        "unique":         set(),
        "total_tips":     0,
        "failed_recipes": 0,
        "used_promos":    set(),
    }


def get_rank(unique_count: int) -> str:
    for threshold, name in RANKS:
        if unique_count >= threshold:
            return name
    return "Новичок"


def get_favorite_drink(history: list) -> str | None:
    if not history:
        return None
    counts: dict[str, int] = {}
    for order in history:
        name = order["drink"]
        counts[name] = counts.get(name, 0) + 1
    return max(counts, key=counts.get)
