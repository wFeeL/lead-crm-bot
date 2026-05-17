from pydantic import BaseModel, ConfigDict


class LeadCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: str | None = None
    is_active: bool
    sort_order: int


class LeadQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    question_text: str
    question_type: str
    is_required: bool
    sort_order: int
    options_json: dict | list | None = None
    validation_json: dict | None = None
