import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # url твоего Render сервиса
bot = telebot.TeleBot(BOT_TOKEN)

# -----------------------
# Инициализация базы
# -----------------------
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

# -----------------------
# Команды бота
# -----------------------
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

@bot.message_handler(commands=['week'])
def report_week(message):
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    cursor.execute("SELECT category, SUM(amount) FROM expenses WHERE date BETWEEN ? AND ? GROUP BY category",
                   (week_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
    rows = cursor.fetchall()
    if not rows:
        bot.reply_to(message, "Нет трат за неделю.")
        return
    text = "📊 Траты за неделю:\n\n"
    for cat, total in rows:
        text += f"{cat}: {total} тг\n"
    bot.reply_to(message, text)

# можно добавить month и period по аналогии

# -----------------------
# Flask сервер
# -----------------------
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

# -----------------------
# Настройка вебхука
# -----------------------
bot.remove_webhook()
bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
