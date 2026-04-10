from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from datetime import datetime
import aiohttp
from aiohttp import web
import asyncio
import os
import aiocron

from config import BOT_TOKEN, ADMIN_GROUP_ID
from google_api import (
    async_get_user_info, async_add_user, async_get_all_users,
    async_is_payment_today, async_update_last_payment_date
)

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())


# Состояния FSM
class RegisterUser(StatesGroup):
    waiting_for_name = State()
    waiting_for_car = State()


class PhotoType(StatesGroup):
    waiting_for_check = State()
    waiting_for_car_photo = State()


# Старт и приветствие
@dp.message_handler(commands=['start', 'help'])
async def greet_user(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        KeyboardButton("🔐 Я арендатор"),
        KeyboardButton("👤 Профиль")
    )
    keyboard.add(
        KeyboardButton("💸 Отправить чек"),
        KeyboardButton("📷 ФОТО АВТО")
    )
    await message.answer(
        "Привет! Я бот по аренде авто 🚗\n\nЯ могу:\n"
        "— Показать твою информацию\n"
        "— Принять оплату (чек)\n"
        "— Напомнить о платеже\n"
        "— Принять фотоотчёт по авто\n\n"
        "Выбери, что хочешь сделать 👇",
        reply_markup=keyboard
    )


# Кнопка регистрации
@dp.message_handler(lambda message: message.text == "🔐 Я арендатор", state="*")
async def start_registration(message: types.Message, state: FSMContext):
    telegram_id = str(message.from_user.id)
    info = await async_get_user_info(telegram_id)

    if info:
        await message.answer(f"Ты уже зарегистрирован как {info['name']}, номер авто: {info['car']}")
        return

    await state.set_state(RegisterUser.waiting_for_name)
    await state.update_data(telegram_id=telegram_id)
    await message.answer("Введи своё имя:")


# Ввод имени
@dp.message_handler(state=RegisterUser.waiting_for_name, content_types=types.ContentTypes.TEXT)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(RegisterUser.waiting_for_car)
    await message.answer("Теперь введи госномер автомобиля (ГРЗ):")


