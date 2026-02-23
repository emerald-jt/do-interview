from sqlalchemy import Column, String, DateTime, Integer
from db import Base
from datetime import datetime

class ShortURL(Base):
    __tablename__ = "short_urls"

    code = Column(String(16), primary_key=True, index=True)
    url = Column(String(2048), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    hits = Column(Integer, default=0)
