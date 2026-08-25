import json
from datetime import datetime, timedelta
# Добавили импорт функций load_users и save_users для работы с кошельком
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
            print("Atgriešanās sākuma izvēlnē...")
            break
        else:
            print("Kļūda: Nepareiza izvēle!")


def show_spots(current_plate):
    """1. Визуализация карты парковки в сетку 2x5 с выводом госномера, времени и подсказки"""
    parking_spots = load_data()
    print("\n" + "=" * 75)
    print("             AUTOSTĀVVIETAS KARTE             ")
    print("=" * 75)

    earliest_spot = None
    earliest_time = None
    free_count = 0

    def get_vis(spot_id):
        nonlocal earliest_spot, earliest_time, free_count
        status = parking_spots.get(str(spot_id), True)

        if status is True:
            free_count += 1
            icon = "🟢"
            owner = ""
        else:
            if isinstance(status, dict):
                plate = status.get("plate", "???")
                time_str = status.get("ends_at", "")

                if " " in time_str:
                    ends = time_str.split(" ")[1]
                else:
                    ends = time_str

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

        space = " " if spot_id < 10 else ""
        return f"{spot_id}{space}[{icon}]{owner:<26}"

    print("  " + " ".join(get_vis(i) for i in range(1, 6)))
    print("  " + "—" * 71)
    print("              < < <  C E L Š  > > >     ")
    print("  " + "—" * 71)
    print("  " + " ".join(get_vis(i) for i in range(6, 11)))
    print("=" * 75)

    print(f" Kopā: {free_count} brīvas vietas no {len(parking_spots)}.")

    if free_count == 0 and earliest_time:
        formatted_time = earliest_time.strftime("%H:%M")
        print(f" ⚠️ Visas vietas aizņemtas! Tuvākā brīvā būs vieta №{earliest_spot} plkst. {formatted_time}.")

    print("=" * 75)


def book_spot(current_plate):
    """2. Функция бронирования места по госномеру с проверкой баланса и списанием денег"""
    try:
        parking_spots = load_data()

        for spot_val in parking_spots.values():
            if isinstance(spot_val, dict) and spot_val.get("plate") == current_plate:
                print(f"❌ Kļūda: Automašīna {current_plate} jau ir novietota stāvvietā!")
                return

        spot_number = input("Ievadiet vietas numuru rezervēšanai (1-10): ").strip()

        if spot_number not in parking_spots:
            print("❌ Kļūda: Šāda vieta neeksistē!")
            return

        if parking_spots[spot_number] is True:
            try:
                duration = int(input("Uz cik stundām rezervēt? (1-24): ").strip())
                if duration < 1 or duration > 24:
                    raise ValueError
            except ValueError:
                print("❌ Kļūda: Nepareizs stundu skaits! Rezervācija atcelta.")
                return

            # --- БЛОК ПРОВЕРКИ И СПИСАНИЯ БАЛАНСА В КОНСОЛИ ---
            users = load_users()
            user_key = None
            for username, u_data in users.items():
                if u_data["plate"] == current_plate:
                    user_key = username
                    break

            total_cost = duration * PRICE_PER_HOUR

            if user_key:
                current_balance = users[user_key].get("balance", 0.0)
                if current_balance < total_cost:
                    print(f"❌ Kļūda: Nepietiek līdzekļu!")
                    print(f"Vajag: {total_cost:.2f} EUR, Jūsu balāns: {current_balance:.2f} EUR")
                    return

                # Списываем деньги с кошелька
                users[user_key]["balance"] = current_balance - total_cost
                save_users(users)
            else:
                print("❌ Kļūda: Lietotājs ar šādu auto numuru nav atrasts!")
                return
            # -------------------------------------------------

            now = datetime.now()
            ends_at = now + timedelta(hours=duration)

            parking_spots[spot_number] = {
                "plate": current_plate,
                "booked_at": now.strftime("%d.%m.%Y %H:%M"),
                "duration_hours": duration,
                "ends_at": ends_at.strftime("%d.%m.%Y %H:%M")
            }
            save_data(parking_spots)
            print(f"✅ Veiksmīgi! Samaksāts: {total_cost:.2f} EUR.")
            print(f"Vieta №{spot_number} ir rezervēta līdz {parking_spots[spot_number]['ends_at']}.")
        else:
            print(f"⚠️ Atvainojiet, vieta №{spot_number} jau ir aizņemta.")
    except Exception as e:
        print(f"❌ Kļūda: {e}")


def free_spot(current_plate):
    """3. Функция освобождения места по госномеру"""
    try:
        parking_spots = load_data()
        spot_number = input("Ievadiet vietas numuru, lai to atbrīvotu (1-10): ").strip()

        if spot_number not in parking_spots:
            print("❌ Kļūda: Šāda vieta neeksistē!")
            return

        if parking_spots[spot_number] is True:
            print(f"⚠️ Vieta №{spot_number} jau ir brīva!")
        elif isinstance(parking_spots[spot_number], dict) and parking_spots[spot_number].get("plate") == current_plate:
            parking_spots[spot_number] = True
            save_data(parking_spots)
            print(f"✅ Veiksmīgi! Jūs atbrīvojāt vietu №{spot_number}.")
        else:
            print(f"❌ Kļūda: Jūs nevarat atbrīvot vietu №{spot_number}, jo to aizņēma cits auto!")
    except Exception as e:
        print(f"❌ Kļūda: {e}")