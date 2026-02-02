# fsm.py — состояния диалога создания задачи

from aiogram.fsm.state import StatesGroup, State


class NewTaskFSM(StatesGroup):
    choosing_assignee = State()
    entering_task_text = State()
    choosing_due_preset = State()
    entering_due_date_manual = State()

class TasksFilterFSM(StatesGroup):
    choosing_period = State()      # выбор день/неделя/месяц/другое
    entering_start = State()       # ввод начала периода
    entering_end = State()         # ввод конца периода

class AdminTasksFSM(StatesGroup):
    choosing_user = State()
    choosing_view = State()
    choosing_period = State()
    entering_start = State()
    entering_end = State()
    editing_text = State()
    editing_due = State()
