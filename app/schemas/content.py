from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.constants import QuestionType


class BrandConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str
    manager_username: str
    manager_phone: str
    working_hours: str
    welcome_intro: str
    support_intro: str
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
