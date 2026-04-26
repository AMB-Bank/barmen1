import requests
import json

TOKEN = "fc8b376973582c5c5bfb219fdf075731"
headers = {"Authorization": f"Bearer {TOKEN}", "X-Time": "14:30"}

# 1. Покупаем 3 разных напитка
requests.post("https://bar.antihype.lol/order", headers=headers, json={"name": "Русский"})
requests.post("https://bar.antihype.lol/order", headers=headers, json={"name": "Отвёртка"})
requests.post("https://bar.antihype.lol/order", headers=headers, json={"name": "Куба Либре"})

# 2. Смотрим, что изменилось в профиле
res = requests.get("https://bar.antihype.lol/profile", headers=headers)
print("СЫРОЙ ПРОФИЛЬ ОРИГИНАЛА:")
print(json.dumps(res.json(), indent=4, ensure_ascii=False))