# Step 0 — Content Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вынести все клиент-специфичные данные (тексты, бренд, FAQ, категории, лимиты, статусные/приоритетные лейблы) из Python-кода в YAML-профили и подключить их через `ContentService`. После Step 0 бот работает идентично сейчасу — но базис для всех последующих шагов готов.

**Architecture:** Pydantic-валидируемые YAML-конфиги в `app/bot/content/<profile>/`. `ContentService` загружает один профиль при старте (singleton в `app.state` для FastAPI и в `dispatcher.workflow_data` для aiogram). Текстовый API: `content.text("dotted.path.key", **kwargs)` → форматированная строка с подстановками. Существующие тексты и категории мигрируются в `default/` профиль без изменения поведения.

**Tech Stack:** PyYAML 6+, Pydantic 2, существующий pydantic-settings.

**Spec sections this plan implements:**
- `Конфигурируемость (Content Layer)` (вся секция)
- `План имплементации → Шаг 0. Content layer`

---

## File Structure

**Create:**
- `app/schemas/content.py` — Pydantic-схемы профиля (BrandConfig, TextsConfig, FaqEntry, CategoryConfig, QuestionConfig, AppContentConfig, ContentBundle)
- `app/services/content.py` — `ContentService` с `load(profile_dir)` и `text(key, **kwargs)`
- `app/bot/content/__init__.py` — пустой
- `app/bot/content/default/brand.yaml`
- `app/bot/content/default/texts.yaml`
- `app/bot/content/default/faq.yaml`
- `app/bot/content/default/categories.yaml`
- `app/bot/content/default/config.yaml`
- `tests/unit/test_content_schemas.py`
- `tests/unit/test_content_service.py`
- `tests/integration/test_content_seed.py`

**Modify:**
- `requirements.txt` — добавить `PyYAML>=6.0`
- `app/core/config.py:Settings` — добавить `content_profile: str = "default"`
- `.env.example` — добавить `CONTENT_PROFILE=default`
- `app/services/forms.py` — `ensure_seed_data(session, content: ContentBundle)`: убираем `LEAD_FORM_DEFINITIONS`, читаем из `content.categories`
- `app/seed.py` — загружает content перед `ensure_seed_data`
- `app/bot_main.py` — загружает content при старте, кладёт в `dispatcher.workflow_data`
- `app/main.py` — загружает content при startup, кладёт в `app.state.content`
- `app/db/repositories/forms.py:create_form` (если потребуется) — нужна проверка

**Read-only (для миграции):** `app/bot/texts/user.py`, `app/core/constants.py:STATUS_TITLES,STATUS_EMOJIS`, `app/services/forms.py:LEAD_FORM_DEFINITIONS`.

**Untouched (всё остальное):** routers, handlers, FSM — НЕ трогаем в этом step.

---

## Task 0.1: Add PyYAML dependency

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt` (нет, PyYAML на проде нужен)

- [ ] **Step 1: Add dependency**

Open `requirements.txt`. Между `python-multipart>=0.0.9` и `redis>=5.0` добавить новую строку (или просто в конец отсортированного списка, по позиции в алфавите):

```
PyYAML>=6.0
```

Файл целиком после правки должен содержать (порядок строк сохраняется, добавляем одну):

```
aiogram>=3.20
alembic>=1.13
apscheduler>=3.10
asyncpg>=0.29
fastapi>=0.115
orjson>=3.10
pydantic>=2.8
pydantic-settings>=2.4
python-dotenv>=1.0
python-multipart>=0.0.9
PyYAML>=6.0
redis>=5.0
sqlalchemy[asyncio]>=2.0
uvicorn[standard]>=0.30
```

- [ ] **Step 2: Install**

Run: `.venv/bin/pip install -r requirements.txt`
Expected: `Successfully installed PyYAML-X.Y.Z` (либо `Requirement already satisfied`).

- [ ] **Step 3: Verify**

Run: `.venv/bin/python -c "import yaml; print(yaml.__version__)"`
Expected: prints version `6.0` or higher.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add PyYAML dependency for content layer"
```

---

## Task 0.2: Pydantic schemas — BrandConfig

**Files:**
- Create: `app/schemas/content.py`
- Test: `tests/unit/test_content_schemas.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_content_schemas.py`:

```python
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
```

- [ ] **Step 2: Run test and verify it fails**

