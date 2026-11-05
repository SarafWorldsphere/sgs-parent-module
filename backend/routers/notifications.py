from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from auth import get_current_parent_or_demo, verify_student_ownership
from database import get_db
from models import ParentMaster
from services.parent_notifications import notification_history

router = APIRouter(tags=['Notifications'])


@router.get('/notification-history/{student_id}')
def get_notification_history(student_id: int,
                             limit: int = Query(50, ge=1, le=100),
                             offset: int = Query(0, ge=0),
                             db: Session = Depends(get_db),
                             current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    try:
        rows = notification_history(db, student_id, current.parent_id, limit + 1, offset)
    except SQLAlchemyError as error:
        raise HTTPException(503, 'Unable to load notifications. Please try again.') from error
    return dict(items=rows[:limit], has_more=len(rows) > limit)
