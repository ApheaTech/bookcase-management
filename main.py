from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import models
import schemas
from database import engine, get_db
from external_api import get_book_from_external_api

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bookcase API", version="1.0.0")

@app.get("/book/{isbn}", response_model=schemas.Book)
def get_book(isbn: str, db: Session = Depends(get_db)):
    db_book = db.query(models.Book).filter(models.Book.isbn == isbn).first()
    if db_book:
        return db_book
    
    book_data = get_book_from_external_api(isbn)
    if not book_data:
        raise HTTPException(status_code=404, detail="Book not found in external API")
    
    db_book = models.Book(**book_data)
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    
    return db_book

@app.get("/")
def root():
    return {"message": "Welcome to Bookcase API"}