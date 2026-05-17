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
        "limits:\n  max_files_per_lead: 7\nui:\n  page_size_my_leads: 10\n",
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


def test_load_missing_brand_file(tmp_path: Path):
    profile = tmp_path / "broken"
    profile.mkdir()
    with pytest.raises(FileNotFoundError, match="brand.yaml"):
        ContentService.load(profile)


def test_load_invalid_yaml(minimal_profile: Path):
    (minimal_profile / "brand.yaml").write_text(
        "company_name: Acme\n[bad yaml",
        encoding="utf-8",
    )
    with pytest.raises(yaml.YAMLError):
        ContentService.load(minimal_profile)


def test_load_invalid_schema(minimal_profile: Path):
    (minimal_profile / "brand.yaml").write_text(
        "company_name: Acme\n",
        encoding="utf-8",
    )
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ContentService.load(minimal_profile)


def test_load_empty_faq_file_yields_empty_list(minimal_profile: Path):
    (minimal_profile / "faq.yaml").write_text("", encoding="utf-8")
    bundle = ContentService.load(minimal_profile)
    assert bundle.faq == []


def test_load_empty_categories_file_yields_empty_list(minimal_profile: Path):
    (minimal_profile / "categories.yaml").write_text("", encoding="utf-8")
    bundle = ContentService.load(minimal_profile)
    assert bundle.categories == []


def test_load_empty_config_file_uses_defaults(minimal_profile: Path):
    (minimal_profile / "config.yaml").write_text("", encoding="utf-8")
    bundle = ContentService.load(minimal_profile)
    assert bundle.config.limits.max_files_per_lead == 5  # default


def test_text_simple_lookup(minimal_profile: Path):
    bundle = ContentService.load(minimal_profile)
    service = ContentService(bundle)
    assert service.text("main_menu.title") == "Меню"


def test_text_format_substitution(minimal_profile: Path):
    # Add a parametrized string
    (minimal_profile / "texts.yaml").write_text(
        "main_menu:\n"
        "  title: 'Привет, {name}!'\n"
        "statuses:\n"
        "  new: {label: 'Новая', emoji: '🆕'}\n"
        "priorities:\n"
        "  normal: {label: 'Обычный', emoji: '⚪'}\n"
        "close_reasons:\n"
        "  rejected: ['x']\n"
        "  done: ['x']\n"
        "  cancelled: ['x']\n",
        encoding="utf-8",
    )
    bundle = ContentService.load(minimal_profile)
    service = ContentService(bundle)
    assert service.text("main_menu.title", name="Иван") == "Привет, Иван!"


def test_text_missing_key_raises(minimal_profile: Path):
    bundle = ContentService.load(minimal_profile)
    service = ContentService(bundle)
    with pytest.raises(KeyError, match="missing.key"):
        service.text("missing.key")


def test_text_non_string_value_raises(minimal_profile: Path):
    bundle = ContentService.load(minimal_profile)
    service = ContentService(bundle)
    # 'main_menu' itself is a dict, not a string
    with pytest.raises(TypeError, match="main_menu"):
        service.text("main_menu")
