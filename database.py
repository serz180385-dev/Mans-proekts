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

    # =========================================================================
    # INTELIĢENTĀ AUTOMĀTISKĀ PAGARINĀŠANA UN STUNDAS NORAKSTĪŠANA NO MAKA
    # ИНТЕЛЛЕКТУАЛЬНОЕ АВТОПРОДЛЕНИЕ И ПОЧАСОВОЕ СПИСАНИЕ С КОШЕЛЬКА
    # =========================================================================
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

                        # KRITISKS CIKLA KĻŪDAS LABOJUMS:
                        # Aprēķinām precīzu laika starpību un nosakām kavēto stundu skaitu
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ БАГА ЗАЦИКЛИВАНИЯ:
                        # Считаем точную разницу во времени и определяем количество просроченных часов
                        time_delta = now - ends_at_time
                        hours_overdue = int(time_delta.total_seconds() // 3600) + 1

                        # Meklējam automašīnas īpašnieku pēc valsts numura iekš users.json
                        # Ищем владельца машины по госномер в users.json
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
                            # Iegūstam autovadītāja pašreizējo bilanci
                            # Извлекаем текущий баланс водителя
                            current_balance = users[owner_username].get("balance", 10.0)

                            # Norakstām naudu par visām kavētajām stundām uzreiz kā vienu summu
                            # Списываем деньги за все просроченные часы сразу одной суммой
                            users[owner_username]["balance"] = round(current_balance - total_overdue_cost, 2)
                            users_updated = True

                            # Pabīdām rezervācijas beigu laiku stingri uz priekšu par aprēķināto stundu skaitu
                            # Сдвигаем время окончания брони строго на вычисленное количество часов вперед
                            ends_at_time = ends_at_time + timedelta(hours=hours_overdue)
                            parking_spots[spot_id]["status"]["ends_at"] = ends_at_time.strftime("%d.%m.%Y %H:%M")

                            # Palielinām apmaksāto stundu skaitītāju stāvvietas sesijā par kavējuma stundu skaitu
                            # Увеличиваем счетчик оплаченных часов в сессии парковки на количество часов просрочки
                            if "duration_hours" in parking_spots[spot_id]["status"]:
                                parking_spots[spot_id]["status"]["duration_hours"] += hours_overdue

                            # 🆕 PIEVIENOTS: Automātiskās pagarināšanas marķieris attēlošanai klientam
                            # 🆕 ДОБАВЛЕНО: Маркер автоматического продления для отображения клиенту
                            parking_spots[spot_id]["status"]["is_extended"] = True
                            updated_spots = True

                            # Ierakstām vienu skaistu kopsavilkuma rindu failā transactions.txt bezgalīgu ciklu vietā
                            # Пишем одну красивую итоговую строчку в transactions.txt вместо бесконечных циклов
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
                            # Ja tas ir nereģistrēts viesis no kameras, vienkārši pabīdām sesijas laiku
                            # Если это незарегистрированный гость с камеры, просто сдвигаем время сессии
                            ends_at_time = ends_at_time + timedelta(hours=hours_overdue)
                            parking_spots[spot_id]["status"]["ends_at"] = ends_at_time.strftime("%d.%m.%Y %H:%M")
                            if "duration_hours" in parking_spots[spot_id]["status"]:
                                parking_spots[spot_id]["status"]["duration_hours"] += hours_overdue

                            parking_spots[spot_id]["status"]["is_extended"] = True
                            updated_spots = True

                except ValueError:
                    pass

        # Sinhronizējam un pārrakstām JSON failus diskā, ja ir izmaiņas
        # Синхронизируем и перезаписываем JSON-файлы на диск при наличии изменений
        if users_updated and users:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=4)

        if updated_spots:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(parking_spots, f, ensure_ascii=False, indent=4)

        return parking_spots

def save_data(data):
        """Datu saglabāšana JSON failā"""
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

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