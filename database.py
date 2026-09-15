import json
import os
from datetime import datetime

DATA_FILE = "parking_data.json"
USERS_FILE = "users.json"

# =========================================================================
# ГЕНЕРАЦИЯ СХЕМЫ НА 25 МЕСТ (Совместимо с новыми HTML шаблонами)
# =========================================================================
# 1-5: Для людей с инвалидностью, 6-20: Обычные, 21-25: Электромобили (EV)
DEFAULT_SPOTS = {}
for i in range(1, 26):
    if i <= 5:
        DEFAULT_SPOTS[str(i)] = {"status": True, "type": "disabled"}
    elif i > 20:
        DEFAULT_SPOTS[str(i)] = {"status": True, "type": "ev"}
    else:
        DEFAULT_SPOTS[str(i)] = {"status": True, "type": "regular"}


def load_data():
    """Datu ielāde no JSON faila ar automātisku laika pārbaudi"""
    parking_spots = DEFAULT_SPOTS

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                parking_spots = json.load(f)
                # Проверка для плавной миграции старой базы данных на полные 25 мест
                for spot_id, spot_type in DEFAULT_SPOTS.items():
                    if spot_id not in parking_spots:
                        parking_spots[spot_id] = spot_type
        except json.JSONDecodeError:
            parking_spots = DEFAULT_SPOTS

    # --- ЛОГИКА АВТООЧИСТКИ ИСТЕКШЕЙ БРОНИ ПО ВРЕМЕНИ ПК ---
    now = datetime.now()
    updated = False

    for spot_id, spot_val in parking_spots.items():
        if isinstance(spot_val, dict) and isinstance(spot_val.get("status"), dict):
            status_dict = spot_val["status"]
            if "ends_at" in status_dict:
                try:
                    ends_at_time = datetime.strptime(status_dict["ends_at"], "%d.%m.%Y %H:%M")
                    if now > ends_at_time:
                        parking_spots[spot_id]["status"] = True
                        updated = True
                except ValueError:
                    pass

    if updated:
        save_data(parking_spots)

    return parking_spots


def save_data(data):
    """Datu saglabāšana JSON failā"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# =========================================================================
# РАБОТА С ПОЛЬЗОВАТЕЛЯМИ И ИХ СТАТУСАМИ
# =========================================================================

def load_users():
    """Загрузка пользователей из JSON с защитой структуры старых аккаунтов"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)

                # Защита структуры данных для старых профилей водителей
                for username in users:
                    if "balance" not in users[username]:
                        users[username]["balance"] = 10.0
                    if "is_ev" not in users[username]:
                        users[username]["is_ev"] = False
                    if "is_disabled" not in users[username]:
                        users[username]["is_disabled"] = False
                    if "disabled_card" not in users[username]:
                        users[username]["disabled_card"] = None
                    if "is_admin" not in users[username]:
                        users[username]["is_admin"] = False
                return users
        except json.JSONDecodeError:
            return {}
    return {}


def save_users(users_data):
    """Сохранение пользователей в JSON"""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users_data, f, ensure_ascii=False, indent=4)