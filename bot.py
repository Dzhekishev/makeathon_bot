import asyncio
import requests
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import sys

# --- 1. КОНСТАНТЫ И НАСТРОЙКИ ---
API_TOKEN = "8586313859:AAHamf-jU80EdU6aMV3Vgj9yn3L5LysPjpo"

# ВАЖНО: УБРАТЬ ПРОБЕЛ В НАЧАЛЕ!
LAMP_IP = "172.20.10.3"  # БЕЗ ПРОБЕЛА!
LAMP_URL = f"http://{LAMP_IP}"
TIMEOUT_SEC = 3  # Таймаут для HTTP-запросов к ESP32

# Цвета для меню
COLORS = {
    "Красный": {"rgb": (255, 0, 0), "emoji": "🟥"},
    "Зеленый": {"rgb": (0, 255, 0), "emoji": "🟩"},
    "Синий": {"rgb": (0, 0, 255), "emoji": "🟦"},
    "Желтый": {"rgb": (255, 255, 0), "emoji": "🟨"},
    "Пурпурный": {"rgb": (128, 0, 128), "emoji": "🟪"},
    "Оранжевый": {"rgb": (255, 165, 0), "emoji": "🟧"}
}

# Режимы
MODES = {
    "Ночь": {"r": 255, "g": 100, "b": 0, "brightness": 10, "color_name": "Теплый", "emoji": "🌙", "api_mode": "manual"},
    "Чтение": {"r": 255, "g": 255, "b": 200, "brightness": 60, "color_name": "Мягкий Белый", "emoji": "📖",
               "api_mode": "manual"},
    "Вечеринка": {"r": 255, "g": 0, "b": 255, "brightness": 90, "color_name": "Диско", "emoji": "🎉",
                  "api_mode": "manual"},
    "Авто": {"r": 0, "g": 0, "b": 0, "brightness": 0, "color_name": "Авто", "emoji": "🤖", "api_mode": "auto"},
}

# ТЕКУЩЕЕ СОСТОЯНИЕ ЛАМПЫ
current_lamp_status = "Авто"
current_color = "Синий"
current_brightness = 80

# Инициализация роутера
router = Router()


# --- Функции для создания клавиатур ---
def create_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✨ Режимы", callback_data="menu_modes"))
    builder.row(
        InlineKeyboardButton(text="🎨 Цвет", callback_data="menu_color"),
        InlineKeyboardButton(text="🎵 Музыка", callback_data="menu_music")
    )
    builder.row(
        InlineKeyboardButton(text="🌡 Статус", callback_data="menu_status"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")
    )
    return builder.as_markup()


def create_color_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name, data in COLORS.items():
        builder.button(text=data["emoji"], callback_data=f"setcolor_{name}")
    builder.adjust(4, 2)
    builder.row(InlineKeyboardButton(text="⬅️ Назад в Главное меню", callback_data="show_main_menu"))
    return builder.as_markup()


def create_settings_menu(brightness: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"🔆 Яркость: {brightness}%", callback_data="ignore"))
    builder.row(
        InlineKeyboardButton(text="➖ 10%", callback_data="bright_-10"),
        InlineKeyboardButton(text="➕ 10%", callback_data="bright_+10")
    )
    builder.row(
        InlineKeyboardButton(text="⚫ Выкл (0%)", callback_data="bright_0"),
        InlineKeyboardButton(text="⚪ Макс (100%)", callback_data="bright_100")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад в Главное меню", callback_data="show_main_menu"))
    return builder.as_markup()


def create_modes_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for name, data in MODES.items():
        button_text = f"{data['emoji']} {name}"
        builder.button(text=button_text, callback_data=f"set_mode_{name}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Назад в Главное меню", callback_data="show_main_menu"))
    return builder.as_markup()


# --- Функция проверки ESP32 ---
def check_esp32_connection():
    """Проверяет доступность ESP32"""
    try:
        # Пробуем получить корневую страницу или любой эндпоинт
        response = requests.get(f"{LAMP_URL}/", timeout=2)
        print(f"✅ ESP32 доступен! Статус: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ Нет соединения с ESP32 по адресу {LAMP_URL}")
        return False
    except requests.exceptions.Timeout:
        print(f"⏱️ Таймаут при подключении к ESP32")
        return False
    except Exception as e:
        print(f"⚠️ Ошибка при проверке ESP32: {e}")
        return False


# --- Хендлеры ---
@router.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "👋 Привет! Управляй лампой и музыкой:",
        reply_markup=create_main_menu()
    )


