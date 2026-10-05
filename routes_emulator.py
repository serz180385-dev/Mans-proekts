from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, session
from database import load_data, save_data, load_users, save_users, log_transaction  # Подключили из базы данных

# Блупринт для эмулятора AI-камеры
emulator_bp = Blueprint('emulator', __name__)

# Константа тарифа
PRICE_PER_HOUR = 2.0


@emulator_bp.route('/admin/camera-emulator', methods=['POST'])
def camera_emulator():
    """Эмулятор камеры для демонстрации диплома комиссии"""
    if "username" not in session:
        return redirect('/login')

    users = load_users()
    if not users.get(session["username"], {}).get("is_admin", False):
        return redirect('/?msg=Kluda: Piekluve liegta!')

    spot_id = request.form.get("spot_id", "").strip()
    plate = request.form.get("plate", "").strip().upper()
    action = request.form.get("action")

    parking_spots = load_data()

    if spot_id not in parking_spots:
        return redirect('/admin?msg=Kluda: Sada vieta neegziste!')

    # --- СЦЕНАРИЙ 1: МАШИНА УЕХАЛА ---
    if action == "departure":
        current_status = parking_spots[spot_id].get("status", True) if isinstance(parking_spots[spot_id], dict) else parking_spots[spot_id]

        if current_status is True or current_status == "True":
            return redirect('/admin?msg=Kluda: Vieta jau ir briva!')

        is_guest = True
        owner_username = "system"

        actual_parked_plate = ""
        if isinstance(current_status, dict):
            actual_parked_plate = current_status.get("plate", "").replace("-", "").strip().upper()
        elif isinstance(current_status, str):
            actual_parked_plate = current_status.replace("-", "").strip().upper()

        if actual_parked_plate:
            plate = actual_parked_plate

        cam_plate = plate.replace("-", "").strip().upper()
        for uname, udata in users.items():
            db_plate = udata.get("plate", "").replace("-", "").strip().upper()
            if db_plate == cam_plate:
                is_guest = False
                owner_username = uname
                break

        if isinstance(parking_spots[spot_id], dict):
            parking_spots[spot_id]["status"] = True
        else:
            spot_id_int = int(spot_id)
            s_type = "disabled" if spot_id_int <= 5 else ("ev" if spot_id_int > 20 else "regular")
            parking_spots[spot_id] = {"status": True, "type": s_type}

        save_data(parking_spots)

        if is_guest:
            log_transaction("[⚠️ PENALTY]", "system", f"AI Kamera: Auto {plate} aizbrauca bez apmaksas! Nosutits CSDD", "30.00")
            return redirect(f'/admin?msg=Kamera fikseja parkapeju {plate}! Izrakstits sods 30.00 EUR.')
        else:
            log_transaction("[🚗 CAM_OUT]", owner_username, f"AI Kamera: Auto {plate} pameta vietu Nr. {spot_id}", "0.00")
            return redirect(f'/admin?msg=Kamera fikseja izbrauksanu! Vieta Nr. {spot_id} ir briva.')

    # --- СЦЕНАРИЙ 2: МАШИНА ПРИЕХАЛА ---
    if action == "arrival":
        if not isinstance(parking_spots[spot_id], dict):
            parking_spots[spot_id] = {"type": "regular"}

        now = datetime.now()
        ends_at = now + timedelta(hours=1)

        owner_username = "system"
        collected_amount = "0.00"

        for uname, udata in users.items():
            db_plate = udata.get("plate", "").replace("-", "").strip().upper()
            cam_plate = plate.replace("-", "").strip().upper()

            if db_plate == cam_plate:
                owner_username = uname
                current_balance = udata.get("balance", 0.0)

                if current_balance >= PRICE_PER_HOUR:
                    users[uname]["balance"] = round(current_balance - PRICE_PER_HOUR, 2)
                    save_users(users)
                    collected_amount = f"-{PRICE_PER_HOUR:.2f}"
                else:
                    collected_amount = "0.00"
                break

        parking_spots[spot_id]["status"] = {
            "plate": plate,
            "booked_at": now.strftime("%d.%m.%Y %H:%M"),
            "duration_hours": 1,
            "ends_at": ends_at.strftime("%d.%m.%Y %H:%M"),
            "disabled_card": None
        }
        save_data(parking_spots)

        log_transaction("[💸 CAM_IN]", owner_username, f"AI Kamera: Auto {plate} ienema vietu Nr. {spot_id}", collected_amount)
        return redirect(f'/admin?msg=Kamera fikseja iebrauksanu! Vieta Nr. {spot_id} aiznemta ar {plate}.')

    return redirect('/admin')