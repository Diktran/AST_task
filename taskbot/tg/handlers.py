# handlers.py — все Telegram-команды и callback-обработчики
# В ЭТОЙ ВЕРСИИ:
# - добавлены кнопки выбора срока: Сегодня/Завтра/Конец недели/Другой
# - "Другой" -> включаем ручной ввод даты, как было раньше
# - сохранены: whitelist, /unregister, запрет повторной регистрации

from __future__ import annotations  # чтобы типы работали стабильно

from typing import Optional, Tuple, List  # типы
import uuid  # генерация коротких TaskID

from aiogram import Dispatcher, Router, F, Bot  # aiogram
from aiogram.types import Message, CallbackQuery  # типы апдейтов
from aiogram.filters import Command  # фильтр команд
from aiogram.fsm.context import FSMContext  # FSM
from aiogram.fsm.storage.memory import MemoryStorage  # хранилище FSM

from taskbot.tg.fsm import NewTaskFSM  # состояния

from taskbot.tg.keyboards import (  # клавиатуры
    assignee_keyboard,
    due_date_keyboard,
    done_personal_keyboard,
    done_common_keyboard,
    main_menu_keyboard,
)

from taskbot.sheets.users import (  # пользователи
    users_get_map,
    users_upsert,
    users_get_by_telegram_id,
    users_get_by_name,
    users_delete_by_telegram_id,
)

from taskbot.sheets.tasks import (  # задачи
    TaskRow,
    task_append,
    tasks_list,
    task_set_done,
    now_iso,
)

from taskbot.sheets.common import (  # общие задачи
    common_tasks_for_user,
    common_progress_set_done,
)

from taskbot.utils.dates import (  # даты
    normalize_due_date,
    is_overdue,
    today_iso,
    tomorrow_iso,
    end_of_week_iso,
)

from taskbot.utils.formatters import (  # форматирование
    format_task_line,
    chunk_text,
)

from taskbot.config import (  # конфиг
    COMMON_SHEET,
    STATUS_TODO,
    STATUS_DONE,
    ALLOWED_TELEGRAM_IDS,
    ADMIN_TELEGRAM_IDS,
)


router = Router()  # роутер

def is_admin(user_id: int) -> bool:
    """Проверяем, является ли пользователь админом."""
    return user_id in ADMIN_TELEGRAM_IDS


def is_allowed(user_id: int) -> bool:
    """Доступ разрешён, если в whitelist ИЛИ админ."""
    return (user_id in ALLOWED_TELEGRAM_IDS) or is_admin(user_id)


async def deny_if_not_allowed(message: Message) -> bool:
    """Проверка доступа для message-хендлеров. True = доступ запрещён."""
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён. Твой Telegram ID не в белом списке.")
        return True
    return False


async def deny_cb_if_not_allowed(callback: CallbackQuery) -> bool:
    """Проверка доступа для callback-хендлеров. True = доступ запрещён."""
    if not is_allowed(callback.from_user.id):
        await callback.message.answer("⛔ Доступ запрещён. Твой Telegram ID не в белом списке.")
        await callback.answer()
        return True
    return False


def get_my_sheet_name_or_none(telegram_id: int, users_map: dict[str, int]) -> Optional[str]:
    """Находим имя вкладки пользователя по TelegramID."""
    for name, tid in users_map.items():
        if tid == telegram_id:
            return name
    return None


