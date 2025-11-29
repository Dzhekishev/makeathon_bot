import asyncio
import requests
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- КОНСТАНТЫ И НАСТРОЙКИ ---
API_TOKEN = "8586313859:AAHamf-jU80EdU6aMV3Vgj9yn3L5LysPjpo"
LAMP_URL = "http://IP_ЛАМПЫ"

# Цвета для меню (остаются без изменений)
COLORS = {
    "Красный": {"rgb": (255, 0, 0), "emoji": "🟥"},
    "Зеленый": {"rgb": (0, 255, 0), "emoji": "🟩"},
    "Синий": {"rgb": (0, 0, 255), "emoji": "🟦"},
    "Желтый": {"rgb": (255, 255, 0), "emoji": "🟨"},
    "Пурпурный": {"rgb": (128, 0, 128), "emoji": "🟪"},
    "Оранжевый": {"rgb": (255, 165, 0), "emoji": "🟧"}
}

# СЛОВАРЬ РЕЖИМОВ (Яркость Чтения 60%)
MODES = {
    "Ночь": {"r": 255, "g": 100, "b": 0, "brightness": 10, "color_name": "Теплый", "emoji": "🌙"},
    "Чтение": {"r": 255, "g": 255, "b": 200, "brightness": 60, "color_name": "Мягкий Белый", "emoji": "📖"},
    "Вечеринка": {"r": 255, "g": 0, "b": 255, "brightness": 90, "color_name": "Диско", "emoji": "🎉"},
}

# ТЕКУЩЕЕ СОСТОЯНИЕ ЛАМПЫ
current_lamp_status = "Выключена"
current_color = "Красный"
current_brightness = 50

# Инициализация роутера для хендлеров
router = Router()


# --- ФУНКЦИИ ДЛЯ СОЗДАНИЯ КЛАВИАТУР ---

