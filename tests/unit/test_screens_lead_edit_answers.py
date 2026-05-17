from pathlib import Path

from app.bot.screens.lead_edit_answers import (
    LEAD_EDIT_ANSWERS_SCREEN_ID,
    LeadEditAnswerCallback,
    render_lead_edit_answers,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"
STACK = ["main_menu", "lead_category", "lead_question", "lead_confirm", "lead_edit_answers"]


def _content() -> ContentService:
    return ContentService(ContentService.load(_CONTENT_DIR))


def _draft(answers: list[dict]) -> dict:
    return {"answers": answers, "questions": [{"id": i + 1} for i in range(len(answers))]}


def test_render_edit_answers_lists_each_answer_with_pencil():
    answers = [
        {"key": "name", "question_text": "Как вас зовут?", "value_text": "Иван"},
        {"key": "city", "question_text": "Город?", "value_text": "Москва"},
    ]
    screen = render_lead_edit_answers(content=_content(), draft=_draft(answers), stack=STACK)
    assert screen.screen_id == LEAD_EDIT_ANSWERS_SCREEN_ID
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    # Each answer becomes a row.
    assert any("Как вас зовут?" in lbl and "Иван" in lbl and "✏" in lbl for lbl in labels)
    assert any("Город?" in lbl and "Москва" in lbl for lbl in labels)
    # Done button exists.
    assert any("Готово" in lbl for lbl in labels)


def test_render_edit_answers_handles_empty_list():
    screen = render_lead_edit_answers(content=_content(), draft={"answers": []}, stack=STACK)
    assert "Нет ответов" in screen.text
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("Готово" in lbl for lbl in labels)


def test_render_edit_answers_truncates_long_value():
    long_value = "А" * 500
    answers = [{"key": "x", "question_text": "Вопрос?", "value_text": long_value}]
    screen = render_lead_edit_answers(content=_content(), draft=_draft(answers), stack=STACK)
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    # The long button label is truncated to a reasonable length.
    long_btn = next(lbl for lbl in labels if "Вопрос" in lbl)
    assert len(long_btn) < 100


def test_edit_answer_callbacks_pack():
    assert LeadEditAnswerCallback(action="pick", index=2).pack() == "lead_edit:pick:2"
    assert LeadEditAnswerCallback(action="done").pack().startswith("lead_edit:done")


def test_render_edit_answers_falls_back_to_key_when_question_text_missing():
    answers = [{"key": "company_name", "value_text": "X"}]
    screen = render_lead_edit_answers(content=_content(), draft=_draft(answers), stack=STACK)
    labels = [btn.text for row in screen.keyboard.inline_keyboard for btn in row]
    assert any("company_name" in lbl for lbl in labels)
