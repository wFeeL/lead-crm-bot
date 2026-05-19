from aiogram.fsm.state import State, StatesGroup


class AdminFlowState(StatesGroup):
    writing_internal_comment = State()
    writing_client_reply = State()
    writing_close_reason = State()  # for DONE/REJECTED custom reason
    searching = State()  # admin typing the search query
