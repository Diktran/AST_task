# fsm.py — состояния диалогов

from aiogram.fsm.state import StatesGroup, State


class NewTaskFSM(StatesGroup):
    choosing_assignee = State()
    entering_task_text = State()
    choosing_due_preset = State()
    entering_due_date_manual = State()


class AdminTasksFSM(StatesGroup):
    choosing_user = State()
    choosing_view = State()
    editing_text = State()
    editing_due = State()
