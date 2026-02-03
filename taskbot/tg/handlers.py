# handlers.py — команды и callbacks Telegram-бота
# Функционал:
# - whitelist пользователей + админы
# - регистрация /register (запрет повторной регистрации)
# - админ-команды /registrations и /unregister <ID|Name>
# - главное меню кнопками (постоянное)
# - создание задач через диалог (с кнопками срока + назад)
# - просмотр задач (/my /overdue /done /all) без период-фильтров
# - /team_overdue
# - DONE для личных и общих задач
# - админ: просмотр задач пользователей + редакт/удалить/переключить статус (без подтверждений)
# - ARCHIVE скрывается из /my /overdue /all (показывается только если захотите отдельно)

from __future__ import annotations

from datetime import date
from typing import Optional, Tuple, List

from aiogram import Dispatcher, Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from taskbot.tg.fsm import NewTaskFSM, AdminTasksFSM
from taskbot.tg.keyboards import (
    assignee_keyboard,
    due_date_keyboard,
    newtask_back_to_assignee_keyboard,
    newtask_back_from_manual_due_keyboard,
    done_personal_keyboard,
    done_common_keyboard,
    main_menu_keyboard,
    admin_users_keyboard,
    admin_view_keyboard,
    admin_task_actions_keyboard,
    admin_nav_keyboard,
)

from taskbot.sheets.users import (
    users_get_map,
    users_list,
    users_upsert,
    users_get_by_telegram_id,
    users_get_by_name,
    users_delete_by_telegram_id,
    users_delete_by_name,
)

from taskbot.sheets.tasks import (
    TaskRow,
    task_append,
    tasks_list,
    task_set_done,
    task_set_status,
    task_update_text,
    task_update_due,
    task_delete,
    now_iso,
)

from taskbot.sheets.common import (
    common_tasks_for_user,
    common_progress_set_done,
)

from taskbot.utils.dates import (
    normalize_due_date,
    is_overdue,
    today_iso,
    tomorrow_iso,
    end_of_week_iso,
)

from taskbot.utils.formatters import (
    format_task_line,
    chunk_text,
)

from taskbot.config import (
    COMMON_SHEET,
    STATUS_TODO,
    STATUS_DONE,
    STATUS_ARCHIVE,
    ALLOWED_TELEGRAM_IDS,
    ADMIN_TELEGRAM_IDS,
)

router = Router()


# ---------- access helpers ----------

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_TELEGRAM_IDS


def is_allowed(user_id: int) -> bool:
    return (user_id in ALLOWED_TELEGRAM_IDS) or is_admin(user_id)


async def deny_if_not_allowed(message: Message) -> bool:
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён. Твой Telegram ID не в белом списке.")
        return True
    return False


async def deny_cb_if_not_allowed(callback: CallbackQuery) -> bool:
    if not is_allowed(callback.from_user.id):
        await callback.message.answer("⛔ Доступ запрещён. Твой Telegram ID не в белом списке.")
        await callback.answer()
        return True
    return False


async def deny_if_not_admin(message: Message) -> bool:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Команда доступна только администраторам.")
        return True
    return False


async def send_with_menu(message: Message, text: str):
    """
    Всегда отвечаем с главным меню снизу, чтобы кнопки не пропадали.
    """
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(is_admin(message.from_user.id)),
    )


# ---------- misc helpers ----------

def get_my_sheet_name_or_none(telegram_id: int, users_map: dict[str, int]) -> Optional[str]:
    for name, tid in users_map.items():
        if tid == telegram_id:
            return name
    return None


def _parse_unregister_target(arg: str) -> Tuple[Optional[int], Optional[str]]:
    arg = (arg or "").strip()
    if not arg:
        return None, None
    if arg.isdigit():
        return int(arg), None
    return None, arg


# ---------- commands ----------

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот задач.\n\n"
        "Если у тебя есть доступ, зарегистрируйся:\n"
        "/register <ИмяВкладки>\n\n"
        "Можно работать через меню кнопками 👇",
        reply_markup=main_menu_keyboard(is_admin(message.from_user.id)),
    )


