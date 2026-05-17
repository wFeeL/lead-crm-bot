# Step 1a — Migration 0003 (`category.is_internal`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute this plan task-by-task.

**Goal:** Добавить булево поле `lead_categories.is_internal` (default `false`) — отметка «системной» категории, скрытой от пользователей в `LEAD_CATEGORY`-экране. Это необходимая инфраструктура для Step 4 (категория `support` будет помечена internal).

**Architecture:** Альembic-миграция 0003, расширение модели `LeadCategory`, расширение `FormRepository.create_category`, расширение `ensure_seed_data` для переноса `CategoryConfig.internal` → БД, опциональный фильтр в `list_categories`.

**Tech Stack:** Alembic, SQLAlchemy 2 async, существующий `ContentBundle`.

**Spec sections:** `Миграции БД → 0003_add_category_is_internal.py`, `LEAD_CATEGORY (без internal-категорий)`.

---

## File Structure

**Create:**
- `migrations/versions/0003_add_category_is_internal.py`

**Modify:**
- `app/db/models/category.py` — добавить `is_internal: Mapped[bool]`
- `app/db/repositories/forms.py` — `create_category(*, is_internal=False)`, `list_categories(*, include_internal=False)`
- `app/services/forms.py` — `ensure_seed_data` устанавливает `is_internal=category_cfg.internal`
- `tests/integration/test_alembic_migrations.py` — тест что 0003 применяется
- `tests/integration/test_content_seed.py` — тест что seed устанавливает is_internal

---

## Task 1a.1 — Migration + Model + Repository

**Files:**
- Create: `migrations/versions/0003_add_category_is_internal.py`
- Modify: `app/db/models/category.py`
- Modify: `app/db/repositories/forms.py`
- Modify: `tests/integration/test_alembic_migrations.py`

### Step 1: Failing test (alembic migration applies cleanly)

In `tests/integration/test_alembic_migrations.py`, examine existing tests first. Add a new test that:
1. Runs migrations to head against an in-memory SQLite engine.
2. Inspects `lead_categories` table — `is_internal` column exists, `default false`.

If existing test pattern already validates "head", just add a column-existence assertion:

```python
@pytest.mark.asyncio
async def test_lead_categories_has_is_internal_column():
    """0003 migration adds is_internal column with default false."""
    from sqlalchemy import inspect, text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Run alembic upgrade head (existing helper or direct):
    from alembic.command import upgrade
    from alembic.config import Config

    sync_url = "sqlite:///:memory:"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", sync_url)
    upgrade(config, "head")
    # Now verify via inspect — separate engine for inspection since the in-memory DB is per-connection
    # Better: use the model class introspection
    from app.db.models.category import LeadCategory
    assert "is_internal" in LeadCategory.__table__.columns
    col = LeadCategory.__table__.columns["is_internal"]
    assert col.type.python_type is bool
    assert col.nullable is False
    assert col.default.arg is False
```

> Note: This test asserts model shape, not migration content. The existing test file likely has a different idiom — match it. If the existing test file uses a different pattern (e.g. apply migrations to a tmp sqlite file and inspect via async engine), follow that pattern instead.

### Step 2: Run, expect failure

`.venv/bin/pytest tests/integration/test_alembic_migrations.py -v`
Expected: AssertionError — `is_internal` not in `LeadCategory.__table__.columns`.

### Step 3: Create migration file

Create `migrations/versions/0003_add_category_is_internal.py`:

```python
"""add is_internal flag to lead_categories

Revision ID: 0003_add_category_is_internal
Revises: 0002_add_lead_submission_key
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_category_is_internal"
down_revision: str | Sequence[str] | None = "0002_add_lead_submission_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lead_categories",
        sa.Column(
            "is_internal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("lead_categories", "is_internal")
```

### Step 4: Update model

In `app/db/models/category.py`, add to `LeadCategory` class after `sort_order`:

```python
    is_internal: Mapped[bool] = mapped_column(default=False, nullable=False)
```

### Step 5: Update repository

In `app/db/repositories/forms.py`:

1. `create_category` — add `is_internal: bool = False` parameter:

```python
    async def create_category(
        self,
        *,
        slug: str,
        title: str,
        description: str | None,
        sort_order: int,
        is_internal: bool = False,
    ) -> LeadCategory:
        category = LeadCategory(
            slug=slug,
            title=title,
            description=description,
            sort_order=sort_order,
            is_active=True,
            is_internal=is_internal,
        )
        self.session.add(category)
        await self.session.flush()
        return category
```

2. `list_categories` — add `include_internal: bool = False` filter:

