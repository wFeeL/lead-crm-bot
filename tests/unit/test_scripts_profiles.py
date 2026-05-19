"""Tests for the profile-management CLI (``python -m app.scripts.profiles``)."""

import shutil
from pathlib import Path

import pytest

from app.scripts import profiles as profiles_cli

CONTENT_ROOT = Path(__file__).resolve().parents[2] / "app" / "bot" / "content"


@pytest.fixture
def cleanup_test_profile():
    """Remove any leftover test profile from previous runs and after this test."""
    target = CONTENT_ROOT / "_pytest_tmp_profile"
    if target.exists():
        shutil.rmtree(target)
    yield target
    if target.exists():
        shutil.rmtree(target)


def test_list_includes_bundled_profiles(capsys):
    exit_code = profiles_cli.main(["list"])
    assert exit_code == 0
    out = capsys.readouterr().out
    for profile in ("default", "auto_service", "beauty_salon", "medical_clinic"):
        assert profile in out


def test_validate_known_profile(capsys):
    exit_code = profiles_cli.main(["validate", "auto_service"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "auto_service" in out


def test_validate_unknown_profile_returns_nonzero(capsys):
    exit_code = profiles_cli.main(["validate", "definitely_does_not_exist"])
    assert exit_code != 0


def test_new_profile_clones_and_loads(cleanup_test_profile, capsys):
    target = cleanup_test_profile
    exit_code = profiles_cli.main(["new", target.name, "--from", "auto_service"])
    assert exit_code == 0, capsys.readouterr().out
    assert target.is_dir()
    for fname in ("brand.yaml", "categories.yaml", "config.yaml", "faq.yaml", "texts.yaml"):
        assert (target / fname).exists(), f"missing {fname}"

    # Verifies that the clone loads through ContentService.
    validate_exit = profiles_cli.main(["validate", target.name])
    assert validate_exit == 0


def test_new_profile_refuses_to_overwrite(cleanup_test_profile, capsys):
    target = cleanup_test_profile
    target.mkdir()
    exit_code = profiles_cli.main(["new", target.name])
    assert exit_code != 0
    err = capsys.readouterr().err
    assert "already exists" in err


def test_new_profile_with_missing_source_fails(cleanup_test_profile, capsys):
    target = cleanup_test_profile
    exit_code = profiles_cli.main(["new", target.name, "--from", "does_not_exist"])
    assert exit_code != 0
    assert not target.exists()
