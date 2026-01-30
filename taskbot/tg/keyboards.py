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

    for name in sorted(user_names):
        kb.button(text=name, callback_data=f"assignee:{name}")

    kb.button(text="📌 Общие", callback_data=f"assignee:{COMMON_SHEET}")

    kb.adjust(2)
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
