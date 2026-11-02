"""
Communication Center router.

Provides clean /comm/ prefixed endpoints for the parent↔teacher
academic communication system. Uses the existing SupportTicket and
TicketMessage tables repurposed as Conversation + Message.

Route prefix avoids the 422 ambiguity in the legacy /tickets/ routes
where FastAPI matched /tickets/{ticket_id}/messages against
/tickets/{parent_id}/{student_id} before integer validation failed.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from datetime import datetime
from typing import List
import uuid

from models import (
    SupportTicket, TicketMessage,
    StudentMaster, UsersMaster, SubjectMaster, ParentMaster,
    # TeacherMaster removed: SubjectMaster.teacher_id now FKs to
    # users_masters.user_id, so the teacher-lookup JOIN uses UsersMaster.
)
from auth import get_current_parent_or_demo, verify_student_ownership, verify_conversation_ownership
from schemas import (
    TeacherOptionSchema,
    ConversationSummarySchema,
    ConversationMessageSchema,
    CreateConversationSchema,
    SendConversationMessageSchema,
)

router = APIRouter(prefix="/comm", tags=["Communication"])

# ── Available teachers / departments for a student's class ─────────────────

@router.get("/teachers/{student_id}", response_model=List[TeacherOptionSchema])
def get_available_recipients(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # SubjectMaster.teacher_id → users_masters.user_id (production FK).
    # Join UsersMaster on user_id to resolve the teacher's display name.
    rows = (
        db.query(UsersMaster, SubjectMaster.subject_name)
        .join(SubjectMaster, UsersMaster.user_id == SubjectMaster.teacher_id)
        .filter(SubjectMaster.class_id == student.class_id)
        .all()
    )

    result: List[TeacherOptionSchema] = []
    seen: set = set()
    for user, subject_name in rows:
        if user.user_id not in seen:
            result.append(TeacherOptionSchema(
                teacher_id=user.user_id,   # user_id used as the recipient identifier
                name=user.full_name,
                role=f"{subject_name} Teacher",
            ))
            seen.add(user.user_id)

    return result


# ── List conversations for a student ──────────────────────────────────────

@router.get("/conversations/{student_id}", response_model=List[ConversationSummarySchema])
def list_conversations(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    tickets = (
        db.query(SupportTicket)
        .filter(
            SupportTicket.student_id == student_id,
            SupportTicket.parent_id == current.parent_id,
        )
        .order_by(SupportTicket.updated_at.desc())
        .all()
    )

    result = []
    for t in tickets:
        # Latest message
        latest = (
            db.query(TicketMessage)
            .filter(TicketMessage.ticket_id == t.ticket_id)
            .order_by(TicketMessage.created_at.desc())
            .first()
        )
        unread = (
            db.query(TicketMessage)
            .filter(
                TicketMessage.ticket_id == t.ticket_id,
                TicketMessage.sender_type == "TEACHER",
                TicketMessage.is_read == False,
            )
            .count()
        )
        result.append(ConversationSummarySchema(
            conv_id=t.ticket_id,
            subject=t.subject or "Untitled",
            category=t.category or "General",
            recipient_name=t.recipient_name or t.category or "School",
            status=t.status or "OPEN",
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else "",
            latest_message=latest.message[:80] if latest else None,
            latest_message_time=latest.created_at.isoformat() if latest and latest.created_at else None,
            latest_sender=latest.sender_type if latest else None,
            unread_count=unread,
        ))
    return result


# ── Create new conversation ────────────────────────────────────────────────

@router.post("/conversations", response_model=ConversationSummarySchema)
def create_conversation(body: CreateConversationSchema, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, body.student_id)
    ref = f"CONV-{str(uuid.uuid4())[:8].upper()}"
    ticket = SupportTicket(
        ticket_number=ref,
        parent_id=current.parent_id,
        student_id=body.student_id,
        subject=body.subject,
        category=body.category,
        recipient_name=body.recipient_name,
        # The picker hands the client a real user_id; store it rather than
        # relying on the name to identify the teacher later.
        recipient_user_id=body.recipient_user_id,
        priority="MEDIUM",
        status="OPEN",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # First message from parent
    first_msg = TicketMessage(
        ticket_id=ticket.ticket_id,
        sender_type="PARENT",
        sender_name=current.full_name or "Parent",
        message=body.first_message,
        is_read=False,
    )
    db.add(first_msg)
    db.commit()
    db.refresh(first_msg)

    return ConversationSummarySchema(
        conv_id=ticket.ticket_id,
        subject=ticket.subject,
        category=ticket.category,
        recipient_name=ticket.recipient_name or ticket.category,
        status=ticket.status,
        created_at=ticket.created_at.isoformat() if ticket.created_at else "",
        updated_at=ticket.updated_at.isoformat() if ticket.updated_at else "",
        latest_message=first_msg.message[:80],
        latest_message_time=first_msg.created_at.isoformat() if first_msg.created_at else "",
        latest_sender="PARENT",
        unread_count=0,
    )


# ── Get messages for a conversation ──────────────────────────────────────

@router.get("/conversations/{conv_id}/messages", response_model=List[ConversationMessageSchema])
def get_messages(conv_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_conversation_ownership(db, current, conv_id)
    ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == conv_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Mark teacher messages as read
    db.query(TicketMessage).filter(
        TicketMessage.ticket_id == conv_id,
        TicketMessage.sender_type == "TEACHER",
        TicketMessage.is_read == False,
    ).update({"is_read": True})
    db.commit()

    messages = (
        db.query(TicketMessage)
        .filter(TicketMessage.ticket_id == conv_id)
        .order_by(TicketMessage.created_at.asc())
        .all()
    )

    return [
        ConversationMessageSchema(
            message_id=m.message_id,
            conv_id=m.ticket_id,
            sender_type=m.sender_type,
            sender_name=m.sender_name,
            message=m.message,
            created_at=m.created_at.isoformat() if m.created_at else "",
            is_read=m.is_read,
        )
        for m in messages
    ]


# ── Send a message ────────────────────────────────────────────────────────

@router.post("/conversations/{conv_id}/messages", response_model=ConversationMessageSchema)
def send_message(conv_id: int, body: SendConversationMessageSchema, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_conversation_ownership(db, current, conv_id)
    ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == conv_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg = TicketMessage(
        ticket_id=conv_id,
        sender_type=body.sender_type,
        sender_name=body.sender_name,
        message=body.message,
        is_read=False,
    )
    db.add(msg)

    # Keep conversation open and bump updated_at
    ticket.status = "OPEN"
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)

    return ConversationMessageSchema(
        message_id=msg.message_id,
        conv_id=msg.ticket_id,
        sender_type=msg.sender_type,
        sender_name=msg.sender_name,
        message=msg.message,
        created_at=msg.created_at.isoformat() if msg.created_at else "",
        is_read=msg.is_read,
    )


# ── Close / reopen a conversation ─────────────────────────────────────────

@router.patch("/conversations/{conv_id}/status")
def update_status(conv_id: int, status: str, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_conversation_ownership(db, current, conv_id)
    ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == conv_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if status not in ("OPEN", "CLOSED"):
        raise HTTPException(status_code=400, detail="status must be OPEN or CLOSED")
    ticket.status = status
    ticket.updated_at = datetime.utcnow()
    db.commit()
    return {"conv_id": conv_id, "status": status}
