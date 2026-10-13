import re  # <-- OBLIGĀTI: Pievienojam regulāro izteiksmju moduli
           # <-- ОБЯЗАТЕЛЬНО: Добавляем модуль регулярных выражений
from database import load_users, save_users


def register_user():
    """
    Jauna lietotāja reģistrācija ar automašīnas valsts numuru
    Регистрация нового пользователя с госномером автомобиля
    """
    print("\n--- REĢISTRĀCIJA ---")
    users = load_users()

    # Aizsardzība pret lielajiem burtiem terminālī
    # Защита от заглавных букв в терминале
    username = input("Ievadiet lietotājvārdu: ").strip().lower()
    if not username:
        print("❌ Kļūda: Lietotājvārds nevar būt tukšs!")
        return False

    # Sinhronizācija ar Flask: pārvēršam uz mazajiem burtiem JSON atslēgai
    # Синхронизация с Flask: переводим в нижний регистр для ключа в JSON
    username_key = username.lower()

    if username_key in users:
        print("❌ Kļūda: Šāds lietotājvārds jau eksistē!")
        return False

    password = input("Ievadiet paroli: ").strip()
    if len(password) < 4:
        print("❌ Kļūda: Parolei jābūt vismaz 4 simbolus garai!")
        return False

    # Pieprasām automašīnas valsts numuru
    # Запрашиваем госномер машины
    car_plate = input("Ievadiet automašīnas numuru (piemēram, AA-1234): ").strip().upper()

    # =========================================================================
    # =========================================================================
    # REGEX VALIDĀCIJA LATVIJAS NUMURIEM (2 burti, defise, 1-4 cipari)
    # ВАЛИДАЦИЯ REGEX ДЛЯ ЛАТВИЙСКИХ НОМЕРОВ (2 буквы, дефис, 1-4 цифры)
    # =========================================================================
    plate_pattern = r"^[A-Z]{2}-\d{1,4}$"

    if not re.match(plate_pattern, car_plate):
        print("❌ Kļūda: Nepareizs auto numura formāts! Jābūt, piemēram, AA-1234")
        return False
    # =========================================================================

    # 📞 PIEVIENOTS: Autovadītāja tālruņa numura pieprasījums
    # 📞 ДОБАВЛЕНО: Запрос телефонного номера водителя
    phone = input("Ievadiet tālruņa numuru (piemēram, +37120000000): ").strip()
    phone_pattern = r"^\+\d{1,3}\d{6,10}$"
    if not re.match(phone_pattern, phone):
        print("❌ Kļūda: Nepareizs tālruņa formāts! Jāsākas ar + un valsts kodu.")
        return False

    # 📧 PIEVIENOTS: Autovadītāja e-pasta adreses pieprasījums
    # 📧 ДОБАВЛЕНО: Запрос E-mail адреса водителя
    email = input("Ievadiet e-pastu (piemēрам, vards@piemers.lv): ").strip()
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        print("❌ Kļūda: Nepareizs e-pasta formāts!")
        return False

    # Aptaujas īpašo zonu loģikas atbalstam (vietas 1-5 un 21-25)
    # Опросы для поддержки логики спец-зон (места 1-5 и 21-25)
    is_ev_input = input("Vai tas ir elektroauto? (j/n): ").strip().lower()
    is_ev = True if is_ev_input == 'j' else False

    is_disabled_input = input("Vai ir invaliditātes statuss? (j/n): ").strip().lower()
    is_disabled = True if is_disabled_input == 'j' else False

    # Saglabājam datus struktūrā ar maka, auto tipu karodziņu, tālruņa un e-pasta atbalstu
    # Сохраняем данные в структуру с поддержкой кошелька, флагов типов авто, телефона и почты
    users[username_key] = {
        "password": password,
        "plate": car_plate,
        "phone": phone,  # <-- PIEVIENOTS: saglabājam tālruni iekš users.json
                         # <-- ДОБАВЛЕНО: сохраняем телефон в users.json
        "email": email,  # <-- PIEVIENOTS: saglabājam e-pastu iekš users.json
                         # <-- ДОБАВЛЕНО: сохраняем e-mail в users.json
        "balance": 10.0,  # Sveiciena balanss / Приветственный баланс
        "is_ev": is_ev,
        "is_disabled": is_disabled,
        "disabled_card": None
    }
    save_users(users)
    print(f"✅ Lietotājs '{username_key}' ({car_plate}) veiksmīgi reģistrēts!")
    return True


def login_user():
    """
    Lietotāja ieiešana sistēmā (atgriež LIETOTĀJVĀRDU)
    Вход пользователя в систему (возвращает ИМЯ ПОЛЬЗОВАТЕЛЯ)
    """
    print("\n--- AUTORIZĀCIJA ---")
    users = load_users()

    # Pārveidojam uz mazajiem burtiem savietojamībai ar datubāzi
    # Приводим к нижнему регистру для совместимости с базой данных
    username = input("Lietotājvārds: ").strip().lower()
    password = input("Parole: ").strip()

    # LABOTS: atgriežam lietotājvārdu (pieteikvārdu), lai strādātu atsevišķi balansi!
    # ИСПРАВЛЕНО: возвращаем имя пользователя (логин), чтобы работали раздельные балансы!
    if username in users and users[username]["password"] == password:
        print(f"✅ Sveiki, {username}! Automašīna: {users[username]['plate']}.")
        return username  # <--- Tagad atgriežam unikālu lietotājvārdu / Теперь возвращаем уникальное имя пользователя
    else:
        print("❌ Kļūda: Nepareizs lietotājvārds vai parole!")
        return None