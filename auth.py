from database import load_users, save_users


def register_user():
    """Регистрация нового пользователя с госномером автомобиля"""
    print("\n--- REĢISTRĀCIJA ---")
    users = load_users()

    username = input("Ievadiet lietotājvārdu: ").strip()
    if not username:
        print("❌ Kļūda: Lietotājvārds nevar būt tukšs!")
        return False

    if username in users:
        print("❌ Kļūda: Šāds lietotājvārds jau eksistē!")
        return False

    password = input("Ievadiet paroli: ").strip()
    if len(password) < 4:
        print("❌ Kļūda: Parolei jābūt vismaz 4 simbolus garai!")
        return False

    # Запрашиваем госномер машины
    car_plate = input("Ievadiet automašīnas numuru (piemēram, AA-1234): ").strip().upper()
    if not car_plate:
        print("❌ Kļūda: Automašīnas numurs nevar būt tukšs!")
        return False

    # Сохраняем новые данные в структуру
    users[username] = {
        "password": password,
        "plate": car_plate
    }
    save_users(users)
    print(f"✅ Lietotājs '{username}' ({car_plate}) veiksmīgi reģistrēts!")
    return True


def login_user():
    """Вход пользователя в систему (возвращает госномер автомобиля)"""
    print("\n--- AUTORIZĀCIJA ---")
    users = load_users()

    username = input("Lietotājvārds: ").strip()
    password = input("Parole: ").strip()

    # Проверяем, существует ли пользователь и совпадает ли пароль
    if username in users and users[username]["password"] == password:
        car_plate = users[username]["plate"]
        print(f"✅ Sveiki, {username}! Automašīna: {car_plate}.")
        return car_plate  # <--- Возвращаем госномер вместо имени пользователя!
    else:
        print("❌ Kļūda: Nepareizs lietotājvārds vai parole!")
        return None