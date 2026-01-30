# formatters.py — форматирование вывода и разбиение сообщений

from typing import List  # типы
from taskbot.config import STATUS_DONE  # статус DONE
from taskbot.utils.dates import is_overdue  # проверка просрочки


def format_task_line(task_id: str, task: str, from_name: str, due_str: str, status: str, is_common: bool) -> str:
    """
    Форматируем одну задачу для вывода.
    is_common=True => добавляем значок 📌.
    """
    common_prefix = "📌 " if is_common else ""  # маркер общей задачи
    overdue_mark = ""  # маркер просрочки

    # Если срок есть, статус не DONE и срок прошёл — показываем предупреждение
    if due_str and status != STATUS_DONE and is_overdue(due_str):
        overdue_mark = " ⚠️ПРОСРОЧЕНО"

    return (
        f"• {common_prefix}[{task_id}] {task}\n"
        f"  От: {from_name} | Срок: {due_str or '-'} | Статус: {status}{overdue_mark}"
    )


def chunk_text(lines: List[str], max_chars: int = 3500) -> List[str]:
    """
    Telegram имеет ограничение на длину сообщения.
    Разбиваем список строк на несколько сообщений.
    """
    chunks: List[str] = []  # список готовых кусочков
    buf = ""  # буфер текущего сообщения

    for line in lines:
        # +2 на переносы строки
        if len(buf) + len(line) + 2 > max_chars:
            chunks.append(buf)  # фиксируем буфер
            buf = ""  # начинаем новый
        buf += line + "\n\n"  # добавляем строку

    if buf.strip():
        chunks.append(buf)

    return chunks
