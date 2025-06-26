from database import SessionLocal
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

# Dependency to get DB session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()