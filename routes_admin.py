import os
import re
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, session, send_file
from database import load_data, save_data, load_users, save_users, log_transaction  # Подключаем лог из базы данных

# Создаем блупринт для админки
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
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

    # Детальное форматирование статусов парковочных мест с проверкой просрочки [KAVĒ!]
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
                ends_at_str = status.get("ends_at", "")  # Формат: "dd.mm.yyyy HH:MM"

                time_part = ends_at_str.split(" ")[1] if " " in ends_at_str else ends_at_str
                display_text = f"{plate} līdz {time_part}"

                is_overdue = False
                if ends_at_str:
                    try:
                        ends_time = datetime.strptime(ends_at_str, "%d.%m.%Y %H:%M")
                        if datetime.now() > ends_time:
                            is_overdue = True
                            display_text += " [KAVĒ!]"  # Пометка нарушения времени парковки
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

    # Самостоятельный расчет загруженности регулярной зоны в процентах
    regular_spots = [s for k, s in spots.items() if (isinstance(s, dict) and s.get("type") == "regular") or (6 <= int(k) <= 20)]
    total_reg = len(regular_spots) if regular_spots else 15
    busy_reg = 0
    for k, s in spots.items():
        if (isinstance(s, dict) and s.get("type") == "regular") or (6 <= int(k) <= 20):
            status = s.get("status", True) if isinstance(s, dict) else s
            if status is not True:
                busy_reg += 1
    reg_occupancy = round((busy_reg / total_reg) * 100, 1)

    # Инициализируем финансовые счетчики по модулю abs()
    fin_report = {
        "total_revenue": 0.0,
        "total_penalties": 0.0,
        "total_topups": 0.0
    }

    transaction_history = []

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

    return render_template('admin.html',
                           users=users,
                           fin=fin_report,
                           occ=occupancy,
                           spots=admin_spots_display,
                           transactions=transaction_history,
                           msg=request.args.get('msg'))


@admin_bp.route('/admin/topup-user', methods=['POST'])
def admin_topup_user():
    """Принудительное начисление/списание баланса админом"""
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
        users[target_user]["balance"] = round(users[target_user].get("balance", 0.0) + bonus_amount, 2)
        save_users(users)

        sign = f"+{bonus_amount:.2f}" if bonus_amount >= 0 else f"{bonus_amount:.2f}"
        log_transaction("[💳 TOPUP]", target_user, f"Admin ({session['username']}) mainīja bilanci", sign)

        return redirect(f'/admin?msg=Lietotaja {target_user} balanss mainits par {bonus_amount:.2f} EUR!')
    return redirect('/admin?msg=Kluda: Lietotajs nav atrasts!')


@admin_bp.route('/admin/clear-spot/<spot_id>', methods=['POST'])
def admin_clear_spot(spot_id):
    """Экстренная эвакуация машины администратором"""
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

        log_transaction("[⚠️ PENALTY]", "admin", f"Piespiedu evakuācija no vietas Nr. {spot_id} (Auto: {plate_info})", "0.00")

        return redirect(f'/admin?msg=Vieta Nr. {spot_id} veiksmigi atbrivota piespiedu karta!')
    return redirect('/admin?msg=Kluda: Sada vieta neegziste!')


@admin_bp.route('/admin/export')
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