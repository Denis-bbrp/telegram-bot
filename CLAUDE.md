# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

Telegram-бот для управления арендой автомобилей. Арендаторы регистрируются, отправляют чеки об оплате и фото авто. Администратор получает уведомления в группу.

## Запуск

```bash
pip3 install -r requirements.txt
python3 bot.py
```

## Структура

- [bot.py](bot.py) — основной файл, все хендлеры и планировщик
- [config.py](config.py) — читает переменные из `.env`
- [google_api.py](google_api.py) — работа с Google Таблицей

## Переменные окружения

Хранятся в `.env` (локально) или в Render → Environment (продакшн):

| Переменная | Описание |
|-----------|----------|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `ADMIN_GROUP_ID` | ID группы администраторов (`-4709157297`) |
| `SPREADSHEET_ID` | ID Google Таблицы (`1QP0mT5IgA54bIS_g2EKza6J2SvvkLj_ecFVPDpDGi3A`) |
| `GOOGLE_CREDENTIALS_BASE64` | credentials.json сервисного аккаунта в base64 |

Получить base64 из файла: `cat credentials.json | base64`

## Google Таблица

Лист называется **«Пользователи»**. Колонки (порядок важен):

| A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|
| ID | Имя | ГРЗ | Статус | Задолженность | Последняя оплата | Фотоотчет сдан | Последний фотоотчет |

Сервисный аккаунт: `bot-sheet-access@carbot-457709.iam.gserviceaccount.com` — должен быть добавлен как **Редактор** в таблицу.

## Хостинг (Render)

- Сервис: **telegram-bot-1** (Web Service, Frankfurt, Free)
- Репозиторий: `Denis-bbrp/telegram-bot`, ветка `main`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python bot.py`
- Бот открывает порт 8080 (`/` → 200 OK) чтобы Render не убивал процесс

Render деплоит автоматически при пуше в `main`.

## Планировщик (cron)

Все времена в **UTC** (Москва = UTC+3):

- `0 20 * * *` — напоминание об оплате в 23:00 МСК
- `0 10 * * 5` — напоминание о фото авто в 13:00 МСК по пятницам (только чётные недели)
- `*/10 * * * *` — самопинг: бот пингует `RENDER_EXTERNAL_URL` каждые 10 минут, чтобы Render Free не засыпал

## FSM состояния

- `RegisterUser.waiting_for_name` / `waiting_for_car` — регистрация арендатора
- `PhotoType.waiting_for_check` — ожидание фото чека (фиксирует оплату в таблице)
- `PhotoType.waiting_for_car_photo` — ожидание фото авто (пересылает администратору)

## Важные детали

- При получении фото чека вызывается `update_last_payment_date()` — дата записывается в колонку F
- `credentials.json` не пушится в GitHub (в `.gitignore`), на Render передаётся через `GOOGLE_CREDENTIALS_BASE64`
- Клиент Google API инициализируется лениво (`get_client()`) — при первом обращении к таблице
- `BOT_TOKEN` в старом коде был захардкожен и попал в публичный GitHub — токен был отозван и заменён

## Архитектура Google API

Все функции `google_api.py` — синхронные (gspread blocking I/O). Чтобы не блокировать asyncio event loop, в боте используются **async-обёртки** через `loop.run_in_executor`:

```python
async def async_get_user_info(telegram_id):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_user_info, telegram_id)
```

Аналогично: `async_add_user`, `async_is_payment_today`, `async_update_last_payment_date`, `async_get_all_users`.

**Важно:** никогда не вызывать sync-функции напрямую из async-хендлеров — это замораживает бота.

`notify_users_about_debt` делает **1 запрос** к Google (не N+1) — берёт всех юзеров, проверяет дату в памяти. Рассылки через `asyncio.gather` — параллельно.

## Известные баги / история правок

- **Веб-сервер запускается только на Render** (`if os.getenv("PORT")`). Локально порт 8080 не нужен — без этой проверки бот падал при повторном запуске (`address already in use`)
- **Всегда пушить после правок** — Render деплоит только из GitHub. В прошлом коммиты были только локально, на Render ехал старый код, бот не работал. После любых изменений обязательно `git push origin main`
- **Задержки/зависания бота** — причина: sync gspread вызовы в async-хендлерах блокировали event loop. Исправлено 2026-04-10: все вызовы через `run_in_executor` + самопинг для Render Free.
