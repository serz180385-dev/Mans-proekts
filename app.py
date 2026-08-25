from flask import Flask, render_template, request, redirect, session
from database import load_data, save_data, load_users, save_users
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "super_secret_parking_key"

# Тариф системы: 2 евро за один час парковки
PRICE_PER_HOUR = 2.0


@app.route('/')
def home():
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

    # Высчитываем интеллектуальную подсказку о следующем свободном месте
    earliest_spot = None
    earliest_time = None
    all_occupied = True

    for spot_id, spot_val in spots.items():
        if not isinstance(spot_val, dict):
            status = spot_val
        else:
            status = spot_val.get("status", True)

        if status is True:
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
        next_free_info = f"Visas vietas ir aizņemtas. Tuvākā brīvā būs vieta №{earliest_spot} plkst. {earliest_time.strftime('%H:%M')}."

    return render_template('index.html', spots=spots, current_plate=current_plate,
                           current_balance=current_balance, msg=request.args.get('msg'),
                           next_free_info=next_free_info)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        users = load_users()
        if username in users and users[username]["password"] == password:
            # Запоминаем уникальное имя пользователя, а не номер машины
            session["username"] = username
            return redirect('/')
        return render_template('login.html', error="Nepareizs lietotājvārds vai parole!")

    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    username = request.form['username'].strip()
    password = request.form['password'].strip()
    plate = request.form['plate'].strip().upper()

    if not username or not password or not plate:
        return render_template('login.html', error="Visi lauki ir obligāti!")

    users = load_users()

    # Проверка существования логина без учета регистра
    if username.lower() in [u.lower() for u in users.keys()]:
        return render_template('login.html', error="Šāds lietotājvārds jau eksistē!")

    # Привязываем профиль. Совпадение номеров машин (plate) теперь разрешено!
    users[username] = {"password": password, "plate": plate, "balance": 10.0, "is_ev": False}
    save_users(users)

    session["username"] = username
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

    # Проверка: занято ли место именно ЭТИМ госномером (работает для обоих водителей)
    car_already_parked = False
    for spot_val in parking_spots.values():
        if isinstance(spot_val, dict):
            status = spot_val.get("status")
            if isinstance(status, dict) and status.get("plate") == current_plate:
                car_already_parked = True
                break

    if action == 'book':
        if car_already_parked:
            return redirect('/?msg=Kluda: Jusu auto jau ir novietots!')

        target_spot = parking_spots[spot_number]
        is_user_ev = users[username].get("is_ev", False)

        # Блокировка ДВС-автомобилей на зарядках EV
        if isinstance(target_spot, dict) and target_spot.get("type") == "ev" and not is_user_ev:
            return redirect('/?msg=Kluda: Vietas no 21 lidz 25 paredzetas tikai Elektroauto!')

        # НОВАЯ БЛОКИРОВКА: Защита мест для инвалидов (1-5 места)
        is_user_disabled = users[username].get("is_disabled", False)
        if isinstance(target_spot, dict) and target_spot.get("type") == "disabled" and not is_user_disabled:
            return redirect('/?msg=Kluda: Vietas no 1 lidz 5 paredzetas tikai cilvekiem ar ipasam vajadzibam!')

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

            if not isinstance(parking_spots[spot_number], dict):
                parking_spots[spot_number] = {"type": "regular"}

            parking_spots[spot_number]["status"] = {
                "plate": current_plate,
                "booked_at": now.strftime("%d.%m.%Y %H:%M"),
                "duration_hours": duration,
                "ends_at": ends_at.strftime("%d.%m.%Y %H:%M")
            }
            save_data(parking_spots)
            return redirect(f'/?msg=Veiksmigi rezervets! Samaksats: {total_cost:.2f} EUR')
        else:
            return redirect('/?msg=Vieta jau aiznemta!')

    elif action == 'free':
        target_spot = parking_spots[spot_number]
        current_status = target_spot.get("status", True) if isinstance(target_spot, dict) else target_spot

        if current_status is True:
            return redirect('/?msg=Vieta jau ir briva!')
        # Любой из водителей этой машины может освободить её парковку
        elif isinstance(current_status, dict) and current_status.get("plate") == current_plate:
            if isinstance(parking_spots[spot_number], dict):
                parking_spots[spot_number]["status"] = True
            else:
                parking_spots[spot_number] = True
            save_data(parking_spots)
            return redirect('/?msg=Vieta veiksmigi atbrivota!')
        else:
            return redirect('/?msg=Kluda: Jus nevarat atbrivot svesu auto!')


@app.route('/topup', methods=['POST'])
def topup():
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
        # Деньги приходят строго тому, кто авторизован
        users[username]["balance"] = users[username].get("balance", 0.0) + amount
        save_users(users)

    return redirect(f'/?msg=Balanss veiksmigi papildinats par {amount:.2f} EUR!')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


if __name__ == '__main__':
    app.run(debug=True)