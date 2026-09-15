import re  # <-- ШАГ 1: Добавляем встроенный модуль регулярных выражений
from flask import Flask, render_template, request, redirect, session
from database import load_data, save_data, load_users, save_users
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "super_secret_parking_key"

# Тариф системы: 2 евро за один час парковки
PRICE_PER_HOUR = 2.0


def log_transaction(tag, user, details, amount_str):
    """
    Вспомогательная функция для наведения красоты в файле transactions.txt.
    Выравнивает все записи строго по колонкам «тютелька в тютельку».
    """
    try:
        log_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        with open("transactions.txt", "a", encoding="utf-8") as log_file:
            # Строгое форматирование по ширине полей: тэг (12), юзер (12), детали (50), сумма (7)
            log_file.write(
                f"{log_time} {tag:<12} Lietotājs: {user:<12} | "
                f"{details:<50} | Summa: {amount_str:>7} EUR\n"
            )
    except Exception:
        pass  # Защита сервера от сбоев записи на диск, чтобы программа не падала


@app.route('/')
def home():
    """Главная страница интерактивной карты парковки для авторизованных водителей"""
    # Проверяем авторизацию по имени пользователя
    if "username" not in session:
        return redirect('/login')

    username = session["username"]
    spots = load_data()
    users = load_users()

    # Извлекаем данные конкретного авторизованного пользователя
    user_data = users.get(username)
    if not user_data:
        session.clear()
        return redirect('/login')

    current_plate = user_data["plate"]
    current_balance = user_data.get("balance", 0.0)

    # Безопасное считывание флага админа
    is_admin = user_data.get("is_admin", False)

    # Высчитываем интеллектуальную подсказку о следующем свободном месте
    earliest_spot = None
    earliest_time = None
    all_occupied = True

    for spot_id, spot_val in spots.items():
        # УНИВЕРСАЛЬНАЯ ПРОВЕРКА СТАТУСА (для старого и нового формата JSON)
        if isinstance(spot_val, dict):
            status = spot_val.get("status", True)
        else:
            status = spot_val

        if status is True or status == "True":
            all_occupied = False
        elif isinstance(status, dict) and "ends_at" in status:
            try:
                spot_time = datetime.strptime(status["ends_at"], "%d.%m.%Y %H:%M")
                if earliest_time is None or spot_time < earliest_time:
                    earliest_time = spot_time
                    earliest_spot = spot_id
            except ValueError:
                continue

    next_free_info = None
    if all_occupied and earliest_time:
        next_free_info = (
            f"Visas vietas ir aizņemtas. Tuvākā brīvā būs vieta №{earliest_spot} "
            f"plkst. {earliest_time.strftime('%H:%M')}."
        )

    # Возвращаем полностью рабочий рендер страницы без ошибок
    return render_template('index.html', spots=spots, current_plate=current_plate,
                           current_balance=current_balance, msg=request.args.get('msg'),
                           next_free_info=next_free_info, is_admin=is_admin)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Считываем введенные в форму данные и очищаем от пробелов
        username_input = request.form['username'].strip().lower()
        password = request.form['password'].strip()

        users = load_users()

        # Переводим ключи базы данных в нижний регистр для безошибочного сравнения
        found_username = None
        for existing_user in users.keys():
            if existing_user.lower() == username_input:
                found_username = existing_user
                break

        # Если пользователь найден и пароль совпал — авторизуем
        if found_username and users[found_username]["password"] == password:
            session["username"] = found_username
            return redirect('/')

        return render_template('login.html', error="Nepareizs lietotājvārds vai parole!")

    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    # Принудительно переводим логин в нижний регистр при создании аккаунта
    username = request.form['username'].strip().lower()
    password = request.form['password'].strip()
    plate = request.form['plate'].strip().upper()

    # Считывание чекбоксов специальных статусов из HTML-формы
    is_ev = True if request.form.get('is_ev') == 'on' else False
    is_disabled = True if request.form.get('is_disabled') == 'on' else False

    # ДОБАВЛЕНО: Считывание номера удостоверения инвалида из формы
    disabled_card = request.form.get('disabled_card', '').strip()

    if not username or not password or not plate:
        return render_template('login.html', error="Visi lauki ir obligāti!")

    # =========================================================================
    # ШАГ 2: ВАЛИДАЦИЯ REGEX ДЛЯ ЛАТВИЙСКИХ НОМЕРОВ
    # Шаблон: 2 заглавные латинские буквы, дефис, от 1 до 4 цифр (например, AA-1234)
    # =========================================================================
    plate_pattern = r"^[A-Z]{2}\d{1,4}$"

    if not re.match(plate_pattern, plate):
        return render_template('login.html', error="Nepareizs auto numura formāts! Jābūt, piemēram, AA1234")
    # =========================================================================

    # =========================================================================
    # ДОБАВЛЕНО: ВАЛИДАЦИЯ REGEX ДЛЯ УДОСТОВЕРЕНИЯ ИНВАЛИДА (Строго 6 цифр)
    # =========================================================================
    if is_disabled:
        if not disabled_card:
            return render_template('login.html', error="Kļūda: Jāievada invalīda apliecības numurs!")

        card_pattern = r"^\d{6}$"  # Регулярное выражение: ровно 6 цифр
        if not re.match(card_pattern, disabled_card):
            return render_template('login.html',
                                   error="Nepareizs apliecības formāts! Jābūt taisni 6 cipariem (piem., 123456)")
    else:
        disabled_card = None  # Если статус инвалида не выбран, обнуляем поле
    # =========================================================================

    users = load_users()

    # Исключаем создание дубликатов в разном регистре
    username_key = username.lower()
    if username_key in [u.lower() for u in users.keys()]:
        return render_template('login.html', error="Šāds lietotājvārds jau eksistē!")

    # Привязываем профиль с поддержкой флагов EV, Инвалидности и Номера удостоверения
    users[username_key] = {
        "password": password,
        "plate": plate,
        "balance": 10.0,
        "is_ev": is_ev,
        "is_disabled": is_disabled,
        "disabled_card": disabled_card  # <-- ДОБАВЛЕНО: сохраняем документ в базу данных
    }
    save_users(users)

    session["username"] = username_key
    return redirect('/')


