from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.constants import STATUS_EMOJIS, STATUS_TITLES, LeadStatus
from app.db.models.category import LeadCategory
from app.db.models.lead import Lead
from app.services.status import available_statuses


class MenuCallback(CallbackData, prefix="m"):
    action: str


class CategoryCallback(CallbackData, prefix="cat"):
    slug: str


class FlowCallback(CallbackData, prefix="flow"):
    action: str


class QuestionChoiceCallback(CallbackData, prefix="qc"):
    question_id: int
    option_index: int


class QuestionSkipCallback(CallbackData, prefix="qs"):
    question_id: int


class QuestionBackCallback(CallbackData, prefix="qb"):
    question_id: int


class UserLeadCallback(CallbackData, prefix="ul"):
    action: str
    lead_id: int


class AdminMenuCallback(CallbackData, prefix="am"):
    action: str
    status: str = ""


class AdminLeadCallback(CallbackData, prefix="al"):
    action: str
    lead_id: int


class AdminStatusCallback(CallbackData, prefix="as"):
    lead_id: int
    status: str


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Оставить заявку", callback_data=MenuCallback(action="create"))
    builder.button(text="📋 Мои заявки", callback_data=MenuCallback(action="my_leads"))
    builder.button(text="💬 Связаться с менеджером", callback_data=MenuCallback(action="support"))
    builder.button(text="❓ FAQ", callback_data=MenuCallback(action="faq"))
    builder.adjust(1)
    return builder.as_markup()


def categories_keyboard(categories: list[LeadCategory]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=category.title,
            callback_data=CategoryCallback(slug=category.slug),
        )
    builder.button(text="⬅️ Назад", callback_data=MenuCallback(action="back"))
    builder.adjust(1)
    return builder.as_markup()


def question_keyboard(
    *,
    required: bool,
    question_id: int | None = None,
    options: list[str] | None = None,
    can_go_back: bool = False,
) -> InlineKeyboardMarkup | None:
    if required and not options and not can_go_back:
        return None
    builder = InlineKeyboardBuilder()
    if question_id is not None and options:
        for index, option in enumerate(options):
            builder.button(
                text=str(option)[:64],
                callback_data=QuestionChoiceCallback(
                    question_id=question_id,
                    option_index=index,
                ),
            )
    if not required:
        callback_data = (
            QuestionSkipCallback(question_id=question_id)
            if question_id is not None
            else FlowCallback(action="skip_question")
        )
        builder.button(text="⏭ Пропустить", callback_data=callback_data)
    if can_go_back and question_id is not None:
        builder.button(
            text="⬅️ Назад",
            callback_data=QuestionBackCallback(question_id=question_id),
        )
    builder.adjust(1)
    return builder.as_markup()


def files_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Продолжить", callback_data=FlowCallback(action="files_done"))
    builder.button(
        text="⬅️ Назад к вопросам",
        callback_data=FlowCallback(action="back_to_questions"),
    )
    builder.button(text="🚫 Отмена", callback_data=FlowCallback(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📨 Отправить заявку", callback_data=FlowCallback(action="submit"))
    builder.button(text="📎 Добавить файл", callback_data=FlowCallback(action="add_file"))
    builder.button(text="✏️ Изменить ответы", callback_data=FlowCallback(action="edit_answers"))
    builder.button(text="🚫 Отмена", callback_data=FlowCallback(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить телефон", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Телефон или @username",
    )


def admin_comment_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🚫 Отменить комментарий",
        callback_data=AdminLeadCallback(action="cancel_comment", lead_id=lead_id),
    )
    return builder.as_markup()


def user_leads_keyboard(leads: list[Lead]) -> InlineKeyboardMarkup | None:
    if not leads:
        return None
    builder = InlineKeyboardBuilder()
    for lead in leads:
        builder.button(
            text=f"🔎 {lead.public_id or lead.id} {STATUS_EMOJIS.get(lead.status, '')}",
            callback_data=UserLeadCallback(action="detail", lead_id=lead.id),
        )
    builder.adjust(1)
    return builder.as_markup()


def user_lead_detail_keyboard(lead: Lead) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if lead.status == LeadStatus.NEW:
        builder.button(
            text="🚫 Отменить заявку",
            callback_data=UserLeadCallback(action="cancel", lead_id=lead.id),
        )
    builder.button(
        text="⬅️ К моим заявкам",
        callback_data=UserLeadCallback(action="back_to_list", lead_id=lead.id),
    )
    builder.adjust(1)
    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Все заявки", callback_data=AdminMenuCallback(action="list"))
    builder.button(
        text="🆕 Новые",
        callback_data=AdminMenuCallback(action="list", status=LeadStatus.NEW),
    )
    builder.button(
        text="🛠 В работе",
        callback_data=AdminMenuCallback(action="list", status=LeadStatus.IN_PROGRESS),
    )
    builder.button(
        text="⏳ Ждем клиента",
        callback_data=AdminMenuCallback(action="list", status=LeadStatus.WAITING),
    )
    builder.button(text="📤 CSV", callback_data=AdminMenuCallback(action="export"))
    builder.adjust(1)
    return builder.as_markup()


def admin_lead_keyboard(lead: Lead) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔎 Подробнее",
        callback_data=AdminLeadCallback(action="detail", lead_id=lead.id),
    )
    if lead.status == LeadStatus.NEW and lead.assigned_admin_id is None:
        builder.button(
            text="🛠 Взять в работу",
            callback_data=AdminLeadCallback(action="take", lead_id=lead.id),
        )
    for status in available_statuses(lead.status):
        if status == LeadStatus.CANCELLED:
            continue
        builder.button(
            text=f"{STATUS_EMOJIS.get(status, '')} {STATUS_TITLES.get(status, status)}",
            callback_data=AdminStatusCallback(lead_id=lead.id, status=status),
        )
    builder.button(
        text="📝 Внутренний комментарий",
        callback_data=AdminLeadCallback(action="comment", lead_id=lead.id),
    )
    builder.button(
        text="💬 Ответ клиенту",
        callback_data=AdminLeadCallback(action="public_comment", lead_id=lead.id),
    )
    builder.button(text="⬅️ Админ-меню", callback_data=AdminMenuCallback(action="menu"))
    builder.adjust(2, 1, 1)
    return builder.as_markup()
