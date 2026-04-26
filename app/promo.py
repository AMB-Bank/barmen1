# app/promo.py
import os
from flask import Blueprint, request, jsonify
from .database import users_db

promo_bp = Blueprint('promo', __name__)

# ── State ────────────────────────────────────────────────────────────────────
promo_enabled: bool = True   # toggleable via /admin/promo

# Промокоды: code → {"remaining": int|None, "effect": callable(user)}
# remaining=None → бесконечный; remaining=N → ограниченный глобально

PROMO_CATALOG: dict[str, dict] = {
    "ANTIHACK": {
        "remaining": None,          # безлимитный
        "effect": lambda u: _add_balance(u, 20),
    },
    "FREESHOT": {
        "remaining": None,
        "effect": lambda u: _add_balance(u, 10),
    },
    "RICHBOY": {
        "remaining": None,
        "effect": lambda u: _add_balance(u, 50),
    },
    "GOODMOOD": {
        "remaining": None,
        "effect": lambda u: _set_mood(u, "happy"),
    },
    "NIGHT": {
        "remaining": None,
        "effect": lambda u: _add_balance(u, 15),
    },
    "LEGEND": {
        "remaining": None,
        "effect": lambda u: _add_balance(u, 100),
    },
}

# Счётчик глобальных использований (для кодов с лимитом)
promo_uses: dict[str, int] = {code: 0 for code in PROMO_CATALOG}


# ── Effects ───────────────────────────────────────────────────────────────────
def _add_balance(user: dict, amount: int):
    user["balance"] = user.get("balance", 0) + amount

def _set_mood(user: dict, mood: str):
    user["mood"] = mood


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_auth_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, ("unauthorized", 401)
    token = auth.split(" ", 1)[1].strip()
    user = users_db.get(token)
    if not user:
        return None, ("unauthorized", 401)
    return user, None


def _promo_404():
    return jsonify({"status": "error", "error": "not_found"}), 404


# ── Routes ────────────────────────────────────────────────────────────────────

@promo_bp.route("/promo", methods=["POST"])
def activate_promo():
    if not promo_enabled:
        return _promo_404()

    user, err = _get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err[0]}), err[1]

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").upper().strip()

    if code not in PROMO_CATALOG:
        return jsonify({
            "status": "error",
            "error": "invalid_code",
            "balance": user["balance"],
            "mood_level": user["mood"],
        })

    used_codes: set = user.setdefault("used_promos", set())
    if code in used_codes:
        return jsonify({
            "status": "error",
            "error": "already_used",
            "balance": user["balance"],
            "mood_level": user["mood"],
        })

    # Проверяем глобальный лимит
    promo = PROMO_CATALOG[code]
    if promo["remaining"] is not None:
        if promo_uses[code] >= promo["remaining"]:
            return jsonify({
                "status": "error",
                "error": "invalid_code",   # исчерпан — снаружи выглядит как невалидный
                "balance": user["balance"],
                "mood_level": user["mood"],
            })

    # Применяем эффект
    promo["effect"](user)
    used_codes.add(code)
    promo_uses[code] += 1

    return jsonify({
        "status": "ok",
        "code": code,
        "balance": user["balance"],
        "mood_level": user["mood"],
    })


@promo_bp.route("/promo", methods=["GET"])
def list_promos():
    if not promo_enabled:
        return _promo_404()

    user, err = _get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err[0]}), err[1]

    used: set = user.get("used_promos", set())

    active = []
    for code, meta in PROMO_CATALOG.items():
        if code in used:
            continue  # уже активирован этим пользователем
        remaining = meta["remaining"]
        if remaining is not None:
            left = remaining - promo_uses[code]
            if left <= 0:
                continue
            active.append({"code": code, "remaining": left})
        else:
            active.append({"code": code, "remaining": None})

    return jsonify({
        "status": "ok",
        "active": active,
        "balance": user["balance"],
        "mood_level": user["mood"],
    })


# ── Admin ─────────────────────────────────────────────────────────────────────

@promo_bp.route("/admin/promo", methods=["POST"])
def admin_toggle_promo():
    global promo_enabled

    ADMIN_KEY = os.getenv("ADMIN_KEY", "secret-admin-key")
    data = request.get_json(silent=True) or {}

    if data.get("key") != ADMIN_KEY:
        return jsonify({"status": "error", "error": "forbidden"}), 403

    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        return jsonify({"status": "error", "error": "invalid_payload"}), 400

    promo_enabled = enabled
    return jsonify({"status": "ok", "promo_enabled": promo_enabled})


@promo_bp.route("/admin/promo", methods=["GET"])
def admin_promo_status():
    return jsonify({"promo_enabled": promo_enabled})
