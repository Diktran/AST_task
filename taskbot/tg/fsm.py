# fsm.py — состояния диалога /newtask

from aiogram.fsm.state import StatesGroup, State  # FSM сущности


class NewTaskFSM(StatesGroup):
    choosing_assignee = State()     # выбор исполнителя
    entering_task_text = State()    # ввод текста
    entering_due_date = State()     # ввод срока
