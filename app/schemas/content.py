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
