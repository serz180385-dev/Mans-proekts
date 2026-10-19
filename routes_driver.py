import re
from datetime import datetime, timedelta
# Pievienojam flash funkciju Flask importa rindā vienreizējiem paziņojumiem
# Добавляем функцию flash в строку импорта Flask для одноразовых уведомлений
from flask import Blueprint, request, redirect, session, render_template, flash
from database import load_data, save_data, load_users, save_users, log_transaction  # Pieslēdzam no datu bāzes / Подключаем из базы данных

# Vadītāju maršrutu Blueprint
# Блупринт для роутов водителей
driver_bp = Blueprint('driver', __name__)

PRICE_PER_HOUR = 2.0


@driver_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_input = request.form['username'].strip().lower()
        password = request.form['password'].strip()

        users = load_users()
        found_username = None
        for existing_user in users.keys():
            if existing_user.lower() == username_input:
                found_username = existing_user
                break

        if found_username and users[found_username]["password"] == password:
            session["username"] = found_username
            return redirect('/')

        return render_template('login.html', error="Nepareizs lietotājvārds vai parole!")

    return render_template('login.html')


@driver_bp.route('/register', methods=['POST'])
def register():
    username = request.form['username'].strip().lower()
    password = request.form['password'].strip()
    plate = request.form['plate'].strip().upper()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()

    is_ev = True if request.form.get('is_ev') == 'on' else False
    is_disabled = True if request.form.get('is_disabled') == 'on' else False
    disabled_card = request.form.get('disabled_card', '').strip()

    if not username or not password or not plate or not phone or not email:
        return render_template('login.html', error="Visi lauki ir obligāti!")

    # REGEX VALIDĀCIJAS
    # ВАЛИДАЦИИ REGEX
    if not re.match(r"^[A-Z]{2}\d{1,4}$", plate):
        return render_template('login.html', error="Nepareizs auto numura formāts! Jābūt, piemēram, AA1234")

    if not re.match(r"^\+\d{1,3}\d{6,10}$", phone):
        return render_template('login.html', error="Nepareizs tālruņa formāts! Piemēрам +37120000000")

    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return render_template('login.html', error="Nepareizs e-pasta formāts! Piemēram: vards@piemers.lv")

    if is_disabled:
        if not disabled_card or not re.match(r"^\d{6}$", disabled_card):
            return render_template('login.html', error="Nepareizs apliecības formāts! Jābūt taisni 6 cipariem (piem., 123456)")
    else:
        disabled_card = None

    users = load_users()
    if username.lower() in [u.lower() for u in users.keys()]:
        return render_template('login.html', error="Šāds lietotājvārds jau eksistē!")

    users[username.lower()] = {
        "password": password,
        "plate": plate,
        "phone": phone,
        "email": email,
        "balance": 10.0,
        "is_ev": is_ev,
        "is_disabled": is_disabled,
        "disabled_card": disabled_card
    }
    save_users(users)

    session["username"] = username.lower()
    return redirect('/')


