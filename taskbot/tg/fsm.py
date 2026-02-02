# fsm.py — состояния диалога создания задачи

from aiogram.fsm.state import StatesGroup, State


class NewTaskFSM(StatesGroup):
    choosing_assignee = State()
    entering_task_text = State()
    choosing_due_preset = State()
    entering_due_date_manual = State()
