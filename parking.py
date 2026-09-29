import json
from datetime import datetime, timedelta
from database import load_data, save_data, load_users, save_users

# Стоимость одного часа парковки (2 евро)
PRICE_PER_HOUR = 2.0


def parking_menu(current_user):  # <-- ИСПРАВЛЕНО: Принимаем имя пользователя
    """Главное меню управления парковкой"""
    while True:
        # Динамически подгружаем госномер и актуальный баланс авторизованного юзера
        users = load_users()
        if current_user not in users:
            print("❌ Kļūda: Lietotājs nav atrasts.")
            break

        current_plate = users[current_user]["plate"]
        current_balance = users[current_user].get("balance", 0.0)

        print(f"\nLietotājs: {current_user} | Auto: {current_plate} | Balanss: {current_balance:.2f} EUR")
        print("1. Skatīt stāvvietu karti")
        print("2. Rezervēt vietu")
        print("3. Atbrīvot vietu")
        print("4. Iziet uz sākuma izvēlni")

        choice = input("Izvēlieties darbību (1-4): ").strip()

        if choice == "1":
            show_spots(current_plate)
        elif choice == "2":
            book_spot(current_user)  # <-- ИСПРАВЛЕНО: Передаем имя пользователя
        elif choice == "3":
            free_spot(current_plate)
        elif choice == "4":
            print("Atgriešanās sākuma izvēlē...")
            break
        else:
            print("Kļūda: Nepareiza izvēle!")


def show_spots(current_plate):
    """Визуализация карты парковки в сетку с выводом госномера, времени и подсказки (25 мест)"""
    parking_spots = load_data()
    print("\n" + "=" * 80)
    print("                              P A R K N O W                                   ")
    print("                         Viedā autostāvvietas karte                           ")
    print("=" * 80)

    earliest_spot = None
    earliest_time = None
    free_count = 0

    def get_vis(spot_id):
        nonlocal earliest_spot, earliest_time, free_count
        spot_val = parking_spots.get(str(spot_id), True)

        if isinstance(spot_val, dict):
            status = spot_val.get("status", True)
            spot_type = spot_val.get("type", "regular")
        else:
            status = spot_val
            spot_id_int = int(spot_id)
            if spot_id_int <= 5:
                spot_type = "disabled"
            elif spot_id_int > 20:
                spot_type = "ev"
            else:
                spot_type = "regular"

        # Присваиваем правильную иконку для типа места
        if spot_type == "disabled":
            spot_label = f"{spot_id}♿"
        elif spot_type == "ev":
            spot_label = f"{spot_id}⚡"
        else:
            spot_label = f"{spot_id} "

        if status is True:
            free_count += 1
            icon = "🟢"
            owner = ""
        else:
            icon = "🔴"
            if isinstance(status, dict):
                plate = status.get("plate", "???")
                time_str = status.get("ends_at", "")

                # Безопасно вырезаем только время ЧЧ:ММ
                ends = time_str.split(" ")[1] if " " in time_str else time_str

                if plate == current_plate:
                    owner = f"({plate} līdz {ends})"
                else:
                    owner = f"(Aizņemts līdz {ends})"

                if time_str:
                    try:
                        spot_time = datetime.strptime(time_str, "%d.%m.%Y %H:%M")
                        if earliest_time is None or spot_time < earliest_time:
                            earliest_time = spot_time
                            earliest_spot = spot_id
                    except ValueError:
                        pass
            else:
                if status == current_plate:
                    owner = f"({status})"
                else:
                    owner = "(Aizņemts)"

        return f"{spot_label:<3}[{icon}]{owner:<23}"

    # Порядовая отрисовка 25 мест (по 5 штук в ряд)
    print("              ♿ ♿ ♿  CILVĒKIEM AR ĪPAŠĀM VAJADZĪBĀM (1-5)  ♿ ♿ ♿     ")
    print("  " + " ".join(get_vis(i) for i in range(1, 6)))
    print("  " + "—" * 76)
    print("                             PARASTĀS VIETAS (6-20)                           ")
    print("  " + " ".join(get_vis(i) for i in range(6, 11)))
    print("  " + " ".join(get_vis(i) for i in range(11, 16)))
    print("  " + " ".join(get_vis(i) for i in range(16, 21)))
    print("  " + "—" * 76)
    print("              ⚡ ⚡ ⚡  ELEKTROAUTO ZONA (21-25)  ⚡ ⚡ ⚡     ")
    print("  " + " ".join(get_vis(i) for i in range(21, 26)))
    print("=" * 80)

    print(f" Kopā: {free_count} brīvas vietas no {len(parking_spots)}.")

    if free_count == 0 and earliest_time:
        formatted_time = earliest_time.strftime("%H:%M")
        print(f" ⚠️ Visas vietas aizņemtas! Tuvākā brīvā būs vieta Nr. {earliest_spot} plkst. {formatted_time}.")

    print("=" * 80)


