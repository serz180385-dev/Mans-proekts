import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for, flash
from database import load_data, load_users

app = Flask(__name__)
app.secret_key = "super_secret_parking_key"

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

# ATSLODZES MODUĻU REĢISTRĀCIJA (Importējam pēc žurnāla deklarēšanas)
# РЕГИСТРАЦИЯ МОДУЛЕЙ-РАЗГРУЗЧИКОВ (Импортируем после объявления лога)
from routes_driver import driver_bp
from routes_admin import admin_bp
from routes_emulator import emulator_bp

app.register_blueprint(driver_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(emulator_bp)

@app.route('/')
def home():
    """
    Interaktīvās stāvvietu kartes galvenā lapa autorizētiem vadītājiem
    Главная страница интерактивной карты парковки для авторизованных водителей
    """
    if "username" not in session:
        return redirect('/login')

    username = session["username"]
    spots = load_data()
    users = load_users()

    user_data = users.get(username)
    if not user_data:
        session.clear()
        return redirect('/login')

    current_plate = user_data["plate"]
    current_balance = user_data.get("balance", 0.0)
    is_admin = user_data.get("is_admin", False)

    # Aprēķinām viedo ieteikumu par nākamo brīvo vietu
    # Высчитываем интеллектуальную подсказку о следующем свободном месте
    earliest_spot = None
    earliest_time = None
    all_occupied = True

    for spot_id, spot_val in spots.items():
        status = spot_val.get("status", True) if isinstance(spot_val, dict) else spot_val

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
            f"Visas vietas ir aizņemtas. Tuvākā brīvā būs vieta Nr. {earliest_spot} "
            f"plkst. {earliest_time.strftime('%H:%M')}."
        )

    # Izņemts msg=request.args.get('msg') jaunās flash sistēmas atbalstam
    # Удален msg=request.args.get('msg') для поддержки новой системы flash
    return render_template('index.html', spots=spots, current_plate=current_plate,
                           current_balance=current_balance, next_free_info=next_free_info,
                           is_admin=is_admin)

@app.route('/logout')
def logout():
    """
    Lietotāja izrakstīšanās un sesijas dzēšana tīmekļa saskarnē
    Выход пользователя из системы и очистка сессии в веб-интерфейсе
    """
    # Dzēšam visus datus no lietotāja sesijas / Полностью очищаем куки сессии водителя/админа
    session.clear()
    # Pārvirzām uz autorizācijas lapu / Перенаправляем на страницу входа
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)