@driver_bp.route('/', methods=['POST'])
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

    car_already_parked = False
    for spot_val in parking_spots.values():
        if isinstance(spot_val, dict):
            status = spot_val.get("status")
            if isinstance(status, dict) and status.get("plate") == current_plate:
                car_already_parked = True
                break

        # === DARBĪBA: REZERVĀCIJA ===
        # === ДЕЙСТВИЕ: БРОНИРОВАНИЕ ===
        if action == 'book':
            if car_already_parked:
                flash('Kļūda: Jūsu auto jau ir novietots!')
                return redirect('/')

            target_spot = parking_spots[spot_number]
            spot_id_int = int(spot_number)
            username_key = username.lower()

            is_user_disabled = users[username_key].get("is_disabled", False)
            user_disabled_card = users[username_key].get("disabled_card")
            is_user_ev = users[username_key].get("is_ev", False)

            if isinstance(target_spot, dict):
                spot_type = target_spot.get("type", "regular")
            else:
                spot_type = "disabled" if spot_id_int <= 5 else ("ev" if spot_id_int > 20 else "regular")

            if (spot_type == "disabled" or 1 <= spot_id_int <= 5) and (not is_user_disabled or not user_disabled_card):
                flash('Kļūda: Vietas no 1 līdz 5 paredzētas tikai cilvēkiem ar īpašām vajadzībām!')
                return redirect('/')

            if (spot_type == "ev" or 21 <= spot_id_int <= 25) and not is_user_ev:
                flash('Kļūda: Vietas no 21 līdz 25 paredzētas tikai Elektroauto!')
                return redirect('/')

            current_status = target_spot.get("status", True) if isinstance(target_spot, dict) else target_spot

            if current_status is True:
                total_cost = duration * PRICE_PER_HOUR
                current_balance = users[username_key].get("balance", 0.0)

                if current_balance < total_cost:
                    flash(f'Kļūda: Nepietiek līdzekļu! Vajag {total_cost:.2f} EUR, Jums ir {current_balance:.2f} EUR')
                    return redirect('/')

                users[username_key]["balance"] = round(current_balance - total_cost, 2)
                save_users(users)

                now = datetime.now()
                ends_at = now + timedelta(hours=duration)

                if not isinstance(parking_spots[spot_number], dict):
                    parking_spots[spot_number] = {"type": spot_type}

                parking_spots[spot_number]["status"] = {
                    "plate": current_plate,
                    "booked_at": now.strftime("%d.%m.%Y %H:%M"),
                    "duration_hours": duration,
                    "ends_at": ends_at.strftime("%d.%m.%Y %H:%M"),
                    "disabled_card": user_disabled_card if spot_id_int <= 5 else None
                }
                save_data(parking_spots)

                log_transaction("[💸 PAYMENT]", username_key, f"Rezervēta vieta Nr. {spot_number} uz {duration} st.",
                                f"-{total_cost:.2f}")
                flash(f'Veiksmīgi rezervēts! Samaksāts: {total_cost:.2f} EUR')
                return redirect('/')
            else:
                flash('Vieta jau aizņemta!')
                return redirect('/')

        # === DARBĪBA: ATBRĪVOŠANA ===
        # === ДЕЙСТВИЕ: ОСВОБОЖДЕНИЕ ===
        elif action == 'free':
            target_spot = parking_spots[spot_number]
            current_status = target_spot.get("status", True) if isinstance(target_spot, dict) else target_spot

            if current_status is True:
                flash('Vieta jau ir brīva!')
                return redirect('/')

            elif isinstance(current_status, dict) and current_status.get("plate") == current_plate:
                if isinstance(parking_spots[spot_number], dict):
                    parking_spots[spot_number]["status"] = True
                else:
                    parking_spots[spot_number] = True
                save_data(parking_spots)

                log_transaction("[🚗 FREE]", username, f"Atbrīvoja vietu Nr. {spot_number}", "0.00")
                flash('Vieta veiksmīgi atbrīvota!')
                return redirect('/')
            else:
                flash('Kļūda: Jūs nevarat atbrīvot svešu auto!')
                return redirect('/')

        return redirect('/')

    @driver_bp.route('/topup', methods=['POST'])
    def topup():
        if "username" not in session:
            return redirect('/login')

        username = session["username"]
        try:
            amount_raw = request.form.get('amount', '0').strip().replace(',', '.')
            amount = round(float(amount_raw), 2)

            if amount <= 0:
                flash('Kļūda: Summai jābūt lielākai par 0!')
                return redirect('/')
            if amount > 1000.0:
                flash('Kļūda: Maksimālā viena papildināšanas summa ir 1000 EUR!')
                return redirect('/')
        except ValueError:
            flash('Kļūda: Nepareizs summas formāts!')
            return redirect('/')

        users = load_users()
        if username in users:
            current_balance = users[username].get("balance", 0.0)
            users[username]["balance"] = round(current_balance + amount, 2)
            save_users(users)

            log_transaction("[💳 TOPUP]", username, "Papildināja savu virtuālo maku", f"+{amount:.2f}")

        flash(f'Balanss veiksmīgi papildināts par {amount:.2f} EUR!')
        return redirect('/')

    @app.route('/logout')
    def logout():
        """Lietotāja izrakstīšanās un sesijas dzēšana"""
        session.clear()
        return redirect('/login')