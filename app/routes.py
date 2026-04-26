# app/routes.py
from flask import Blueprint, request, jsonify
import uuid
from .database import MENU, VALID_INGREDIENTS, users_db, get_rank, get_favorite_drink

bar_bp = Blueprint('bar', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_auth_user():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, "unauthorized", 401
    token = auth.split(' ', 1)[1].strip()
    user = users_db.get(token)
    if not user:
        return None, "unauthorized", 401
    return user, None, None


def get_time_hour():
    x_time = request.headers.get('X-Time', '12:00')
    try:
        return int(x_time.split(':')[0])
    except Exception:
        return 12


def is_bar_closed():
    hour = get_time_hour()
    return 0 <= hour <= 5   # полночь–5:59 → закрыто


def recalc_mood(user):
    """Пересчитываем настроение по числу чаевых и истории."""
    # mood хранится как строка: normal / happy / grumpy
    # Базовая логика: много tip → happy; unknown_recipe → grumpy; tip сбрасывает grumpy
    pass  # mood меняется явно в роутах


def make_user():
    return {
        "id": None,
        "balance": 100,
        "mood": "normal",
        "history": [],
        "unique": set(),
        "total_tips": 0,
        "failed_recipes": 0,
        "bar_closed": False,
    }


# ---------------------------------------------------------------------------
# Auth / Account
# ---------------------------------------------------------------------------

@bar_bp.route('/register', methods=['POST'])
def register():
    token = uuid.uuid4().hex
    u_id = f"BAR-{len(users_db) + 1:04d}"
    user = make_user()
    user["id"] = u_id
    users_db[token] = user
    return jsonify({"status": "ok", "id": u_id, "token": token})


@bar_bp.route('/reset', methods=['POST'])
def reset():
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    uid = user["id"]
    user.update(make_user())
    user["id"] = uid
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

@bar_bp.route('/menu', methods=['GET'])
def menu():
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    closed = is_bar_closed()
    resp = {
        "status": "ok",
        "drinks": [] if closed else MENU,
        "balance": user["balance"],
        "mood_level": user["mood"],
    }
    if closed:
        resp["bar_closed"] = True
    return jsonify(resp)


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

@bar_bp.route('/order', methods=['POST'])
def order():
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    if is_bar_closed():
        return jsonify({
            "status": "error",
            "error": "bar_closed",
            "balance": user["balance"],
            "mood_level": user["mood"],
        }), 403

    data = request.get_json(silent=True) or {}
    drink_name = data.get("name")
    drink = next((d for d in MENU if d["name"] == drink_name), None)

    if not drink:
        return jsonify({
            "status": "error",
            "error": "unknown_drink",
            "balance": user["balance"],
            "mood_level": user["mood"],
        })

    price = drink["price"]
    # Настроение влияет на цену: grumpy → наценка, happy → скидка
    if user["mood"] == "happy":
        price = max(1, price - 1)
    elif user["mood"] == "grumpy":
        price = price + 2

    if user["balance"] < price:
        return jsonify({
            "status": "error",
            "error": "insufficient_funds",
            "price": price,
            "balance": user["balance"],
            "mood_level": user["mood"],
        })

    user["balance"] -= price
    user["history"].append({"drink": drink["name"], "price": price, "method": "order"})
    user["unique"].add(drink["name"])

    # После каждых 5 заказов бармен чуть добреет
    if len(user["history"]) % 5 == 0 and user["mood"] == "grumpy":
        user["mood"] = "normal"

    return jsonify({
        "status": "ok",
        "drink": drink["name"],
        "price": price,
        "balance": user["balance"],
        "mood_level": user["mood"],
    })


# ---------------------------------------------------------------------------
# Mix
# ---------------------------------------------------------------------------

@bar_bp.route('/mix', methods=['POST'])
def mix():
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    if is_bar_closed():
        return jsonify({
            "status": "error",
            "error": "bar_closed",
            "balance": user["balance"],
            "mood_level": user["mood"],
        }), 403

    data = request.get_json(silent=True) or {}
    ingredients = data.get("ingredients", [])

    # Валидация ингредиентов
    for ing in ingredients:
        if ing not in VALID_INGREDIENTS:
            user["mood"] = "grumpy"
            return jsonify({
                "status": "error",
                "error": "unknown_ingredient",
                "balance": user["balance"],
                "mood_level": user["mood"],
            })

    ingr_sorted = sorted(ingredients)
    drink = next((d for d in MENU if sorted(d["ingredients"]) == ingr_sorted), None)

    if not drink:
        user["mood"] = "grumpy"
        user["failed_recipes"] = user.get("failed_recipes", 0) + 1
        return jsonify({
            "status": "error",
            "error": "unknown_recipe",
            "balance": user["balance"],
            "mood_level": user["mood"],
        })

    mix_price = max(1, drink["price"] - 2)
    # Настроение тоже влияет на микс
    if user["mood"] == "happy":
        mix_price = max(1, mix_price - 1)
    elif user["mood"] == "grumpy":
        mix_price = mix_price + 1

    if user["balance"] < mix_price:
        return jsonify({
            "status": "error",
            "error": "insufficient_funds",
            "price": mix_price,
            "balance": user["balance"],
            "mood_level": user["mood"],
        })

    user["balance"] -= mix_price
    user["history"].append({"drink": drink["name"], "price": mix_price, "method": "mix"})
    user["unique"].add(drink["name"])

    return jsonify({
        "status": "ok",
        "drink": drink["name"],
        "price": mix_price,
        "balance": user["balance"],
        "mood_level": user["mood"],
    })


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

@bar_bp.route('/balance', methods=['GET'])
def get_balance():
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    return jsonify({"status": "ok", "balance": user["balance"], "mood_level": user["mood"]})


# ---------------------------------------------------------------------------
# Tip
# ---------------------------------------------------------------------------

@bar_bp.route('/tip', methods=['POST'])
def tip():
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    data = request.get_json(silent=True) or {}
    amount = data.get("amount", 0)

    if not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({
            "status": "error",
            "error": "invalid_amount",
            "balance": user["balance"],
            "mood_level": user["mood"],
        })

    user["balance"] -= amount
    user["total_tips"] = user.get("total_tips", 0) + amount

    # Чаевые улучшают настроение
    total = user["total_tips"]
    if total >= 20:
        user["mood"] = "happy"
    elif user["mood"] == "grumpy":
        user["mood"] = "normal"  # любые чаевые снимают grumpy

    return jsonify({
        "status": "ok",
        "tip": amount,
        "balance": user["balance"],
        "mood_level": user["mood"],
    })


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@bar_bp.route('/history', methods=['GET'])
def get_history():
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    return jsonify({
        "status": "ok",
        "orders": user["history"],
        "balance": user["balance"],
        "mood_level": user["mood"],
    })


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@bar_bp.route('/profile', methods=['GET'])
def profile():
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    unique_cnt = len(user["unique"])
    rank = get_rank(unique_cnt)
    fav = get_favorite_drink(user["history"])

    return jsonify({
        "status": "ok",
        "id": user["id"],
        "rank": rank,
        "total_orders": len(user["history"]),
        "unique_drinks": unique_cnt,
        "favorite_drink": fav,
        "bar_closed": is_bar_closed(),
    })


# ---------------------------------------------------------------------------
# Hidden / Secret endpoints (reverse-engineered from task hints)
# ---------------------------------------------------------------------------

@bar_bp.route('/status', methods=['GET'])
def status():
    """Скрытый статус бара."""
    hour = get_time_hour()
    closed = is_bar_closed()
    return jsonify({
        "status": "ok",
        "bar_open": not closed,
        "hour": hour,
        "message": "Бар закрыт. Приходите позже." if closed else "Добро пожаловать!",
    })


@bar_bp.route('/mood', methods=['GET'])
def mood():
    """Скрытый эндпоинт — узнать настроение напрямую."""
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    messages = {
        "happy":  "Бармен сегодня в отличном настроении! 🎉",
        "normal": "Бармен работает в штатном режиме.",
        "grumpy": "Бармен явно не выспался. Будьте осторожны.",
    }
    return jsonify({
        "status": "ok",
        "mood_level": user["mood"],
        "message": messages.get(user["mood"], "..."),
    })


@bar_bp.route('/cheat', methods=['POST'])
def cheat():
    """Пасхалка: попытка сжульничать."""
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    user["mood"] = "grumpy"
    return jsonify({
        "status": "error",
        "error": "caught_cheating",
        "message": "Бармен всё видит. Настроение испорчено.",
        "mood_level": user["mood"],
    }), 418


@bar_bp.route('/secret', methods=['GET'])
def secret():
    """Секретный эндпоинт с паролем."""
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    password = request.args.get('password') or (request.get_json(silent=True) or {}).get('password')
    if password == 'blackbar':
        user["balance"] += 50
        return jsonify({
            "status": "ok",
            "message": "Знаешь пароль — заслужил угощение.",
            "bonus": 50,
            "balance": user["balance"],
            "mood_level": user["mood"],
        })
    return jsonify({
        "status": "error",
        "error": "wrong_password",
        "mood_level": user["mood"],
    })


@bar_bp.route('/ingredients', methods=['GET'])
def ingredients():
    """Список всех ингредиентов."""
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    return jsonify({
        "status": "ok",
        "ingredients": sorted(VALID_INGREDIENTS),
        "mood_level": user["mood"],
    })


@bar_bp.route('/top', methods=['GET'])
def top():
    """Топ напитков (скрытый рейтинг)."""
    user, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    counts = {}
    for u in users_db.values():
        for order in u.get("history", []):
            name = order["drink"]
            counts[name] = counts.get(name, 0) + 1

    top_drinks = sorted(counts.items(), key=lambda x: -x[1])[:5]
    return jsonify({
        "status": "ok",
        "top": [{"drink": d, "count": c} for d, c in top_drinks],
        "mood_level": user["mood"],
    })


# ---------------------------------------------------------------------------
# 404 handler
# ---------------------------------------------------------------------------

@bar_bp.app_errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "error": "not_found"}), 404


@bar_bp.app_errorhandler(405)
def method_not_allowed(e):
    return jsonify({"status": "error", "error": "method_not_allowed"}), 405
