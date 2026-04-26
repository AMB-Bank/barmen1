# app/routes.py
from flask import Blueprint, request, jsonify
import uuid
from .database import (
    MENU, VALID_INGREDIENTS, get_rank, get_favorite_drink,
    get_user, save_user, count_users, all_users, make_user
)

bar_bp = Blueprint('bar', __name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_auth_user():
    """Возвращает (user_dict, token) или кидает 401."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, None, "unauthorized", 401
    token = auth.split(' ', 1)[1].strip()
    if not token:
        return None, None, "unauthorized", 401
    user = get_user(token)
    if not user:
        return None, None, "unauthorized", 401
    return user, token, None, None


def get_time_hour():
    x_time = request.headers.get('X-Time', '12:00')
    try:
        return int(str(x_time).split(':')[0])
    except Exception:
        return 12


def is_bar_closed():
    hour = get_time_hour()
    return 0 <= hour <= 5


# ── Auth / Account ────────────────────────────────────────────────────────────

@bar_bp.route('/register', methods=['POST'])
def register():
    token = uuid.uuid4().hex
    u_id = f"BAR-{count_users() + 1:04d}"
    user = make_user(u_id)
    save_user(token, user)
    return jsonify({"status": "ok", "id": u_id, "token": token})


@bar_bp.route('/reset', methods=['POST'])
def reset():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    uid = user["id"]
    fresh = make_user(uid)
    save_user(token, fresh)
    return jsonify({"status": "ok"})


# ── Menu ─────────────────────────────────────────────────────────────────────

@bar_bp.route('/menu', methods=['GET'])
def menu():
    user, token, err, code = get_auth_user()
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


# ── Order ─────────────────────────────────────────────────────────────────────

@bar_bp.route('/order', methods=['POST'])
def order():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    if is_bar_closed():
        return jsonify({
            "status": "error", "error": "bar_closed",
            "balance": user["balance"], "mood_level": user["mood"],
        }), 403

    data = request.get_json(silent=True) or {}
    drink_name = data.get("name")
    drink = next((d for d in MENU if d["name"] == drink_name), None)

    if not drink:
        return jsonify({
            "status": "error", "error": "unknown_drink",
            "balance": user["balance"], "mood_level": user["mood"],
        })

    price = drink["price"]
    if user["mood"] == "happy":
        price = max(1, price - 1)
    elif user["mood"] == "grumpy":
        price = price + 2

    if user["balance"] < price:
        return jsonify({
            "status": "error", "error": "insufficient_funds",
            "price": price, "balance": user["balance"], "mood_level": user["mood"],
        })

    user["balance"] -= price
    user["history"].append({"drink": drink["name"], "price": price, "method": "order"})
    user["unique"].add(drink["name"])

    if len(user["history"]) % 5 == 0 and user["mood"] == "grumpy":
        user["mood"] = "normal"

    save_user(token, user)
    return jsonify({
        "status": "ok", "drink": drink["name"],
        "price": price, "balance": user["balance"], "mood_level": user["mood"],
    })


# ── Mix ───────────────────────────────────────────────────────────────────────

@bar_bp.route('/mix', methods=['POST'])
def mix():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    if is_bar_closed():
        return jsonify({
            "status": "error", "error": "bar_closed",
            "balance": user["balance"], "mood_level": user["mood"],
        }), 403

    data = request.get_json(silent=True) or {}
    ingredients = data.get("ingredients", [])

    for ing in ingredients:
        if ing not in VALID_INGREDIENTS:
            user["mood"] = "grumpy"
            save_user(token, user)
            return jsonify({
                "status": "error", "error": "unknown_ingredient",
                "balance": user["balance"], "mood_level": user["mood"],
            })

    ingr_sorted = sorted(ingredients)
    drink = next((d for d in MENU if sorted(d["ingredients"]) == ingr_sorted), None)

    if not drink:
        user["mood"] = "grumpy"
        user["failed_recipes"] = user.get("failed_recipes", 0) + 1
        save_user(token, user)
        return jsonify({
            "status": "error", "error": "unknown_recipe",
            "balance": user["balance"], "mood_level": user["mood"],
        })

    mix_price = max(1, drink["price"] - 2)
    if user["mood"] == "happy":
        mix_price = max(1, mix_price - 1)
    elif user["mood"] == "grumpy":
        mix_price = mix_price + 1

    if user["balance"] < mix_price:
        return jsonify({
            "status": "error", "error": "insufficient_funds",
            "price": mix_price, "balance": user["balance"], "mood_level": user["mood"],
        })

    user["balance"] -= mix_price
    user["history"].append({"drink": drink["name"], "price": mix_price, "method": "mix"})
    user["unique"].add(drink["name"])

    save_user(token, user)
    return jsonify({
        "status": "ok", "drink": drink["name"],
        "price": mix_price, "balance": user["balance"], "mood_level": user["mood"],
    })


# ── Balance ───────────────────────────────────────────────────────────────────

@bar_bp.route('/balance', methods=['GET'])
def get_balance():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    return jsonify({"status": "ok", "balance": user["balance"], "mood_level": user["mood"]})


# ── Tip ───────────────────────────────────────────────────────────────────────

@bar_bp.route('/tip', methods=['POST'])
def tip():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    data = request.get_json(silent=True) or {}
    amount = data.get("amount", 0)

    if not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({
            "status": "error", "error": "invalid_amount",
            "balance": user["balance"], "mood_level": user["mood"],
        })

    user["balance"] -= amount
    user["total_tips"] = user.get("total_tips", 0) + amount

    total = user["total_tips"]
    if total >= 20:
        user["mood"] = "happy"
    elif user["mood"] == "grumpy":
        user["mood"] = "normal"

    save_user(token, user)
    return jsonify({
        "status": "ok", "tip": amount,
        "balance": user["balance"], "mood_level": user["mood"],
    })


# ── History ───────────────────────────────────────────────────────────────────

@bar_bp.route('/history', methods=['GET'])
def get_history():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    return jsonify({
        "status": "ok", "orders": user["history"],
        "balance": user["balance"], "mood_level": user["mood"],
    })


# ── Profile ───────────────────────────────────────────────────────────────────

@bar_bp.route('/profile', methods=['GET'])
def profile():
    user, token, err, code = get_auth_user()
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


# ── Hidden endpoints ──────────────────────────────────────────────────────────

@bar_bp.route('/status', methods=['GET'])
def status():
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
    user, token, err, code = get_auth_user()
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
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    user["mood"] = "grumpy"
    save_user(token, user)
    return jsonify({
        "status": "error", "error": "caught_cheating",
        "message": "Бармен всё видит. Настроение испорчено.",
        "mood_level": user["mood"],
    }), 418


@bar_bp.route('/secret', methods=['GET'])
def secret():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    password = request.args.get('password') or (request.get_json(silent=True) or {}).get('password')
    if password == 'blackbar':
        user["balance"] += 50
        save_user(token, user)
        return jsonify({
            "status": "ok",
            "message": "Знаешь пароль — заслужил угощение.",
            "bonus": 50, "balance": user["balance"], "mood_level": user["mood"],
        })
    return jsonify({"status": "error", "error": "wrong_password", "mood_level": user["mood"]})


@bar_bp.route('/ingredients', methods=['GET'])
def ingredients():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code
    return jsonify({
        "status": "ok",
        "ingredients": sorted(VALID_INGREDIENTS),
        "mood_level": user["mood"],
    })


@bar_bp.route('/top', methods=['GET'])
def top():
    user, token, err, code = get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err}), code

    counts: dict[str, int] = {}
    for u in all_users():
        for order in u.get("history", []):
            name = order["drink"]
            counts[name] = counts.get(name, 0) + 1

    top_drinks = sorted(counts.items(), key=lambda x: -x[1])[:5]
    return jsonify({
        "status": "ok",
        "top": [{"drink": d, "count": c} for d, c in top_drinks],
        "mood_level": user["mood"],
    })


# ── Error handlers ────────────────────────────────────────────────────────────

@bar_bp.app_errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "error": "not_found"}), 404


@bar_bp.app_errorhandler(405)
def method_not_allowed(e):
    return jsonify({"status": "error", "error": "method_not_allowed"}), 405
