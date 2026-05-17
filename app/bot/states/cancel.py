from aiogram.fsm.state import State, StatesGroup


class MyLeadCancelState(StatesGroup):
    writing_custom_reason = State()
