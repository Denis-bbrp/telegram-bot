from aiogram import Bot, Dispatcher, types, executor
from google_api import get_all_users, is_payment_today
import aiocron
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from datetime import datetime

from config import BOT_TOKEN, ADMIN_GROUP_ID
from google_api import get_user_info, add_user

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Состояния для FSM
class RegisterUser(StatesGroup):
    waiting_for_name = State()
    waiting_for_car = State()

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
@dp.message_handler(lambda message: message.text == "🔐 Я арендатор")
async def start_registration(message: types.Message, state: FSMContext):
    telegram_id = str(message.from_user.id)
    info = get_user_info(telegram_id)

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

    add_user(telegram_id, name, car)
    await message.answer(f"Спасибо, {name}! Ты зарегистрирован как арендатор машины {car}.")
    await state.finish()

# Команда /профиль
from google_api import get_user_info, is_payment_today

@dp.message_handler(commands=['профиль'])
async def show_profile(message: types.Message):
    user_id = str(message.from_user.id)
    info = get_user_info(user_id)

    if info:
        payment_today = is_payment_today(user_id)
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

# Приём чеков (фото)
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def receive_photo(message: types.Message):
    user_id = str(message.from_user.id)
    info = get_user_info(user_id)

    if not info:
        await message.answer("Ты не зарегистрирован в системе.")
        return

    caption = (
        f"📷 Фото авто от {info['name']} ({info['car']})\n"
        f"Telegram ID: {user_id}\n"
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    await bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=message.photo[-1].file_id, caption=caption)
    await message.answer("Фото принято. Спасибо!")

@dp.message_handler(lambda message: message.text == "👤 Профиль")
async def show_profile_button(message: types.Message):
    from google_api import get_user_info, is_payment_today

    user_id = str(message.from_user.id)
    info = get_user_info(user_id)

    if info:
        payment_today = is_payment_today(user_id)
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

@dp.message_handler(lambda message: message.text == "💸 Отправить чек")
async def send_check_info(message: types.Message):
    await message.answer(
        "📸 Чтобы отправить чек, просто пришли мне фото (скриншот или фото чека).\n\n"
        "Я автоматически передам его администратору и зафиксирую оплату. "
        "Чек должен быть понятным и с видимой суммой. Спасибо!"
    )

@dp.message_handler(lambda message: message.text == "📷 ФОТО АВТО")
async def request_car_photos(message: types.Message):
    await message.answer(
        "📷 Пожалуйста, пришли 5 фото автомобиля:\n"
        "1. Справа\n2. Слева\n3. Спереди\n4. Сзади\n5. Спидометр\n\n"
        "Можно отправить всё одним или несколькими сообщениями."
    )

# Функция: бот рассылает напоминания арендаторам, которые не оплатили
async def notify_users_about_debt():
    users = get_all_users()
    if not users:
        return

    for user in users:
        user_id = str(user.get("ID"))
        name = user.get("Имя")
        car = user.get("ГРЗ")

        if not is_payment_today(user_id):
            try:
                await bot.send_message(
                    user_id,
                    f"❗ Привет, {name}!\n\nТы ещё не оплатил аренду за сегодня.\n"
                    f"🚗 Госномер: {car}\n\nПожалуйста, отправь чек до полуночи. Спасибо!"
                )
            except Exception as e:
                print(f"[Ошибка отправки уведомления {user_id}] {e}")

# Планировщик: запуск каждый день в 23:00
@aiocron.crontab('0 23 * * *')
async def scheduled_reminder():
    await notify_users_about_debt()

# Каждые 2 недели по пятницам в 13:00
@aiocron.crontab('0 13 */14 * 5')
async def remind_photo_report():
    users = get_all_users()
    for user in users:
        user_id = str(user.get("ID"))
        name = user.get("Имя")

        if not user_id:
            continue

        try:
            await bot.send_message(
                user_id,
                f"📷 Привет, {name}!\n\nНапоминаем, что пора прислать свежие фото автомобиля:\n"
                "1. Справа\n2. Слева\n3. Спереди\n4. Сзади\n5. Спидометр\n\n"
                "Ждём фотоотчёт 🙌"
            )
        except Exception as e:
            print(f"[Ошибка отправки напоминания для {user_id}] {e}")

# Запуск бота
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
