import re  # <-- ОБЯЗАТЕЛЬНО: Добавляем модуль регулярных выражений
from database import load_users, save_users


def register_user():
    """Регистрация нового пользователя с госномером автомобиля"""
    print("\n--- REĢISTRĀCIJA ---")
    users = load_users()

    username = input("Ievadiet lietotājvārdu: ").strip()
    if not username:
        print("❌ Kļūda: Lietotājvārds nevar būt tukšs!")
        return False

    # Синхронизация с Flask: переводим в нижний регистр для ключа в JSON
    username_key = username.lower()

    if username_key in users:
        print("❌ Kļūda: Šāds lietotājvārds jau eksistē!")
        return False

    password = input("Ievadiet paroli: ").strip()
    if len(password) < 4:
        print("❌ Kļūda: Parolei jābūt vismaz 4 simbolus garai!")
        return False

    # Запрашиваем госномер машины
    car_plate = input("Ievadiet automašīnas numuru (piemēram, AA-1234): ").strip().upper()

    # =========================================================================
    # ВАЛИДАЦИЯ REGEX ДЛЯ ЛАТВИЙСКИХ НОМЕРОВ (2 буквы, дефис, 1-4 цифры)
    # =========================================================================
    plate_pattern = r"^[A-Z]{2}-\d{1,4}$"

    if not re.match(plate_pattern, car_plate):
        print("❌ Kļūda: Nepareizs auto numura formāts! Jābūt, piemēram, AA-1234")
        return False
    # =========================================================================

    # Опросы для поддержки логики спец-зон (места 1-5 и 21-25)
    is_ev_input = input("Vai tas ir elektroauto? (j/n): ").strip().lower()
    is_ev = True if is_ev_input == 'j' else False

    is_disabled_input = input("Vai ir invaliditātes statuss? (j/n): ").strip().lower()
    is_disabled = True if is_disabled_input == 'j' else False

    # Сохраняем данные в структуру с поддержкой кошелька и флагов типов авто
    users[username_key] = {
        "password": password,
        "plate": car_plate,
        "balance": 10.0,  # Приветственный баланс
        "is_ev": is_ev,
        "is_disabled": is_disabled
    }
    save_users(users)
    print(f"✅ Lietotājs '{username_key}' ({car_plate}) veiksmīgi reģistrēts!")
    return True


def login_user():
    """Вход пользователя в систему (возвращает ИМЯ ПОЛЬЗОВАТЕЛЯ)"""
    print("\n--- AUTORIZĀCIJA ---")
    users = load_users()

    # Приводим к нижнему регистру для совместимости с базой данных
    username = input("Lietotājvārds: ").strip().lower()
    password = input("Parole: ").strip()

    # ИСПРАВЛЕНО: возвращаем имя пользователя (логин), чтобы работали раздельные балансы!
    if username in users and users[username]["password"] == password:
        print(f"✅ Sveiki, {username}! Automašīna: {users[username]['plate']}.")
        return username  # <--- Теперь возвращаем уникальное имя пользователя
    else:
        print("❌ Kļūda: Nepareizs lietotājvārds vai parole!")
        return None