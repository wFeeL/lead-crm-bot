from aiogram.fsm.state import State, StatesGroup


class LeadFormState(StatesGroup):
    choosing_category = State()
    answering_questions = State()
    uploading_files = State()
    entering_contact = State()
    confirming = State()


# AdminCommentState removed — admin flow states now live in app/bot/states/admin_flow.py
