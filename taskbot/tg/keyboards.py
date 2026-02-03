# keyboards.py — inline и reply клавиатуры

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from taskbot.config import COMMON_SHEET


# --------------------- REPLY MENU ---------------------

def main_menu_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    """
    Главное меню снизу (постоянное).
    """
    rows = [
        [KeyboardButton(text="➕ Новая задача")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="⏰ Просроченные")],
        [KeyboardButton(text="✅ Выполненные"), KeyboardButton(text="📦 Все")],
        [KeyboardButton(text="🧾 Помощь")],
    ]

    if is_admin:
        rows.insert(3, [KeyboardButton(text="👥 Регистрации")])
        rows.insert(4, [KeyboardButton(text="🛠 Админ: задачи")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        selective=False,
    )


# --------------------- NEW TASK (INLINE) ---------------------

def assignee_keyboard(user_names: list[str]):
    """
    Выбор исполнителя + "Общие" + выход в меню.
    """
    kb = InlineKeyboardBuilder()

    for name in sorted(user_names):
        kb.button(text=name, callback_data=f"assignee:{name}")

    kb.button(text="📌 Общие", callback_data=f"assignee:{COMMON_SHEET}")
    kb.button(text="⬅️ В меню", callback_data="newtask_cancel")

    kb.adjust(2)
    return kb.as_markup()


def newtask_back_to_assignee_keyboard():
    """
    Назад к выбору исполнителя (когда вводим текст).
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="newtask_back:assignee")
    kb.button(text="⬅️ В меню", callback_data="newtask_cancel")
    kb.adjust(2)
    return kb.as_markup()


def due_date_keyboard():
    """
    Выбор срока + назад к тексту + выход.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Сегодня", callback_data="due:today")
    kb.button(text="Завтра", callback_data="due:tomorrow")
    kb.button(text="Конец недели", callback_data="due:eow")
    kb.button(text="Другой", callback_data="due:other")
    kb.button(text="⬅️ Назад", callback_data="newtask_back:text")
    kb.button(text="⬅️ В меню", callback_data="newtask_cancel")
    kb.adjust(2)
    return kb.as_markup()


def newtask_back_from_manual_due_keyboard():
    """
    Назад с ручного ввода даты к выбору пресета.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="newtask_back:due")
    kb.button(text="⬅️ В меню", callback_data="newtask_cancel")
    kb.adjust(2)
    return kb.as_markup()


def done_personal_keyboard(sheet_name: str, task_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Done", callback_data=f"done_personal:{sheet_name}:{task_id}")
    return kb.as_markup()


def done_common_keyboard(task_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Done", callback_data=f"done_common:{task_id}")
    return kb.as_markup()


# --------------------- ADMIN (INLINE) ---------------------

def admin_users_keyboard(user_names: list[str]):
    """
    Админ: выбрать пользователя или "Общие", либо выйти.
    """
    kb = InlineKeyboardBuilder()

    for name in sorted(user_names):
        kb.button(text=name, callback_data=f"admin_user:{name}")

    kb.button(text="📌 Общие", callback_data=f"admin_user:{COMMON_SHEET}")
    kb.button(text="⬅️ В меню", callback_data="admin_back:exit")

    kb.adjust(2)
    return kb.as_markup()


def admin_view_keyboard():
    """
    Админ: выбрать режим просмотра по пользователю.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Активные", callback_data="admin_view:my")
    kb.button(text="Просроченные", callback_data="admin_view:overdue")
    kb.button(text="Выполненные", callback_data="admin_view:done")
    kb.button(text="Все", callback_data="admin_view:all")
    kb.button(text="⬅️ Назад", callback_data="admin_back:users")
    kb.button(text="⬅️ В меню", callback_data="admin_back:exit")
    kb.adjust(2)
    return kb.as_markup()


def admin_nav_keyboard():
    """
    Админ: навигация после просмотра списка задач.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад к режиму", callback_data="admin_back:views")
    kb.button(text="⬅️ Назад к пользователям", callback_data="admin_back:users")
    kb.button(text="⬅️ В меню", callback_data="admin_back:exit")
    kb.adjust(1)
    return kb.as_markup()


def admin_task_actions_keyboard(sheet_name: str, task_id: str, status: str):
    """
    Админ: действия над задачей.
    """
    kb = InlineKeyboardBuilder()

    kb.button(text="✏️ Текст", callback_data=f"admin_edit_text:{sheet_name}:{task_id}")
    kb.button(text="📅 Срок", callback_data=f"admin_edit_due:{sheet_name}:{task_id}")

    if status == "DONE":
        kb.button(text="↩️ Вернуть в TODO", callback_data=f"admin_toggle:{sheet_name}:{task_id}:TODO")
    else:
        kb.button(text="✅ В DONE", callback_data=f"admin_toggle:{sheet_name}:{task_id}:DONE")

    kb.button(text="🗑 Удалить", callback_data=f"admin_delete:{sheet_name}:{task_id}")

    kb.adjust(2)
    return kb.as_markup()
