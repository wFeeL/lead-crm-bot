from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    role: str
    is_blocked: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime

