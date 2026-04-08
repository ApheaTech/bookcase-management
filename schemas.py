from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BookBase(BaseModel):
    isbn: str
    title: Optional[str] = None
    authors: Optional[str] = None
    publisher: Optional[str] = None
    publish_date: Optional[str] = None
    pages: Optional[int] = None
    language: Optional[str] = None
    cover_url: Optional[str] = None
    description: Optional[str] = None

class BookCreate(BookBase):
    pass

class Book(BookBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True