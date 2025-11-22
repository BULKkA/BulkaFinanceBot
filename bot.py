import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# -------------------------
# Настройки бота
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://<твоя-служба>.onrender.com
bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------
# Инициализация базы
# -------------------------
DB_PATH = "expenses.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    category TEXT,
    amount INTEGER
)
""")
conn.commit()

# -------------------------
# Меню команд Telegram
# -------------------------
bot.set_my_commands([
    telebot.types.BotCommand("/week", "Траты за неделю"),
    telebot.types.BotCommand("/month", "Траты за месяц"),
    telebot.types.BotCommand("/period", "Траты за выбранный период")
])

# -------------------------
# Основные функции
# -------------------------
def get_report(start_date, end_date):
    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE date BETWEEN ? AND ?
        GROUP BY category
    """, (start_date, end_date))
    rows = cursor.fetchall()
    return rows

def format_report(rows, start, end=None):
    if not rows:
        return f"Нет трат за период {start}" if end is None else f"Нет трат за период {start} — {end}"
    if end:
        text = f"📊 Траты за период {start} — {end}:\n\n"
    else:
        text = f"📊 Траты с {start}:\n\n"
    for cat, total in rows:
        text += f"{cat}: {total} тг\n"
    return text

# -------------------------
# Добавление трат
# -------------------------
@bot.message_handler(func=lambda m: not m.text.startswith("/"))
def add_expense(message):
    text = message.text.strip()
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(message, "Формат: категория сумма (пример: еда 1500)")
        return
    category = parts[0]
    amount = int(parts[1])
    date = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO expenses (date, category, amount) VALUES (?, ?, ?)",
                   (date, category, amount))
    conn.commit()
    bot.reply_to(message, f"Добавлено: {category} — {amount} тг")

# -------------------------
# Отчёты
# -------------------------
@bot.message_handler(commands=['week'])
def report_week(message):
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    rows = get_report(week_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    text = format_report(rows, week_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    bot.reply_to(message, text)

@bot.message_handler(commands=['month'])
def report_month(message):
    today = datetime.now()
    month_ago = today - timedelta(days=30)
    rows = get_report(month_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    text = format_report(rows, month_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    bot.reply_to(message, text)

# -------------------------
# Интерактивная команда /period
# -------------------------
@bot.message_handler(commands=['period'])
def period_start(message):
    bot.send_message(message.chat.id, "Введите период в формате: YYYY-MM-DD YYYY-MM-DD")
    bot.register_next_step_handler(message, period_process)

def period_process(message):
    text = message.text.strip()
    parts = text.split()
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

    rows = get_report(start, end)
    text = format_report(rows, start, end)
    bot.send_message(message.chat.id, text)

# -------------------------
# Кнопки меню /start
# -------------------------
@bot.message_handler(commands=['start'])
def start(message):
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
# Flask сервер для Webhook
# -------------------------
app = Flask(__name__)

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
