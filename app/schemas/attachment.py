import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AttachmentResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    file_name: str
    file_path: str
    mime_type: str
    file_size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

