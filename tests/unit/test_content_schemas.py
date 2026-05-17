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
