from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.constants import QuestionType


class BrandConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1)
    manager_username: str = Field(min_length=1)
    manager_phone: str = Field(min_length=1)
    working_hours: str = Field(min_length=1)
    welcome_intro: str = Field(min_length=1)
    support_intro: str = Field(min_length=1)
    eta_response_hours: int = Field(ge=0)


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

    @model_validator(mode="after")
    def _choice_requires_options(self) -> Self:
        if self.type in (QuestionType.CHOICE, QuestionType.MULTI_CHOICE):
            if not self.options:
                raise ValueError(
                    f"question {self.key!r}: type {self.type.value!r} requires"
                    " a non-empty 'options' list"
                )
        return self


class CategoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    title: str
    description: str
    internal: bool = False
    questions: list[QuestionConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_question_keys(self) -> Self:
        seen: set[str] = set()
        for q in self.questions:
            if q.key in seen:
                raise ValueError(f"duplicate question key {q.key!r} in category {self.slug!r}")
            seen.add(q.key)
        return self


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
    """Loaded content profile.

    Used as a value object after ContentService.load(). Note: ``frozen=True`` here
    prevents field *reassignment* but does NOT prevent in-place mutation of contained
    lists (e.g. ``bundle.faq.append(...)`` succeeds). Treat contents as read-only by
    convention.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    brand: BrandConfig
    texts: TextsConfig
    faq: list[FaqEntry]
    categories: list[CategoryConfig]
    config: AppContentConfig
