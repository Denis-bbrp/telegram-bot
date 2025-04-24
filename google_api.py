import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Подключение к Google Таблице
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

SHEET_ID = "1QP0mT5IgA54bIS_g2EKza6J2SvvkLj_ecFVPDpDGi3A"

def get_user_info(telegram_id):
    sheet = client.open_by_key(SHEET_ID).worksheet("Пользователи")
    records = sheet.get_all_records()

    for row in records:
        if str(row["ID"]) == str(telegram_id):
            return {
                "name": row["Имя"],
                "car": row["ГРЗ"],
                "debt": row.get("Задолженность", "0"),
                "status": row.get("Статус", "арендатор")
            }
    return None

from datetime import datetime

def is_payment_today(telegram_id):
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Пользователи")
        records = sheet.get_all_records()

        for row in records:
            if str(row.get("ID")) == str(telegram_id):
                last_payment = row.get("Последняя оплата", "")
                if last_payment:
                    today = datetime.now().strftime("%d.%m.%Y")
                    return last_payment.strip() == today
        return False
    except Exception as e:
        print(f"[Ошибка is_payment_today] {e}")
        return False

def add_user(user_id, name, car_plate):
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Пользователи")
        sheet.append_row([str(user_id), name, car_plate, "арендатор", "0", ""])
        print(f"Новый пользователь зарегистрирован: {name} ({car_plate}), ID: {user_id}")
    except Exception as e:
        print(f"[Ошибка add_user] {e}")

def update_user_debt(telegram_id, new_debt):
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Пользователи")
        records = sheet.get_all_records()
        cell_list = sheet.range(f"A2:A{len(records) + 1}")

        for i, cell in enumerate(cell_list):
            if str(cell.value) == str(telegram_id):
                sheet.update_cell(i + 2, 5, str(new_debt))  # Колонка 5 = "Задолженность"
                print(f"[OK] Задолженность пользователя {telegram_id} обновлена на {new_debt}")
                return True

        print(f"[Ошибка] Пользователь с ID {telegram_id} не найден")
        return False

    except Exception as e:
        print(f"[Ошибка update_user_debt] {e}")
        return False

def exists_user(telegram_id):
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Пользователи")
        records = sheet.get_all_records()
        return any(str(row.get("ID")) == str(telegram_id) for row in records)
    except Exception as e:
        print(f"[Ошибка exists_user] {e}")
        return False

def update_last_payment_date(telegram_id, date_str):
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Пользователи")
        records = sheet.get_all_records()
        cell_list = sheet.range(f"A2:A{len(records) + 1}")

        for i, cell in enumerate(cell_list):
            if str(cell.value) == str(telegram_id):
                sheet.update_cell(i + 2, 6, date_str)  # Колонка 6 = "Последняя оплата"
                print(f"[OK] Последняя оплата обновлена: {telegram_id} — {date_str}")
                return True

        print(f"[Ошибка] Пользователь с ID {telegram_id} не найден")
        return False

    except Exception as e:
        print(f"[Ошибка update_last_payment_date] {e}")
        return False
def get_all_users():
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Пользователи")
        records = sheet.get_all_records()
        return records
    except Exception as e:
        print(f"[Ошибка get_all_users] {e}")
        return []