Run: `.venv/bin/pytest tests/unit/test_content_schemas.py -v`
Expected: `ImportError: cannot import name 'BrandConfig' from 'app.schemas.content'` (or similar — module doesn't exist).

- [ ] **Step 3: Write minimal implementation**

Create `app/schemas/content.py`:

```python
from pydantic import BaseModel, ConfigDict, Field


class BrandConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str
    manager_username: str
    manager_phone: str
    working_hours: str
    welcome_intro: str
    support_intro: str
    eta_response_hours: int = Field(ge=0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_content_schemas.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/content.py tests/unit/test_content_schemas.py
git commit -m "feat(content): add BrandConfig schema"
```

---

## Task 0.3: Pydantic schemas — FAQ, Question, Category

**Files:**
- Modify: `app/schemas/content.py`
- Modify: `tests/unit/test_content_schemas.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/unit/test_content_schemas.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `.venv/bin/pytest tests/unit/test_content_schemas.py -v`
Expected: ImportError for `CategoryConfig`, `FaqEntry`, `QuestionConfig`.

- [ ] **Step 3: Implement**

Append to `app/schemas/content.py`:

```python
from typing import Self

from pydantic import field_validator, model_validator

from app.core.constants import QuestionType


class FaqEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str
    a: str


class QuestionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    text: str
    type: QuestionType
    required: bool = False
    options: list[str] | None = None


class CategoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    title: str
    description: str
    internal: bool = False
    questions: list[QuestionConfig]

    @model_validator(mode="after")
    def _unique_question_keys(self) -> Self:
        seen: set[str] = set()
        for q in self.questions:
            if q.key in seen:
                raise ValueError(f"duplicate question key {q.key!r} in category {self.slug!r}")
            seen.add(q.key)
        return self
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `.venv/bin/pytest tests/unit/test_content_schemas.py -v`
Expected: all tests pass (3 from Task 0.2 + 7 new = 10).

- [ ] **Step 5: Commit**

```bash
git add app/schemas/content.py tests/unit/test_content_schemas.py
git commit -m "feat(content): add FaqEntry, QuestionConfig, CategoryConfig schemas"
```

---

## Task 0.4: Pydantic schemas — TextsConfig, AppContentConfig, ContentBundle

**Files:**
- Modify: `app/schemas/content.py`
- Modify: `tests/unit/test_content_schemas.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/unit/test_content_schemas.py`:

```python
from app.schemas.content import (
    AppContentConfig,
    ContentBundle,
    StatusEntry,
    PriorityEntry,
    CloseReasons,
    TextsConfig,
)


def test_texts_config_minimal():
    texts = TextsConfig.model_validate({
        "main_menu": {"title": "Hi"},
        "statuses": {
            "new": {"label": "Новая", "emoji": "🆕"},
            "in_progress": {"label": "В работе", "emoji": "🛠"},
        },
        "priorities": {
            "normal": {"label": "Обычный", "emoji": "⚪"},
        },
        "close_reasons": {
            "rejected": ["Спам"],
            "done": ["Готово"],
            "cancelled": ["Передумал"],
        },
    })
    assert texts.statuses["new"].label == "Новая"
    assert texts.priorities["normal"].emoji == "⚪"
    assert texts.close_reasons.rejected == ["Спам"]


def test_status_entry_emoji_required():
    with pytest.raises(ValidationError):
        StatusEntry.model_validate({"label": "X"})


def test_app_content_config_defaults():
    cfg = AppContentConfig.model_validate({})
    assert cfg.limits.max_files_per_lead > 0
    assert cfg.ui.page_size_my_leads == 5


def test_content_bundle_assembles():
    bundle = ContentBundle(
        brand=BrandConfig(
            company_name="Acme",
            manager_username="@a",
            manager_phone="+7",
            working_hours="x",
            welcome_intro="x",
            support_intro="x",
            eta_response_hours=24,
        ),
        texts=TextsConfig(
            main_menu={"title": "Hi"},
            statuses={"new": StatusEntry(label="Новая", emoji="🆕")},
            priorities={"normal": PriorityEntry(label="Обычный", emoji="⚪")},
            close_reasons=CloseReasons(rejected=["x"], done=["x"], cancelled=["x"]),
        ),
        faq=[FaqEntry(q="Q", a="A")],
        categories=[CategoryConfig(
            slug="x", title="X", description="X",
            questions=[QuestionConfig(key="k", text="t", type=QuestionType.TEXT)],
        )],
        config=AppContentConfig(),
    )
    assert bundle.brand.company_name == "Acme"
    assert len(bundle.faq) == 1
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/unit/test_content_schemas.py -v`
Expected: ImportError on new symbols.

- [ ] **Step 3: Implement**

Append to `app/schemas/content.py`:

```python
from typing import Any


class StatusEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    emoji: str


class PriorityEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    emoji: str


class CloseReasons(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rejected: list[str] = Field(default_factory=list)
    done: list[str] = Field(default_factory=list)
    cancelled: list[str] = Field(default_factory=list)


class TextsConfig(BaseModel):
    """Nested dict of UI text templates. Loosely typed below `main_menu` etc."""

    model_config = ConfigDict(extra="allow")

    main_menu: dict[str, Any] = Field(default_factory=dict)
    statuses: dict[str, StatusEntry] = Field(default_factory=dict)
    priorities: dict[str, PriorityEntry] = Field(default_factory=dict)
    close_reasons: CloseReasons = Field(default_factory=CloseReasons)


class LimitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_leads_per_10_minutes: int = Field(default=3, ge=0)
    max_files_per_lead: int = Field(default=5, ge=0)
    max_file_size_mb: int = Field(default=20, ge=0)


class UiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_size_my_leads: int = Field(default=5, ge=1)
    page_size_admin: int = Field(default=5, ge=1)


class AppContentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    ui: UiConfig = Field(default_factory=UiConfig)


class ContentBundle(BaseModel):
    """Loaded content profile. Used as a value object after ContentService.load()."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    brand: BrandConfig
    texts: TextsConfig
    faq: list[FaqEntry]
    categories: list[CategoryConfig]
    config: AppContentConfig
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/test_content_schemas.py -v`
Expected: all tests pass (10 + 4 new = 14).

- [ ] **Step 5: Commit**

```bash
git add app/schemas/content.py tests/unit/test_content_schemas.py
git commit -m "feat(content): add TextsConfig, AppContentConfig, ContentBundle"
```

---

## Task 0.5: ContentService.load() — happy path

**Files:**
- Create: `app/services/content.py`
- Create: `tests/unit/test_content_service.py`

- [ ] **Step 1: Failing test**

Create `tests/unit/test_content_service.py`:

```python
from pathlib import Path

import pytest

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
```

- [ ] **Step 2: Run test, expect failure**

Run: `.venv/bin/pytest tests/unit/test_content_service.py -v`
Expected: ImportError for `ContentService`.

- [ ] **Step 3: Implement**

Create `app/services/content.py`:

```python
from pathlib import Path
from typing import Any

import yaml

from app.schemas.content import (
    AppContentConfig,
    BrandConfig,
    CategoryConfig,
    ContentBundle,
    FaqEntry,
    TextsConfig,
)


class ContentService:
    """Loads and serves a content profile (brand, texts, faq, categories, config)."""

    def __init__(self, bundle: ContentBundle) -> None:
        self._bundle = bundle

    @property
    def bundle(self) -> ContentBundle:
        return self._bundle

    @property
    def brand(self) -> BrandConfig:
        return self._bundle.brand

    @property
    def texts(self) -> TextsConfig:
        return self._bundle.texts

    @property
    def faq(self) -> list[FaqEntry]:
        return self._bundle.faq

    @property
    def categories(self) -> list[CategoryConfig]:
        return self._bundle.categories

    @property
    def config(self) -> AppContentConfig:
        return self._bundle.config

    @classmethod
    def load(cls, profile_dir: Path) -> ContentBundle:
        """Load all YAML files from a profile directory and validate them."""
        brand_data = _read_yaml(profile_dir / "brand.yaml")
        texts_data = _read_yaml(profile_dir / "texts.yaml")
        faq_data = _read_yaml(profile_dir / "faq.yaml")
        categories_data = _read_yaml(profile_dir / "categories.yaml")
        config_data = _read_yaml(profile_dir / "config.yaml")

        return ContentBundle(
            brand=BrandConfig.model_validate(brand_data),
            texts=TextsConfig.model_validate(texts_data),
            faq=[FaqEntry.model_validate(item) for item in faq_data],
            categories=[CategoryConfig.model_validate(item) for item in categories_data],
            config=AppContentConfig.model_validate(config_data or {}),
        )


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Content file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
```

- [ ] **Step 4: Run test**

Run: `.venv/bin/pytest tests/unit/test_content_service.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/content.py tests/unit/test_content_service.py
git commit -m "feat(content): ContentService.load() reads YAML profile"
```

---

## Task 0.6: ContentService.load() — error paths

**Files:**
- Modify: `tests/unit/test_content_service.py`

- [ ] **Step 1: Failing tests**

Append to `tests/unit/test_content_service.py`:

```python
def test_load_missing_brand_file(tmp_path: Path):
    profile = tmp_path / "broken"
    profile.mkdir()
    with pytest.raises(FileNotFoundError, match="brand.yaml"):
        ContentService.load(profile)


def test_load_invalid_yaml(tmp_path: Path, minimal_profile: Path):
    (minimal_profile / "brand.yaml").write_text(
        "company_name: Acme\n[bad yaml",
        encoding="utf-8",
    )
    with pytest.raises(yaml.YAMLError):
        ContentService.load(minimal_profile)


def test_load_invalid_schema(tmp_path: Path, minimal_profile: Path):
    (minimal_profile / "brand.yaml").write_text(
        "company_name: Acme\n",  # missing required fields
        encoding="utf-8",
    )
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ContentService.load(minimal_profile)
```

Add `import yaml` to the top of the file.

- [ ] **Step 2: Run tests**

Run: `.venv/bin/pytest tests/unit/test_content_service.py -v`
Expected: all 4 pass (no implementation change needed — happy path code already raises on these).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_content_service.py
git commit -m "test(content): cover load error paths"
```

---

## Task 0.7: ContentService.text() — dotted key lookup with format()

**Files:**
- Modify: `app/services/content.py`
- Modify: `tests/unit/test_content_service.py`

- [ ] **Step 1: Failing tests**

Append to `tests/unit/test_content_service.py`:

```python
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
```

- [ ] **Step 2: Run tests, expect failures**

Run: `.venv/bin/pytest tests/unit/test_content_service.py -v`
Expected: 4 new tests fail with `AttributeError: 'ContentService' object has no attribute 'text'`.

- [ ] **Step 3: Implement**

In `app/services/content.py`, add a `text` method to `ContentService`:

```python
    def text(self, key: str, **kwargs: object) -> str:
        """Look up a text template by dotted path and apply str.format() with kwargs.

        Falls back to KeyError when the path does not resolve and TypeError when
        the resolved value is not a string template.
        """
        node: object = self._bundle.texts.model_dump()
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                raise KeyError(key)
            node = node[part]
        if not isinstance(node, str):
            raise TypeError(f"text key {key!r} resolves to non-string {type(node).__name__}")
        return node.format(**kwargs) if kwargs else node
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/test_content_service.py -v`
Expected: all 7 pass.

- [ ] **Step 5: Commit**

```bash
git add app/services/content.py tests/unit/test_content_service.py
git commit -m "feat(content): ContentService.text() dotted-path lookup"
```

---

## Task 0.8: default/brand.yaml + default/config.yaml

**Files:**
- Create: `app/bot/content/__init__.py`
- Create: `app/bot/content/default/brand.yaml`
- Create: `app/bot/content/default/config.yaml`

- [ ] **Step 1: Create package marker**

Create empty file `app/bot/content/__init__.py`:

```python
```

- [ ] **Step 2: Create `default/brand.yaml`**

Content:

```yaml
company_name: "LeadBot Demo"
manager_username: "@manager_demo"
manager_phone: "+7 (000) 000-00-00"
working_hours: "Пн-Пт 09:00–21:00"
welcome_intro: "Здесь вы можете оставить заявку — мы свяжемся в течение рабочего дня."
support_intro: "Опишите ваш вопрос — менеджер ответит лично."
eta_response_hours: 24
```

- [ ] **Step 3: Create `default/config.yaml`**

Content:

```yaml
limits:
  max_leads_per_10_minutes: 3
  max_files_per_lead: 5
  max_file_size_mb: 20
ui:
  page_size_my_leads: 5
  page_size_admin: 5
```

- [ ] **Step 4: Verify YAML is parseable**

Run:
```bash
.venv/bin/python -c "
from pathlib import Path
import yaml
for p in ['app/bot/content/default/brand.yaml', 'app/bot/content/default/config.yaml']:
    print(p, '->', yaml.safe_load(Path(p).read_text(encoding='utf-8')))
"
```
Expected: prints two dicts, no exceptions.

- [ ] **Step 5: Commit**

```bash
git add app/bot/content/__init__.py app/bot/content/default/brand.yaml app/bot/content/default/config.yaml
git commit -m "feat(content): default profile brand and config yaml"
```

---

## Task 0.9: default/texts.yaml — migrate existing strings

**Files:**
- Create: `app/bot/content/default/texts.yaml`

Reference: existing strings live in `app/bot/texts/user.py` (`START_TEXT`, `SUPPORT_TEXT`, `FAQ_TEXT`) and `app/core/constants.py` (`STATUS_TITLES`, `STATUS_EMOJIS`). We migrate them verbatim so behavior is identical after Step 0.

- [ ] **Step 1: Create `default/texts.yaml`**

Content:

```yaml
main_menu:
  title: "Выберите действие."

support:
  intro: "Напишите менеджеру или оставьте заявку, чтобы мы связались с вами."

faq:
  intro: "FAQ пока минимальный: заполните заявку, и менеджер ответит в ближайшее время."

statuses:
  new:         { label: "Новая",        emoji: "🆕" }
  contacted:   { label: "Связались",    emoji: "📞" }
  in_progress: { label: "В работе",     emoji: "🛠" }
  waiting:     { label: "Ждем клиента", emoji: "⏳" }
  done:        { label: "Завершена",    emoji: "✅" }
  rejected:    { label: "Отклонена",    emoji: "❌" }
  cancelled:   { label: "Отменена",     emoji: "🚫" }

priorities:
  low:    { label: "Низкий",   emoji: "🔵" }
  normal: { label: "Обычный",  emoji: "⚪" }
  high:   { label: "Высокий",  emoji: "🟠" }
  urgent: { label: "Срочный",  emoji: "🔴" }

close_reasons:
  rejected:
    - "Спам / тестовая заявка"
    - "Дубликат существующей"
    - "Нет требуемой услуги"
    - "Клиент не отвечает"
    - "Своя причина"
  done:
    - "Выполнено"
    - "Передано мастеру"
    - "Своя причина"
  cancelled:
    - "Передумал"
    - "Решил вопрос сам"
    - "Слишком долго ждать"
    - "Своя причина"
```

> Note: `contacted` status is included now even though the DB enum does not yet contain it. Step 4a migration adds it. Until then the bot never references `contacted` at runtime, so its presence in YAML is harmless.

- [ ] **Step 2: Validate**

Run:
```bash
.venv/bin/python -c "
from pathlib import Path
from app.services.content import ContentService
# Only validates texts.yaml schema, not full profile
from app.schemas.content import TextsConfig
import yaml
data = yaml.safe_load(Path('app/bot/content/default/texts.yaml').read_text(encoding='utf-8'))
TextsConfig.model_validate(data)
print('OK')
"
```
Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add app/bot/content/default/texts.yaml
git commit -m "feat(content): default profile texts yaml (migrated from constants.py and texts/user.py)"
```

---

## Task 0.10: default/faq.yaml

**Files:**
- Create: `app/bot/content/default/faq.yaml`

- [ ] **Step 1: Create file**

Content:

```yaml
- q: "Сколько ждать ответа?"
  a: "В рабочее время — до 30 минут. После 21:00 — на следующий день."

- q: "Можно ли отменить заявку?"
  a: "Да, пока статус «Новая». В разделе «Мои заявки» откройте карточку и нажмите «🚫 Отменить заявку»."

- q: "Как прикрепить файл или фото?"
  a: "На шаге загрузки файлов отправьте фото или документ как обычное вложение в Telegram. Максимум 5 файлов на заявку."

- q: "Что значит «Связались»?"
  a: "Менеджер связался с вами и уточняет детали. Когда работа начнётся, статус сменится на «В работе»."

- q: "Сохранятся ли мои данные?"
  a: "Да. Все заявки видны в разделе «Мои заявки» в этом боте."
```

- [ ] **Step 2: Validate**

Run:
```bash
.venv/bin/python -c "
from pathlib import Path
import yaml
from app.schemas.content import FaqEntry
data = yaml.safe_load(Path('app/bot/content/default/faq.yaml').read_text(encoding='utf-8'))
for item in data: FaqEntry.model_validate(item)
print('OK', len(data), 'entries')
"
```
Expected: `OK 5 entries`.

- [ ] **Step 3: Commit**

```bash
git add app/bot/content/default/faq.yaml
git commit -m "feat(content): default profile faq yaml"
```

---

## Task 0.11: default/categories.yaml — migrate LEAD_FORM_DEFINITIONS

**Files:**
- Create: `app/bot/content/default/categories.yaml`

Reference: `app/services/forms.py:LEAD_FORM_DEFINITIONS` has 4 categories — `telegram_bot`, `website`, `consultation`, `other`. Migrate verbatim.

- [ ] **Step 1: Create file**

Content:

```yaml
- slug: telegram_bot
  title: "Разработка бота"
  description: "Telegram-боты и автоматизация"
  questions:
    - key: goal
      text: "Что должен делать бот?"
      type: long_text
      required: true
    - key: deadline
      text: "Какие сроки?"
      type: text
      required: false
    - key: budget
      text: "Какой ориентировочный бюджет?"
      type: text
      required: false

- slug: website
  title: "Сайт / backend"
  description: "Сайты, API и backend-разработка"
  questions:
    - key: project_type
      text: "Какой проект нужен?"
      type: text
      required: true
    - key: features
      text: "Какие основные функции нужны?"
      type: long_text
      required: true
    - key: deadline
      text: "Есть ли дедлайн?"
      type: text
      required: false

- slug: consultation
  title: "Консультация"
  description: "Разбор задачи и техническая консультация"
  questions:
    - key: topic
      text: "По какой теме нужна консультация?"
      type: text
      required: true
    - key: context
      text: "Опишите контекст задачи."
      type: long_text
      required: false

- slug: other
  title: "Другое"
  description: "Любая другая заявка"
  questions:
    - key: description
      text: "Опишите задачу."
      type: long_text
      required: true
```

- [ ] **Step 2: Validate**

Run:
```bash
.venv/bin/python -c "
from pathlib import Path
import yaml
from app.schemas.content import CategoryConfig
data = yaml.safe_load(Path('app/bot/content/default/categories.yaml').read_text(encoding='utf-8'))
for item in data: CategoryConfig.model_validate(item)
print('OK', len(data), 'categories')
"
```
Expected: `OK 4 categories`.

- [ ] **Step 3: End-to-end load**

Run:
```bash
.venv/bin/python -c "
from pathlib import Path
from app.services.content import ContentService
bundle = ContentService.load(Path('app/bot/content/default'))
print('brand:', bundle.brand.company_name)
print('faq:', len(bundle.faq))
print('cats:', [c.slug for c in bundle.categories])
print('max_files:', bundle.config.limits.max_files_per_lead)
"
```
Expected:
```
brand: LeadBot Demo
faq: 5
cats: ['telegram_bot', 'website', 'consultation', 'other']
max_files: 5
```

- [ ] **Step 4: Commit**

```bash
git add app/bot/content/default/categories.yaml
git commit -m "feat(content): default profile categories yaml (migrated from forms.py)"
```

---

## Task 0.12: Settings.content_profile + .env.example

**Files:**
- Modify: `app/core/config.py`
- Modify: `.env.example`
- Modify: `tests/unit/test_config.py`

- [ ] **Step 1: Failing test**

Append to `tests/unit/test_config.py`:

```python
from app.core.config import Settings


def test_content_profile_default(monkeypatch):
    monkeypatch.delenv("CONTENT_PROFILE", raising=False)
    s = Settings(_env_file=None)  # ignore .env for this test
    assert s.content_profile == "default"


def test_content_profile_from_env(monkeypatch):
    monkeypatch.setenv("CONTENT_PROFILE", "acme")
    s = Settings(_env_file=None)
    assert s.content_profile == "acme"
```

> `_env_file=None` is a pydantic-settings v2 mechanism to bypass `.env` loading for a single instantiation. We avoid `get_settings()` because it's cached via `lru_cache` and would return a stale value between tests. If the existing tests in `test_config.py` use a different pattern (e.g. `get_settings.cache_clear()`), keep it consistent.

- [ ] **Step 2: Run, expect failure**

Run: `.venv/bin/pytest tests/unit/test_config.py -v -k content_profile`
Expected: AttributeError — `Settings` object has no `content_profile`.

- [ ] **Step 3: Add field to Settings**

In `app/core/config.py`, inside the `Settings` class, after `sentry_dsn: str | None = None` add:

```python
    content_profile: str = "default"
```

- [ ] **Step 4: Add to .env.example**

Append to `.env.example`:

```
# Content profile directory (under app/bot/content/<name>)
CONTENT_PROFILE=default
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/unit/test_config.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/core/config.py .env.example tests/unit/test_config.py
git commit -m "feat(content): add CONTENT_PROFILE setting"
```

---

## Task 0.13: ensure_seed_data reads from ContentBundle

**Files:**
- Modify: `app/services/forms.py`
- Modify: `app/seed.py`
- Create: `tests/integration/test_content_seed.py`

This task changes the seed pipeline to consume `ContentBundle` instead of the hardcoded `LEAD_FORM_DEFINITIONS`. The constant stays for now (deleted in Step 6) but is unused after this task.

- [ ] **Step 1: Failing integration test**

Create `tests/integration/test_content_seed.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.forms import FormRepository
from app.services.content import ContentService
from app.services.forms import ensure_seed_data


@pytest.mark.asyncio
async def test_ensure_seed_data_from_default_profile(db_session: AsyncSession):
    bundle = ContentService.load(Path("app/bot/content/default"))
    await ensure_seed_data(db_session, bundle)
    await db_session.commit()

    repo = FormRepository(db_session)
    categories = await repo.list_categories()
    slugs = {c.slug for c in categories}
    assert slugs == {"telegram_bot", "website", "consultation", "other"}

    tg = await repo.get_category_by_slug("telegram_bot")
    assert tg is not None
    form = await repo.get_active_form(tg.id)
    assert form is not None
    # Form has 3 questions for telegram_bot per categories.yaml
    assert len(form.questions) == 3
    assert form.questions[0].key == "goal"


@pytest.mark.asyncio
async def test_ensure_seed_data_is_idempotent(db_session: AsyncSession):
    bundle = ContentService.load(Path("app/bot/content/default"))
    await ensure_seed_data(db_session, bundle)
    await db_session.commit()
    await ensure_seed_data(db_session, bundle)
    await db_session.commit()

    repo = FormRepository(db_session)
    categories = await repo.list_categories()
    # Still exactly 4 — no duplicates
    assert len(categories) == 4
```

> `db_session` fixture must exist in `tests/conftest.py`. Check `tests/conftest.py` before writing this test. If the fixture has a different name (e.g. `session`), use that. Use the integration-test session pattern already used by `tests/integration/test_lead_service.py`.

- [ ] **Step 2: Run, expect failure**

Run: `.venv/bin/pytest tests/integration/test_content_seed.py -v`
Expected: `TypeError: ensure_seed_data() takes 1 positional argument but 2 were given`.

- [ ] **Step 3: Update `ensure_seed_data` signature**

Open `app/services/forms.py`. Keep the existing `LEAD_FORM_DEFINITIONS` constant **untouched** (do not modify, do not delete — it's still imported by some existing tests until Step 6).

Replace only the `ensure_seed_data` function and add the `ContentBundle` import.

Add to imports (after `from app.db.repositories.forms import FormRepository`):

```python
from app.schemas.content import ContentBundle
```

Replace the entire `ensure_seed_data` function body (from `async def ensure_seed_data` to end of file) with:

```python
async def ensure_seed_data(session: AsyncSession, content: ContentBundle) -> None:
    repository = FormRepository(session)
    for index, category_cfg in enumerate(content.categories):
        category = await repository.get_category_by_slug(category_cfg.slug)
        if category is None:
            category = await repository.create_category(
                slug=category_cfg.slug,
                title=category_cfg.title,
                description=category_cfg.description,
                sort_order=index,
            )
        form = await repository.get_active_form(category.id)
        if form is None:
            form = await repository.create_form(
                category_id=category.id,
                title=category_cfg.title,
                description=category_cfg.description,
            )
        questions_payload = [
            {
                "key": q.key,
                "text": q.text,
                "type": q.type,
                "required": q.required,
            }
            for q in category_cfg.questions
        ]
        await repository.replace_questions(form, questions_payload)
```

> Keep `LEAD_FORM_DEFINITIONS` intact (do not modify content, just retain). Removal is Step 6.

- [ ] **Step 4: Update `app/seed.py` to pass bundle**

Replace `app/seed.py` content:

```python
import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import session_scope
from app.services.content import ContentService
from app.services.forms import ensure_seed_data


async def main() -> None:
    setup_logging()
    settings = get_settings()
    profile_dir = Path(__file__).parent / "bot" / "content" / settings.content_profile
    bundle = ContentService.load(profile_dir)
    async with session_scope() as session:
        await ensure_seed_data(session, bundle)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/integration/test_content_seed.py tests/integration/test_lead_service.py -v`
Expected: both new tests pass; existing tests still pass.

If `test_lead_service.py` fails because it calls `ensure_seed_data(session)` without a bundle, update those calls to pass a bundle loaded from `default`. Search:

```bash
grep -rn "ensure_seed_data" tests/
```

For each found call, update to:

```python
bundle = ContentService.load(Path("app/bot/content/default"))
await ensure_seed_data(session, bundle)
```

- [ ] **Step 6: Full test sweep**

Run: `.venv/bin/pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/services/forms.py app/seed.py tests/integration/test_content_seed.py tests/integration/test_lead_service.py
git commit -m "feat(content): ensure_seed_data consumes ContentBundle"
```

---

## Task 0.14: Wire ContentService into FastAPI and aiogram startup

**Files:**
- Modify: `app/main.py`
- Modify: `app/bot_main.py`

ContentService becomes a singleton available in both runtime contexts:

- FastAPI: `app.state.content: ContentService` in `lifespan`.
- aiogram: `dispatcher["content"] = service` via `dispatcher.workflow_data` keyword (also `dispatcher["content_service"]` for clarity) — set in `bot_main.main()` before `start_polling`.

In Step 0 nothing reads these yet (no handlers migrated), so failures would surface only at startup. We add a smoke test for FastAPI startup; aiogram polling is verified manually.

- [ ] **Step 1: Update `app/main.py`**

Replace the `lifespan` body to load content. Full lifespan + create_app:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.routers import admin, health, webhooks
from app.bot.create import create_bot, create_dispatcher
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.services.content import ContentService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    settings = get_settings()
    profile_dir = Path(__file__).parent / "bot" / "content" / settings.content_profile
    app.state.content = ContentService(ContentService.load(profile_dir))
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.bot = create_bot(settings)
    app.state.dispatcher = create_dispatcher(settings, app.state.redis)
    try:
        yield
    finally:
        await app.state.bot.session.close()
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(webhooks.router)
    app.include_router(admin.router)
    return app


app = create_app()
```

- [ ] **Step 2: Update `app/bot_main.py`**

Replace `main()`:

```python
import asyncio
from pathlib import Path

from redis.asyncio import Redis

from app.bot.create import create_bot, create_dispatcher
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.services.content import ContentService

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    profile_dir = Path(__file__).parent / "bot" / "content" / settings.content_profile
    content = ContentService(ContentService.load(profile_dir))
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings, redis)
    dispatcher["content"] = content
    try:
        await bot.delete_webhook(drop_pending_updates=settings.drop_pending_updates)
        logger.info("bot_polling_started", extra={"profile": settings.content_profile})
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Smoke-test FastAPI startup**

Add to `tests/integration/test_content_seed.py`:

```python
def test_fastapi_lifespan_loads_content():
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    with TestClient(app):  # triggers lifespan startup
        assert app.state.content.brand.company_name == "LeadBot Demo"
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/integration/test_content_seed.py -v`
Expected: 3 pass (2 seed + 1 lifespan).

- [ ] **Step 5: Run full suite + lint**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check .`
Expected: all green. If ruff complains about formatting, run `.venv/bin/ruff format .` then re-check.

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/bot_main.py tests/integration/test_content_seed.py
git commit -m "feat(content): wire ContentService into FastAPI and aiogram startup"
```

---

## Step 0 Completion Checklist

Before tagging the step as done, verify:

- [ ] `.venv/bin/pytest -q` — all green.
- [ ] `.venv/bin/ruff check .` — green.
- [ ] `.venv/bin/ruff format --check .` — green.
- [ ] Manual smoke: `CONTENT_PROFILE=default .venv/bin/python -m app.seed` runs without error against a fresh DB (`alembic upgrade head` first).
- [ ] Manual smoke: bot can start (`.venv/bin/python -m app.bot_main`) — logs show `bot_polling_started profile=default`. Stop with Ctrl-C.
- [ ] `git log --oneline` shows clean commit-per-task history.

Then tag:

```bash
git tag stage1-step-0-content-layer
```

Notify orchestrator (or human) that Step 0 is done — Step 1a (migration `0003_add_category_is_internal`) plan should be generated next.

---

## What's NOT in this step (deferred)

- Migration `0003_add_category_is_internal.py` — Step 1a.
- Removing `app/bot/texts/user.py` — Step 6 (Refactoring).
- Removing `LEAD_FORM_DEFINITIONS` constant — Step 6.
- Any UI/Screen change — Step 1 onwards.
- `support` category in YAML — Step 4 (added when SUPPORT_WRITING is implemented).
- `default/examples/*` placeholder dirs — created later when first example profile is needed.

This boundary keeps Step 0 strictly additive: behavior is identical, but the content layer is now the source of truth for all clients-specific data.
