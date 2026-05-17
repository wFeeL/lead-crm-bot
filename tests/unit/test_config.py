from app.core.config import Settings


def test_admin_ids_parse_single_env_value(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_IDS", "416966184")

    settings = Settings(_env_file=None)

    assert settings.admin_ids == [416966184]


def test_admin_ids_parse_comma_separated_env_value(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_IDS", "1,2, 3")

    settings = Settings(_env_file=None)

    assert settings.admin_ids == [1, 2, 3]


def test_admin_ids_parse_json_env_value(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_IDS", "[1, 2, 3]")

    settings = Settings(_env_file=None)

    assert settings.admin_ids == [1, 2, 3]

