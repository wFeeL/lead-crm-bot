from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeadAnswerInput(BaseModel):
    question_id: int | None = None
    key: str
    value_text: str | None = None
    value_json: dict | list | None = None


class LeadFileInput(BaseModel):
    telegram_file_id: str
    file_unique_id: str | None = None
    file_type: str
    file_name: str | None = None
    mime_type: str | None = None
    size: int | None = None


class LeadCreateInput(BaseModel):
    user_id: int
    category_id: int
    submission_key: str | None = Field(default=None, max_length=64)
    title: str
    description: str
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_username: str | None = None
    preferred_contact_time: str | None = None
    answers: list[LeadAnswerInput] = Field(default_factory=list)
    files: list[LeadFileInput] = Field(default_factory=list)
    source: str = "bot"


class LeadStatusUpdate(BaseModel):
    status: str


class LeadCommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    is_internal: bool = True


class LeadAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value_text: str | None = None
    value_json: dict | list | None = None


class LeadFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_file_id: str
    file_unique_id: str | None = None
    file_type: str
    file_name: str | None = None
    mime_type: str | None = None
    size: int | None = None


class LeadCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int
    text: str
    is_internal: bool
    created_at: datetime


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str | None
    user_id: int
    category_id: int
    status: str
    title: str
    description: str
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_username: str | None = None
    preferred_contact_time: str | None = None
    assigned_admin_id: int | None = None
    source: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    answers: list[LeadAnswerRead] = Field(default_factory=list)
    files: list[LeadFileRead] = Field(default_factory=list)
    comments: list[LeadCommentRead] = Field(default_factory=list)


class DailyStatsRead(BaseModel):
    date: str
    new: int = 0
    in_progress: int = 0
    waiting: int = 0
    done: int = 0
    rejected: int = 0
    cancelled: int = 0
    top_category: str | None = None
