from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from database import Base

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, index=True)
    authors = Column(String)
    publisher = Column(String)
    publish_date = Column(String)
    pages = Column(Integer)
    language = Column(String)
    cover_url = Column(String)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())