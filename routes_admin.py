import os
import re
from datetime import datetime
# Pievienojam flash funkciju Flask importa rindā vienreizējiem paziņojumiem
# Добавляем функцию flash в строку импорта Flask для одноразовых уведомлений
from flask import Blueprint, render_template, request, redirect, session, send_file, flash
from database import load_data, save_data, load_users, save_users, \
    log_transaction  # Pieslēdzam žurnalēšanu no datu bāzes moduļa
                     # Подключаем лог из базы данных

# Izveidojam administrators moduļa Blueprint
# Создаем блупринт для админки
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def admin_panel():
    """
    Administratora galvenā lapa ar vizuālām tabulām, precīzu statistiku un žurnāliem
    Главная страница администратора с визуальными таблицами, точной статистикой и логами
    """
    if "username" not in session:
        return redirect('/login')

    all_users = load_users()
    current_user_data = all_users.get(session["username"])

    # Stingra administratora tiesību pārbaude
    # Строгая проверка на права администратора
    if not current_user_data or not current_user_data.get("is_admin", False):
        flash('Kluda: Tev nav administratora tiesibu!')
        return redirect('/')

    # =========================================================================
    # NEREĢISTRĒTO TRANSPORTLĪDZEKĻU FIKSĀCIJA UN UZSKAITE
    # СИСТЕМА ФИКСАЦИИ И УЧЕТА НЕЗАРЕГИСТРИРОВАННЫХ МАШИН (ГОСТЕЙ)
    # =========================================================================
    spots = load_data()
    guest_cars_parked = []
    price_per_hour = 2.0  # Sistēmas pamata tarifs / Базовый тариф системы

    for spot_id, spot_val in spots.items():
        if isinstance(spot_val, dict) and isinstance(spot_val.get("status"), dict):
            status_dict = spot_val["status"]
            plate = status_dict.get("plate", "").strip().upper()

            # Pārbaudām, vai auto numurs ir reģistrēts lietotāju bāzē
            # Проверяем, зарегистрирован ли номер машины в базе пользователей
            is_registered = False
            for udata in all_users.values():
                if udata.get("plate", "").replace("-", "").strip().upper() == plate.replace("-", "").strip().upper():
                    is_registered = True
                    break

            # Ja auto nav reģistrēts, bet vieta ir aizņemta — tas ir viesis
            # Если машина не зарегистрирована, но место занято — это гость
            if not is_registered and plate:
                try:
                    booked_at_time = datetime.strptime(status_dict["booked_at"], "%d.%m.%Y %H:%M")
                    time_stayed = datetime.now() - booked_at_time
                    hours_stayed = int(time_stayed.total_seconds() // 3600) + 1
                    if hours_stayed <= 0:
                        hours_stayed = 1
                except Exception:
                    hours_stayed = 1

                guest_cars_parked.append({
                    "spot_id": spot_id,
                    "plate": plate,
                    "booked_at": status_dict.get("booked_at"),
                    "potential_fee": f"{hours_stayed * price_per_hour:.2f}"
                })

    # =========================================================================
    # 🚀 MEKLĒŠANAS UN PAGINĀCIJAS SISTĒMA (AIZSARDZĪBA LIELAM LIETOTĀJU SKAITAM)
    # 🚀 СИСТЕМА ПОИСКА И ПАГИНАЦИИ (ЗАЩИТА ОТ СЛОВАРЕЙ С СОТНЯМИ ВОДИТЕЛЕЙ)
    # =========================================================================
    search_query = request.args.get('search', '').strip().lower()

    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    PER_PAGE = 5  # Izvadam tieši 5 lietotājus vienā lapā / Ограничиваем вывод строго по 5 водителей на одну страницу

    # 1. Lietotāju filtrēšana lidojumā
    # 1. Фильтрация пользователей на лету
    filtered_users = {}
    for uname, udata in all_users.items():
        plate = udata.get("plate", "").lower()
        phone = udata.get("phone", "").lower()
        email = udata.get("email", "").lower()

        # Meklējam sakritības visos profila laukos
        # Поиск совпадений по всем полям профиля
        if (not search_query or
                search_query in uname.lower() or
                search_query in plate or
                search_query in phone or
                search_query in email):
            filtered_users[uname] = udata

    # 2. Lapu skaita matemātiskais aprēķins
    # 2. Математический расчёт количества страниц
    total_filtered = len(filtered_users)
    total_pages = (total_filtered + PER_PAGE - 1) // PER_PAGE
    if total_pages == 0:
        total_pages = 1
    if page > total_pages:
        page = total_pages

    # 3. Droša datu apgriešana pašreizējai lapai
    # 3. Получение безопасного среза (слайса) данных для текущей страницы
    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE

    users_items = list(filtered_users.items())
    paginated_users = dict(users_items[start_idx:end_idx])
    # =========================================================================

    spots = load_data()

    # Detalizēta stāvvietu statusu formatēšana ar kavējuma pārbaudi [KAVĒ!]
    # Детальное форматирование статусов парковочных мест с проверкой просрочки [KAVЕ!]
    admin_spots_display = {}
    for i in range(1, 26):
        i_str = str(i)
        spot_val = spots.get(i_str, True)

        status = spot_val.get("status", True) if isinstance(spot_val, dict) else spot_val

        if status is True or status == "True":
            admin_spots_display[i_str] = {
                "text": "Brīvs",
                "is_occupied": False,
                "is_overdue": False,
                "plate": ""
            }
        else:
            if isinstance(status, dict):
                plate = status.get("plate", "???")
                ends_at_str = status.get("ends_at", "")  # Formāts: "dd.mm.yyyy HH:MM" / Формат: "dd.mm.yyyy HH:MM"

                # Izgūstam tikai laika daļu (HH:MM), nogriežot datumu / Берем только время, отрезая дату
                time_part = ends_at_str.split(" ")[1] if " " in ends_at_str else ends_at_str
                display_text = f"{plate} līdz {time_part}"

                # Automašīnas stāvēšanas laika pārkāpuma pārbaudes algoritms attiecībā pret servera laiku
                # Алгоритм проверки нарушения времени парковки относительно времени сервера
                is_overdue = False
                if ends_at_str:
                    try:
                        ends_time = datetime.strptime(ends_at_str, "%d.%m.%Y %H:%M")
                        if datetime.now() > ends_time:
                            is_overdue = True
                            display_text += " [KAVĒ!]"  # Pārkāpuma atzīme / Пометка нарушения
                    except ValueError:
                        pass

                admin_spots_display[i_str] = {
                    "text": display_text,
                    "is_occupied": True,
                    "is_overdue": is_overdue,
                    "plate": plate
                }
            else:
                admin_spots_display[i_str] = {
                    "text": f"{status}",
                    "is_occupied": True,
                    "is_overdue": False,
                    "plate": str(status)
                }

    # Parastās zonas noslodzes patstāvīgs aprēķins procentos
    # Самостоятельный расчет загруженности регулярной зоны в процентах
    regular_spots = [s for k, s in spots.items() if
                     (isinstance(s, dict) and s.get("type") == "regular") or (6 <= int(k) <= 20)]
    total_reg = len(regular_spots) if regular_spots else 15
    busy_reg = 0
    for k, s in spots.items():
        if (isinstance(s, dict) and s.get("type") == "regular") or (6 <= int(k) <= 20):
            status = s.get("status", True) if isinstance(s, dict) else s
            if status is not True:
                busy_reg += 1
    reg_occupancy = round((busy_reg / total_reg) * 100, 1)

    # Finanšu skaitītāju inicializācija ar moduli abs()
    # Инициализируем финансовые счетчики по модулю abs()
    fin_report = {
        "total_revenue": 0.0,
        "total_penalties": 0.0,
        "total_topups": 0.0
    }

    transaction_history = []

    # Žurnālu lasīšana un droša finanšu datu parsēšana
    # Чтение логов и безопасный финансовый парсинг
    if os.path.exists("transactions.txt"):
        try:
            with open("transactions.txt", "r", encoding="utf-8") as f:
                for line in f:
                    cleaned_line = line.strip()
                    if not cleaned_line:
                        continue

                    transaction_history.append(cleaned_line)

                    match = re.search(r"Summa:\s*[+-]?\s*([\d.]+)", cleaned_line)
                    if match:
                        try:
                            actual_amount = abs(float(match.group(1)))

                            if "PAYMENT" in cleaned_line:
                                fin_report["total_revenue"] = round(fin_report["total_revenue"] + actual_amount, 2)
                            elif "PENALTY" in cleaned_line:
                                fin_report["total_penalties"] = round(fin_report["total_penalties"] + actual_amount, 2)
                            elif "TOPUP" in cleaned_line:
                                fin_report["total_topups"] = round(fin_report["total_topups"] + actual_amount, 2)
                        except ValueError:
                            continue
        except Exception:
            pass
        
        transaction_history.reverse()
        occupancy = {"regular": reg_occupancy}

        # =========================================================================
        # NEREĢISTRĒTO VIESU PARĀDU UN ATSKAIŠU SISTĒMA (ATJAUNINĀTS)
        # СИСТЕМА УЧЕТА ДОЛГОВ И ОТЧЕТОВ НЕЗАРЕГИСТРИРОВАННЫХ ГОСТЕЙ (ОБНОВЛЕНО)
        # =========================================================================
        spots = load_data()
        guest_cars_parked = []
        price_per_hour = 2.0  # Tarifu konstante / Константа тарифа

        for spot_id, spot_val in spots.items():
            if isinstance(spot_val, dict) and isinstance(spot_val.get("status"), dict):
                status_dict = spot_val["status"]
                plate = status_dict.get("plate", "").strip().upper()

                # Pārbaudām, vai auto numurs ir reģistrēts lietotāju bāzē
                # Проверяем, зарегистрирован ли номер машины в базе пользователей
                is_registered = False
                for udata in all_users.values():
                    if udata.get("plate", "").replace("-", "").strip().upper() == plate.replace("-",
                                                                                                "").strip().upper():
                        is_registered = True
                        break

                # Ja auto nav reģistrēts — tas ir viesis, kuram jārēķina parāds
                # Если машина не зарегистрирована — это гость, которому нужно считать долг
                if not is_registered and plate:
                    try:
                        booked_at_time = datetime.strptime(status_dict["booked_at"], "%d.%m.%Y %H:%M")
                        time_stayed = datetime.now() - booked_at_time

                        # Aprēķinām pilno stundu skaitu (pat ja stāvējis 1 minūti, jāmaksā par pilnu stundu)
                        # Считаем количество полных часов (даже если стоял 1 минуту, платит за полный час)
                        hours_stayed = int(time_stayed.total_seconds() // 3600) + 1
                        if hours_stayed <= 0:
                            hours_stayed = 1
                    except Exception:
                        hours_stayed = 1

                    # Aprēķinām aktuālo parāda summu reālajā laikā
                    # Рассчитываем актуальную сумму долга в реальном времени
                    total_debt = hours_stayed * price_per_hour

                    guest_cars_parked.append({
                        "spot_id": spot_id,
                        "plate": plate,
                        "booked_at": status_dict.get("booked_at"),
                        "hours_stayed": hours_stayed,
                        "debt_amount": f"{total_debt:.2f}"
                    })
        # =========================================================================

        # Nosūtām paginētos datus, lapu marķierus un viesu sarakstu uz HTML priekšgalu
        # Отправляем пагинированные данные, маркеры страниц и список гостей в HTML-фронтенд
        return render_template('admin.html',
                               users=paginated_users,
                               current_page=page,
                               total_pages=total_pages,
                               search_query=search_query,
                               fin=fin_report,
                               occ=occupancy,
                               spots=admin_spots_display,
                               transactions=transaction_history,
                               guest_cars=guest_cars_parked)


    @admin_bp.route('/admin/clear-spot/<spot_id>', methods=['POST'])
    def admin_clear_spot(spot_id):
        """
        Operatīva automašīnas evakuācija no administratora puses ar žurnalēšanu
        Экстренная эвакуация машины администратором с логированием
        """
        if "username" not in session:
            return redirect('/login')

        users = load_users()
        if not users.get(session["username"], {}).get("is_admin", False):
            flash('Kļūda: Piekļuve liegta!')
            return redirect('/')

        spots = load_data()
        if spot_id in spots:
            old_status = spots[spot_id].get("status") if isinstance(spots[spot_id], dict) else spots[spot_id]
            plate_info = "Nezināms"

            # Droši izgūstam valsts numura zīmi
            # Безопасно извлекаем госномер
            if isinstance(old_status, dict):
                plate_info = old_status.get("plate", "Nezināms")
            elif isinstance(old_status, str):
                plate_info = old_status

            # Atiestatām stāvvietas statusu
            # Сбрасываем статус места парковки
            if isinstance(spots[spot_id], dict):
                spots[spot_id]["status"] = True
            else:
                spots[spot_id] = True

            save_data(spots)

            # Reģistrējam darbību sistēmas žurnālā
            # Записываем действие в лог
            log_transaction("[⚠️ PENALTY]", "admin",
                            f"Piespiedu evakuācija no vietas Nr. {spot_id} (Auto: {plate_info})", "0.00")

            flash(f'Vieta Nr. {spot_id} veiksmīgi atbrīvota piespiedu kārtā!')
            return redirect('/admin')

        flash('Kļūda: Šāda vieta neeksistē!')
        return redirect('/admin')