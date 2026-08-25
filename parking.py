import json
from datetime import datetime, timedelta
from database import load_data, save_data, load_users, save_users

# Стоимость одного часа парковки (2 евро)
PRICE_PER_HOUR = 2.0


def parking_menu(current_plate):
    """Главное меню управления парковкой"""
    while True:
        print(f"\nAuto: {current_plate} (Autostāvvieta):")
        print("1. Skatīt stāvvietu karti")
        print("2. Rezervēt vietu")
        print("3. Atbrīvot vietu")
        print("4. Iziet uz sākuma izvēlni")

        choice = input("Izvēlieties darbību (1-4): ").strip()

        if choice == "1":
            show_spots(current_plate)
        elif choice == "2":
            book_spot(current_plate)
        elif choice == "3":
            free_spot(current_plate)
        elif choice == "4":
            print("Atgriešanās sākuma izvēлnē...")
            break
        else:
            print("Kļūda: Nepareiza izvēle!")


def show_spots(current_plate):
    """1. Визуализация карты парковки в сетку с выводом госномера, времени и подсказки"""
    parking_spots = load_data()
    print("\n" + "=" * 80)
    print("                             AUTOSTĀVVIETAS KARTE                             ")
    print("=" * 80)

    earliest_spot = None
    earliest_time = None
    free_count = 0

    def get_vis(spot_id):
        nonlocal earliest_spot, earliest_time, free_count
        spot_val = parking_spots.get(str(spot_id), True)

        # Вытаскиваем статус и тип места с поддержкой старых и новых структур
        if isinstance(spot_val, dict):
            status = spot_val.get("status", True)
            is_ev = spot_val.get("type") == "ev"
        else:
            status = spot_val
            is_ev = int(spot_id) > 10

        spot_label = f"{spot_id}⚡" if is_ev else f"{spot_id} "

        if status is True:
            free_count += 1
            icon = "🟢"
            owner = ""
        else:
            icon = "🔴"
            if isinstance(status, dict):
                plate = status.get("plate", "???")
                time_str = status.get("ends_at", "")
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

    # Отрисовка 15 мест по 5 мест в ряд для красоты
    print("  " + " ".join(get_vis(i) for i in range(1, 6)))
    print("  " + " " + " ".join(get_vis(i) for i in range(6, 11)))
    print("  " + "—" * 76)
    print("              ⚡ ⚡ ⚡  ELEKTROAUTO ZONA (11-15)  ⚡ ⚡ ⚡     ")
    print("  " + "—" * 76)
    print("  " + " ".join(get_vis(i) for i in range(11, 16)))
    print("=" * 80)

    print(f" Kopā: {free_count} brīvas vietas no {len(parking_spots)}.")

    if free_count == 0 and earliest_time:
        formatted_time = earliest_time.strftime("%H:%M")
        print(f" ⚠️ Visas vietas aizņemtas! Tuvākā brīvā būs vieta №{earliest_spot} plkst. {formatted_time}.")

    print("=" * 80)


def book_spot(current_plate):
    """2. Функция бронирования места по госномеру с проверкой баланса и EV-типа"""
    try:
        parking_spots = load_data()

        # Проверка: не припаркована ли машина уже где-то
        for spot_val in parking_spots.values():
            if isinstance(spot_val, dict):
                status = spot_val.get("status")
                if isinstance(status, dict) and status.get("plate") == current_plate:
                    print(f"❌ Kļūda: Automašīna {current_plate} jau ir novietota stāvvietā!")
                    return
            elif spot_val == current_plate:
                print(f"❌ Kļūda: Automašīna {current_plate} jau ir novietota stāvvietā!")
                return

        spot_number = input("Ievadiet vietas numuru rezervēšanai (1-15): ").strip()

        if spot_number not in parking_spots:
            print("❌ Kļūda: Šāda vieta neeksistē!")
            return

        target_spot = parking_spots[spot_number]
        users = load_users()

        # Ищем текущего пользователя для проверки баланса и флага EV
        user_key = None
        for username, u_data in users.items():
            if u_data["plate"] == current_plate:
                user_key = username
                break

        is_user_ev = users[user_key].get("is_ev", False) if user_key else False

        # Блокировка ДВС на зарядках EV
        if isinstance(target_spot, dict) and target_spot.get("type") == "ev" and not is_user_ev:
            print("❌ Kļūda: Vietas no 11 līdz 15 paredzētas tikai Elektroauto!")
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

            if user_key:
                current_balance = users[user_key].get("balance", 0.0)
                if current_balance < total_cost:
                    print(f"❌ Kļūda: Nepietiek līdzekļu!")
                    print(f"Vajag: {total_cost:.2f} EUR, Jūsu balāns: {current_balance:.2f} EUR")
                    return

                # Списание средств
                users[user_key]["balance"] = current_balance - total_cost
                save_users(users)
            else:
                print("❌ Kļūда: Lietotājs ar šādu auto numuru nav atrasts!")
                return

            now = datetime.now()
            ends_at = now + timedelta(hours=duration)

            if not isinstance(parking_spots[spot_number], dict):
                parking_spots[spot_number] = {"type": "regular"}

            parking_spots[spot_number]["status"] = {
                "plate": current_plate,
                "booked_at": now.strftime("%d.%m.%Y %H:%M"),
                "duration_hours": duration,
                "ends_at": ends_at.strftime("%d.%m.%Y %H:%M")
            }
            save_data(parking_spots)
            print(f"✅ Veiksmīgi! Samaksāts: {total_cost:.2f} EUR.")
            print(f"Vieta №{spot_number} ir rezervēta līdz {parking_spots[spot_number]['status']['ends_at']}.")
        else:
            print(f"⚠️ Atvainojiet, vieta №{spot_number} jau ir aizņemta.")
    except Exception as e:
        print(f"❌ Kļūda: {e}")


def free_spot(current_plate):
    """3. Функция безопасного освобождения места по госномеру"""
    try:
        parking_spots = load_data()
        spot_number = input("Ievadiet vietas numuru, lai to atbrīvotu (1-15): ").strip()

        if spot_number not in parking_spots:
            print("❌ Kļūda: Šāda vieta neeksistē!")
            return

        target_spot = parking_spots[spot_number]
        current_status = target_spot.get("status", True) if isinstance(target_spot, dict) else target_spot

        if current_status is True:
            print(f"⚠️ Vieta №{spot_number} jau ir brīva!")
        elif isinstance(current_status, dict) and current_status.get("plate") == current_plate:
            # Безопасно меняем статус, не ломая структуру словаря
            if isinstance(parking_spots[spot_number], dict):
                parking_spots[spot_number]["status"] = True
            else:
                parking_spots[spot_number] = True
            save_data(parking_spots)
            print(f"✅ Veiksmīgi! Jūs atbrīvojāt vietu №{spot_number}.")
        else:
            print(f"❌ Kļūda: Jūs nevarat atbrīvot vietu №{spot_number}, jo to aizņēма cits auto!")
    except Exception as e:
        print(f"❌ Kļūda: {e}")