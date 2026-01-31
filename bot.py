# =============================================
# Telegram бот — Планнер тренировок для Railway (Напоминания каждые 3 часа)
# • Выбор дня недели и времени
# • Добавление/удаление тренировок
# • Inline-кнопки
# • Напоминания каждые 3 часа
# • Поддержка Telegram Stars @GRAF_DEMIDOV
# =============================================

import asyncio
import logging
import sqlite3
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command

# 🔑 Токен берём из переменной окружения (для Railway)
API_TOKEN = os.environ.get("API_TOKEN")

logging.basicConfig(level=logging.INFO)

# -------------------------------
# База данных
conn = sqlite3.connect("planner.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    day_of_week TEXT,
    time TEXT,
    title TEXT
)
""")
conn.commit()

# -------------------------------
# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# -------------------------------
# Inline клавиатуры
main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить тренировку", callback_data="add")],
    [InlineKeyboardButton(text="📅 Мои тренировки", callback_data="list")],
    [InlineKeyboardButton(text="⭐ Поддержать автора", url="https://t.me/stars/GRAF_DEMIDOV")]
])

days_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text=d, callback_data=f"day_{d}")] for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
])

times_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text=f"{h}:00", callback_data=f"time_{h}:00")] for h in range(6, 24)
])

# -------------------------------
# Старт бота
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("👋 Привет! Я бот-планнер тренировок. Выбери действие ниже:", reply_markup=main_kb)

# -------------------------------
# Добавление тренировок
user_temp = {}

@dp.callback_query(F.data == "add")
async def add_start(callback: CallbackQuery):
    await callback.message.answer("Выбери день недели для тренировки:", reply_markup=days_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("day_"))
async def add_day(callback: CallbackQuery):
    day = callback.data.split("_")[1]
    user_temp[callback.from_user.id] = {'day': day}
    await callback.message.answer(f"Выбран день: {day}\nТеперь выбери время:", reply_markup=times_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("time_"))
async def add_time(callback: CallbackQuery):
    time_chosen = callback.data.split("_")[1]
    user_temp[callback.from_user.id]['time'] = time_chosen
    await callback.message.answer("Отправь название тренировки:")
    await callback.answer()

@dp.message()
async def add_title(message: Message):
    if message.from_user.id in user_temp and 'day' in user_temp[message.from_user.id] and 'time' in user_temp[message.from_user.id]:
        day = user_temp[message.from_user.id]['day']
        t = user_temp[message.from_user.id]['time']
        title = message.text

        cursor.execute("INSERT INTO workouts (user_id, day_of_week, time, title) VALUES (?, ?, ?, ?)",
                       (message.from_user.id, day, t, title))
        conn.commit()
        await message.answer(f"✅ Тренировка добавлена: {day} в {t} — {title}", reply_markup=main_kb)
        user_temp.pop(message.from_user.id)

# -------------------------------
# Список и удаление
@dp.callback_query(F.data == "list")
async def list_workouts(callback: CallbackQuery):
    cursor.execute("SELECT id, day_of_week, time, title FROM workouts WHERE user_id=? ORDER BY day_of_week, time",
                   (callback.from_user.id,))
    rows = cursor.fetchall()

    if not rows:
        await callback.message.answer("Тренировок пока нет 😴", reply_markup=main_kb)
        await callback.answer()
        return

    for wid, day, t, title in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{wid}")]])
        await callback.message.answer(f"📅 {day} {t}\n🏋️ {title}", reply_markup=kb)

    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete_workout(callback: CallbackQuery):
    wid = int(callback.data.split("_")[1])
    cursor.execute("DELETE FROM workouts WHERE id=?", (wid,))
    conn.commit()
    await callback.message.edit_text("❌ Тренировка удалена")
    await callback.answer()

# -------------------------------
# Напоминания каждые 3 часа
async def reminder_task():
    while True:
        now = datetime.now()
        weekday = now.strftime('%a')
        time_now = now.strftime('%H:00')  # каждые полные часы

        cursor.execute("SELECT user_id, title FROM workouts WHERE day_of_week=? AND time=?", (weekday, time_now))
        reminders = cursor.fetchall()

        for user_id, title in reminders:
            try:
                await bot.send_message(user_id, f"⏰ Напоминание! Сегодня тренировка:\n🏋️ {title}")
            except Exception:
                pass

        await asyncio.sleep(3 * 60 * 60)  # пауза 3 часа

# -------------------------------
# Запуск
async def main():
    asyncio.create_task(reminder_task())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())