@app.route('/', methods=['POST'])
def handle_parking():
    if "username" not in session:
        return redirect('/login')

    username = session["username"]
    users = load_users()

    if username not in users:
        return redirect('/login')

    current_plate = users[username]["plate"]
    spot_number = request.form.get('spot_number', '').strip()
    action = request.form.get('action')

    try:
        duration = int(request.form.get('duration', 1))
    except ValueError:
        duration = 1

    parking_spots = load_data()

    if spot_number not in parking_spots:
        return redirect('/?msg=Kluda: Sada vieta neegziste!')

    # Проверка: занято ли в принципе хоть одно место на парковке этой машиной
    car_already_parked = False
    for spot_val in parking_spots.values():
        if isinstance(spot_val, dict):
            status = spot_val.get("status")
            if isinstance(status, dict) and status.get("plate") == current_plate:
                car_already_parked = True
                break

    # === ДЕЙСТВИЕ: БРОНИРОВАНИЕ ===
    if action == 'book':
        if car_already_parked:
            return redirect('/?msg=Kluda: Jusu auto jau ir novietots!')

        target_spot = parking_spots[spot_number]

        # ---------------------------------------------------------------------
        # УЛУЧШЕНО: ГЛУБОКАЯ ПРОВЕРКА УДОСТОВЕРЕНИЯ ИНВАЛИДА ПРИ БРОНИРОВАНИИ
        # ---------------------------------------------------------------------
        is_user_disabled = users[username].get("is_disabled", False)
        # Извлекаем сохраненный номер удостоверения из базы данных пользователей
        user_disabled_card = users[username].get("disabled_card")

        # Определяем, является ли выбранное место инвалидным (места 1-5)
        is_spot_disabled = (isinstance(target_spot, dict) and target_spot.get("type") == "disabled") or (
                    1 <= int(spot_number) <= 5)

        if is_spot_disabled:
            # Блокируем бронирование, если нет статуса ИЛИ в базе отсутствует/пустой номер удостоверения
            if not is_user_disabled or not user_disabled_card:
                return redirect(
                    '/?msg=Kluda: Vietas no 1 lidz 5 paredzetas tikai cilvekiem ar ipasam vajadzibam un invalidu apliecibu!')
        # ---------------------------------------------------------------------

        # Блокировка ДВС-автомобилей на зарядках EV (21-25 места) по типу и по номеру
        is_user_ev = users[username].get("is_ev", False)
        is_spot_ev = (isinstance(target_spot, dict) and target_spot.get("type") == "ev") or (
                21 <= int(spot_number) <= 25)
        if is_spot_ev and not is_user_ev:
            return redirect('/?msg=Kluda: Vietas no 21 lidz 25 paredzetas tikai Elektroauto!')

        current_status = target_spot.get("status", True) if isinstance(target_spot, dict) else target_spot

        if current_status is True:
            total_cost = duration * PRICE_PER_HOUR
            current_balance = users[username].get("balance", 0.0)

            if current_balance < total_cost:
                return redirect(
                    f'/?msg=Kluda: Nepietiek lidzeklu! Vajag {total_cost:.2f} EUR, Jums ir {current_balance:.2f} EUR')

            # Точечное списание баланса конкретного водителя
            users[username]["balance"] = current_balance - total_cost
            save_users(users)

            now = datetime.now()
            ends_at = now + timedelta(hours=duration)

            # Восстанавливаем структуру типа данных при ручных сбросах базы
            if not isinstance(parking_spots[spot_number], dict):
                spot_id_int = int(spot_number)
                s_type = "disabled" if spot_id_int <= 5 else ("ev" if spot_id_int > 20 else "regular")
                parking_spots[spot_number] = {"type": s_type}

            # Записываем полные данные о бронировании, включая номер документа
            parking_spots[spot_number]["status"] = {
                "plate": current_plate,
                "booked_at": now.strftime("%d.%m.%Y %H:%M"),
                "duration_hours": duration,
                "ends_at": ends_at.strftime("%d.%m.%Y %H:%M"),
                # ДОБАВЛЕНО: привязываем номер удостоверения к активной брони места
                "disabled_card": user_disabled_card if is_spot_disabled else None
            }
            save_data(parking_spots)
            return redirect(f'/?msg=Veiksmigi rezervets! Samaksats: {total_cost:.2f} EUR')
        else:
            return redirect('/?msg=Vieta jau aiznemta!')

    # === ДЕЙСТВИЕ: ОСВОБОЖДЕНИЕ ===
    elif action == 'free':
        target_spot = parking_spots[spot_number]
        current_status = target_spot.get("status", True) if isinstance(target_spot, dict) else target_spot

        if current_status is True:
            return redirect('/?msg=Vieta jau ir briva!')
        elif isinstance(current_status, dict) and current_status.get("plate") == current_plate:
            if isinstance(parking_spots[spot_number], dict):
                parking_spots[spot_number]["status"] = True
            else:
                parking_spots[spot_number] = True
            save_data(parking_spots)
            return redirect('/?msg=Vieta veiksmigi atbrivota!')
        else:
            return redirect('/?msg=Kluda: Jus nevarat atbrivot svesu auto!')

    return redirect('/')