@router.callback_query(F.data == "show_main_menu")
async def back_to_main_menu(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        "🏠 Главное меню. Управляй лампой и музыкой:",
        reply_markup=create_main_menu()
    )
    await callback_query.answer()


@router.callback_query(F.data == "menu_modes")
async def modes_menu_callback(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        "✨ **Выбор режима**\n\nВыберите сценарий освещения:",
        reply_markup=create_modes_menu()
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("set_mode_"))
async def set_mode_callback(callback_query: CallbackQuery):
    global current_color, current_brightness, current_lamp_status
    mode_name = callback_query.data.split("_")[2]

    if mode_name in MODES:
        mode_data = MODES[mode_name]

        try:
            if mode_data['api_mode'] == "auto":
                # Режим Авто
                response = requests.post(f"{LAMP_URL}/set_mode_auto", timeout=TIMEOUT_SEC)
                if response.status_code == 200:
                    current_lamp_status = "Авто"
                    current_color = "Авто"
                    current_brightness = 100
                else:
                    raise Exception(f"Ошибка ESP32: {response.status_code}")
            else:
                # Ручные режимы
                r = mode_data['r']
                g = mode_data['g']
                b = mode_data['b']
                brightness = mode_data['brightness']

                # Отправляем команды
                requests.post(f"{LAMP_URL}/set_brightness?brightness={brightness}", timeout=TIMEOUT_SEC)
                requests.post(f"{LAMP_URL}/set_color?r={r}&g={g}&b={b}", timeout=TIMEOUT_SEC)

                # Обновляем состояние
                current_brightness = brightness
                current_color = mode_data['color_name']
                current_lamp_status = "Включена"

        except requests.exceptions.RequestException as e:
            print(f"Ошибка подключения к ESP32: {e}")
            await callback_query.answer(
                text="🚫 Ошибка: Не удалось подключиться к ESP32!\nПроверьте:\n1. ESP32 включен\n2. Правильный IP адрес\n3. ESP32 и телефон в одной сети",
                show_alert=True
            )
            return
        except Exception as e:
            print(f"Ошибка: {e}")
            await callback_query.answer(text="🚫 Ошибка при отправке команды!", show_alert=True)
            return

        # Успешно
        emoji = mode_data['emoji']
        await callback_query.message.edit_text(
            f"{emoji} **Активирован режим: {mode_name}**\n"
            f"Цвет: {current_color}, Яркость: {current_brightness}%",
            reply_markup=create_main_menu()
        )
        await callback_query.answer(text=f"Режим '{mode_name}' установлен!")
    else:
        await callback_query.answer(text="Ошибка: Неизвестный режим.", show_alert=True)


@router.callback_query(F.data == "menu_settings")
async def settings_menu_callback(callback_query: CallbackQuery):
    global current_brightness
    await callback_query.message.edit_text(
        "⚙️ **Настройки лампы**\n\nИзмените яркость:",
        reply_markup=create_settings_menu(current_brightness)
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("bright_"))
async def adjust_brightness(callback_query: CallbackQuery):
    global current_brightness, current_lamp_status
    action = callback_query.data.split("_")[1]

    # Расчет новой яркости
    if action.startswith('+'):
        new_brightness = current_brightness + int(action[1:])
    elif action.startswith('-'):
        new_brightness = current_brightness - int(action[1:])
    elif action == '100':
        new_brightness = 100
    elif action == '0':
        new_brightness = 0
    else:
        new_brightness = current_brightness

    current_brightness = max(0, min(100, new_brightness))
    current_lamp_status = "Включена" if current_brightness > 0 else "Выключена"

    try:
        # Отправляем команду на ESP32
        response = requests.post(f"{LAMP_URL}/set_brightness?brightness={current_brightness}", timeout=TIMEOUT_SEC)
        if response.status_code != 200:
            raise Exception(f"Ошибка ESP32: {response.status_code}")

        # Переключаем в ручной режим
        requests.post(f"{LAMP_URL}/set_mode_auto", timeout=TIMEOUT_SEC)

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при установке яркости: {e}")
        await callback_query.answer(
            text=f"🚫 Не удалось установить яркость!\nESP32 недоступен.",
            show_alert=True
        )
        return

    # Обновляем интерфейс
    await callback_query.message.edit_text(
        f"⚙️ **Настройки лампы**\n\nИзмените яркость:",
        reply_markup=create_settings_menu(current_brightness)
    )
    await callback_query.answer(text=f"Яркость: {current_brightness}%")


