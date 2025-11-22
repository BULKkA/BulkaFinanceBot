import os
import json
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# -------------------------
# Настройки бота
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://<твоя-служба>.onrender.com
CHAT_ID = int(os.getenv("CHAT_ID"))  # твой Telegram ID
bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------
# Google Sheets
# -------------------------
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")  # JSON ключ сервисного аккаунта
creds_dict = json.loads(GOOGLE_CREDS_JSON)
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

SHEET_NAME = os.getenv("SHEET_NAME", "ExpensesBot")
sheet = client.open(SHEET_NAME).sheet1

# -------------------------
# Функции работы с данными
# -------------------------
def add_expense(category, amount):
    date = datetime.now().strftime("%Y-%m-%d")
    sheet.append_row([date, category, amount])

def get_report(start_date, end_date):
    data = sheet.get_all_records()
    if not data:
        return {}
    df = pd.DataFrame(data)
    df['Date'] = pd.to_datetime(df['Date'])
    mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))
    filtered = df.loc[mask]
    report = filtered.groupby('Category')['Amount'].sum().to_dict()
    return report

def format_table_report(report_dict, start, end):
    if not report_dict:
        return f"Нет трат за период {start} — {end}"
    text = f"📊 Траты за период {start} — {end}\n\n"
    text += f"{'Категория':<15} {'Сумма':>7}\n"
    text += "-"*24 + "\n"
    for cat, total in report_dict.items():
        text += f"{cat:<15} {total:>7} тг\n"
    return f"```\n{text}\n```"

# -------------------------
# Обработка сообщений
# -------------------------
@bot.message_handler(func=lambda m: not m.text.startswith("/"))
def handle_add(message):
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(message, "Формат: категория сумма (пример: еда 1500)")
        return
    category, amount = parts[0], int(parts[1])
    add_expense(category, amount)
    bot.reply_to(message, f"Добавлено: {category} — {amount} тг")

# -------------------------
# Отчёты
# -------------------------
@bot.message_handler(commands=['week'])
def report_week(message):
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    report = get_report(week_ago, today)
    text = format_table_report(report, week_ago, today)
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['month'])
def report_month(message):
    today = datetime.now().date()
    month_ago = today - timedelta(days=30)
    report = get_report(month_ago, today)
    text = format_table_report(report, month_ago, today)
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['period'])
def period_start(message):
    bot.send_message(message.chat.id, "Введите период в формате: YYYY-MM-DD YYYY-MM-DD")
    bot.register_next_step_handler(message, period_process)

def period_process(message):
    parts = message.text.strip().split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Неверный формат! Попробуйте снова: YYYY-MM-DD YYYY-MM-DD")
        bot.register_next_step_handler(message, period_process)
        return
    start, end = parts[0], parts[1]
    try:
        datetime.strptime(start, "%Y-%m-%d")
        datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат дат! Попробуйте снова: YYYY-MM-DD YYYY-MM-DD")
        bot.register_next_step_handler(message, period_process)
        return
    report = get_report(start, end)
    text = format_table_report(report, start, end)
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# -------------------------
# Меню /start
# -------------------------
@bot.message_handler(commands=['start'])
def start_cmd(message):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Траты за неделю", callback_data="week"),
        InlineKeyboardButton("Траты за месяц", callback_data="month")
    )
    markup.row(
        InlineKeyboardButton("Траты за период", callback_data="period")
    )
    bot.send_message(message.chat.id, "Выберите команду:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "week":
        report_week(call.message)
    elif call.data == "month":
        report_month(call.message)
    elif call.data == "period":
        period_start(call.message)

# -------------------------
# Автоматическая еженедельная и ежемесячная отправка
# -------------------------
def scheduled_reports():
    while True:
        now = datetime.now()
        # Еженедельный отчёт — понедельник 10:00
        if now.weekday() == 0 and now.hour == 10 and now.minute == 0:
            start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
            report = get_report(start, end)
            text = format_table_report(report, start, end)
            bot.send_message(CHAT_ID, text, parse_mode="Markdown")
            time.sleep(60)
        # Ежемесячный отчёт — 1 число 10:00
        if now.day == 1 and now.hour == 10 and now.minute == 0:
            first_day_last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
            last_day_last_month = now.replace(day=1) - timedelta(days=1)
            report = get_report(first_day_last_month.strftime("%Y-%m-%d"), last_day_last_month.strftime("%Y-%m-%d"))
            text = format_table_report(report, first_day_last_month.strftime("%Y-%m-%d"), last_day_last_month.strftime("%Y-%m-%d"))
            bot.send_message(CHAT_ID, text, parse_mode="Markdown")
            time.sleep(60)
        time.sleep(30)

threading.Thread(target=scheduled_reports, daemon=True).start()

# -------------------------
# Flask сервер и Webhook
# -------------------------
app = Flask(__name__)

@app.route("/ping")
def ping():
    return "Bot alive", 200

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running"

# -------------------------
# Настройка вебхука
# -------------------------
bot.remove_webhook()
bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
