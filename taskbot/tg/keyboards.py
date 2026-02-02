# keyboards.py — все inline-кнопки

from aiogram.utils.keyboard import InlineKeyboardBuilder  # builder клавиатур
from taskbot.config import COMMON_SHEET  # имя листа общих задач


def assignee_keyboard(user_names: list[str]):
    """
    Клавиатура выбора исполнителя:
      - кнопки людей
      - кнопка 📌 Общие
    """
    kb = InlineKeyboardBuilder()

    # кнопки людей
    for name in sorted(user_names):
        kb.button(text=name, callback_data=f"assignee:{name}")

    # кнопка общих задач
    kb.button(text="📌 Общие", callback_data=f"assignee:{COMMON_SHEET}")

    kb.adjust(2)  # по 2 кнопки в ряд
    return kb.as_markup()


def due_date_keyboard():
    """
    Клавиатура выбора срока:
      - Сегодня
      - Завтра
      - Конец недели
      - Другой (ручной ввод)
    """
    kb = InlineKeyboardBuilder()

    kb.button(text="Сегодня", callback_data="due:today")      # пресет сегодня
    kb.button(text="Завтра", callback_data="due:tomorrow")   # пресет завтра
    kb.button(text="Конец недели", callback_data="due:eow")  # конец недели
    kb.button(text="Другой", callback_data="due:other")      # ручной ввод

    kb.adjust(2)  # 2 в ряд
    return kb.as_markup()


def done_personal_keyboard(sheet_name: str, task_id: str):
    """Кнопка DONE для личной задачи."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Done", callback_data=f"done_personal:{sheet_name}:{task_id}")
    return kb.as_markup()


def done_common_keyboard(task_id: str):
    """Кнопка DONE для общей задачи."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Done", callback_data=f"done_common:{task_id}")
    return kb.as_markup()
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton  # меню-кнопки


def main_menu_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    """
    Главное меню бота (кнопки снизу).
    is_admin=True -> добавляем админ-кнопки.
    """
    rows = [
        [KeyboardButton(text="➕ Новая задача")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="⏰ Просроченные")],
        [KeyboardButton(text="✅ Выполненные"), KeyboardButton(text="📦 Все")],
        [KeyboardButton(text="🧾 Помощь")],
    ]

    # Если пользователь админ — показываем ещё кнопку “Регистрации”
    if is_admin:
        rows.insert(3, [KeyboardButton(text="👥 Регистрации")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,  # чтобы красиво помещалось
        one_time_keyboard=False,  # меню остаётся
        selective=False,
    )
