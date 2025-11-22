import telebot
import sqlite3
import os
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
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

    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE date BETWEEN ? AND ?
        GROUP BY category
    """, (week_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))

    rows = cursor.fetchall()

    if not rows:
        bot.reply_to(message, "Нет трат за неделю.")
        return

    text = "Траты за неделю:\n\n"
    for cat, total in rows:
        text += f"{cat}: {total} тг\n"

    bot.reply_to(message, text)


@bot.message_handler(commands=['month'])
def report_month(message):
    today = datetime.now()
    month_ago = today - timedelta(days=30)

    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE date BETWEEN ? AND ?
        GROUP GROUP BY category
    """, (month_ago.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))

    rows = cursor.fetchall()

    if not rows:
        bot.reply_to(message, "Нет трат за месяц.")
        return

    text = "Траты за месяц:\n\n"
    for cat, total in rows:
        text += f"{cat}: {total} тг\n"

    bot.reply_to(message, text)


@bot.message_handler(commands=['period'])
def report_period(message):
    parts = message.text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Формат: /period 2025-01-01 2025-01-31")
        return

    start, end = parts[1], parts[2]

    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE date BETWEEN ? AND ?
        GROUP BY category
    """, (start, end))

    rows = cursor.fetchall()

    if not rows:
        bot.reply_to(message, "Нет трат за этот период.")
        return

    text = f"Траты за период {start} — {end}:\n\n"
    for cat, total in rows:
        text += f"{cat}: {total} тг\n"

    bot.reply_to(message, text)


bot.polling(none_stop=True)