@router.callback_query(F.data == "menu_color")
async def choose_color_menu(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        "🌈 **Выберите цвет**:",
        reply_markup=create_color_menu()
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("setcolor_"))
async def set_color_callback(callback_query: CallbackQuery):
    global current_color, current_lamp_status, current_brightness
    color_name = callback_query.data.split("_")[1]

    # Если яркость 0, увеличиваем до 50%
    if current_brightness == 0:
        current_brightness = 50

    if color_name in COLORS:
        r, g, b = COLORS[color_name]["rgb"]
        try:
            # Отправляем команды на ESP32
            requests.post(f"{LAMP_URL}/set_color?r={r}&g={g}&b={b}", timeout=TIMEOUT_SEC)
            requests.post(f"{LAMP_URL}/set_brightness?brightness={current_brightness}", timeout=TIMEOUT_SEC)
            requests.post(f"{LAMP_URL}/set_mode_auto", timeout=TIMEOUT_SEC)  # Ручной режим

            print(f"Установлен цвет: {color_name} RGB({r},{g},{b})")

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при установке цвета: {e}")
            await callback_query.answer(
                text="🚫 Не удалось установить цвет!\nESP32 недоступен.",
                show_alert=True
            )
            return

        # Обновляем состояние
        current_color = color_name
        current_lamp_status = "Включена"
        color_emoji = COLORS[color_name]["emoji"]

        await callback_query.message.edit_text(
            f"🌈 **Цвет изменен**\n\nЛампа установлена на: {color_emoji} **{current_color}**",
            reply_markup=create_main_menu()
        )
        await callback_query.answer(text=f"Цвет: {current_color}!")
    else:
        await callback_query.answer(text="Ошибка: Неизвестный цвет.", show_alert=True)


@router.callback_query(F.data == "menu_music")
async def music_menu_callback(callback_query: CallbackQuery):
    await callback_query.answer("🎶 Музыка пока не реализована", show_alert=True)
    await callback_query.message.edit_text(
        "🎵 **Музыка**\n\nФункция в разработке...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="show_main_menu")]
        ])
    )


@router.callback_query(F.data == "menu_status")
async def show_status_callback(callback_query: CallbackQuery):
    color_emoji = COLORS.get(current_color, {"emoji": "💡"}).get("emoji")

    # Пробуем получить реальные данные с ESP32
    sensor_data = "Не удалось получить данные"
    try:
        response = requests.get(f"{LAMP_URL}/", timeout=2)
        if response.status_code == 200:
            sensor_data = "Данные получены с ESP32"
    except:
        sensor_data = "ESP32 недоступен"

    status_text = (
        f"🌡️ **Текущий статус**\n\n"
        f"🔹 Состояние лампы: **{current_lamp_status}**\n"
        f"🔹 Текущий цвет: {color_emoji} **{current_color}**\n"
        f"🔹 Яркость: **{current_brightness}%**\n"
        f"🔹 ESP32: **{LAMP_IP}**\n"
        f"---\n"
        f"📡 {sensor_data}\n"
    )

    await callback_query.message.edit_text(
        status_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="menu_status")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="show_main_menu")]
        ])
    )
    await callback_query.answer()


# --- Главная функция ---
async def main():
    print("=" * 50)
    print("🤖 Запуск телеграм бота для управления ESP32")
    print("=" * 50)

    # Проверяем подключение к ESP32
    print(f"🔍 Проверяем подключение к ESP32...")
    print(f"📡 IP адрес: {LAMP_URL}")

    if check_esp32_connection():
        print("✅ ESP32 доступен!")
    else:
        print("⚠️  ВНИМАНИЕ: ESP32 недоступен!")
        print("Возможные причины:")
        print("1. ESP32 не включен")
        print("2. Неправильный IP адрес")
        print("3. ESP32 и компьютер в разных сетях")
        print("4. На ESP32 не запущен веб-сервер")
        user_input = input("Продолжить без ESP32? (y/n): ")
        if user_input.lower() != 'y':
            print("Выход...")
            sys.exit(1)
        else:
            print("Продолжаем в демо-режиме...")

    print("\n🚀 Запуск бота...")

    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Удаляем предыдущие обновления
    await bot.delete_webhook(drop_pending_updates=True)

    print(f"✅ Бот запущен! Имя: @{(await bot.get_me()).username}")
    print("📱 Откройте телеграм и найдите своего бота")
    print("💡 Используйте /start для начала работы")
    print("=" * 50)

    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    # Проверяем, не запущен ли уже бот
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Завершение работы...")
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")