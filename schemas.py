from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class ShortenRequest(BaseModel):
    url: HttpUrl
    custom_alias: Optional[str] = None

class ShortenResponse(BaseModel):
    code: str
    url: HttpUrl
    created_at: datetime

class MetadataResponse(BaseModel):
    code: str
    url: HttpUrl
    created_at: datetime
    hits: int
