# keyboards.py — inline и reply клавиатуры

from aiogram.utils.keyboard import InlineKeyboardBuilder  # inline builder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton  # reply keyboard

from taskbot.config import COMMON_SHEET  # вкладка общих задач


def assignee_keyboard(user_names: list[str]):
    """
    Клавиатура выбора исполнителя + 📌 Общие
    """
    kb = InlineKeyboardBuilder()

    for name in sorted(user_names):
        kb.button(text=name, callback_data=f"assignee:{name}")

    kb.button(text="📌 Общие", callback_data=f"assignee:{COMMON_SHEET}")

    kb.adjust(2)
    return kb.as_markup()


def due_date_keyboard():
    """
    Клавиатура выбора срока:
    Сегодня / Завтра / Конец недели (пятница) / Другой
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Сегодня", callback_data="due:today")
    kb.button(text="Завтра", callback_data="due:tomorrow")
    kb.button(text="Конец недели", callback_data="due:eow")
    kb.button(text="Другой", callback_data="due:other")
    kb.adjust(2)
    return kb.as_markup()


def done_personal_keyboard(sheet_name: str, task_id: str):
    """
    DONE для личной задачи
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Done", callback_data=f"done_personal:{sheet_name}:{task_id}")
    return kb.as_markup()


def done_common_keyboard(task_id: str):
    """
    DONE для общей задачи (персонально)
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Done", callback_data=f"done_common:{task_id}")
    return kb.as_markup()


def main_menu_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    """
    Главное меню (кнопки снизу).
    Админ видит дополнительно “👥 Регистрации”.
    """
    rows = [
        [KeyboardButton(text="➕ Новая задача")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="⏰ Просроченные")],
        [KeyboardButton(text="✅ Выполненные"), KeyboardButton(text="📦 Все")],
        [KeyboardButton(text="🧾 Помощь")],
    ]

    if is_admin:
        rows.insert(3, [KeyboardButton(text="👥 Регистрации")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        selective=False,
    )
