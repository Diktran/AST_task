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
    Админ видит дополнительно “👥 Регистрации” и “🛠 Админ: задачи”.
    """
    rows = [
        [KeyboardButton(text="➕ Новая задача")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="⏰ Просроченные")],
        [KeyboardButton(text="✅ Выполненные"), KeyboardButton(text="📦 Все")],
        [KeyboardButton(text="🧾 Помощь")],
    ]

    if is_admin:
        # админские пункты меню
        rows.insert(3, [KeyboardButton(text="👥 Регистрации")])
        rows.insert(4, [KeyboardButton(text="🛠 Админ: задачи")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        selective=False,
    )


def period_filter_keyboard(mode: str):
    """
    Фильтр по сроку (due date) для обычного пользователя.
    mode: "overdue" или "done"
    callback: period:<mode>:day/week/month/other
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="День", callback_data=f"period:{mode}:day")
    kb.button(text="Неделя", callback_data=f"period:{mode}:week")
    kb.button(text="Месяц", callback_data=f"period:{mode}:month")
    kb.button(text="Другое", callback_data=f"period:{mode}:other")
    kb.adjust(2)
    return kb.as_markup()


# -------------------- ADMIN INLINE --------------------

def admin_users_keyboard(user_names: list[str]):
    """
    Админ: выбор пользователя для просмотра задач + 📌 Общие
    callback: admin_user:<ИмяЛиста>
    """
    kb = InlineKeyboardBuilder()

    for name in sorted(user_names):
        kb.button(text=name, callback_data=f"admin_user:{name}")

    kb.button(text="📌 Общие", callback_data=f"admin_user:{COMMON_SHEET}")

    kb.adjust(2)
    return kb.as_markup()


def admin_view_keyboard():
    """
    Админ: выбор режима просмотра задач:
    Активные / Просроченные / Выполненные / Все
    callback: admin_view:my|overdue|done|all
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="Активные", callback_data="admin_view:my")
    kb.button(text="Просроченные", callback_data="admin_view:overdue")
    kb.button(text="Выполненные", callback_data="admin_view:done")
    kb.button(text="Все", callback_data="admin_view:all")
    kb.adjust(2)
    return kb.as_markup()


def admin_period_filter_keyboard(view_mode: str):
    """
    Админ: фильтр по сроку (due).
    callback: aperiod:<view_mode>:day|week|month|other
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="День", callback_data=f"aperiod:{view_mode}:day")
    kb.button(text="Неделя", callback_data=f"aperiod:{view_mode}:week")
    kb.button(text="Месяц", callback_data=f"aperiod:{view_mode}:month")
    kb.button(text="Другое", callback_data=f"aperiod:{view_mode}:other")
    kb.adjust(2)
    return kb.as_markup()


def admin_task_actions_keyboard(sheet_name: str, task_id: str, status: str):
    """
    Админ: действия над задачей (редактировать/удалить/сменить статус)
    callback:
      admin_edit_text:<sheet>:<task_id>
      admin_edit_due:<sheet>:<task_id>
      admin_toggle:<sheet>:<task_id>:TODO|DONE
      admin_delete:<sheet>:<task_id>
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