# Ввод ГРЗ
@dp.message_handler(state=RegisterUser.waiting_for_car, content_types=types.ContentTypes.TEXT)
async def process_car(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    name = user_data.get("name")
    car = message.text
    telegram_id = user_data.get("telegram_id")

    await async_add_user(telegram_id, name, car)
    await message.answer(f"Спасибо, {name}! Ты зарегистрирован как арендатор машины {car}.")
    await state.finish()


# Профиль (кнопка и команда)
async def _send_profile(message: types.Message):
    user_id = str(message.from_user.id)
    info = await async_get_user_info(user_id)

    if info:
        payment_today = await async_is_payment_today(user_id)
        payment_status = "✅ Оплата за сегодня получена" if payment_today else "⚠️ Оплата за сегодня не найдена"
        await message.answer(
            f"👤 Имя: {info['name']}\n"
            f"🚗 Госномер: {info['car']}\n"
            f"📌 Статус: {info['status']}\n"
            f"💸 Задолженность: {info['debt']} ₽\n"
            f"{payment_status}"
        )
    else:
        await message.answer("Ты не зарегистрирован в системе.")


@dp.message_handler(commands=['профиль'])
async def show_profile(message: types.Message):
    await _send_profile(message)


@dp.message_handler(lambda message: message.text == "👤 Профиль", state="*")
async def show_profile_button(message: types.Message):
    await _send_profile(message)


# Кнопка "Отправить чек" — устанавливает стейт ожидания фото чека
@dp.message_handler(lambda message: message.text == "💸 Отправить чек", state="*")
async def send_check_info(message: types.Message, state: FSMContext):
    await state.set_state(PhotoType.waiting_for_check)
    await message.answer(
        "📸 Пришли фото чека (скриншот или фото).\n\n"
        "Я автоматически передам его администратору и зафиксирую оплату. "
        "Чек должен быть понятным и с видимой суммой. Спасибо!"
    )


# Кнопка "ФОТО АВТО" — устанавливает стейт ожидания фото авто
@dp.message_handler(lambda message: message.text == "📷 ФОТО АВТО", state="*")
async def request_car_photos(message: types.Message, state: FSMContext):
    await state.set_state(PhotoType.waiting_for_car_photo)
    await message.answer(
        "📷 Пожалуйста, пришли 5 фото автомобиля:\n"
        "1. Справа\n2. Слева\n3. Спереди\n4. Сзади\n5. Спидометр\n\n"
        "Можно отправить всё одним или несколькими сообщениями."
    )


# Приём фото чека
@dp.message_handler(state=PhotoType.waiting_for_check, content_types=types.ContentType.PHOTO)
async def receive_check_photo(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    info = await async_get_user_info(user_id)

    if not info:
        await message.answer("Ты не зарегистрирован в системе.")
        await state.finish()
        return

    today = datetime.now().strftime("%d.%m.%Y")
    caption = (
        f"💸 Чек оплаты от {info['name']} ({info['car']})\n"
        f"Telegram ID: {user_id}\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    await bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=message.photo[-1].file_id, caption=caption)
    await async_update_last_payment_date(user_id, today)
    await message.answer("Чек принят. Оплата зафиксирована. Спасибо!")
    await state.finish()


# Приём фото авто
@dp.message_handler(state=PhotoType.waiting_for_car_photo, content_types=types.ContentType.PHOTO)
async def receive_car_photo(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    info = await async_get_user_info(user_id)

    if not info:
        await message.answer("Ты не зарегистрирован в системе.")
        await state.finish()
        return

    caption = (
        f"📷 Фото авто от {info['name']} ({info['car']})\n"
        f"Telegram ID: {user_id}\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    await bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=message.photo[-1].file_id, caption=caption)
    await message.answer("Фото принято. Спасибо!")


# Рассылка напоминаний об оплате
async def notify_users_about_debt():
    users = await async_get_all_users()
    if not users:
        return

    today = datetime.now().strftime("%d.%m.%Y")
    tasks = []
    for user in users:
        user_id = str(user.get("ID"))
        name = user.get("Имя")
        car = user.get("ГРЗ")
        last_payment = str(user.get("Последняя оплата", "")).strip()

        if last_payment != today:
            tasks.append(bot.send_message(
                user_id,
                f"❗ Привет, {name}!\n\nТы ещё не оплатил аренду за сегодня.\n"
                f"🚗 Госномер: {car}\n\nПожалуйста, отправь чек до полуночи. Спасибо!"
            ))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[Ошибка отправки уведомления] {result}")


# Самопинг каждые 10 минут — не даёт Render Free засыпать
@aiocron.crontab('*/10 * * * *')
async def self_ping():
    url = os.getenv("RENDER_EXTERNAL_URL")
    if url:
        try:
            async with aiohttp.ClientSession() as session:
                await session.get(url, timeout=aiohttp.ClientTimeout(total=10))
            print("[self_ping] OK")
        except Exception as e:
            print(f"[self_ping] {e}")


# Ежедневно в 23:00 — напоминание об оплате
@aiocron.crontab('0 20 * * *')  # 20:00 UTC = 23:00 МСК
async def scheduled_reminder():
    await notify_users_about_debt()


# Каждую пятницу в 13:00 МСК (10:00 UTC) — напоминание о фото (только чётные недели)
@aiocron.crontab('0 10 * * 5')
async def remind_photo_report():
    if datetime.now().isocalendar()[1] % 2 != 0:
        return

    users = await async_get_all_users()
    tasks = []
    for user in users:
        user_id = str(user.get("ID"))
        name = user.get("Имя")

        if not user_id:
            continue

        tasks.append(bot.send_message(
            user_id,
            f"📷 Привет, {name}!\n\nНапоминаем, что пора прислать свежие фото автомобиля:\n"
            "1. Справа\n2. Слева\n3. Спереди\n4. Сзади\n5. Спидометр\n\n"
            "Ждём фотоотчёт 🙌"
        ))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            print(f"[Ошибка отправки напоминания] {result}")


# Простой веб-сервер для Render (Web Service требует открытый порт)
async def health(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# Запуск бота
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    if os.getenv("PORT"):  # только на Render
        loop.run_until_complete(start_web())
    executor.start_polling(dp, skip_updates=True, loop=loop)