def book_spot(current_user):  # <-- ИСПРАВЛЕНО: Привязка строго к юзеру
    """Функция бронирования места по имени пользователя с проверкой баланса и спец-статусов"""
    try:
        parking_spots = load_data()
        users = load_users()
        current_plate = users[current_user]["plate"]

        # Проверка на дублирование машины на парковке
        for spot_val in parking_spots.values():
            if isinstance(spot_val, dict):
                status = spot_val.get("status")
                if isinstance(status, dict) and status.get("plate") == current_plate:
                    print(f"❌ Kļūda: Automašīna {current_plate} jau ir novietota stāvvietā!")
                    return
            elif spot_val == current_plate:
                print(f"❌ Kļūda: Automašīna {current_plate} jau ir novietota stāvvietā!")
                return

        spot_number = input("Ievadiet vietas numuru rezervēšanai (1-25): ").strip()

        if spot_number not in parking_spots:
            print("❌ Kļūda: Šāda vieta neeksistē!")
            return

        target_spot = parking_spots[spot_number]

        # === ИСПРАВЛЕНО: Читаем флаги напрямую из кошелька вошедшего водителя ===
        is_user_ev = users[current_user].get("is_ev", False)
        is_user_disabled = users[current_user].get("is_disabled", False)

        # Валидация зоны электромобилей (21-25)
        if isinstance(target_spot, dict) and target_spot.get("type") == "ev" and not is_user_ev:
            print("❌ Kļūda: Vietas no 21 līdz 25 paredзētas tikai Elektroauto!")
            return

        # Валидация зоны для инвалидов (1-5)
        if isinstance(target_spot, dict) and target_spot.get("type") == "disabled" and not is_user_disabled:
            print("❌ Kļūda: Vietas no 1 līdz 5 paredzētas tikai cilvēkiem ar īpašām vajadzībām!")
            return

        current_status = target_spot.get("status", True) if isinstance(target_spot, dict) else target_spot

        if current_status is True:
            try:
                duration = int(input("Uz cik stundām rezervēt? (1-24): ").strip())
                if duration < 1 or duration > 24:
                    raise ValueError
            except ValueError:
                print("❌ Kļūda: Nepareizs stundu skaits! Rezervācija atcelta.")
                return

            total_cost = duration * PRICE_PER_HOUR
            current_balance = users[current_user].get("balance", 0.0)

            if current_balance < total_cost:
                print(f"❌ Kļūda: Nepietiek līdzekļu! Vajag: {total_cost:.2f} EUR, Jums ir: {current_balance:.2f} EUR")
                return

            # Списание средств СТРОГО со счета авторизованного пользователя
            users[current_user]["balance"] = current_balance - total_cost
            save_users(users)

            now = datetime.now()
            ends_at = now + timedelta(hours=duration)

            if not isinstance(parking_spots[spot_number], dict):
                spot_id_int = int(spot_number)
                s_type = "disabled" if spot_id_int <= 5 else ("ev" if spot_id_int > 20 else "regular")
                parking_spots[spot_number] = {"type": s_type}

            parking_spots[spot_number]["status"] = {
                "plate": current_plate,
                "booked_at": now.strftime("%d.%m.%Y %H:%M"),
                "duration_hours": duration,
                "ends_at": ends_at.strftime("%d.%m.%Y %H:%M")
            }
            save_data(parking_spots)
            print(f"✅ Veiksmīgi! Samaksāts: {total_cost:.2f} EUR. Vieta Nr. {spot_number} rezervēta līdz {ends_at.strftime('%H:%M')}.")
        else:
            print(f"⚠️ Atvainojiet, vieta Nr. {spot_number} jau ir aizņemta.")

    except Exception as e:
        print(f"❌ Kļūda: {e}")


def free_spot(current_plate):
    """Функция безопасного освобождения места по госномеру"""
    try:
        parking_spots = load_data()
        spot_number = input("Ievadiet vietas numuru, lai to atbrīvotu (1-25): ").strip()

        if spot_number not in parking_spots:
            print("❌ Kļūda: Šāda vieta neeksistē!")
            return

        target_spot = parking_spots[spot_number]
        current_status = target_spot.get("status", True) if isinstance(target_spot, dict) else target_spot

        if current_status is True:
            print(f"⚠️ Vieta Nr. {spot_number} jau ir brīva!")
        elif isinstance(current_status, dict) and current_status.get("plate") == current_plate:
            if isinstance(parking_spots[spot_number], dict):
                parking_spots[spot_number]["status"] = True
            else:
                parking_spots[spot_number] = True
            save_data(parking_spots)
            print(f"✅ Veiksmīgi! Jūs atbrīvojāt vietu Nr. {spot_number}.")
        else:
            print(f"❌ Kļūda: Jūs nevarat atbrīvot vietu Nr. {spot_number}, jo to aizņēma c持o!")
    except Exception as e:
        print(f"❌ Kļūda: {e}")