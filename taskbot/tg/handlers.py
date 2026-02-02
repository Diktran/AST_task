# handlers.py — все Telegram-команды и callback-обработчики
# В ЭТОЙ ВЕРСИИ ДОБАВЛЕНО:
# 1) /unregister — удалить регистрацию
# 2) белый список TelegramID (ALLOWED_TELEGRAM_IDS) — без него нельзя регистрироваться/смотреть/менять задачи
# 3) запрет повторной регистрации с одного TelegramID — сначала /unregister, потом /register
#
# Файл рассчитан на модульную структуру проекта, которую мы делали ранее.

from __future__ import annotations  # чтобы типы работали без проблем в старых версиях Python

from typing import Optional, Tuple, List  # типы для читаемости
import uuid  # генерация коротких TaskID

from aiogram import Dispatcher, Router, F, Bot  # ядро aiogram
from aiogram.types import Message, CallbackQuery  # апдейты Telegram
from aiogram.filters import Command  # фильтр команд
from aiogram.fsm.context import FSMContext  # контекст FSM
from aiogram.fsm.storage.memory import MemoryStorage  # хранилище FSM (в памяти)

from taskbot.tg.fsm import NewTaskFSM  # состояния FSM
from taskbot.tg.keyboards import (  # клавиатуры
    assignee_keyboard,
    done_personal_keyboard,
    done_common_keyboard,
)

from taskbot.sheets.users import (  # работа с пользователями в Sheets
    users_get_map,
    users_upsert,
    users_get_by_telegram_id,
    users_get_by_name,
    users_delete_by_telegram_id,
)

from taskbot.sheets.tasks import (  # работа с задачами
    TaskRow,
    task_append,
    tasks_list,
    task_set_done,
    now_iso,
)

from taskbot.sheets.common import (  # общие задачи и прогресс
    common_tasks_for_user,
    common_progress_set_done,
)

from taskbot.utils.dates import (  # даты
    normalize_due_date,
    is_overdue,
)

from taskbot.utils.formatters import (  # форматирование вывода
    format_task_line,
    chunk_text,
)

from taskbot.config import (  # константы и whitelist
    COMMON_SHEET,
    STATUS_TODO,
    STATUS_DONE,
    ALLOWED_TELEGRAM_IDS,
)


router = Router()  # роутер всех хендлеров


def is_allowed(user_id: int) -> bool:
    """
    Проверяем, есть ли TelegramID в белом списке.
    """
    return user_id in ALLOWED_TELEGRAM_IDS


async def deny_if_not_allowed(message: Message) -> bool:
    """
    Универсальная проверка доступа для message-хендлеров.
    Возвращает True если доступ запрещён (и уже ответили пользователю).
    """
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён. Твой Telegram ID не в белом списке.")
        return True
    return False


async def deny_cb_if_not_allowed(callback: CallbackQuery) -> bool:
    """
    Универсальная проверка доступа для callback-хендлеров.
    Возвращает True если доступ запрещён.
    """
    if not is_allowed(callback.from_user.id):
        # отвечаем в чат, чтобы было видно причину
        await callback.message.answer("⛔ Доступ запрещён. Твой Telegram ID не в белом списке.")
        await callback.answer()  # закрываем “часики”
        return True
    return False


def get_my_sheet_name_or_none(telegram_id: int, users_map: dict[str, int]) -> Optional[str]:
    """
    Находим имя вкладки пользователя по TelegramID.
    """
    for name, tid in users_map.items():  # перебираем все привязки
        if tid == telegram_id:  # нашли совпадение
            return name  # возвращаем имя вкладки
    return None  # не найден


