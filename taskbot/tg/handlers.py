# handlers.py — все Telegram-команды и callback-обработчики

from aiogram import Dispatcher, Router, F  # ядро
from aiogram.types import Message, CallbackQuery  # апдейты
from aiogram.filters import Command  # команды
from aiogram.fsm.context import FSMContext  # FSM контекст
from aiogram.fsm.storage.memory import MemoryStorage  # память FSM
from aiogram import Bot  # для отправки уведомлений

from taskbot.tg.fsm import NewTaskFSM  # состояния
from taskbot.tg.keyboards import assignee_keyboard, done_personal_keyboard, done_common_keyboard  # клавиатуры

from taskbot.sheets.users import users_get_map, users_upsert  # пользователи
from taskbot.sheets.tasks import TaskRow, task_append, tasks_list, task_set_done, now_iso  # задачи
from taskbot.sheets.common import common_tasks_for_user, common_progress_set_done  # общие
from taskbot.utils.dates import normalize_due_date, is_overdue  # даты
from taskbot.utils.formatters import format_task_line, chunk_text  # форматирование

from taskbot.config import COMMON_SHEET, STATUS_TODO, STATUS_DONE  # константы


router = Router()  # единый роутер хендлеров


def get_my_sheet_name_or_none(telegram_id: int, users_map: dict[str, int]):
    """Находим имя вкладки пользователя по TelegramID."""
    for name, tid in users_map.items():
        if tid == telegram_id:
            return name
    return None


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Приветствие и подсказки."""
    await message.answer(
        "Привет! Я бот задач.\n\n"
        "Сначала зарегистрируйся:\n"
        "/register <ИмяВкладки>\n\n"
        "Команды:\n"
        "/newtask — создать задачу\n"
        "/my — мои активные (личные + общие)\n"
        "/overdue — мои просроченные\n"
        "/done — мои выполненные\n"
        "/all — все мои\n"
        "/team_overdue — просрочка по команде\n"
    )


@router.message(Command("register"))
async def cmd_register(message: Message):
    """
    /register <ИмяВкладки>
    Создаёт/обновляет пользователя и создаёт личный лист при первой регистрации.
    """
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /register <ИмяВкладки>\nНапример: /register Иван")
        return

    sheet_name = parts[1].strip()
    telegram_id = message.from_user.id

    # Важно: users_upsert создаёт личный лист и заголовки автоматически
    await users_upsert(sheet_name, telegram_id)

    await message.answer(f"Готово ✅ Ты зарегистрирован как '{sheet_name}'.")


@router.message(Command("newtask"))
async def cmd_newtask(message: Message, state: FSMContext):
    """Запуск диалога создания задачи."""
    users_map = await users_get_map()

    if not users_map:
        await message.answer("Пока нет зарегистрированных пользователей. Сначала сделайте /register <ИмяВкладки>.")
        return

    # Сохраняем “кто ставит” (From)
    await state.update_data(from_name=message.from_user.full_name)

    # Переходим к выбору исполнителя
    await state.set_state(NewTaskFSM.choosing_assignee)

    await message.answer("Кому поставить задачу?", reply_markup=assignee_keyboard(list(users_map.keys())))


@router.callback_query(NewTaskFSM.choosing_assignee, F.data.startswith("assignee:"))
async def pick_assignee(callback: CallbackQuery, state: FSMContext):
    """Поймали выбор исполнителя."""
    assignee = callback.data.split(":", 1)[1].strip()

    # Сохраняем исполнителя
    await state.update_data(assignee=assignee)

    # Следующий шаг — ввод текста
    await state.set_state(NewTaskFSM.entering_task_text)

    await callback.message.answer(f"Ок. Напиши текст задачи для: {assignee}")
    await callback.answer()


@router.message(NewTaskFSM.entering_task_text)
async def enter_task_text(message: Message, state: FSMContext):
    """Получаем текст задачи."""
    task_text = (message.text or "").strip()
    if not task_text:
        await message.answer("Текст задачи пустой. Напиши ещё раз.")
        return

    await state.update_data(task_text=task_text)
    await state.set_state(NewTaskFSM.entering_due_date)

    await message.answer("Теперь введи срок (например 2026-02-05 или 05.02.2026).")


@router.message(NewTaskFSM.entering_due_date)
async def enter_due_date(message: Message, state: FSMContext, bot: Bot):
    """Получаем срок, создаём задачу, пишем в Sheets, уведомляем (если личная)."""
    raw_due = (message.text or "").strip()

    try:
        due_iso = normalize_due_date(raw_due)
    except Exception:
        await message.answer("Не смог распознать дату. Пример: 2026-02-05 или 05.02.2026. Попробуй ещё раз.")
        return

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

    # Запись задачи (в личный лист или в "Общие")
    await task_append(assignee, row)

    # Уведомление — только для личной задачи
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
        + format_task_line(row.task_id, row.task, row.from_name, row.due_str, row.status, is_common=(assignee == COMMON_SHEET))
    )

    await state.clear()


def uuid_short() -> str:
    """Короткий TaskID (8 символов)."""
    import uuid
    return uuid.uuid4().hex[:8]


async def show_tasks(message: Message, my_sheet_name: str, mode: str):
    """
    Показ задач пользователя:
      - личные из my_sheet_name
      - общие из "Общие" с персональным статусом
    """
    # Личные задачи
    personal = await tasks_list(my_sheet_name)

    # Фильтр личных по mode
    if mode == "my":
        personal = [t for t in personal if t.status != STATUS_DONE]
    elif mode == "overdue":
        personal = [t for t in personal if t.status != STATUS_DONE and t.due_str and is_overdue(t.due_str)]
    elif mode == "done":
        personal = [t for t in personal if t.status == STATUS_DONE]

    # Общие задачи (персонально)
    common = await common_tasks_for_user(my_sheet_name, mode)

    # Объединяем с флагом “общая/личная”
    combined: list[tuple[TaskRow, bool]] = []
    combined += [(t, False) for t in personal]
    combined += [(t, True) for t in common]

    if not combined:
        await message.answer("Нет задач по выбранному фильтру.")
        return

    # Сортируем: просроченные вверх, затем по due
    def sort_key(item):
        t, _is_common = item
        overdue_flag = 0 if (t.due_str and t.status != STATUS_DONE and is_overdue(t.due_str)) else 1
        due_val = t.due_str or "9999-12-31"
        return (overdue_flag, due_val)

    combined.sort(key=sort_key)

    # Формируем текст
    lines = [
        format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=is_common)
        for (t, is_common) in combined
    ]

    # Отправляем кусками
    for part in chunk_text(lines):
        await message.answer(part)

    # Кнопки DONE для невыполненных
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
    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return
    await show_tasks(message, my_sheet, "my")


@router.message(Command("overdue"))
async def cmd_overdue(message: Message):
    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return
    await show_tasks(message, my_sheet, "overdue")


@router.message(Command("done"))
async def cmd_done(message: Message):
    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return
    await show_tasks(message, my_sheet, "done")


@router.message(Command("all"))
async def cmd_all(message: Message):
    users_map = await users_get_map()
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        return
    await show_tasks(message, my_sheet, "all")


@router.message(Command("team_overdue"))
async def cmd_team_overdue(message: Message):
    """Просрочка по всем пользователям (личные + общие персонально)."""
    users_map = await users_get_map()
    if not users_map:
        await message.answer("В Users нет регистраций.")
        return

    out: list[str] = []

    for name in sorted(users_map.keys()):
        # Личная просрочка
        personal = await tasks_list(name)
        personal_overdue = [t for t in personal if t.status != STATUS_DONE and t.due_str and is_overdue(t.due_str)]

        # Общая просрочка персонально
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
    """DONE для личной задачи: done_personal:<sheet_name>:<task_id>"""
    _prefix, sheet_name, task_id = callback.data.split(":", 2)

    ok = await task_set_done(sheet_name, task_id)
    if ok:
        await callback.message.answer(f"Готово ✅ Задача [{task_id}] отмечена как DONE.")
    else:
        await callback.message.answer("Не нашёл задачу (возможно удалили или изменили ID).")

    await callback.answer()


@router.callback_query(F.data.startswith("done_common:"))
async def cb_done_common(callback: CallbackQuery):
    """DONE для общей задачи: done_common:<task_id>"""
    task_id = callback.data.split(":", 1)[1].strip()

    users_map = await users_get_map()
    my_name = get_my_sheet_name_or_none(callback.from_user.id, users_map)

    if not my_name:
        await callback.message.answer("Ты не зарегистрирован. Сделай: /register <ИмяВкладки>")
        await callback.answer()
        return

    # Пишем прогресс (TaskID, Name) -> DONE
    await common_progress_set_done(task_id, my_name)

    await callback.message.answer(f"Готово ✅ Общая задача [{task_id}] отмечена DONE для {my_name}.")
    await callback.answer()


def build_dispatcher() -> Dispatcher:
    """Собираем Dispatcher и подключаем router."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return dp
