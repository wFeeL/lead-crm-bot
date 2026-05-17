from pathlib import Path

import pytest
import yaml

from app.services.content import ContentService


@pytest.fixture
def minimal_profile(tmp_path: Path) -> Path:
    profile = tmp_path / "minimal"
    profile.mkdir()
    (profile / "brand.yaml").write_text(
        "company_name: Acme\n"
        "manager_username: '@acme'\n"
        "manager_phone: '+7 000'\n"
        "working_hours: 'Пн-Пт'\n"
        "welcome_intro: 'Hi'\n"
        "support_intro: 'Ask'\n"
        "eta_response_hours: 24\n",
        encoding="utf-8",
    )
    (profile / "texts.yaml").write_text(
        "main_menu:\n"
        "  title: 'Меню'\n"
        "statuses:\n"
        "  new: {label: 'Новая', emoji: '🆕'}\n"
        "priorities:\n"
        "  normal: {label: 'Обычный', emoji: '⚪'}\n"
        "close_reasons:\n"
        "  rejected: ['Спам']\n"
        "  done: ['Готово']\n"
        "  cancelled: ['Передумал']\n",
        encoding="utf-8",
    )
    (profile / "faq.yaml").write_text("- q: 'Q'\n  a: 'A'\n", encoding="utf-8")
    (profile / "categories.yaml").write_text(
        "- slug: telegram_bot\n"
        "  title: 'Боты'\n"
        "  description: 'Telegram'\n"
        "  questions:\n"
        "    - {key: goal, text: 'Что?', type: long_text, required: true}\n",
        encoding="utf-8",
    )
    (profile / "config.yaml").write_text(
        "limits:\n"
        "  max_files_per_lead: 7\n"
        "ui:\n"
        "  page_size_my_leads: 10\n",
        encoding="utf-8",
    )
    return profile


def test_load_minimal_profile(minimal_profile: Path):
    bundle = ContentService.load(minimal_profile)

    assert bundle.brand.company_name == "Acme"
    assert bundle.texts.statuses["new"].emoji == "🆕"
    assert len(bundle.faq) == 1
    assert bundle.faq[0].q == "Q"
    assert len(bundle.categories) == 1
    assert bundle.categories[0].slug == "telegram_bot"
    assert bundle.config.limits.max_files_per_lead == 7
    assert bundle.config.ui.page_size_my_leads == 10