```python
    async def list_categories(
        self,
        *,
        active_only: bool = True,
        include_internal: bool = False,
    ) -> list[LeadCategory]:
        stmt = select(LeadCategory).order_by(LeadCategory.sort_order, LeadCategory.id)
        if active_only:
            stmt = stmt.where(LeadCategory.is_active.is_(True))
        if not include_internal:
            stmt = stmt.where(LeadCategory.is_internal.is_(False))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

### Step 6: Run tests

```
.venv/bin/pytest tests/integration/test_alembic_migrations.py -v
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format migrations/versions/0003_add_category_is_internal.py app/db/models/category.py app/db/repositories/forms.py tests/integration/test_alembic_migrations.py
```

All green. Note: existing integration tests using `list_categories` may need attention — by default they now exclude internal categories. Since no existing data has `is_internal=true`, behavior is unchanged for them.

### Step 7: Commit

```bash
git add migrations/versions/0003_add_category_is_internal.py app/db/models/category.py app/db/repositories/forms.py tests/integration/test_alembic_migrations.py
git commit -m "feat(db): migration 0003 — add is_internal to lead_categories"
```

---

## Task 1a.2 — Update `ensure_seed_data` to set `is_internal`

**Files:**
- Modify: `app/services/forms.py`
- Modify: `tests/integration/test_content_seed.py`

### Step 1: Failing test

Append to `tests/integration/test_content_seed.py`:

```python
@pytest.mark.asyncio
async def test_ensure_seed_data_sets_is_internal_from_yaml(session: AsyncSession, tmp_path: Path):
    """seed honors CategoryConfig.internal flag."""
    profile = tmp_path / "internal_profile"
    profile.mkdir()
    # Reuse minimum scaffolding by writing only the categories.yaml override + symlink to default
    import shutil
    for fname in ("brand.yaml", "texts.yaml", "faq.yaml", "config.yaml"):
        shutil.copy(_CONTENT_DIR / fname, profile / fname)
    (profile / "categories.yaml").write_text(
        "- slug: public_cat\n"
        "  title: Public\n"
        "  description: Visible to clients\n"
        "  questions:\n"
        "    - {key: q1, text: 'Q1', type: text, required: true}\n"
        "- slug: secret_cat\n"
        "  title: Secret\n"
        "  description: Hidden\n"
        "  internal: true\n"
        "  questions:\n"
        "    - {key: q1, text: 'Q1', type: text, required: true}\n",
        encoding="utf-8",
    )
    bundle = ContentService.load(profile)
    await ensure_seed_data(session, bundle)
    await session.commit()

    repo = FormRepository(session)
    public = await repo.get_category_by_slug("public_cat")
    secret = await repo.get_category_by_slug("secret_cat")
    assert public is not None and public.is_internal is False
    assert secret is not None and secret.is_internal is True

    # list_categories without include_internal hides secret_cat
    visible = await repo.list_categories()
    visible_slugs = {c.slug for c in visible}
    assert "public_cat" in visible_slugs
    assert "secret_cat" not in visible_slugs

    # list_categories with include_internal=True shows both
    all_cats = await repo.list_categories(include_internal=True)
    all_slugs = {c.slug for c in all_cats}
    assert "public_cat" in all_slugs
    assert "secret_cat" in all_slugs
```

Make sure existing imports include `from pathlib import Path` and pytest fixtures are usable.

### Step 2: Run, expect failure

`.venv/bin/pytest tests/integration/test_content_seed.py::test_ensure_seed_data_sets_is_internal_from_yaml -v`
Expected: `secret.is_internal` is False (not set from YAML).

### Step 3: Update `ensure_seed_data`

In `app/services/forms.py`, in the `create_category` call inside `ensure_seed_data`, pass `is_internal=category_cfg.internal`:

```python
        if category is None:
            category = await repository.create_category(
                slug=category_cfg.slug,
                title=category_cfg.title,
                description=category_cfg.description,
                sort_order=index,
                is_internal=category_cfg.internal,
            )
```

> Note: this only sets `is_internal` on category **creation**. If a category exists and its `internal` flag changes in YAML, this code does NOT update the existing row. That's intentional for Step 1a — seed remains idempotent only for the "category exists" case. Step 4 (where `support` is introduced) will create the category fresh.

### Step 4: Run tests

```
.venv/bin/pytest tests/integration/test_content_seed.py -v
.venv/bin/pytest -q
.venv/bin/ruff check .
```

All green.

### Step 5: Commit

```bash
git add app/services/forms.py tests/integration/test_content_seed.py
git commit -m "feat(content): seed honors CategoryConfig.internal flag"
```

---

## Task 1a.3 — Document `list_categories(include_internal=...)` use

This task is a hold-over documentation moment, NOT a code change. We update the plan and ensure no caller of `list_categories` in the current codebase accidentally needs `include_internal=True` for admin views.

### Step 1: Audit callers

Run:
```bash
grep -rn "list_categories" app/ tests/ | grep -v "\.venv"
```

For each caller:
- Client-facing path (selecting category to create a lead) → keep default (`include_internal=False`).
- Admin-facing path (listing categories in admin reports/UI) → may need `include_internal=True`.

In Step 0/1a, there are likely zero admin callers of `list_categories`. Most calls are from `tests/integration/test_lead_service.py` and `test_admin_api.py` — for these, default is fine (no internal categories in default profile).

If audit confirms no caller needs `include_internal=True` at the moment, NO commit is needed. Otherwise update specific callers and commit.

### Step 2: Verify

If no changes needed, skip commit. Otherwise commit per audit findings with message:

```
chore(forms): explicitly pass include_internal at admin call sites
```

---

## Step 1a Completion Checklist

- [ ] `.venv/bin/pytest -q` — green.
- [ ] `.venv/bin/ruff check .` — green.
- [ ] Migration 0003 exists and links to `0002_add_lead_submission_key`.
- [ ] `LeadCategory.is_internal` exists with `default=False, nullable=False`.
- [ ] `FormRepository.create_category(is_internal=False)` works.
- [ ] `FormRepository.list_categories(include_internal=False)` filters internal out by default.
- [ ] `ensure_seed_data` passes `category_cfg.internal` on create.
- [ ] Audit of `list_categories` callers complete.

Then tag:

```bash
git tag stage1-step-1a-cat-internal
```

## Out of scope

- Filtering `is_internal` from any UI screen — happens in Step 3 (`LEAD_CATEGORY`).
- `support` category itself — added to YAML in Step 4.
- Refreshing `is_internal` on existing categories during seed — deferred (would require a separate update path; not needed until someone toggles internal in production).
