import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    icon: str = Field(default="tag", max_length=50)
    color_hex: str = Field(default="#64748B", max_length=7)


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: uuid.UUID
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

