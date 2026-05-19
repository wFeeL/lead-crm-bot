from aiogram.fsm.state import State, StatesGroup


class LeadFormState(StatesGroup):
    choosing_category = State()
    answering_questions = State()
    uploading_files = State()
    entering_contact = State()
    confirming = State()
    editing_one_answer = State()
