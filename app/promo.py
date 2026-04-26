# app/promo.py
import os
from flask import Blueprint, request, jsonify
from .database import get_user, save_user

promo_bp = Blueprint('promo', __name__)

# ── State ─────────────────────────────────────────────────────────────────────
promo_enabled: bool = True

PROMO_CATALOG: dict[str, dict] = {
    "ANTIHACK": {"remaining": None, "effect": lambda u: _add_balance(u, 20)},
    "FREESHOT": {"remaining": None, "effect": lambda u: _add_balance(u, 10)},
    "RICHBOY":  {"remaining": None, "effect": lambda u: _add_balance(u, 50)},
    "GOODMOOD": {"remaining": None, "effect": lambda u: _set_mood(u, "happy")},
    "NIGHT":    {"remaining": None, "effect": lambda u: _add_balance(u, 15)},
    "LEGEND":   {"remaining": None, "effect": lambda u: _add_balance(u, 100)},
}

promo_uses: dict[str, int] = {code: 0 for code in PROMO_CATALOG}


def _add_balance(user: dict, amount: int):
    user["balance"] = user.get("balance", 0) + amount

def _set_mood(user: dict, mood: str):
    user["mood"] = mood


def _get_auth_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, None, ("unauthorized", 401)
    token = auth.split(" ", 1)[1].strip()
    user = get_user(token)
    if not user:
        return None, None, ("unauthorized", 401)
    return user, token, None


def _promo_404():
    return jsonify({"status": "error", "error": "not_found"}), 404


# ── Routes ────────────────────────────────────────────────────────────────────

@promo_bp.route("/promo", methods=["POST"])
def activate_promo():
    if not promo_enabled:
        return _promo_404()

    user, token, err = _get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err[0]}), err[1]

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").upper().strip()

    if code not in PROMO_CATALOG:
        return jsonify({
            "status": "error", "error": "invalid_code",
            "balance": user["balance"], "mood_level": user["mood"],
        })

    used_codes: set = user.setdefault("used_promos", set())
    if code in used_codes:
        return jsonify({
            "status": "error", "error": "already_used",
            "balance": user["balance"], "mood_level": user["mood"],
        })

    promo = PROMO_CATALOG[code]
    if promo["remaining"] is not None and promo_uses[code] >= promo["remaining"]:
        return jsonify({
            "status": "error", "error": "invalid_code",
            "balance": user["balance"], "mood_level": user["mood"],
        })

    promo["effect"](user)
    used_codes.add(code)
    promo_uses[code] += 1

    save_user(token, user)
    return jsonify({
        "status": "ok", "code": code,
        "balance": user["balance"], "mood_level": user["mood"],
    })


@promo_bp.route("/promo", methods=["GET"])
def list_promos():
    if not promo_enabled:
        return _promo_404()

    user, token, err = _get_auth_user()
    if err:
        return jsonify({"status": "error", "error": err[0]}), err[1]

    used: set = user.get("used_promos", set())
    active = []
    for code, meta in PROMO_CATALOG.items():
        if code in used:
            continue
        remaining = meta["remaining"]
        if remaining is not None:
            left = remaining - promo_uses[code]
            if left <= 0:
                continue
            active.append({"code": code, "remaining": left})
        else:
            active.append({"code": code, "remaining": None})

    return jsonify({
        "status": "ok", "active": active,
        "balance": user["balance"], "mood_level": user["mood"],
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
