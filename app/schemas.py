from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    task_name: str
    payload: dict = Field(default_factory=dict)
    max_attempts: int = Field(5, ge=1, le=20)
    delay_seconds: int = Field(0, ge=0)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_name: str
    payload: dict
    status: str
    attempts: int
    max_attempts: int
    run_at: datetime
    locked_by: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