def uuid_short() -> str:
    """Короткий TaskID (8 символов)."""
    return uuid.uuid4().hex[:8]


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Инструкция."""
    await message.answer(
        "Привет! Я бот задач.\n\n"
        "Регистрация:\n"
        "/register <ИмяВкладки>\n\n"
        "Можно пользоваться кнопками меню снизу 👇",
        reply_markup=main_menu_keyboard(is_admin(message.from_user.id)),
    )


@router.message(Command("register"))
async def cmd_register(message: Message):
    """
    /register <ИмяВкладки>

    Правила:
      1) Только пользователи из белого списка могут регистрироваться
      2) Нельзя регистрироваться повторно с одного TelegramID
      3) Нельзя занять имя вкладки, которое уже привязано к другому TelegramID
    """
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
            f"Если нужно сменить имя — сначала сделай /unregister, потом /register <Имя>."
        )
        return

    existing_tid = await users_get_by_name(sheet_name)
    if existing_tid is not None and existing_tid != telegram_id:
        await message.answer(f"⛔ Имя '{sheet_name}' уже занято другим пользователем. Выбери другое.")
        return

    await users_upsert(sheet_name, telegram_id)


    await message.answer(
        f"Готово ✅ Ты зарегистрирован как '{sheet_name}'.\n"
        f"Теперь можно работать через меню снизу 👇",
        reply_markup=main_menu_keyboard(is_admin(message.from_user.id)),
        )


@router.message(Command("unregister"))
async def cmd_unregister(message: Message):
    """
    /unregister
    Удаляем строку из Users по TelegramID.
    Личный лист задач НЕ удаляем (чтобы не терять историю).
    """
    if await deny_if_not_allowed(message):
        return

    telegram_id = message.from_user.id

    deleted_name = await users_delete_by_telegram_id(telegram_id)
    if deleted_name is None:
        await message.answer("Ты не зарегистрирован. Удалять нечего.")
        return

    await message.answer(
        f"Готово ✅ Регистрация удалена (было имя: '{deleted_name}').\n"
        f"Теперь можно зарегистрироваться заново: /register <ИмяВкладки>"
    )


@router.message(Command("newtask"))
async def cmd_newtask(message: Message, state: FSMContext):
    """
    /newtask — старт диалога.
    """
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()

    # инициатор должен быть зарегистрирован
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сначала сделай: /register <ИмяВкладки>")
        return

    if not users_map:
        await message.answer("Пока нет зарегистрированных пользователей. Сначала сделайте /register <ИмяВкладки>.")
        return

    await state.update_data(from_name=message.from_user.full_name)
    await state.set_state(NewTaskFSM.choosing_assignee)

    await message.answer("Кому поставить задачу?", reply_markup=assignee_keyboard(list(users_map.keys())))


@router.callback_query(NewTaskFSM.choosing_assignee, F.data.startswith("assignee:"))
async def pick_assignee(callback: CallbackQuery, state: FSMContext):
    """Выбор исполнителя."""
    if await deny_cb_if_not_allowed(callback):
        return

    assignee = callback.data.split(":", 1)[1].strip()

    await state.update_data(assignee=assignee)
    await state.set_state(NewTaskFSM.entering_task_text)

    await callback.message.answer(f"Ок. Напиши текст задачи для: {assignee}")
    await callback.answer()


@router.message(NewTaskFSM.entering_task_text)
async def enter_task_text(message: Message, state: FSMContext):
    """Ввод текста задачи."""
    if await deny_if_not_allowed(message):
        return

    task_text = (message.text or "").strip()
    if not task_text:
        await message.answer("Текст задачи пустой. Напиши ещё раз.")
        return

    await state.update_data(task_text=task_text)

    # ВМЕСТО ручного ввода даты сразу — показываем кнопки срока
    await state.set_state(NewTaskFSM.choosing_due_preset)

    await message.answer("Выбери срок задачи:", reply_markup=due_date_keyboard())


@router.callback_query(NewTaskFSM.choosing_due_preset, F.data.startswith("due:"))
async def pick_due_preset(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Выбор срока кнопкой.
    Если "Другой" — переводим в ручной ввод.
    Если preset — сразу создаём задачу (как раньше после ввода даты).
    """
    if await deny_cb_if_not_allowed(callback):
        return

    preset = callback.data.split(":", 1)[1].strip()  # today/tomorrow/eow/other

    # Если пользователь выбрал "Другой" — просим ввести дату текстом
    if preset == "other":
        await state.set_state(NewTaskFSM.entering_due_date_manual)
        await callback.message.answer("Введи срок (например 2026-02-05 или 05.02.2026).")
        await callback.answer()
        return

    # Пресеты дат
    if preset == "today":
        due_iso = today_iso()
    elif preset == "tomorrow":
        due_iso = tomorrow_iso()
    elif preset == "eow":
        due_iso = end_of_week_iso()
    else:
        # На всякий случай (если пришло что-то неожиданное)
        await callback.message.answer("Неизвестный вариант срока. Выбери ещё раз.")
        await callback.answer()
        return

    # Создаём задачу с выбранной датой
    await create_task_and_notify(callback.message, state, bot, due_iso, chosen_via_buttons=True)
    await callback.answer()


