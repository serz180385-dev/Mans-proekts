import re
from datetime import datetime
# Pievienots send_file failu lejupielādes atbalstam / Добавлено send_file для поддержки скачивания файлов
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file
from database import load_data, save_data, load_users, save_users  # Pievienots save_users / Добавлено save_users

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


# =========================================================================
# PIEVIENOTS: Globālais maršruts lietotāja bilances maiņai administratora panelī
# ДОБАВЛЕНО: Глобальный маршрут изменения баланса пользователя в админке
# =========================================================================
@app.route('/topup-user', methods=['POST'])
def admin_topup_user():
    """
    Lietotāja bilances piespiedu maiņa no administratora puses
    Принудительное начисление/списание баланса админом
    """
    if "username" not in session:
        return redirect('/login')

    users = load_users()
    if not users.get(session["username"], {}).get("is_admin", False):
        flash('Kļūda: Piekļuve liegta!')
        return redirect('/')

    target_user = request.form.get("target_user", "").strip().lower()
    try:
        bonus_amount = float(request.form.get("amount", 0))
    except ValueError:
        flash('Kļūda: Nepareizs summas formāфts!')
        return redirect('/admin')

    if target_user in users:
        users[target_user]["balance"] = round(users[target_user].get("balance", 0.0) + bonus_amount, 2)
        save_users(users)

        sign = f"+{bonus_amount:.2f}" if bonus_amount >= 0 else f"{bonus_amount:.2f}"
        log_transaction("[💳 TOPUP]", target_user, f"Admin ({session['username']}) mainīja bilanci", sign)

        flash(f'Lietotāja {target_user} balanss mainīts par {bonus_amount:.2f} EUR!')
        return redirect('/admin')

    flash('Kļūda: Lietotājs nav atrasts!')
    return redirect('/admin')


# =========================================================================
# PIEVIENOTS: Viesu piespiedu sodīšanas un CSDD datu nosūtīšanas maršruts
# ДОБАВЛЕНО: Маршрут принудительного штрафования гостей и отправки данных в CSDD
# =========================================================================
@app.route('/admin/guest-penalty/<spot_id>', methods=['POST'])
def admin_guest_penalty(spot_id):
    """
    Administratīvapārkāpuma akta sastādīšana viesim ar stundu maksas un fiksētā soda summēšanu
    Составление акта правонарушения гостю со складыванием платы за часы и фиксированного штрафа
    """
    if "username" not in session:
        return redirect('/login')

    users = load_users()
    if not users.get(session["username"], {}).get("is_admin", False):
        flash('Kļūda: Piekļuve liegta!')
        return redirect('/')

    spots = load_data()
    if spot_id in spots:
        plate = request.form.get("plate", "Nezināms").strip().upper()

        # Izgūstam stundu maksu no formas un droši konvertējam par skaitli
        # Извлекаем плату за часы из формы и безопасно конвертируем в число
        try:
            hours_fee = float(request.form.get("potential_fee", "0.00"))
        except ValueError:
            hours_fee = 0.0

        # KOMBINĒTAIS SODS: 30.00 EUR pamata sods + sakrājusies stundu maksa
        # КОМБИНИРОВАННЫЙ ШТРАФ: 30.00 EUR базовый штраф + набежавшая плата за часы
        base_penalty = 30.00
        total_penalty_calculated = base_penalty + hours_fee

        # Atbrīvojam vietu, saglabājot zonējuma tipu
        if isinstance(spots[spot_id], dict):
            spots[spot_id]["status"] = True
        else:
            spot_id_int = int(spot_id)
            s_type = "disabled" if spot_id_int <= 5 else ("ev" if spot_id_int > 20 else "regular")
            spots[spot_id] = {"status": True, "type": s_type}

        save_data(spots)

        # Žurnalējam pilno aprēķināto summu, lai tā korekti pieskaitītos finanšu skaitītājam
        # Логируем полную рассчитанную сумму, чтобы она корректно прибавилась к финансовому счетчику
        penalty_str = f"{total_penalty_calculated:.2f}"
        log_transaction("[⚠️ PENALTY]", "system",
                        f"Dispečers: Auto {plate} izrakstīts protokols (Sods+Stundas) vietā Nr. {spot_id}", penalty_str)

        flash(
            f'Pārkāpuma akts auto {plate} reģistrēts! Sods {base_penalty:.2f} EUR + stāvvietas maksa {hours_fee:.2f} EUR (Kopā: {penalty_str} EUR) nosūtīts uz CSDD.')
        return redirect('/admin')

    flash('Kļūda: Šāda vieta neeksistē!')
    return redirect('/admin')


# =========================================================================
# PIEVIENOTS: Globālais maršruts finanšu atskaiņu eksportēšanai failā .txt
# ДОБАВЛЕНО: Глобальный маршрут экспорта финансовых отчетов в файл .txt
# =========================================================================
@app.route('/admin/export')
def admin_export_report():
    """
    Darījumu vēstures faila lejupielāde tieši no administratora paneļa
    Скачивание файла истории транзакций напрямую из админки
    """
    import os
    if "username" not in session:
        return redirect('/login')

    users = load_users()
    if not users.get(session["username"], {}).get("is_admin", False):
        flash('Kļūda: Piekļuve liegta!')
        return redirect('/')

    # Pārbaudām faila fizisko eksistenci uz diska
    # Проверяем физическое наличие файла на диске
    if os.path.exists("transactions.txt"):
        return send_file("transactions.txt", as_attachment=True, download_name="parking_transactions.txt")

    # Kļūda: Žurnāli ir tukši!
    # Ошибка: Логи пустые!
    flash('Kļūda: Žurnāli ir tukši!')
    return redirect('/admin')


if __name__ == '__main__':
    app.run(debug=True)