@router.message(Command("register"))
async def cmd_register(message: Message):
    if await deny_if_not_allowed(message):
        return

    telegram_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await send_with_menu(message, "Использование: /register <ИмяВкладки>\nНапример: /register Иван")
        return

    sheet_name = parts[1].strip()

    existing_name = await users_get_by_telegram_id(telegram_id)
    if existing_name is not None:
        await send_with_menu(
            message,
            f"⛔ Ты уже зарегистрирован как '{existing_name}'.\n"
            f"Повторная регистрация запрещена.\n"
            f"Если нужно изменить регистрацию — попроси админа удалить её.",
        )
        return

    existing_tid = await users_get_by_name(sheet_name)
    if existing_tid is not None and existing_tid != telegram_id:
        await send_with_menu(message, f"⛔ Имя '{sheet_name}' уже занято другим пользователем. Выбери другое.")
        return

    await users_upsert(sheet_name, telegram_id)

    await send_with_menu(
        message,
        f"Готово ✅ Ты зарегистрирован как '{sheet_name}'.\nТеперь можно работать через меню 👇",
    )


@router.message(Command("registrations"))
async def cmd_registrations(message: Message):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    regs = await users_list()
    if not regs:
        await send_with_menu(message, "Регистраций нет.")
        return

    lines = [f"• {name} — {tid}" for name, tid in sorted(regs, key=lambda x: (x[0].lower(), x[1]))]
    for part in chunk_text(lines):
        await send_with_menu(message, part)


@router.message(Command("unregister"))
async def cmd_unregister(message: Message):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await send_with_menu(message, "Использование: /unregister <TelegramID|Name>\nПример: /unregister 123456789 или /unregister Иван")
        return

    telegram_id, name = _parse_unregister_target(parts[1])

    if telegram_id is not None:
        deleted_name = await users_delete_by_telegram_id(telegram_id)
        if deleted_name is None:
            await send_with_menu(message, "Не нашёл регистрацию по этому TelegramID.")
            return
        await send_with_menu(message, f"Готово ✅ Удалил регистрацию: {deleted_name} — {telegram_id}")
        return

    if name is not None:
        deleted_tid = await users_delete_by_name(name)
        if deleted_tid is None:
            await send_with_menu(message, "Не нашёл регистрацию по этому имени.")
            return
        await send_with_menu(message, f"Готово ✅ Удалил регистрацию: {name} — {deleted_tid}")
        return

    await send_with_menu(message, "Не понял, кого удалять. Пример: /unregister 123456789 или /unregister Иван")


@router.message(Command("newtask"))
async def cmd_newtask(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)

    if not my_sheet:
        await send_with_menu(message, "Ты не зарегистрирован. Сначала сделай: /register <ИмяВкладки>")
        return

    await state.update_data(from_name=message.from_user.full_name)
    await state.set_state(NewTaskFSM.choosing_assignee)

    await message.answer("Кому поставить задачу?", reply_markup=assignee_keyboard(list(users_map.keys())))