def create_main_menu() -> InlineKeyboardMarkup:
    """Создает клавиатуру Главного меню с кнопкой Режимы."""
    builder = InlineKeyboardBuilder()

    # 1. Режимы
    builder.row(InlineKeyboardButton(text="✨ Режимы", callback_data="menu_modes"))

    # 2. Основные функции
    builder.row(
        InlineKeyboardButton(text="🎨 Цвет", callback_data="menu_color"),
        InlineKeyboardButton(text="🎵 Музыка", callback_data="menu_music")
    )

    # 3. Дополнительные функции
    builder.row(
        InlineKeyboardButton(text="🌡 Статус", callback_data="menu_status"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")
    )

    return builder.as_markup()


def create_color_menu() -> InlineKeyboardMarkup:
    """Создает клавиатуру палитры цветов с кнопкой 'Назад'."""
    builder = InlineKeyboardBuilder()
    for name, data in COLORS.items():
        builder.button(text=data["emoji"], callback_data=f"setcolor_{name}")
    builder.adjust(4, 2)
    builder.row(InlineKeyboardButton(text="⬅️ Назад в Главное меню", callback_data="show_main_menu"))
    return builder.as_markup()


def create_music_playback_menu() -> InlineKeyboardMarkup:
    """ВОССТАНОВЛЕНО: Создает клавиатуру для управления воспроизведением музыки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏹️ Стоп музыка", callback_data="stop_music")
    builder.button(text="⬅️ Назад в Главное меню", callback_data="show_main_menu")
    builder.adjust(2)
    return builder.as_markup()


def create_settings_menu(brightness: int) -> InlineKeyboardMarkup:
    """Клавиатура настроек (только яркость)."""
    builder = InlineKeyboardBuilder()

    # Управление яркостью
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
    """Клавиатура меню режимов."""
    builder = InlineKeyboardBuilder()

    for name, data in MODES.items():
        button_text = f"{data['emoji']} {name}"
        builder.button(text=button_text, callback_data=f"set_mode_{name}")

    builder.adjust(1)

    # Кнопка для возврата в Главное меню
    builder.row(InlineKeyboardButton(text="⬅️ Назад в Главное меню", callback_data="show_main_menu"))
    return builder.as_markup()


# --- ХЕНДЛЕРЫ: ГЛАВНОЕ МЕНЮ И СТАРТ ---

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


# --- ХЕНДЛЕРЫ: РЕЖИМЫ ---

@router.callback_query(F.data == "menu_modes")
async def modes_menu_callback(callback_query: CallbackQuery):
    """Открывает меню режимов."""
    await callback_query.message.edit_text(
        "✨ **Выбор режима**\n\nВыберите сценарий освещения:",
        reply_markup=create_modes_menu()
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("set_mode_"))
async def set_mode_callback(callback_query: CallbackQuery):
    """Устанавливает выбранный режим."""
    global current_color, current_brightness, current_lamp_status

    mode_name = callback_query.data.split("_")[2]

    if mode_name in MODES:
        mode_data = MODES[mode_name]

        # Обновляем глобальное состояние
        current_brightness = mode_data['brightness']
        current_color = mode_data['color_name']
        current_lamp_status = "Включена"

        r = mode_data['r']
        g = mode_data['g']
        b = mode_data['b']

        try:
            # requests.post(f"{LAMP_URL}/set_color_and_brightness", json={"r": r, "g": g, "b": b, "brightness": current_brightness})
            pass
        except requests.exceptions.RequestException:
            await callback_query.answer(text="Ошибка: Не удалось подключиться к лампе!", show_alert=True)
            return

        # Редактируем сообщение, чтобы показать результат и вернуться в главное меню
        emoji = mode_data['emoji']
        await callback_query.message.edit_text(
            f"{emoji} **Активирован режим: {mode_name}**\n"
            f"Цвет: {mode_data['color_name']}, Яркость: {current_brightness}%",
            reply_markup=create_main_menu()
        )
        await callback_query.answer(text=f"Режим '{mode_name}' установлен!")
    else:
        await callback_query.answer(text="Ошибка: Неизвестный режим.", show_alert=True)


# --- ХЕНДЛЕРЫ: НАСТРОЙКИ И ЯРКОСТЬ ---

@router.callback_query(F.data == "menu_settings")
async def settings_menu_callback(callback_query: CallbackQuery):
    """ОТКРЫВАЕТ МЕНЮ НАСТРОЕК (только яркость)."""
    global current_brightness
    await callback_query.message.edit_text(
        "⚙️ **Настройки лампы**\n\nИзмените яркость:",
        reply_markup=create_settings_menu(current_brightness)
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("bright_"))
async def adjust_brightness(callback_query: CallbackQuery):
    """Регулирует яркость."""
    global current_brightness, current_lamp_status
    action = callback_query.data.split("_")[1]

    if action.startswith('+'):
        new_brightness = current_brightness + int(action[1:])
    elif action.startswith('-'):
        new_brightness = current_brightness - int(action[1:])
    elif action == '100':
        new_brightness = 100
    elif action == '0':
        new_brightness = 0

    current_brightness = max(0, min(100, new_brightness))
    current_lamp_status = "Включена" if current_brightness > 0 else "Выключена"

    # Обновляем клавиатуру, чтобы отобразить новое значение яркости
    await callback_query.message.edit_text(
        f"⚙️ **Настройки лампы**\n\nИзмените яркость:",
        reply_markup=create_settings_menu(current_brightness)
    )
    await callback_query.answer(text=f"Яркость установлена на {current_brightness}%")


# --- ХЕНДЛЕРЫ: ЦВЕТ ---

@router.callback_query(F.data == "menu_color")
async def choose_color_menu(callback_query: CallbackQuery):
    """ОТКРЫВАЕТ МЕНЮ ВЫБОРА ЦВЕТА."""
    await callback_query.message.edit_text(
        "🌈 **Выберите цвет**:",
        reply_markup=create_color_menu()
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("setcolor_"))
async def set_color_callback(callback_query: CallbackQuery):
    global current_color, current_lamp_status, current_brightness
    color_name = callback_query.data.split("_")[1]
    current_color = color_name
    current_lamp_status = "Включена"
    if current_brightness == 0:
        current_brightness = 50

    if color_name in COLORS:
        r, g, b = COLORS[color_name]["rgb"]
        try:
            # requests.post(f"{LAMP_URL}/set_color", json={"r": r, "g": g, "b": b})
            pass
        except requests.exceptions.RequestException:
            await callback_query.answer(text="Ошибка: Не удалось подключиться к лампе!", show_alert=True)
            return

    color_emoji = COLORS[color_name]["emoji"]
    new_text = (
        f"🌈 **Цвет изменен**\n\n"
        f"Лампа установлена на: {color_emoji} **{current_color}**"
    )
    await callback_query.message.edit_text(new_text, reply_markup=create_main_menu())
    await callback_query.answer(text=f"Лампа установлена на {current_color}!")


# --- ХЕНДЛЕРЫ: МУЗЫКА И СТАТУС ---

@router.callback_query(F.data == "menu_music")
async def music_menu_callback(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        "🎵 **Отправка музыки**\n\nОтправьте ссылку на YouTube в следующем сообщении.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="show_main_menu")]
        ])
    )
    await callback_query.answer()


@router.message(lambda message: "youtube.com" in message.text.lower())
async def play_music_handler(message: Message):
    try:
        # requests.post(f"{LAMP_URL}/play_music", json={"youtube_url": message.text}, timeout=5)
        await message.answer(
            "Музыка воспроизводится 🎶\nИспользуйте кнопки для управления:",
            reply_markup=create_music_playback_menu()
        )
    except requests.exceptions.RequestException:
        await message.answer("Ошибка при попытке воспроизвести музыку. Проверьте соединение с лампой.")


@router.callback_query(F.data == "stop_music")
async def stop_music_callback(callback_query: CallbackQuery):
    # requests.post(f"{LAMP_URL}/stop_music")
    await callback_query.message.edit_text(
        "Музыка остановлена 🛑\nВыберите следующее действие:",
        reply_markup=create_main_menu()
    )
    await callback_query.answer("Воспроизведение остановлено.")


@router.callback_query(F.data == "menu_status")
async def show_status_callback(callback_query: CallbackQuery):
    color_emoji = COLORS.get(current_color, {"emoji": "💡"}).get("emoji")
    status_text = (
        f"🌡️ **Текущий статус**\n\n"
        f"Состояние: **{current_lamp_status}**\n"
        f"Текущий цвет: {color_emoji} **{current_color}**\n"
        f"Яркость: **{current_brightness}%**\n"
        f"Датчик температуры: **25.0°C** (пример)\n"
    )
    await callback_query.message.edit_text(
        status_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="show_main_menu")]
        ])
    )
    await callback_query.answer()


# --- ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА ---

async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")