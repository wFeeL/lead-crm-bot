import pytest
from pydantic import ValidationError

from app.schemas.content import BrandConfig


def test_brand_config_parses_minimal_fields():
    data = {
        "company_name": "Acme",
        "manager_username": "@acme_manager",
        "manager_phone": "+7 (000) 000-00-00",
        "working_hours": "Пн-Пт 09-21",
        "welcome_intro": "Привет.",
        "support_intro": "Опишите вопрос.",
        "eta_response_hours": 24,
    }
    brand = BrandConfig.model_validate(data)
    assert brand.company_name == "Acme"
    assert brand.eta_response_hours == 24


def test_brand_config_rejects_missing_required():
    with pytest.raises(ValidationError):
        BrandConfig.model_validate({"company_name": "Only this"})


def test_brand_config_rejects_invalid_eta():
    with pytest.raises(ValidationError):
        BrandConfig.model_validate({
            "company_name": "Acme",
            "manager_username": "@a",
            "manager_phone": "+7",
            "working_hours": "x",
            "welcome_intro": "x",
            "support_intro": "x",
            "eta_response_hours": -1,
        })


from app.schemas.content import (
    CategoryConfig,
    FaqEntry,
    QuestionConfig,
)
from app.core.constants import QuestionType


def test_faq_entry_basic():
    entry = FaqEntry.model_validate({"q": "Сколько ждать?", "a": "До часа."})
    assert entry.q == "Сколько ждать?"
    assert entry.a == "До часа."


def test_question_config_basic():
    q = QuestionConfig.model_validate({
        "key": "goal",
        "text": "Что нужно?",
        "type": "long_text",
        "required": True,
    })
    assert q.key == "goal"
    assert q.type is QuestionType.LONG_TEXT
    assert q.required is True


def test_question_config_defaults_required_false():
    q = QuestionConfig.model_validate({
        "key": "deadline",
        "text": "Сроки?",
        "type": "text",
    })
    assert q.required is False


def test_question_config_rejects_unknown_type():
    with pytest.raises(ValidationError):
        QuestionConfig.model_validate({
            "key": "k",
            "text": "t",
            "type": "voice",
        })


def test_category_config_basic():
    cat = CategoryConfig.model_validate({
        "slug": "telegram_bot",
        "title": "Боты",
        "description": "Telegram-боты",
        "questions": [
            {"key": "goal", "text": "Что нужно?", "type": "long_text", "required": True},
        ],
    })
    assert cat.slug == "telegram_bot"
    assert cat.internal is False
    assert len(cat.questions) == 1
    assert cat.questions[0].key == "goal"


def test_category_config_internal_flag():
    cat = CategoryConfig.model_validate({
        "slug": "support",
        "title": "Поддержка",
        "description": "Связь",
        "internal": True,
        "questions": [
            {"key": "message", "text": "Опишите", "type": "long_text", "required": True},
        ],
    })
    assert cat.internal is True


def test_category_config_rejects_duplicate_question_keys():
    with pytest.raises(ValidationError):
        CategoryConfig.model_validate({
            "slug": "x",
            "title": "x",
            "description": "x",
            "questions": [
                {"key": "k", "text": "t1", "type": "text"},
                {"key": "k", "text": "t2", "type": "text"},
            ],
        })