@router.message(NewTaskFSM.entering_due_date_manual)
async def enter_due_date_manual(message: Message, state: FSMContext, bot: Bot):
    """Ручной ввод даты (как было раньше)."""
    if await deny_if_not_allowed(message):
        return

    raw_due = (message.text or "").strip()

    try:
        due_iso = normalize_due_date(raw_due)
    except Exception:
        await message.answer("Не смог распознать дату. Пример: 2026-02-05 или 05.02.2026. Попробуй ещё раз.")
        return

    await create_task_and_notify(message, state, bot, due_iso, chosen_via_buttons=False)


async def create_task_and_notify(message: Message, state: FSMContext, bot: Bot, due_iso: str, chosen_via_buttons: bool):
    """
    Общая функция:
      - собирает данные FSM (assignee, task_text, from_name)
      - создаёт TaskRow
      - пишет в Sheets
      - уведомляет исполнителя (если личная)
      - отвечает автору
      - очищает FSM

    chosen_via_buttons — просто для текста/отладки (не обязательно), оставил как параметр.
    """
    data = await state.get_data()

    assignee = data["assignee"]
    task_text = data["task_text"]
    from_name = data.get("from_name", "Unknown")

    task_id = uuid_short()
    created_at = now_iso()

    row = TaskRow(
        task_id=task_id,
        task=task_text,
        from_name=from_name,
        due_str=due_iso,
        status=STATUS_TODO,
        created_at=created_at,
    )

    # записываем задачу (в личный лист или "Общие")
    await task_append(assignee, row)

    # уведомление исполнителя (только для личной задачи)
    if assignee != COMMON_SHEET:
        users_map = await users_get_map()
        if assignee in users_map:
            assignee_tid = users_map[assignee]
            try:
                await bot.send_message(
                    assignee_tid,
                    "📬 Новая задача!\n\n"
                    + format_task_line(
                        row.task_id,
                        row.task,
                        row.from_name,
                        row.due_str,
                        row.status,
                        is_common=False,
                    )
                    + "\n\nПосмотреть: /my",
                )
            except Exception:
                pass

    # подтверждение автору
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


async def show_tasks(message: Message, my_sheet_name: str, mode: str):
    """
    Показ задач пользователя:
      - личные
      - общие (персонально)
    mode: my / overdue / done / all
    """
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
        t, _is_common = item
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
            await message.answer(
                f"Отметить выполненной ОБЩУЮ задачу [{t.task_id}]?",
                reply_markup=done_common_keyboard(t.task_id),
            )
        else:
            await message.answer(
                f"Отметить выполненной задачу [{t.task_id}]?",
                reply_markup=done_personal_keyboard(my_sheet_name, t.task_id),
            )


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
async def cmd_overdue(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)

    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await show_tasks(message, my_sheet, "overdue")


@router.message(Command("done"))
async def cmd_done(message: Message):
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)

    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return

    await show_tasks(message, my_sheet, "done")


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

@router.message(F.text == "➕ Новая задача")
async def btn_newtask(message: Message, state: FSMContext):
    """
    Кнопка меню: ➕ Новая задача
    Вызываем ту же логику, что и /newtask.
    """
    await cmd_newtask(message, state)


@router.message(F.text == "📋 Мои задачи")
async def btn_my(message: Message):
    """Кнопка меню: 📋 Мои задачи"""
    await cmd_my(message)


@router.message(F.text == "⏰ Просроченные")
async def btn_overdue(message: Message):
    """Кнопка меню: ⏰ Просроченные"""
    await cmd_overdue(message)


@router.message(F.text == "✅ Выполненные")
async def btn_done(message: Message):
    """Кнопка меню: ✅ Выполненные"""
    await cmd_done(message)


@router.message(F.text == "📦 Все")
async def btn_all(message: Message):
    """Кнопка меню: 📦 Все"""
    await cmd_all(message)


@router.message(F.text == "🧾 Помощь")
async def btn_help(message: Message):
    """Кнопка меню: 🧾 Помощь (просто текст подсказки)"""
    await cmd_start(message)


@router.message(F.text == "👥 Регистрации")
async def btn_registrations(message: Message):
    """
    Кнопка меню: 👥 Регистрации
    Доступна только админам (мы всё равно проверим внутри команды).
    """
    await cmd_registrations(message)


def build_dispatcher() -> Dispatcher:
    """Собираем Dispatcher и подключаем router."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return dp
