# =====================================================
# 🏋️ PRO Telegram бот — Планнер тренировок (POSTGRESQL)
# • FSM (aiogram 3)
# • Inline UI
# • Профиль пользователя
# • Статистика тренировок
# • Гибкий интервал напоминаний
# • PostgreSQL (Railway-ready)
# • Поддержка проекта → переход к @GRAF_DEMIDOV
# =====================================================

import asyncio
import logging
import os
from datetime import datetime

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# -------------------------------
# ENV
API_TOKEN = os.getenv("API_TOKEN")
DATABASE_URL = os.getenv("postgresql://postgres:YudFMXUnZvyvseDzxxBboMSrWKKHnNkS@postgres.railway.internal:5432/railway")
logging.basicConfig(level=logging.INFO)

# -------------------------------
# FSM
class AddWorkout(StatesGroup):
    day = State()
    time = State()
    title = State()

class SetInterval(StatesGroup):
    interval = State()

# -------------------------------
# Bot
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# -------------------------------
# DB pool
pool: asyncpg.Pool

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            reminders_interval INT DEFAULT 3,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS workouts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            day TEXT,
            time TEXT,
            title TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS stats (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            workout_id INT REFERENCES workouts(id),
            done_at TIMESTAMP DEFAULT NOW()
        );
        """)

# -------------------------------
# UI
main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить тренировку", callback_data="add")],
    [InlineKeyboardButton(text="📅 Мои тренировки", callback_data="list")],
    [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
    [InlineKeyboardButton(text="⭐ Поддержать проект", url="https://t.me/GRAF_DEMIDOV")]
])

days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
days_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=d, callback_data=f"day_{d}")] for d in days])

times_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{h}:00", callback_data=f"time_{h}:00")] for h in range(6, 24)])

interval_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⏱ 1 час", callback_data="int_1")],
    [InlineKeyboardButton(text="⏱ 3 часа", callback_data="int_3")],
    [InlineKeyboardButton(text="⏱ 6 часов", callback_data="int_6")]
])

# -------------------------------
# Helpers
async def ensure_user(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id
        )

# -------------------------------
# Start
@dp.message(Command("start"))
async def start(message: Message):
    await ensure_user(message.from_user.id)
    await message.answer(
        "🔥 <b>Планнер тренировок</b>\n\n"
        "Тренируйся регулярно и отслеживай прогресс 💪",
        reply_markup=main_kb,
        parse_mode="HTML"
    )

# -------------------------------
# Add workout FSM
@dp.callback_query(F.data == "add")
async def add_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddWorkout.day)
    await cb.message.answer("📅 Выбери день недели", reply_markup=days_kb)
    await cb.answer()

@dp.callback_query(AddWorkout.day, F.data.startswith("day_"))
async def add_day(cb: CallbackQuery, state: FSMContext):
    await state.update_data(day=cb.data.split("_")[1])
    await state.set_state(AddWorkout.time)
    await cb.message.answer("⏰ Выбери время", reply_markup=times_kb)
    await cb.answer()

@dp.callback_query(AddWorkout.time, F.data.startswith("time_"))
async def add_time(cb: CallbackQuery, state: FSMContext):
    await state.update_data(time=cb.data.split("_")[1])
    await state.set_state(AddWorkout.title)
    await cb.message.answer("🏋️ Напиши название тренировки")
    await cb.answer()

@dp.message(AddWorkout.title)
async def add_title(message: Message, state: FSMContext):
    data = await state.get_data()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO workouts (user_id, day, time, title) VALUES ($1,$2,$3,$4)",
            message.from_user.id, data['day'], data['time'], message.text
        )
    await message.answer("✅ Тренировка добавлена", reply_markup=main_kb)
    await state.clear()

# -------------------------------
# Profile & stats
@dp.callback_query(F.data == "profile")
async def profile(cb: CallbackQuery):
    async with pool.acquire() as conn:
        u = await conn.fetchrow("SELECT reminders_interval FROM users WHERE user_id=$1", cb.from_user.id)
        count = await conn.fetchval("SELECT COUNT(*) FROM workouts WHERE user_id=$1", cb.from_user.id)
        done = await conn.fetchval("SELECT COUNT(*) FROM stats WHERE user_id=$1", cb.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏱ Интервал напоминаний", callback_data="set_interval")]])
    await cb.message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"🏋️ Тренировок: {count}\n"
        f"✅ Выполнено: {done}\n"
        f"⏱ Интервал: {u['reminders_interval']} ч",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await cb.answer()

# -------------------------------
# Interval
@dp.callback_query(F.data == "set_interval")
async def set_interval(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SetInterval.interval)
    await cb.message.answer("⏱ Выбери интервал напоминаний", reply_markup=interval_kb)
    await cb.answer()

@dp.callback_query(SetInterval.interval, F.data.startswith("int_"))
async def save_interval(cb: CallbackQuery, state: FSMContext):
    interval = int(cb.data.split("_")[1])
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET reminders_interval=$1 WHERE user_id=$2", interval, cb.from_user.id)
    await cb.message.answer("✅ Интервал обновлён", reply_markup=main_kb)
    await state.clear()
    await cb.answer()

# -------------------------------
# Reminder loop
async def reminder_loop():
    while True:
        async with pool.acquire() as conn:
            users = await conn.fetch("SELECT user_id, reminders_interval FROM users")
            now = datetime.now()
            day = days[now.weekday()]
            time_now = now.strftime("%H:00")

            for u in users:
                if now.hour % u['reminders_interval'] != 0:
                    continue
                workouts = await conn.fetch(
                    "SELECT id, title FROM workouts WHERE user_id=$1 AND day=$2 AND time=$3",
                    u['user_id'], day, time_now
                )
                for w in workouts:
                    try:
                        await bot.send_message(
                            u['user_id'],
                            f"⏰ <b>Пора тренироваться!</b>\n🏋️ {w['title']}",
                            parse_mode="HTML"
                        )
                        await conn.execute(
                            "INSERT INTO stats (user_id, workout_id) VALUES ($1,$2)",
                            u['user_id'], w['id']
                        )
                    except:
                        pass
        await asyncio.sleep(3600)

# -------------------------------
# Run
async def main():
    await init_db()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
