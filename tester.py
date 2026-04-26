import requests
import json
import time

# Твой токен от оригинального бара
ORIGINAL_TOKEN = "fc8b376973582c5c5bfb219fdf075731"


def get_local_token():
    try:
        res = requests.post("http://127.0.0.1:8000/register")
        return res.json().get("token")
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка: Твой локальный сервер (Flask) не запущен!")
        return None


def reset_original_account():
    headers = {"Authorization": f"Bearer {ORIGINAL_TOKEN}"}
    requests.post("https://bar.antihype.lol/reset", headers=headers)
    print("🔄 Оригинальный аккаунт сброшен (баланс 100, история чиста).")


def compare_endpoints(test_name, method, endpoint, local_token, payload=None):
    headers_orig = {"Authorization": f"Bearer {ORIGINAL_TOKEN}", "X-Time": "14:30"}
    headers_local = {"Authorization": f"Bearer {local_token}", "X-Time": "14:30"}

    url_orig = f"https://bar.antihype.lol{endpoint}"
    url_local = f"http://127.0.0.1:8000{endpoint}"

    res_orig = requests.request(method, url_orig, headers=headers_orig, json=payload)
    res_local = requests.request(method, url_local, headers=headers_local, json=payload)

    print(f"\n[{test_name}] Тестируем {method} {endpoint}")

    if res_orig.status_code != res_local.status_code:
        print(f"❌ Статусы не совпадают! Оригинал: {res_orig.status_code}, Клон: {res_local.status_code}")
    else:
        print(f"✅ Статус-коды совпадают ({res_orig.status_code})")

    if res_orig.json() == res_local.json():
        print("✅ JSON-ответы абсолютно идентичны!")
    else:
        print("❌ Найдены отличия в JSON:")
        print("Оригинал:", json.dumps(res_orig.json(), ensure_ascii=False))
        print("Клон:    ", json.dumps(res_local.json(), ensure_ascii=False))

    # Небольшая пауза, чтобы не словить rate_limit от оригинала
    time.sleep(0.5)


# ==========================================
# ЗАПУСК ПОЛНОГО ТЕСТИРОВАНИЯ БАЗЫ
# ==========================================

print("Инициализация полного тестирования...")
LOCAL_TOKEN = get_local_token()

if LOCAL_TOKEN:
    print(f"✅ Локальный токен получен.")
    reset_original_account()
    print("==========================================\n")

    # 1. Запрашиваем меню
    compare_endpoints("МЕНЮ", "GET", "/menu", LOCAL_TOKEN)

    # 2. Делаем обычный заказ (баланс должен стать 90)
    compare_endpoints("ЗАКАЗ", "POST", "/order", LOCAL_TOKEN, {"name": "Русский"})

    # 3. Смешиваем валидный напиток (Отвёртка за 12, скидка за ручной микс)
    compare_endpoints("МИКС (УСПЕХ)", "POST", "/mix", LOCAL_TOKEN, {"ingredients": ["водка", "сок"]})

    # 4. Смешиваем дичь (Ожидаем ошибку unknown_recipe)
    compare_endpoints("МИКС (ОШИБКА)", "POST", "/mix", LOCAL_TOKEN, {"ingredients": ["молоко", "кола", "джин"]})

    # 5. Проверяем баланс после трат
    compare_endpoints("БАЛАНС", "GET", "/balance", LOCAL_TOKEN)

    # 6. Оставляем чаевые
    compare_endpoints("ЧАЕВЫЕ", "POST", "/tip", LOCAL_TOKEN, {"amount": 5})

    # 7. Проверяем историю (должны быть "Русский" и "Отвёртка")
    compare_endpoints("ИСТОРИЯ", "GET", "/history", LOCAL_TOKEN)

    # 8. Проверяем профиль (unique_drinks должно быть 2)
    compare_endpoints("ПРОФИЛЬ", "GET", "/profile", LOCAL_TOKEN)