@app.route('/topup', methods=['POST'])
def topup():
    """Пополнение баланса водителем из личного кабинета с авто-логированием"""
    if "username" not in session:
        return redirect('/login')

    username = session["username"]
    try:
        amount = float(request.form.get('amount', 0))
        if amount <= 0:
            return redirect('/?msg=Kluda: Summai jabut lielakai par 0!')
    except ValueError:
        return redirect('/?msg=Kluda: Nepareizs summas formats!')

    users = load_users()
    if username in users:
        users[username]["balance"] = users[username].get("balance", 0.0) + amount
        save_users(users)

        # Вызов красивой функции логирования
        log_transaction("[💳 TOPUP]", username, "Papildināja savu virtuālo maku", f"+{amount:.2f}")

    return redirect(f'/?msg=Balanss veiksmigi papildinats par {amount:.2f} EUR!')


# =========================================================================
# ВЕБ-ИНТЕРФЕЙС И РОУТЫ ПАНЕЛИ АДМИНИСТРАТОРА
# =========================================================================
from flask import send_file
import os


@app.route('/admin')
def admin_panel():
    """Главная страница администратора с визуальными таблицами, точной статистикой и логами"""
    if "username" not in session:
        return redirect('/login')

    users = load_users()
    current_user_data = users.get(session["username"])

    # Строгая проверка на права администратора
    if not current_user_data or not current_user_data.get("is_admin", False):
        return redirect('/?msg=Kluda: Tev nav administratora tiesibu!')

    spots = load_data()

    # 1. Самостоятельный расчет загруженности регулярной зоны в процентах
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

    # 2. Инициализируем финансовые счетчики и массив истории
    fin_report = {
        "total_revenue": 0.0,
        "total_penalties": 0.0,
        "total_topups": 0.0
    }

    transaction_history = []

    # 3. Безопасно парсим transactions.txt с извлечением реальных сумм
    if os.path.exists("transactions.txt"):
        try:
            with open("transactions.txt", "r", encoding="utf-8") as f:
                for line in f:
                    cleaned_line = line.strip()
                    if not cleaned_line:
                        continue

                    transaction_history.append(cleaned_line)

                    import re
                    match = re.search(r"Summa:\s*[+-]?\s*([\d.]+)", cleaned_line)
                    if match:
                        actual_amount = float(match.group(1))

                        if "[💸 PAYMENT]" in cleaned_line:
                            fin_report["total_revenue"] += actual_amount
                        elif "[⚠️ PENALTY]" in cleaned_line:
                            fin_report["total_penalties"] += actual_amount
                        elif "[💳 TOPUP]" in cleaned_line:
                            fin_report["total_topups"] += actual_amount
        except Exception:
            pass

    transaction_history.reverse()
    occupancy = {"regular": reg_occupancy}

    return render_template('admin.html',
                           users=users,
                           fin=fin_report,
                           occ=occupancy,
                           spots=spots,
                           transactions=transaction_history,
                           msg=request.args.get('msg'))


