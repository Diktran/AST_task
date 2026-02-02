# fsm.py — состояния диалога /newtask

from aiogram.fsm.state import StatesGroup, State  # FSM сущности


class NewTaskFSM(StatesGroup):
    choosing_assignee = State()       # выбор исполнителя
    entering_task_text = State()      # ввод текста задачи
    choosing_due_preset = State()     # выбор срока кнопками (Сегодня/Завтра/Конец недели/Другой)
    entering_due_date_manual = State()  # ручной ввод даты, если выбрали "Другой"
