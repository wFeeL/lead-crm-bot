from pathlib import Path

from app.bot.screens.lead_question import (
    LEAD_QUESTION_SCREEN_ID,
    LeadQuestionBackCallback,
    LeadQuestionChoiceCallback,
    LeadQuestionSkipCallback,
    render_lead_question,
)
from app.core.constants import QuestionType
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def _q(qid=1, text="Q?", qtype=QuestionType.TEXT, required=True, options=None):
    return {
        "id": qid,
        "key": "k",
        "text": text,
        "type": qtype,
        "required": required,
        "options": options or [],
    }


def test_required_question_has_no_skip():
    q = _q(required=True)
    screen = render_lead_question(
        content=_content(),
        question=q,
        index=0,
        total=2,
        stack=["main_menu", "lead_category", "lead_question"],
    )
    labels = [b.text for row in screen.keyboard.inline_keyboard for b in row]
    assert all("Пропустить" not in lbl for lbl in labels)


def test_optional_question_has_skip():
    q = _q(required=False)
    screen = render_lead_question(
        content=_content(),
        question=q,
        index=0,
        total=2,
        stack=["main_menu", "lead_category", "lead_question"],
    )
    labels = [b.text for row in screen.keyboard.inline_keyboard for b in row]
    assert any("Пропустить" in lbl for lbl in labels)


def test_back_button_visible_when_index_gt_0():
    q = _q()
    screen = render_lead_question(
        content=_content(),
        question=q,
        index=1,
        total=3,
        stack=["main_menu", "lead_category", "lead_question"],
    )
    labels = [b.text for row in screen.keyboard.inline_keyboard for b in row]
    assert any("Предыдущий" in lbl for lbl in labels)


def test_choice_question_has_option_buttons():
    q = _q(qtype=QuestionType.CHOICE, options=["A", "B", "C"])
    screen = render_lead_question(
        content=_content(),
        question=q,
        index=0,
        total=1,
        stack=["main_menu", "lead_category", "lead_question"],
    )
    choice_btns = [
        b for row in screen.keyboard.inline_keyboard for b in row if "lq_choice:" in b.callback_data
    ]
    assert len(choice_btns) == 3


def test_screen_id_and_progress_in_text():
    q = _q()
    screen = render_lead_question(
        content=_content(),
        question=q,
        index=2,
        total=5,
        stack=["main_menu", "lead_category", "lead_question"],
    )
    assert screen.screen_id == LEAD_QUESTION_SCREEN_ID
    assert "3/5" in screen.text


def test_callbacks_pack_with_correct_prefixes():
    assert LeadQuestionChoiceCallback(question_id=1, option_index=0).pack().startswith("lq_choice:")
    assert LeadQuestionSkipCallback(question_id=1).pack().startswith("lq_skip:")
    assert LeadQuestionBackCallback(question_id=1).pack().startswith("lq_back:")
