# handlers.py — команды и callbacks Telegram-бота
# Функционал:
# - whitelist пользователей + админы
# - регистрация /register (запрет повторной регистрации)
# - админ-команды /registrations и /unregister <ID|Name>
# - главное меню кнопками
# - создание задач через диалог с кнопками срока
# - просмотр задач (/my /overdue /done /all)
# - /team_overdue
# - DONE для личных и общих задач

from __future__ import annotations
from datetime import date, timedelta
from typing import Optional, Tuple, List
#import uuid

from aiogram import Dispatcher, Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from taskbot.tg.fsm import NewTaskFSM, TasksFilterFSM, AdminTasksFSM
from taskbot.tg.keyboards import (
    assignee_keyboard,
    due_date_keyboard,
    done_personal_keyboard,
    done_common_keyboard,
    main_menu_keyboard,
    period_filter_keyboard,
    admin_users_keyboard,          # ✅
    admin_view_keyboard,           # ✅
    admin_task_actions_keyboard,   # ✅
    admin_period_filter_keyboard,
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
    task_set_todo,
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

@router.message(F.text.startswith("🛠"))
async def btn_admin_tasks(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    users_map = await users_get_map()
    await state.update_data(admin_users=list(users_map.keys()))
    await state.set_state(AdminTasksFSM.choosing_user)

    await message.answer(
        "Выбери пользователя для просмотра задач:",
        reply_markup=admin_users_keyboard(list(users_map.keys())),
    )


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
    await state.set_state(AdminTasksFSM.choosing_period)

    await callback.message.answer(
        "Выбери период по СРОКУ задачи (фильтр по due):",
        reply_markup=admin_period_filter_keyboard(mode),
    )
    await callback.answer()


def _admin_period_range(period: str) -> tuple[str, str]:
    today = date.today()
    if period == "day":
        start = today - timedelta(days=1)
        end = today
    elif period == "week":
        start = today - timedelta(days=7)
        end = today
    elif period == "month":
        start = today - timedelta(days=30)
        end = today
    else:
        start = today - timedelta(days=7)
        end = today
    return start.isoformat(), end.isoformat()


def _due_in_range(due_iso: str, start_iso: str, end_iso: str) -> bool:
    return bool(due_iso) and start_iso <= due_iso <= end_iso


@router.callback_query(AdminTasksFSM.choosing_period, F.data.startswith("aperiod:"))
async def admin_choose_period(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return
    if not is_admin(callback.from_user.id):
        await callback.message.answer("⛔ Только админам.")
        await callback.answer()
        return

    _, view_mode, period = callback.data.split(":", 2)

    if period == "other":
        await state.set_state(AdminTasksFSM.entering_start)
        await callback.message.answer("Введи дату НАЧАЛА (например 2026-02-01 или 01.02.2026):")
        await callback.answer()
        return

    start_iso, end_iso = _admin_period_range(period)
    await admin_show_tasks_filtered(callback.message, state, start_iso, end_iso)

    await state.set_state(AdminTasksFSM.choosing_view)
    await callback.answer()


@router.message(AdminTasksFSM.entering_start)
async def admin_period_start(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    raw = (message.text or "").strip()
    try:
        start_iso = normalize_due_date(raw)
    except Exception:
        await send_with_menu(message, "Не понял дату начала. Пример: 2026-02-01 или 01.02.2026.")
        return

    await state.update_data(admin_filter_start=start_iso)
    await state.set_state(AdminTasksFSM.entering_end)
    await send_with_menu(message, "Теперь введи дату КОНЦА (например 2026-02-10 или 10.02.2026):")


@router.message(AdminTasksFSM.entering_end)
async def admin_period_end(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    data = await state.get_data()
    start_iso = data.get("admin_filter_start")
    raw = (message.text or "").strip()

    try:
        end_iso = normalize_due_date(raw)
    except Exception:
        await send_with_menu(message, "Не понял дату конца. Пример: 2026-02-10 или 10.02.2026.")
        return

    if not start_iso:
        await send_with_menu(message, "Ошибка: нет даты начала. Нажми 🛠 Админ: задачи заново.")
        await state.clear()
        return

    if end_iso < start_iso:
        await send_with_menu(message, f"Дата конца меньше даты начала ({start_iso}). Введи дату конца ещё раз.")
        return

    await admin_show_tasks_filtered(message, state, start_iso, end_iso)
    await state.set_state(AdminTasksFSM.choosing_view)


async def admin_show_tasks_filtered(message: Message, state: FSMContext, start_iso: str, end_iso: str):
    data = await state.get_data()
    sheet = data.get("admin_sheet")
    mode = data.get("admin_view_mode")
    if not sheet or not mode:
        await send_with_menu(message, "Ошибка состояния админ-фильтра. Нажми 🛠 Админ: задачи заново.")
        await state.clear()
        return

    all_tasks = await tasks_list(sheet)

    if mode == "my":
        tasks = [t for t in all_tasks if t.status != STATUS_DONE and _due_in_range(t.due_str, start_iso, end_iso)]
    elif mode == "overdue":
        tasks = [t for t in all_tasks if t.status != STATUS_DONE and t.due_str and is_overdue(t.due_str) and _due_in_range(t.due_str, start_iso, end_iso)]
    elif mode == "done":
        tasks = [t for t in all_tasks if t.status == STATUS_DONE and _due_in_range(t.due_str, start_iso, end_iso)]
    else:
        tasks = [t for t in all_tasks if _due_in_range(t.due_str, start_iso, end_iso)]

    if not tasks:
        await send_with_menu(message, f"Нет задач за период по сроку: {start_iso} — {end_iso}.")
        return

    await send_with_menu(message, f"Админ просмотр: {sheet}\nРежим: {mode}\nПериод по сроку: {start_iso} — {end_iso}")

    for t in tasks:
        line = format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=(sheet == COMMON_SHEET))
        await message.answer(line, reply_markup=admin_task_actions_keyboard(sheet, t.task_id, t.status))


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

#def uuid_short() -> str:
#    return uuid.uuid4().hex[:8]


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

def _period_range(period: str) -> tuple[str, str]:
    """
    Возвращает (start_iso, end_iso) по пресету.
    Считаем от today, но фильтруем ПО DUE ДАТЕ.
    overdue: будем показывать задачи, у которых due попадает в этот диапазон.
    done: аналогично.
    """
    today = date.today()

    if period == "day":
        start = today - timedelta(days=1)
        end = today
    elif period == "week":
        start = today - timedelta(days=7)
        end = today
    elif period == "month":
        start = today - timedelta(days=30)
        end = today
    else:
        # fallback, но вообще сюда не должны попасть
        start = today - timedelta(days=7)
        end = today

    return start.isoformat(), end.isoformat()


def _in_due_range(due_iso: str, start_iso: str, end_iso: str) -> bool:
    """
    Проверка что due находится в диапазоне включительно.
    """
    if not due_iso:
        return False
    return start_iso <= due_iso <= end_iso



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
        await message.answer("Использование: /register <ИмяВкладки>\nНапример: /register Иван")
        return

    sheet_name = parts[1].strip()

    existing_name = await users_get_by_telegram_id(telegram_id)
    if existing_name is not None:
        await message.answer(
            f"⛔ Ты уже зарегистрирован как '{existing_name}'.\n"
            f"Повторная регистрация запрещена.\n"
            f"Если нужно изменить регистрацию — попроси админа удалить её."
        )
        return

    existing_tid = await users_get_by_name(sheet_name)
    if existing_tid is not None and existing_tid != telegram_id:
        await message.answer(f"⛔ Имя '{sheet_name}' уже занято другим пользователем. Выбери другое.")
        return

    await users_upsert(sheet_name, telegram_id)

    await message.answer(
        f"Готово ✅ Ты зарегистрирован как '{sheet_name}'.\n"
        f"Теперь можно работать через меню 👇",
        reply_markup=main_menu_keyboard(is_admin(message.from_user.id)),
    )


@router.message(Command("registrations"))
async def cmd_registrations(message: Message):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    regs = await users_list()
    if not regs:
        await message.answer("Регистраций нет.")
        return

    lines = [f"• {name} — {tid}" for name, tid in sorted(regs, key=lambda x: (x[0].lower(), x[1]))]
    for part in chunk_text(lines):
        await message.answer(part)


@router.message(Command("unregister"))
async def cmd_unregister(message: Message):
    if await deny_if_not_allowed(message):
        return
    if await deny_if_not_admin(message):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /unregister <TelegramID|Name>\nПример: /unregister 123456789 или /unregister Иван")
        return

    telegram_id, name = _parse_unregister_target(parts[1])

    if telegram_id is not None:
        deleted_name = await users_delete_by_telegram_id(telegram_id)
        if deleted_name is None:
            await message.answer("Не нашёл регистрацию по этому TelegramID.")
            return
        await message.answer(f"Готово ✅ Удалил регистрацию: {deleted_name} — {telegram_id}")
        return

    if name is not None:
        deleted_tid = await users_delete_by_name(name)
        if deleted_tid is None:
            await message.answer("Не нашёл регистрацию по этому имени.")
            return
        await message.answer(f"Готово ✅ Удалил регистрацию: {name} — {deleted_tid}")
        return

    await message.answer("Не понял, кого удалять. Пример: /unregister 123456789 или /unregister Иван")


@router.message(Command("newtask"))
async def cmd_newtask(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()

    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сначала сделай: /register <ИмяВкладки>")
        return

    await state.update_data(from_name=message.from_user.full_name)
    await state.set_state(NewTaskFSM.choosing_assignee)

    await message.answer("Кому поставить задачу?", reply_markup=assignee_keyboard(list(users_map.keys())))


# ---------- menu buttons (reply keyboard) ----------

@router.message(F.text == "➕ Новая задача")
async def btn_newtask(message: Message, state: FSMContext):
    await cmd_newtask(message, state)


@router.message(F.text == "📋 Мои задачи")
async def btn_my(message: Message):
    await cmd_my(message)


@router.message(F.text == "⏰ Просроченные")
async def btn_overdue(message: Message, state: FSMContext):
    await cmd_overdue(message, state)


@router.message(F.text == "✅ Выполненные")
async def btn_done(message: Message, state: FSMContext):
    await cmd_done(message, state)



@router.message(F.text == "📦 Все")
async def btn_all(message: Message):
    await cmd_all(message)


@router.message(F.text == "🧾 Помощь")
async def btn_help(message: Message):
    await cmd_start(message)


@router.message(F.text == "👥 Регистрации")
async def btn_registrations(message: Message):
    await cmd_registrations(message)


# ---------- FSM: create task ----------

@router.callback_query(NewTaskFSM.choosing_assignee, F.data.startswith("assignee:"))
async def pick_assignee(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return

    assignee = callback.data.split(":", 1)[1].strip()

    await state.update_data(assignee=assignee)
    await state.set_state(NewTaskFSM.entering_task_text)

    await callback.message.answer(f"Ок. Напиши текст задачи для: {assignee}")
    await callback.answer()


@router.message(NewTaskFSM.entering_task_text)
async def enter_task_text(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return

    task_text = (message.text or "").strip()
    if not task_text:
        await message.answer("Текст задачи пустой. Напиши ещё раз.")
        return

    await state.update_data(task_text=task_text)
    await state.set_state(NewTaskFSM.choosing_due_preset)

    await message.answer("Выбери срок задачи:", reply_markup=due_date_keyboard())


@router.callback_query(NewTaskFSM.choosing_due_preset, F.data.startswith("due:"))
async def pick_due_preset(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if await deny_cb_if_not_allowed(callback):
        return

    preset = callback.data.split(":", 1)[1].strip()

    if preset == "other":
        await state.set_state(NewTaskFSM.entering_due_date_manual)
        await callback.message.answer("Введи срок (например 2026-02-05 или 05.02.2026).")
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


@router.message(NewTaskFSM.entering_due_date_manual)
async def enter_due_date_manual(message: Message, state: FSMContext, bot: Bot):
    if await deny_if_not_allowed(message):
        return

    raw_due = (message.text or "").strip()

    try:
        due_iso = normalize_due_date(raw_due)
    except Exception:
        await message.answer("Не смог распознать дату. Пример: 2026-02-05 или 05.02.2026. Попробуй ещё раз.")
        return

    await create_task_and_notify(message, state, bot, due_iso)


async def create_task_and_notify(message: Message, state: FSMContext, bot: Bot, due_iso: str):
    data = await state.get_data()

    assignee = data["assignee"]
    task_text = data["task_text"]
    from_name = data.get("from_name", "Unknown")

    created_at = now_iso()

    row = TaskRow(
        task_id="",  # ✅ пусто => tasks.py сам назначит порядковый номер
        task=task_text,
        from_name=from_name,
        due_str=due_iso,
        status=STATUS_TODO,
        created_at=created_at,
    )

    task_id = await task_append(assignee, row)  # ✅ получили номер
    row.task_id = task_id

    await task_append(assignee, row)

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

    await message.answer(
        "Готово ✅ Задача создана.\n\n"
        + format_task_line(
            row.task_id,
            row.task,
            row.from_name,
            row.due_str,
            row.status,
            is_common=(assignee == COMMON_SHEET),
        )
    )

    await state.clear()


# ---------- tasks view ----------

async def show_tasks(message: Message, my_sheet_name: str, mode: str):
    personal = await tasks_list(my_sheet_name)

    if mode == "my":
        personal = [t for t in personal if t.status != STATUS_DONE]
    elif mode == "overdue":
        personal = [t for t in personal if t.status != STATUS_DONE and t.due_str and is_overdue(t.due_str)]
    elif mode == "done":
        personal = [t for t in personal if t.status == STATUS_DONE]

    common = await common_tasks_for_user(my_sheet_name, mode)

    combined: List[Tuple[TaskRow, bool]] = []
    combined += [(t, False) for t in personal]
    combined += [(t, True) for t in common]

    if not combined:
        await message.answer("Нет задач по выбранному фильтру.")
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
        await message.answer(part)

    for (t, is_common) in combined:
        if t.status == STATUS_DONE:
            continue
        if is_common:
            await message.answer(f"Отметить выполненной ОБЩУЮ задачу [{t.task_id}]?", reply_markup=done_common_keyboard(t.task_id))
        else:
            await message.answer(f"Отметить выполненной задачу [{t.task_id}]?", reply_markup=done_personal_keyboard(my_sheet_name, t.task_id))


async def show_tasks_filtered(message: Message, my_sheet_name: str, mode: str, start_iso: str, end_iso: str):
    """
    Показываем задачи по фильтру периода (ПО DUE ДАТЕ).
    mode: overdue или done
    start_iso/end_iso: включительно
    """
    personal = await tasks_list(my_sheet_name)

    if mode == "overdue":
        personal = [
            t for t in personal
            if t.status != STATUS_DONE
            and t.due_str
            and is_overdue(t.due_str)                 # просрочено
            and _in_due_range(t.due_str, start_iso, end_iso)  # и в диапазоне по due
        ]
    elif mode == "done":
        personal = [
            t for t in personal
            if t.status == STATUS_DONE
            and t.due_str
            and _in_due_range(t.due_str, start_iso, end_iso)
        ]
    else:
        await send_with_menu(message, "Неизвестный режим фильтра.")
        return

    # общие задачи тоже фильтруем по due
    common = await common_tasks_for_user(my_sheet_name, mode)
    common = [t for t in common if t.due_str and _in_due_range(t.due_str, start_iso, end_iso)]

    combined: List[Tuple[TaskRow, bool]] = []
    combined += [(t, False) for t in personal]
    combined += [(t, True) for t in common]

    if not combined:
        await send_with_menu(message, f"Нет задач за период {start_iso} — {end_iso}.")
        return

    def sort_key(item: Tuple[TaskRow, bool]):
        t, _ = item
        due_val = t.due_str or "9999-12-31"
        return due_val

    combined.sort(key=sort_key)

    lines = [
        f"Период по сроку: {start_iso} — {end_iso}\n"
    ] + [
        format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=is_common)
        for (t, is_common) in combined
    ]

    for part in chunk_text(lines):
        await send_with_menu(message, part)

    # DONE-кнопки показываем только для overdue (чтобы можно было быстро закрывать)
    if mode == "overdue":
        for (t, is_common) in combined:
            if t.status == STATUS_DONE:
                continue
            if is_common:
                await message.answer(f"Отметить выполненной ОБЩУЮ задачу [{t.task_id}]?", reply_markup=done_common_keyboard(t.task_id))
            else:
                await message.answer(f"Отметить выполненной задачу [{t.task_id}]?", reply_markup=done_personal_keyboard(my_sheet_name, t.task_id))


@router.callback_query(TasksFilterFSM.choosing_period, F.data.startswith("period:"))
async def cb_choose_period(callback: CallbackQuery, state: FSMContext):
    if await deny_cb_if_not_allowed(callback):
        return

    _, mode, period = callback.data.split(":", 2)

    data = await state.get_data()
    sheet = data.get("filter_sheet")

    if not sheet:
        await callback.message.answer("Ошибка: не найден пользователь. Открой /done или /overdue заново.")
        await state.clear()
        await callback.answer()
        return

    if period == "other":
        await state.update_data(filter_mode=mode)
        await state.set_state(TasksFilterFSM.entering_start)
        await callback.message.answer("Введи дату НАЧАЛА (например 2026-02-01 или 01.02.2026):")
        await callback.answer()
        return

    start_iso, end_iso = _period_range(period)

    await show_tasks_filtered(callback.message, sheet, mode, start_iso, end_iso)

    await state.clear()
    await callback.answer()


@router.message(TasksFilterFSM.entering_start)
async def filter_enter_start(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return

    raw = (message.text or "").strip()
    try:
        start_iso = normalize_due_date(raw)
    except Exception:
        await send_with_menu(message, "Не понял дату начала. Пример: 2026-02-01 или 01.02.2026.")
        return

    await state.update_data(filter_start=start_iso)
    await state.set_state(TasksFilterFSM.entering_end)

    await send_with_menu(message, "Теперь введи дату КОНЦА (например 2026-02-10 или 10.02.2026):")


@router.message(TasksFilterFSM.entering_end)
async def filter_enter_end(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return

    data = await state.get_data()
    sheet = data.get("filter_sheet")
    mode = data.get("filter_mode")
    start_iso = data.get("filter_start")

    raw = (message.text or "").strip()
    try:
        end_iso = normalize_due_date(raw)
    except Exception:
        await send_with_menu(message, "Не понял дату конца. Пример: 2026-02-10 или 10.02.2026.")
        return

    if not sheet or not mode or not start_iso:
        await send_with_menu(message, "Ошибка состояния фильтра. Открой /done или /overdue заново.")
        await state.clear()
        return

    if end_iso < start_iso:
        await send_with_menu(message, f"Дата конца меньше даты начала. Начало: {start_iso}, конец: {end_iso}. Введи конец ещё раз.")
        return

    await show_tasks_filtered(message, sheet, mode, start_iso, end_iso)

    await state.clear()


@router.message(Command("my"))
async def cmd_my(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)

    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await show_tasks(message, my_sheet, "my")

@router.message(Command("overdue"))
async def cmd_overdue(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)

    if not my_sheet:
        await send_with_menu(message, "Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    # сохраняем контекст фильтра в FSM
    await state.update_data(filter_mode="overdue", filter_sheet=my_sheet)
    await state.set_state(TasksFilterFSM.choosing_period)

    await message.answer(
        "Выбери период по сроку задачи (считаем от даты СРОКА):",
        reply_markup=period_filter_keyboard("overdue"),
    )


@router.message(Command("done"))
async def cmd_done(message: Message, state: FSMContext):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)

    if not my_sheet:
        await send_with_menu(message, "Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await state.update_data(filter_mode="done", filter_sheet=my_sheet)
    await state.set_state(TasksFilterFSM.choosing_period)

    await message.answer(
        "Выбери период по сроку задачи (считаем от даты СРОКА):",
        reply_markup=period_filter_keyboard("done"),
    )



@router.message(Command("all"))
async def cmd_all(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)

    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await show_tasks(message, my_sheet, "all")


@router.message(Command("team_overdue"))
async def cmd_team_overdue(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    if not users_map:
        await message.answer("В Users нет регистраций.")
        return

    out: List[str] = []

    for name in sorted(users_map.keys()):
        personal = await tasks_list(name)
        personal_overdue = [t for t in personal if t.status != STATUS_DONE and t.due_str and is_overdue(t.due_str)]
        common_overdue = await common_tasks_for_user(name, "overdue")

        if personal_overdue or common_overdue:
            out.append(f"== {name} ==")
            for t in personal_overdue:
                out.append(format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=False))
            for t in common_overdue:
                out.append(format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=True))
            out.append("")

    if not out:
        await message.answer("Просроченных задач по команде нет 🎉")
        return

    for part in chunk_text(out):
        await message.answer(part)


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


#ЧЕПУХА
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
    if text in MENU_BUTTONS or text.startswith("🛠"):
        return
    await send_with_menu(message, "Не понял 🙂 Выбери действие в меню 👇")

def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return dp
