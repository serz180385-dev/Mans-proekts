import json
import os
from datetime import datetime, timedelta

DATA_FILE = "parking_data.json"
USERS_FILE = "users.json"

# =========================================================================
# SHĒMAS ĢENERĒŠANA UZ 25 VIETĀM (Saderīgs ar jaunajām HTML veidnēm)
# ГЕНЕРАЦИЯ СХЕМЫ НА 25 МЕСТ (Совместимо с новыми HTML шаблонами)
# =========================================================================
# 1-5: Cilvēkiem ar invaliditāti, 6-20: Parastās, 21-25: Elektroauto (EV)
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
    """Datu ielāde no JSON faila ar automātisku laika pagarināšanu un bilances norakstīšanu"""
    parking_spots = DEFAULT_SPOTS

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                parking_spots = json.load(f)
                # Pārbaude gludai vecās datubāzes migrācijai uz pilnām 25 vietām
                # Проверка для плавной миграции старой базы данных на полные 25 мест
                for spot_id, spot_type in DEFAULT_SPOTS.items():
                    if spot_id not in parking_spots:
                        parking_spots[spot_id] = spot_type
        except json.JSONDecodeError:
            parking_spots = DEFAULT_SPOTS

    now = datetime.now()
    updated_spots = False

    # Ielādējam lietotāju bāzi lokāli, lai izvairītos no failu cikliskā importa
    # Загружаем базу пользователей локально, чтобы избежать циклического импорта файлов
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception:
            users = {}
    else:
        users = {}

    users_updated = False

    for spot_id, spot_val in parking_spots.items():
        if isinstance(spot_val, dict) and isinstance(spot_val.get("status"), dict):
            status_dict = spot_val["status"]

            if "ends_at" in status_dict:
                try:
                    ends_at_time = datetime.strptime(status_dict["ends_at"], "%d.%m.%Y %H:%M")

                    # Ja laiks ir beidzies, bet automašīna joprojām atrodas stāvvietā (nebija izbraukšanas)
                    # Если время вышло, но машина по-прежнему на парковке (не было выезда)
                    if now > ends_at_time:
                        plate = status_dict.get("plate", "")

                        # Aprēķinām precīzu laika starpību un nosakām kavēto stundu skaitu
                        # Считаем точную разницу во времени и определяем количество просроченных часов
                        time_delta = now - ends_at_time
                        hours_overdue = int(time_delta.total_seconds() // 3600) + 1
                        if hours_overdue <= 0:
                            hours_overdue = 1

                        # Meklējam automašīnas īpašnieku pēc valsts numura iekš users.json
                        # Ищем владельца машины по госномуеру в users.json
                        owner_username = None
                        for uname, udata in users.items():
                            if udata.get("plate", "").replace("-", "").strip().upper() == plate.replace("-",
                                                                                                        "").strip().upper():
                                owner_username = uname
                                break

                        price_per_hour = 2.0  # Sistēmas bāzes tarifs par 1 papildu stundu
                        # Базовый тариф системы за 1 дополнительный час
                        total_overdue_cost = hours_overdue * price_per_hour

                        if owner_username:
                            # -------------------------------------------------
                            # 1. SCENĀRIJS: Reģistrēts klients (bīdām laiku un norakstām naudu)
                            # 1. СЦЕНАРИЙ: Зарегистрированный клиент (сдвигаем время и списываем деньги)
                            # -------------------------------------------------
                            current_balance = users[owner_username].get("balance", 10.0)
                            users[owner_username]["balance"] = round(current_balance - total_overdue_cost, 2)
                            users_updated = True

                            ends_at_time = ends_at_time + timedelta(hours=hours_overdue)
                            parking_spots[spot_id]["status"]["ends_at"] = ends_at_time.strftime("%d.%m.%Y %H:%M")

                            if "duration_hours" in parking_spots[spot_id]["status"]:
                                parking_spots[spot_id]["status"]["duration_hours"] += hours_overdue
                            else:
                                parking_spots[spot_id]["status"]["duration_hours"] = hours_overdue

                            parking_spots[spot_id]["status"]["is_extended"] = True
                            updated_spots = True

                            try:
                                log_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                                with open("transactions.txt", "a", encoding="utf-8") as log_file:
                                    log_file.write(
                                        f"{log_time} [💸 AUTO_EXT] Lietotājs: {owner_username:<12} | "
                                        f"Automātisks pagarinājums {hours_overdue} st. vietai Nr. {spot_id:<4} | Summa:  -{total_overdue_cost:.2f} EUR\n"
                                    )
                            except Exception:
                                pass
                        else:
                            # -------------------------------------------------
                            # 2. SCENĀRIJS: Nereģistrēts viesis (pārbīdām laiku droši uz priekšu)
                            # 2. СЦЕНАРИЙ: Незарегистрированный гость (сдвигаем время надежно вперед)
                            # -------------------------------------------------
                            ends_at_time = ends_at_time + timedelta(hours=hours_overdue)

                            # Ja jaunais laiks joprojām atpaliek no reālā, sinhronizējam to ar šo brīdi
                            # Если новое время всё ещё отстает от реального, синхронизируем с текущим моментом
                            if ends_at_time <= now:
                                ends_at_time = now + timedelta(hours=1)

                            parking_spots[spot_id]["status"]["ends_at"] = ends_at_time.strftime("%d.%m.%Y %H:%M")

                            if "duration_hours" in parking_spots[spot_id]["status"]:
                                parking_spots[spot_id]["status"]["duration_hours"] += hours_overdue
                            else:
                                parking_spots[spot_id]["status"]["duration_hours"] = hours_overdue

                            parking_spots[spot_id]["status"]["is_extended"] = True
                            updated_spots = True

                except ValueError:
                    pass

    # =========================================================================
    # FAILU SAGLABĀŠANA DISKĀ (ĀRPUS CIKLA FOR - ATKĀPE 4 ATSTARPES)
    # СОХРАНЕНИЕ ФАЙЛОВ НА ДИСК (ВНЕ ЦИКЛА FOR - ОТСТУП 4 ПРОБЕЛА)
    # =========================================================================
    if users_updated and users:
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    if updated_spots:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(parking_spots, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    return parking_spots


def save_data(data):
    """Datu saglabāšana JSON failā"""
    # Сохранение данных в JSON-файл
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Kļūda saglabājot datus: {e}")

    # =========================================================================
    # DARBS AR LIETOTĀJIEM UN TO STATUSIEM
    # РАБОТА С ПОЛЬЗОВАТЕЛЯМИ И ИХ СТАТУСАМИ
    # =========================================================================

def load_users():
        """
        Lietotāju ielāde no JSON ar veco kontu struktūras aizsardzību
        Загрузка пользователей из JSON с защитой структуры старых аккаунтов
        """
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    users = json.load(f)

                    # Datu struktūras aizsardzība veciem autovadītāju profiliem
                    # Защита структуры данных для старых профилей водителей
                    for username in users:
                        if "balance" not in users[username]:
                            users[username]["balance"] = 10.0

                        if "phone" not in users[username]:
                            users[username]["phone"] = "Nav norādīts"

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
        """
        Lietotāju saglabāšana JSON failā
        Сохранение пользователей в JSON
        """
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, ensure_ascii=False, indent=4)

def log_transaction(tag, user, details, amount_str):
        """
        Globāla skaistas žurnālēšanas funkcija failā transactions.txt
        Глобальная функция красивого логирования в transactions.txt
        """
        try:
            log_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            with open("transactions.txt", "a", encoding="utf-8") as log_file:
                log_file.write(
                    f"{log_time} {tag:<12} Lietotājs: {user:<12} | "
                    f"{details:<50} | Summa: {amount_str:>7} EUR\n"
                )
        except Exception:
            pass