@router.message(Command("my"))
async def cmd_my(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await send_with_menu(message, "Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await show_tasks(message, my_sheet, "my")


@router.message(Command("overdue"))
async def cmd_overdue(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await send_with_menu(message, "Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await show_tasks(message, my_sheet, "overdue")


@router.message(Command("done"))
async def cmd_done(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await send_with_menu(message, "Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await show_tasks(message, my_sheet, "done")


@router.message(Command("all"))
async def cmd_all(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await send_with_menu(message, "Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await show_tasks(message, my_sheet, "all")


@router.message(Command("team_overdue"))
async def cmd_team_overdue(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    if not users_map:
        await send_with_menu(message, "В Users нет регистраций.")
        return

    out: List[str] = []

    for name in sorted(users_map.keys()):
        personal = await tasks_list(name)
        personal_overdue = [
            t for t in personal
            if t.status not in (STATUS_DONE, STATUS_ARCHIVE) and t.due_str and is_overdue(t.due_str)
        ]

        common_overdue = await common_tasks_for_user(name, "overdue")

        if personal_overdue or common_overdue:
            out.append(f"== {name} ==")
            for t in personal_overdue:
                out.append(format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=False))
            for t in common_overdue:
                out.append(format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=True))
            out.append("")

    if not out:
        await send_with_menu(message, "Просроченных задач по команде нет 🎉")
        return

    for part in chunk_text(out):
        await send_with_menu(message, part)


# ---------- menu buttons (reply keyboard) ----------

@router.message(F.text == "➕ Новая задача")
async def btn_newtask(message: Message, state: FSMContext):
    await cmd_newtask(message, state)


@router.message(F.text == "📋 Мои задачи")
async def btn_my(message: Message):
    await cmd_my(message)


@router.message(F.text == "⏰ Просроченные")
async def btn_overdue(message: Message):
    await cmd_overdue(message)


@router.message(F.text == "✅ Выполненные")
async def btn_done(message: Message):
    await cmd_done(message)


@router.message(F.text == "📦 Все")
async def btn_all(message: Message):
    await cmd_all(message)


@router.message(F.text == "🧾 Помощь")
async def btn_help(message: Message):
    await cmd_start(message)


@router.message(F.text == "👥 Регистрации")
async def btn_registrations(message: Message):
    await cmd_registrations(message)


@router.message(F.text.startswith("🛠"))
async def btn_admin_tasks(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    users_map = await users_get_map()
    await state.set_state(AdminTasksFSM.choosing_user)

    await message.answer(
        "Выбери пользователя для просмотра задач:",
        reply_markup=admin_users_keyboard(list(users_map.keys())),
    )


# ---------- FSM: create task ----------

@router.callback_query(NewTaskFSM.choosing_assignee, F.data.startswith("assignee:"))
async def pick_assignee(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return

    assignee = callback.data.split(":", 1)[1].strip()
    await state.update_data(assignee=assignee)
    await state.set_state(NewTaskFSM.entering_task_text)

    await callback.message.answer(
        f"Ок. Напиши текст задачи для: {assignee}",
        reply_markup=newtask_back_to_assignee_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "newtask_cancel")
async def newtask_cancel(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    await state.clear()
    await send_with_menu(callback.message, "Ок, отменил создание задачи. Выбери действие 👇")
    await callback.answer()


@router.callback_query(F.data == "newtask_back:assignee")
async def newtask_back_to_assignee(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return

    users_map = await users_get_map()
    await state.set_state(NewTaskFSM.choosing_assignee)
    await callback.message.answer("Кому поставить задачу?", reply_markup=assignee_keyboard(list(users_map.keys())))
    await callback.answer()


@router.message(NewTaskFSM.entering_task_text)
async def enter_task_text(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return

    task_text = (message.text or "").strip()
    if not task_text:
        await send_with_menu(message, "Текст задачи пустой. Напиши ещё раз.")
        return

    await state.update_data(task_text=task_text)
    await state.set_state(NewTaskFSM.choosing_due_preset)

    await message.answer("Выбери срок задачи:", reply_markup=due_date_keyboard())


@router.callback_query(NewTaskFSM.choosing_due_preset, F.data == "newtask_back:text")
async def newtask_back_to_text(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    await state.set_state(NewTaskFSM.entering_task_text)
    await callback.message.answer("Ок, введи текст задачи заново:", reply_markup=newtask_back_to_assignee_keyboard())
    await callback.answer()


@router.callback_query(NewTaskFSM.choosing_due_preset, F.data.startswith("due:"))
async def pick_due_preset(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if await deny_cb_if_not_allowed(callback):
        return

    preset = callback.data.split(":", 1)[1].strip()

    if preset == "other":
        await state.set_state(NewTaskFSM.entering_due_date_manual)
        await callback.message.answer(
            "Введи срок (например 2026-02-05 или 05.02.2026).",
            reply_markup=newtask_back_from_manual_due_keyboard(),
        )
        await callback.answer()
        return

    if preset == "today":
        due_iso = today_iso()
    elif preset == "tomorrow":
        due_iso = tomorrow_iso()
    elif preset == "eow":
        due_iso = end_of_week_iso()
    else:
        await callback.message.answer("Неизвестный вариант срока. Выбери ещё раз.")
        await callback.answer()
        return

    await create_task_and_notify(callback.message, state, bot, due_iso)
    await callback.answer()


@router.callback_query(NewTaskFSM.entering_due_date_manual, F.data == "newtask_back:due")
async def newtask_back_from_manual_due(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    await state.set_state(NewTaskFSM.choosing_due_preset)
    await callback.message.answer("Выбери срок задачи:", reply_markup=due_date_keyboard())
    await callback.answer()


@router.message(NewTaskFSM.entering_due_date_manual)
async def enter_due_date_manual(message: Message, state: FSMContext, bot: Bot):
    if await deny_if_not_allowed(message):
        return

    raw_due = (message.text or "").strip()
    try:
        due_iso = normalize_due_date(raw_due)
    except Exception:
        await send_with_menu(message, "Не смог распознать дату. Пример: 2026-02-05 или 05.02.2026. Попробуй ещё раз.")
        return

    await create_task_and_notify(message, state, bot, due_iso)


async def create_task_and_notify(message: Message, state: FSMContext, bot: Bot, due_iso: str):
    data = await state.get_data()

    assignee = data["assignee"]
    task_text = data["task_text"]
    from_name = data.get("from_name", "Unknown")

    created_at = now_iso()

    row = TaskRow(
        task_id="",  # tasks.py назначит порядковый номер
        task=task_text,
        from_name=from_name,
        due_str=due_iso,
        status=STATUS_TODO,
        created_at=created_at,
    )

    task_id = await task_append(assignee, row)  # ВАЖНО: только 1 раз!
    row.task_id = task_id

    if assignee != COMMON_SHEET:
        users_map = await users_get_map()
        if assignee in users_map:
            try:
                await bot.send_message(
                    users_map[assignee],
                    "📬 Новая задача!\n\n"
                    + format_task_line(row.task_id, row.task, row.from_name, row.due_str, row.status, is_common=False)
                    + "\n\nПосмотреть: /my",
                )
            except Exception:
                pass

    await send_with_menu(
        message,
        "Готово ✅ Задача создана.\n\n"
        + format_task_line(
            row.task_id,
            row.task,
            row.from_name,
            row.due_str,
            row.status,
            is_common=(assignee == COMMON_SHEET),
        ),
    )

    await state.clear()


# ---------- tasks view (no filters) ----------

async def show_tasks(message: Message, my_sheet_name: str, mode: str):
    personal = await tasks_list(my_sheet_name)

    if mode == "my":
        personal = [t for t in personal if t.status not in (STATUS_DONE, STATUS_ARCHIVE)]
    elif mode == "overdue":
        personal = [t for t in personal if t.status not in (STATUS_DONE, STATUS_ARCHIVE) and t.due_str and is_overdue(t.due_str)]
    elif mode == "done":
        personal = [t for t in personal if t.status == STATUS_DONE]
    elif mode == "all":
        personal = [t for t in personal if t.status != STATUS_ARCHIVE]

    common = await common_tasks_for_user(my_sheet_name, mode)

    # если common модуль когда-то начнёт отдавать ARCHIVE — на всякий случай фильтруем:
    if mode in ("my", "overdue", "all"):
        common = [t for t in common if t.status != STATUS_ARCHIVE]
    if mode == "my":
        common = [t for t in common if t.status != STATUS_DONE]
    if mode == "done":
        common = [t for t in common if t.status == STATUS_DONE]

    combined: List[Tuple[TaskRow, bool]] = []
    combined += [(t, False) for t in personal]
    combined += [(t, True) for t in common]

    if not combined:
        await send_with_menu(message, "Нет задач по выбранному списку.")
        return

    def sort_key(item: Tuple[TaskRow, bool]):
        t, _ = item
        overdue_flag = 0 if (t.due_str and t.status != STATUS_DONE and is_overdue(t.due_str)) else 1
        due_val = t.due_str or "9999-12-31"
        return (overdue_flag, due_val)

    combined.sort(key=sort_key)

    lines = [
        format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=is_common)
        for (t, is_common) in combined
    ]

    for part in chunk_text(lines):
        await send_with_menu(message, part)

    # DONE-кнопки показываем только там, где есть смысл:
    # - my и overdue: можно закрывать
    if mode in ("my", "overdue"):
        for (t, is_common) in combined:
            if t.status == STATUS_DONE:
                continue
            if is_common:
                await message.answer(f"Отметить выполненной ОБЩУЮ задачу [{t.task_id}]?", reply_markup=done_common_keyboard(t.task_id))
            else:
                await message.answer(f"Отметить выполненной задачу [{t.task_id}]?", reply_markup=done_personal_keyboard(my_sheet_name, t.task_id))


# ---------- DONE callbacks ----------

@router.callback_query(F.data.startswith("done_personal:"))
async def cb_done_personal(callback: CallbackQuery):
    if await deny_cb_if_not_allowed(callback):
        return

    _prefix, sheet_name, task_id = callback.data.split(":", 2)

    ok = await task_set_done(sheet_name, task_id)
    if ok:
        await callback.message.answer(f"Готово ✅ Задача [{task_id}] отмечена как DONE.")
    else:
        await callback.message.answer("Не нашёл задачу (возможно удалили или изменили ID).")

    await callback.answer()


@router.callback_query(F.data.startswith("done_common:"))
async def cb_done_common(callback: CallbackQuery):
    if await deny_cb_if_not_allowed(callback):
        return

    task_id = callback.data.split(":", 1)[1].strip()

    users_map = await users_get_map()
    my_name = get_my_sheet_name_or_none(callback.from_user.id, users_map)

    if not my_name:
        await callback.message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        await callback.answer()
        return

    await common_progress_set_done(task_id, my_name)
    await callback.message.answer(f"Готово ✅ Общая задача [{task_id}] отмечена DONE для {my_name}.")
    await callback.answer()


# ---------- ADMIN: navigation + view list (no filters) ----------

@router.callback_query(F.data == "admin_back:exit")
async def admin_back_exit(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    await state.clear()
    await send_with_menu(callback.message, "Ок, вернулся в меню 👇")
    await callback.answer()


@router.callback_query(F.data == "admin_back:users")
async def admin_back_users(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    users_map = await users_get_map()
    await state.set_state(AdminTasksFSM.choosing_user)
    await callback.message.answer("Выбери пользователя:", reply_markup=admin_users_keyboard(list(users_map.keys())))
    await callback.answer()


@router.callback_query(F.data == "admin_back:views")
async def admin_back_views(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    data = await state.get_data()
    sheet = data.get("admin_sheet")
    if not sheet:
        await admin_back_users(callback, state)
        return

    await state.set_state(AdminTasksFSM.choosing_view)
    await callback.message.answer(f"Выбран лист: {sheet}\nВыбери режим просмотра:", reply_markup=admin_view_keyboard())
    await callback.answer()


@router.callback_query(AdminTasksFSM.choosing_user, F.data.startswith("admin_user:"))
async def admin_pick_user(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.message.answer("⛔ Только админам.")
        await callback.answer()
        return

    sheet = callback.data.split(":", 1)[1].strip()
    await state.update_data(admin_sheet=sheet)
    await state.set_state(AdminTasksFSM.choosing_view)

    await callback.message.answer(
        f"Ок. Выбран лист: {sheet}\nВыбери режим просмотра:",
        reply_markup=admin_view_keyboard(),
    )
    await callback.answer()


@router.callback_query(AdminTasksFSM.choosing_view, F.data.startswith("admin_view:"))
async def admin_pick_view(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.message.answer("⛔ Только админам.")
        await callback.answer()
        return

    mode = callback.data.split(":", 1)[1].strip()  # my/overdue/done/all
    data = await state.get_data()
    sheet = data.get("admin_sheet")

    if not sheet:
        await callback.message.answer("Не выбран пользователь. Нажми 🛠 Админ: задачи ещё раз.")
        await callback.answer()
        return

    await state.update_data(admin_view_mode=mode)

    await admin_show_tasks(callback.message, sheet, mode)

    await callback.message.answer("Навигация:", reply_markup=admin_nav_keyboard())
    await callback.answer()


async def admin_show_tasks(message: Message, sheet: str, mode: str):
    """
    Админ: показывает задачи конкретного листа без период-фильтров.
    ARCHIVE скрываем в all/my/overdue, а done показывает только DONE.
    """
    all_tasks = await tasks_list(sheet)

    if mode == "my":
        tasks = [t for t in all_tasks if t.status not in (STATUS_DONE, STATUS_ARCHIVE)]
    elif mode == "overdue":
        tasks = [t for t in all_tasks if t.status not in (STATUS_DONE, STATUS_ARCHIVE) and t.due_str and is_overdue(t.due_str)]
    elif mode == "done":
        tasks = [t for t in all_tasks if t.status == STATUS_DONE]
    else:
        tasks = [t for t in all_tasks if t.status != STATUS_ARCHIVE]

    if not tasks:
        await send_with_menu(message, f"Админ просмотр: {sheet}\nРежим: {mode}\nНет задач.")
        return

    await send_with_menu(message, f"Админ просмотр: {sheet}\nРежим: {mode}\nЗадач: {len(tasks)}")

    # сортировка по due
    tasks.sort(key=lambda t: (t.due_str or "9999-12-31"))

    for t in tasks:
        line = format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=(sheet == COMMON_SHEET))
        await message.answer(line, reply_markup=admin_task_actions_keyboard(sheet, t.task_id, t.status))


# ---------- ADMIN: edit / delete / status callbacks (no confirms) ----------

@router.callback_query(F.data.startswith("admin_toggle:"))
async def cb_admin_toggle(callback: CallbackQuery):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.message.answer("⛔ Только админам.")
        await callback.answer()
        return

    _p, sheet, task_id, new_status = callback.data.split(":", 3)

    ok = await task_set_status(sheet, task_id, new_status)
    if ok:
        await callback.message.answer(f"✅ Готово. Задача [{task_id}] теперь в статусе: {new_status}")
    else:
        await callback.message.answer("Не нашёл задачу (возможно удалили или изменили ID).")

    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete:"))
async def cb_admin_delete(callback: CallbackQuery):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.message.answer("⛔ Только админам.")
        await callback.answer()
        return

    _p, sheet, task_id = callback.data.split(":", 2)

    ok = await task_delete(sheet, task_id)
    if ok:
        await callback.message.answer(f"🗑 Удалено. Задача [{task_id}] удалена.")
    else:
        await callback.message.answer("Не нашёл задачу (возможно уже удалена).")

    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_text:"))
async def cb_admin_edit_text(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.message.answer("⛔ Только админам.")
        await callback.answer()
        return

    _p, sheet, task_id = callback.data.split(":", 2)

    await state.update_data(edit_sheet=sheet, edit_task_id=task_id)
    await state.set_state(AdminTasksFSM.editing_text)

    await callback.message.answer(f"✏️ Введи новый ТЕКСТ для задачи [{task_id}]:")
    await callback.answer()


@router.message(AdminTasksFSM.editing_text)
async def admin_edit_text_enter(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    new_text = (message.text or "").strip()
    if not new_text:
        await send_with_menu(message, "Текст пустой. Введи текст ещё раз.")
        return

    data = await state.get_data()
    sheet = data.get("edit_sheet")
    task_id = data.get("edit_task_id")

    if not sheet or not task_id:
        await send_with_menu(message, "Ошибка состояния редактирования. Нажми 🛠 Админ: задачи заново.")
        await state.clear()
        return

    ok = await task_update_text(sheet, task_id, new_text)
    if ok:
        await send_with_menu(message, f"✅ Готово. Текст задачи [{task_id}] обновлён.")
    else:
        await send_with_menu(message, "Не нашёл задачу (возможно удалили или изменили ID).")

    await state.set_state(AdminTasksFSM.choosing_view)


@router.callback_query(F.data.startswith("admin_edit_due:"))
async def cb_admin_edit_due(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.message.answer("⛔ Только админам.")
        await callback.answer()
        return

    _p, sheet, task_id = callback.data.split(":", 2)

    await state.update_data(edit_sheet=sheet, edit_task_id=task_id)
    await state.set_state(AdminTasksFSM.editing_due)

    await callback.message.answer(
        f"📅 Введи новый СРОК для задачи [{task_id}] (например 2026-02-10 или 10.02.2026):"
    )
    await callback.answer()


@router.message(AdminTasksFSM.editing_due)
async def admin_edit_due_enter(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    raw = (message.text or "").strip()
    try:
        due_iso = normalize_due_date(raw)
    except Exception:
        await send_with_menu(message, "Не понял дату. Пример: 2026-02-10 или 10.02.2026. Введи ещё раз.")
        return

    data = await state.get_data()
    sheet = data.get("edit_sheet")
    task_id = data.get("edit_task_id")

    if not sheet or not task_id:
        await send_with_menu(message, "Ошибка состояния редактирования. Нажми 🛠 Админ: задачи заново.")
        await state.clear()
        return

    ok = await task_update_due(sheet, task_id, due_iso)
    if ok:
        await send_with_menu(message, f"✅ Готово. Срок задачи [{task_id}] обновлён на {due_iso}.")
    else:
        await send_with_menu(message, "Не нашёл задачу (возможно удалили или изменили ID).")

    await state.set_state(AdminTasksFSM.choosing_view)


# ---------- "ЧЕПУХА": любое некомандное сообщение показывает меню ----------

MENU_BUTTONS = {
    "➕ Новая задача",
    "📋 Мои задачи",
    "⏰ Просроченные",
    "✅ Выполненные",
    "📦 Все",
    "🧾 Помощь",
    "👥 Регистрации",
    "🛠 Админ: задачи",
}

@router.message(F.text)
async def catch_any_text_show_menu(message: Message):
    text = (message.text or "").strip()
    if text.startswith("/"):
        return
    if text in MENU_BUTTONS:
        return
    await send_with_menu(message, "Не понял 🙂 Выбери действие в меню 👇")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return dp
