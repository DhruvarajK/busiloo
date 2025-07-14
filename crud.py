# In a file like crud.py

from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import models, schemas

# --- CRUD for Stop Issues ---

def get_stop_issues(db: Session, status: Optional[str] = None, issue_type: Optional[models.StopIssueType] = None) -> List[models.StopIssue]:
    """
    Fetches stop issues from the database, with optional filtering.
    Eagerly loads related stop and user data to prevent extra queries.
    """
    query = db.query(models.StopIssue).options(
        joinedload(models.StopIssue.stop), 
        joinedload(models.StopIssue.user)
    )
    
    if status:
        query = query.filter(models.StopIssue.status == status)
    
    if issue_type:
        query = query.filter(models.StopIssue.issue_type == issue_type)
        
    return query.order_by(models.StopIssue.reported_at.desc()).all()

def get_stop(db: Session, stop_id: int) -> Optional[models.Stop]:
    """Fetches a single stop by its ID."""
    return db.query(models.Stop).filter(models.Stop.id == stop_id).first()

def update_stop(db: Session, stop_id: int, stop_update: schemas.StopUpdate) -> Optional[models.Stop]:
    """Updates a stop's details in the database."""
    db_stop = get_stop(db, stop_id)
    if not db_stop:
        return None
    
    update_data = stop_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_stop, key, value)
        
    db.commit()
    db.refresh(db_stop)
    return db_stop

def update_issue_status(db: Session, issue_id: int, new_status: str) -> Optional[models.StopIssue]:
    """Updates the status of a specific issue."""
    db_issue = db.query(models.StopIssue).filter(models.StopIssue.id == issue_id).first()
    if not db_issue:
        return None
    
    db_issue.status = new_status
    db.commit()
    db.refresh(db_issue)
    return db_issue
