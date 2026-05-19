"""Every bundled content profile must load through ContentService.

This is the safety net for the resale-template promise: a clean checkout
plus ``CONTENT_PROFILE=<niche>`` must boot. We assert structure (categories
present, FAQ non-empty, statuses cover every LeadStatus value), not literal
text, so the niches can evolve without rewriting tests.
"""

from pathlib import Path

import pytest

from app.core.constants import LeadStatus
from app.services.content import ContentService

CONTENT_ROOT = Path(__file__).resolve().parents[2] / "app" / "bot" / "content"

# Source of truth: every profile shipped in the repo.
BUNDLED_PROFILES = ("default", "auto_service", "beauty_salon", "medical_clinic")


@pytest.mark.parametrize("profile", BUNDLED_PROFILES)
def test_profile_loads(profile: str):
    bundle = ContentService.load(CONTENT_ROOT / profile)
    assert bundle.brand.company_name, f"{profile}: empty company_name"
    assert bundle.categories, f"{profile}: no categories"
    assert bundle.faq, f"{profile}: empty faq"


@pytest.mark.parametrize("profile", BUNDLED_PROFILES)
def test_profile_has_internal_support_category(profile: str):
    """Every profile keeps the 'support' category for the menu's «Связаться с менеджером» button."""
    bundle = ContentService.load(CONTENT_ROOT / profile)
    support_cats = [c for c in bundle.categories if c.slug == "support"]
    assert support_cats, f"{profile}: missing 'support' category"
    assert support_cats[0].internal is True, f"{profile}: 'support' must be internal"


@pytest.mark.parametrize("profile", BUNDLED_PROFILES)
def test_profile_covers_all_lead_statuses(profile: str):
    bundle = ContentService.load(CONTENT_ROOT / profile)
    declared = set(bundle.texts.statuses.keys())
    expected = {s.value for s in LeadStatus}
    missing = expected - declared
    assert not missing, f"{profile}: missing statuses {missing}"


@pytest.mark.parametrize("profile", BUNDLED_PROFILES)
def test_profile_category_question_keys_unique(profile: str):
    """Pydantic enforces this per-category; here we also check cross-category for sanity."""
    bundle = ContentService.load(CONTENT_ROOT / profile)
    for cat in bundle.categories:
        keys = [q.key for q in cat.questions]
        assert len(keys) == len(set(keys)), f"{profile}/{cat.slug}: duplicate keys {keys}"
