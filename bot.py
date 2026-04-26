import telebot
from telebot import types
import datetime

API_TOKEN = '8731718777:AAFZmjkloedjRUYY_LxkarwAW6xO0nkiaOY'
ADMIN_KEY = 'SUPER_SECRET_KEY'
bot = telebot.TeleBot(API_TOKEN)

PROMO_DATA = {
    "ANTIHACK": {"bonus": 20, "mood": None, "msg": "Читер? Нет, просто хакер. +20💰"},
    "FREESHOT": {"bonus": 10, "mood": None, "msg": "Стопка за счет заведения! +10💰"},
    "RICHBOY": {"bonus": 50, "mood": None, "msg": "Золотая карточка сработала! +50💰"},
    "GOODMOOD": {"bonus": 0, "mood": "happy", "msg": "Бармен расплылся в улыбке. Настроение: happy!"},
    "NIGHT": {"bonus": 15, "mood": "happy", "msg": "Ночной тариф активирован. +15💰"},
    "LEGEND": {"bonus": 100, "mood": "happy", "msg": "ТЫ — ЛЕГЕНДА ЭТОГО БАРА! +100💰"}
}

MENU = [
    {"name": "Русский", "price": 10, "ingredients": ["водка", "лёд"]},
    {"name": "Отвёртка", "price": 12, "ingredients": ["водка", "сок"]},
    {"name": "Джин-тоник", "price": 14, "ingredients": ["джин", "лёд", "тоник"]},
    {"name": "Куба Либре", "price": 15, "ingredients": ["кола", "лёд", "ром"]},
    {"name": "Виски-кола", "price": 13, "ingredients": ["виски", "кола"]},
    {"name": "Текила-санрайз", "price": 14, "ingredients": ["сок", "текила"]},
    {"name": "Белый русский", "price": 16, "ingredients": ["водка", "лёд", "молоко"]},
    {"name": "Лонг-Айленд", "price": 25, "ingredients": ["водка", "джин", "кола", "ром", "текила"]}
]

users_db = {}
promo_enabled = True


def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "id": f"BAR-{len(users_db) + 1:04d}",
            "balance": 100,
            "mood": "normal",
            "used_promos": set(),
            "drinks_tried": set(),
            "history": []
        }
    return users_db[user_id]


def is_bar_closed():
    hour = datetime.datetime.now().hour
    return 0 <= hour <= 5


bot.set_my_commands([
    types.BotCommand("menu", "📜 Посмотреть меню"),
    types.BotCommand("promo", "🎟 Активировать промокод"),
    types.BotCommand("account", "👤 Мой профиль"),
    types.BotCommand("reset", "🧼 Сбросить всё"),
    types.BotCommand("mix", "🍸 Смешать (например: /mix водка сок)")
])


def main_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📜 Меню", "👤 Профиль")
    markup.row("🎟 Промокод", "🧼 Сброс")
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🥃 Чёрный Бар открыт! Пользуйся кнопками или вводи / для команд.",
        reply_markup=main_kb()
    )


@bot.message_handler(commands=['menu'])
@bot.message_handler(func=lambda m: m.text and "Меню" in m.text)
def cmd_menu(message):
    if is_bar_closed():
        bot.send_message(message.chat.id, "🌙 Бар закрыт до 05:00. Бармен спит.")
        return

    user = get_user(message.from_user.id)
    markup = types.InlineKeyboardMarkup()
    for drink in MENU:
        btn = types.InlineKeyboardButton(f"{drink['name']} — {drink['price']}💰", callback_data=f"buy_{drink['name']}")
        markup.add(btn)
    bot.send_message(message.chat.id, f"Чего желаете? (Твой баланс: {user['balance']}💰)", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    user = get_user(call.from_user.id)
    drink_name = call.data.split('_')[1]
    drink = next(d for d in MENU if d["name"] == drink_name)

    if user["balance"] < drink["price"]:
        bot.answer_callback_query(call.id, "Денег не хватает! 💸", show_alert=True)
        return

    user["balance"] -= drink["price"]
    user["drinks_tried"].add(drink["name"])

    bot.edit_message_text(
        f"🍸 Твой {drink['name']} готов! \nОстаток: {user['balance']}💰\nНастроение бармена: {user['mood']}",
        call.message.chat.id,
        call.message.message_id
    )


@bot.message_handler(commands=['account'])
@bot.message_handler(func=lambda m: m.text and "Профиль" in m.text)
def cmd_profile(message):
    u = get_user(message.from_user.id)
    unique_cnt = len(u["drinks_tried"])

    rank = "Новичок"
    if unique_cnt >= 5: rank = "Постоянный клиент"
    if unique_cnt >= 8: rank = "Мастер дегустации"

    text = (f"👤 Аккаунт: {u['id']}\n"
            f"🏅 Ранг: {rank}\n"
            f"💰 Баланс: {u['balance']}💰\n"
            f"🎭 Настроение: {u['mood']}\n"
            f"🚫 Бар закрыт: {'Да' if is_bar_closed() else 'Нет'}")
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['promo'])
@bot.message_handler(func=lambda m: m.text and "Промокод" in m.text)
def cmd_promo(message):
    if not promo_enabled:
        bot.send_message(message.chat.id, "🚫 Промокоды сейчас не работают.")
        return
    msg = bot.send_message(message.chat.id, "Введи секретный код:")
    bot.register_next_step_handler(msg, apply_promo_logic)


def apply_promo_logic(message):
    code = message.text.upper().strip()
    u = get_user(message.from_user.id)

    if code not in PROMO_DATA:
        bot.send_message(message.chat.id, "🤨 Нет такого кода. (invalid code)")
        return

    if code in u["used_promos"]:
        bot.send_message(message.chat.id, "🙅‍♂️ Ты уже это вводил. (already_used)")
        return

    data = PROMO_DATA[code]
    u["balance"] += data["bonus"]
    if data["mood"]: u["mood"] = data["mood"]
    u["used_promos"].add(code)

    bot.send_message(message.chat.id, f"✅ {data['msg']}\nТвой баланс: {u['balance']}💰")


@bot.message_handler(commands=['reset'])
@bot.message_handler(func=lambda m: m.text and "Сброс" in m.text)
def cmd_reset(message):
    uid = message.from_user.id
    if uid in users_db: del users_db[uid]
    bot.send_message(message.chat.id, "♻️ Всё обнулено. Ты снова новый гость!", reply_markup=main_kb())


@bot.message_handler(commands=['mix'])
def cmd_mix(message):
    user = get_user(message.from_user.id)
    ingredients = message.text.lower().split()[1:]

    if not ingredients:
        bot.send_message(message.chat.id, "Напиши что смешать через пробел. Пример: /mix водка сок")
        return

    drink = next((d for d in MENU if sorted(d["ingredients"]) == sorted(ingredients)), None)

    if not drink:
        user["mood"] = "grumpy"
        bot.send_message(message.chat.id, "👹 Бармен в ярости от такой смеси! (unknown_recipe)")
        return

    price = drink["price"] - 2
    if user["balance"] < price:
        bot.send_message(message.chat.id, "Не хватает денег на такой эксперимент!")
        return

    user["balance"] -= price
    user["drinks_tried"].add(drink["name"])
    bot.send_message(message.chat.id, f"✨ Мастер! Получилось: {drink['name']} всего за {price}💰")


if __name__ == "__main__":
    print("Чёрный бармен готов наливать!")
    bot.infinity_polling()