def uuid_short() -> str:
    """
    Короткий TaskID (8 символов).
    """
    return uuid.uuid4().hex[:8]


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    /start — краткая инструкция.
    """
    # (Даже /start можно ограничить, но обычно оставляют открытым)
    await message.answer(
        "Привет! Я бот задач.\n\n"
        "Если у тебя есть доступ, зарегистрируйся:\n"
        "/register <ИмяВкладки>\n\n"
        "Команды:\n"
        "/newtask — создать задачу (можно 📌 Общие)\n"
        "/my — мои активные (личные + общие)\n"
        "/overdue — мои просроченные\n"
        "/done — мои выполненные\n"
        "/all — все мои\n"
        "/team_overdue — просрочка по команде\n"
        "/unregister — удалить регистрацию\n"
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
    # --- (0) проверка whitelist ---
    if await deny_if_not_allowed(message):
        return

    telegram_id = message.from_user.id  # TelegramID пользователя

    # --- (1) читаем аргумент команды ---
    parts = (message.text or "").split(maxsplit=1)  # делим на "/register" и "Имя"
    if len(parts) < 2 or not parts[1].strip():  # если имя не задано
        await message.answer("Использование: /register <ИмяВкладки>\nНапример: /register Иван")
        return

    sheet_name = parts[1].strip()  # имя вкладки

    # --- (2) запрещаем повторную регистрацию по TelegramID ---
    existing_name = await users_get_by_telegram_id(telegram_id)  # ищем по TelegramID
    if existing_name is not None:
        await message.answer(
            f"⛔ Ты уже зарегистрирован как '{existing_name}'.\n"
            f"Повторная регистрация запрещена.\n"
            f"Если нужно сменить имя — сначала сделай /unregister, потом /register <Имя>."
        )
        return

    # --- (3) запрещаем занять Name, который привязан к другому TelegramID ---
    existing_tid = await users_get_by_name(sheet_name)  # ищем TelegramID по имени вкладки
    if existing_tid is not None and existing_tid != telegram_id:
        await message.answer(
            f"⛔ Имя '{sheet_name}' уже занято другим пользователем.\n"
            f"Выбери другое имя вкладки."
        )
        return

    # --- (4) записываем регистрацию (и создаём личный лист) ---
    await users_upsert(sheet_name, telegram_id)

    await message.answer(f"Готово ✅ Ты зарегистрирован как '{sheet_name}'.")


@router.message(Command("unregister"))
async def cmd_unregister(message: Message):
    """
    /unregister

    Удаляет регистрацию пользователя из листа Users.
    Лист задач пользователя (вкладка) НЕ удаляется, чтобы не потерять историю задач.
    """
    # --- проверка whitelist ---
    if await deny_if_not_allowed(message):
        return

    telegram_id = message.from_user.id  # TelegramID пользователя

    deleted_name = await users_delete_by_telegram_id(telegram_id)  # удаляем запись по TelegramID

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
    /newtask — старт диалога создания задачи.
    1) Проверяем whitelist
    2) Проверяем, что пользователь зарегистрирован (иначе нельзя ставить задачи)
    3) Показываем кнопки людей + 📌 Общие
    """
    # --- проверка whitelist ---
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()  # читаем всех зарегистрированных

    # проверяем регистрацию инициатора (чтобы случайный whitelisted человек не ставил задачи без регистрации)
    my_sheet = get_my_sheet_name_or_none(message.from_user.id, users_map)
    if not my_sheet:
        await message.answer("Ты не зарегистрирован. Сначала сделай: /register <ИмяВкладки>")
        return

    # если никого нет — нечего выбирать
    if not users_map:
        await message.answer("Пока нет зарегистрированных пользователей. Сначала сделайте /register <ИмяВкладки>.")
        return

    # сохраняем “кто ставит” (From)
    await state.update_data(from_name=message.from_user.full_name)

    # включаем FSM на выбор исполнителя
    await state.set_state(NewTaskFSM.choosing_assignee)

    # показываем клавиатуру с исполнителями + общие
    await message.answer("Кому поставить задачу?", reply_markup=assignee_keyboard(list(users_map.keys())))


@router.callback_query(NewTaskFSM.choosing_assignee, F.data.startswith("assignee:"))
async def pick_assignee(callback: CallbackQuery, state: FSMContext):
    """
    Выбор исполнителя кнопкой.
    """
    # --- проверка whitelist ---
    if await deny_cb_if_not_allowed(callback):
        return

    assignee = callback.data.split(":", 1)[1].strip()  # достаём имя исполнителя

    # сохраняем исполнителя
    await state.update_data(assignee=assignee)

    # следующий шаг — ввод текста
    await state.set_state(NewTaskFSM.entering_task_text)

    await callback.message.answer(f"Ок. Напиши текст задачи для: {assignee}")
    await callback.answer()


@router.message(NewTaskFSM.entering_task_text)
async def enter_task_text(message: Message, state: FSMContext):
    """
    Ввод текста задачи.
    """
    # --- проверка whitelist ---
    if await deny_if_not_allowed(message):
        return

    task_text = (message.text or "").strip()  # текст задачи
    if not task_text:  # пустой ввод
        await message.answer("Текст задачи пустой. Напиши ещё раз.")
        return

    await state.update_data(task_text=task_text)  # сохраняем текст в FSM
    await state.set_state(NewTaskFSM.entering_due_date)  # переходим к вводу срока

    await message.answer("Теперь введи срок (например 2026-02-05 или 05.02.2026).")