@app.route('/admin/topup-user', methods=['POST'])
def admin_topup_user():
    """Принудительное начисление/списание баланса админом с выравниванием лога"""
    if "username" not in session:
        return redirect('/login')

    users = load_users()
    if not users.get(session["username"], {}).get("is_admin", False):
        return redirect('/?msg=Kluda: Piekluve liegta!')

    target_user = request.form.get("target_user", "").strip().lower()
    try:
        bonus_amount = float(request.form.get("amount", 0))
    except ValueError:
        return redirect('/admin?msg=Kluda: Nepareizs summas formats!')

    if target_user in users:
        users[target_user]["balance"] = users[target_user].get("balance", 0.0) + bonus_amount
        save_users(users)

        sign = f"+{bonus_amount:.2f}" if bonus_amount >= 0 else f"{bonus_amount:.2f}"
        log_transaction("[💳 TOPUP]", target_user, f"Admin ({session['username']}) mainīja bilanci", sign)

        return redirect(f'/admin?msg=Lietotaja {target_user} balanss mainits par {bonus_amount:.2f} EUR!')
    return redirect('/admin?msg=Kluda: Lietotajs nav atrasts!')


@app.route('/admin/clear-spot/<spot_id>', methods=['POST'])
def admin_clear_spot(spot_id):
    """Экстренная эвакуация машины администратором с красивым логированием"""
    if "username" not in session:
        return redirect('/login')

    users = load_users()
    if not users.get(session["username"], {}).get("is_admin", False):
        return redirect('/?msg=Piekluve+liegta')

    spots = load_data()
    if spot_id in spots:
        old_status = spots[spot_id].get("status") if isinstance(spots[spot_id], dict) else spots[spot_id]
        plate_info = "Nezināms"
        if isinstance(old_status, dict):
            plate_info = old_status.get("plate", "Nezināms")
        elif isinstance(old_status, str):
            plate_info = old_status

        if isinstance(spots[spot_id], dict):
            spots[spot_id]["status"] = True
        else:
            spots[spot_id] = True
        save_data(spots)

        log_transaction("[⚠️ PENALTY]", "admin", f"Piespiedu evakuācija no vietas №{spot_id} (Auto: {plate_info})",
                        "0.00")

        return redirect(f'/admin?msg=Vieta Nr.{spot_id} veiksmigi atbrivota piespiedu karta!')
    return redirect('/admin?msg=Kluda: Sada vieta neegziste!')


@app.route('/admin/export')
def admin_export_report():
    """Скачивание файла истории транзакций напрямую из админки"""
    if "username" not in session:
        return redirect('/login')

    users = load_users()
    if not users.get(session["username"], {}).get("is_admin", False):
        return redirect('/?msg=Piekluve+liegta')

    if os.path.exists("transactions.txt"):
        return send_file("transactions.txt", as_attachment=True, download_name="parking_transactions.txt")
    return redirect('/admin?msg=Kluda: Logi ir tuksni!')


@app.route('/logout')
def logout():
    """Безопасный выход пользователя из системы с очисткой сессии"""
    session.clear()
    return redirect('/login')


if __name__ == '__main__':
    app.run(debug=True)