@router.message(NewTaskFSM.entering_due_date)
async def enter_due_date(message: Message, state: FSMContext, bot: Bot):
    """
    Ввод срока, создание задачи, запись в Sheets, уведомление исполнителя (если личная).
    """
    # --- проверка whitelist ---
    if await deny_if_not_allowed(message):
        return

    raw_due = (message.text or "").strip()  # то, что ввёл пользователь

    # пытаемся распознать дату
    try:
        due_iso = normalize_due_date(raw_due)
    except Exception:
        await message.answer("Не смог распознать дату. Пример: 2026-02-05 или 05.02.2026. Попробуй ещё раз.")
        return

    data = await state.get_data()  # данные FSM
    assignee = data["assignee"]  # выбранный исполнитель
    task_text = data["task_text"]  # текст
    from_name = data.get("from_name", "Unknown")  # от кого

    # генерируем ID и время
    task_id = uuid_short()
    created_at = now_iso()

    # собираем строку задачи
    row = TaskRow(
        task_id=task_id,
        task=task_text,
        from_name=from_name,
        due_str=due_iso,
        status=STATUS_TODO,
        created_at=created_at,
    )

    # записываем задачу в лист исполнителя или в "Общие"
    await task_append(assignee, row)

    # если задача личная — уведомляем исполнителя
    if assignee != COMMON_SHEET:
        users_map = await users_get_map()  # получаем Name->TelegramID
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
                # человек мог не начать чат с ботом / заблокировать бота — тогда Telegram не даст отправить
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

    await state.clear()  # очищаем FSM


async def show_tasks(message: Message, my_sheet_name: str, mode: str):
    """
    Показ задач пользователя:
      - личные из my_sheet_name
      - общие из "Общие" с персональным статусом
    mode: my / overdue / done / all
    """
    # --- 1) личные ---
    personal = await tasks_list(my_sheet_name)

    # фильтр личных по mode
    if mode == "my":
        personal = [t for t in personal if t.status != STATUS_DONE]
    elif mode == "overdue":
        personal = [t for t in personal if t.status != STATUS_DONE and t.due_str and is_overdue(t.due_str)]
    elif mode == "done":
        personal = [t for t in personal if t.status == STATUS_DONE]
    elif mode == "all":
        pass  # без фильтра

    # --- 2) общие (персонально) ---
    common = await common_tasks_for_user(my_sheet_name, mode)

    # --- 3) объединяем ---
    combined: List[Tuple[TaskRow, bool]] = []
    combined += [(t, False) for t in personal]
    combined += [(t, True) for t in common]

    if not combined:
        await message.answer("Нет задач по выбранному фильтру.")
        return

    # --- 4) сортировка: просроченные вверх, затем по сроку ---
    def sort_key(item: Tuple[TaskRow, bool]):
        t, _is_common = item
        overdue_flag = 0 if (t.due_str and t.status != STATUS_DONE and is_overdue(t.due_str)) else 1
        due_val = t.due_str or "9999-12-31"
        return (overdue_flag, due_val)

    combined.sort(key=sort_key)

    # --- 5) вывод списка ---
    lines = [
        format_task_line(t.task_id, t.task, t.from_name, t.due_str, t.status, is_common=is_common)
        for (t, is_common) in combined
    ]

    for part in chunk_text(lines):
        await message.answer(part)

    # --- 6) кнопки DONE для невыполненных ---
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
    """
    /my — мои активные (личные TODO + общие TODO для меня).
    """
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
    """
    /overdue — мои просроченные.
    """
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
    """
    /done — мои выполненные (личные DONE + общие DONE).
    """
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
    """
    /all — все мои задачи.
    """
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
    """
    /team_overdue — просрочка по всем пользователям:
      - личные просроченные
      - общие просроченные персонально (если конкретный человек их не закрыл)
    """
    if await deny_if_not_allowed(message):
        return

    users_map = await users_get_map()
    if not users_map:
        await message.answer("В Users нет регистраций.")
        return

    out: List[str] = []

    for name in sorted(users_map.keys()):
        # личные задачи пользователя
        personal = await tasks_list(name)
        personal_overdue = [t for t in personal if t.status != STATUS_DONE and t.due_str and is_overdue(t.due_str)]

        # общие просроченные для конкретного пользователя
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
    """
    ✅ Done для личной задачи.
    callback_data: done_personal:<sheet_name>:<task_id>
    """
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
    """
    ✅ Done для общей задачи.
    callback_data: done_common:<task_id>
    """
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


def build_dispatcher() -> Dispatcher:
    """
    Собираем Dispatcher и подключаем router.
    """
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return dp
