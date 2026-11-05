import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db
from typing import List, Dict, Any
from datetime import datetime, date, timedelta
from auth import get_current_parent_or_demo, verify_student_ownership
from models import ParentMaster

logger = logging.getLogger(__name__)
from services.dashboard_service import get_dashboard_data
# DISABLED: analytics_service only served GET /analytics/ which has no frontend caller
# from services.analytics_service import get_analytics_data
from schemas import (
    DashboardResponse, MappedChildSchema, AssignmentSchema, QuizSchema, QuizDetailResponse,
    RemarkSchema, NoticeSchema, CallRequestCreate, CallRequestResponse,
    AssignmentSubmitRequest, AssignmentAnalyticsResponse, NotificationSchema,
    AttachmentResponse,
    # DISABLED: AttendanceDataResponse, AttendanceOverviewSchema, AttendanceDaySchema
    #           — attendance module removed from parent portal.
    # DISABLED: LeaveRequestCreate, LeaveRequestResponse, LeaveStatusUpdate
    #           — standalone leave-request endpoints disabled; flow moved to Communication Center.
    # DISABLED: AnalyticsResponse — analytics module removed from frontend.
)
from models import (
    ParentStudentMap, StudentMaster, ClassMaster, AssignmentMaster, SubjectMaster,
    ChapterMaster, StudentSubmission, QuizMaster, QuizResponse,
    UsersMaster, NoticeBoard,
    SupportTicket, TicketMessage, FileStorageMetadata,
    # DISABLED: CallRequest   — call-request routes commented out below.
    # DISABLED: AttendanceMaster — attendance endpoints commented out below.
    # DISABLED: LeaveRequest     — leave-request endpoints commented out below.
    # DISABLED: TeacherParentInteractionV2 — table absent on SGS RDS; remarks
    #           now come from TicketMessage (sender_type='TEACHER') instead.
    # NOTE: TeacherMaster removed — assigned_by / posted_by now FK to
    #       users_masters.user_id; all teacher-name JOINs use UsersMaster.
)

router = APIRouter()

@router.get("/dashboard/{student_id}", response_model=DashboardResponse)
def get_dashboard(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    try:
        return get_dashboard_data(db, student_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── DISABLED: Analytics route ─────────────────────────────────────────────
# GET /analytics/{student_id} had no frontend caller after /parent/analytics
# page was removed. analytics_service.py is preserved on disk for reference.
# Restore by uncommenting this block and re-enabling the analytics_service
# import at the top of this file.
#
# @router.get("/analytics/{student_id}", response_model=AnalyticsResponse)
# def get_analytics(student_id: int, db: Session = Depends(get_db)):
#     try:
#         return get_analytics_data(db, student_id)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
# ──────────────────────────────────────────────────────────────────────────

# ── DISABLED: Communication timeline route ────────────────────────────────
# GET /communication/timeline/{student_id} had no frontend caller. The new
# Communication Center uses /comm/ routes instead. TimelineItemSchema also
# disabled in schemas.py. Restore together if a timeline view is re-added.
#
# from schemas import TimelineItemSchema
#
# @router.get("/communication/timeline/{student_id}", response_model=List[TimelineItemSchema])
# def get_communication_timeline(student_id: int, db: Session = Depends(get_db)):
#     try:
#         timeline = []
#         calls = db.query(CallRequest, TeacherMaster.full_name).outerjoin(...).all()
#         ... (full implementation preserved in git history)
#         return [TimelineItemSchema(**item) for item in timeline]
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
# ──────────────────────────────────────────────────────────────────────────

@router.get("/parents/{parent_id}/children", response_model=List[MappedChildSchema])
def get_parent_children(parent_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    if parent_id != current.parent_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    children_query = db.query(StudentMaster, ClassMaster)\
        .join(ParentStudentMap, ParentStudentMap.student_id == StudentMaster.student_id)\
        .outerjoin(ClassMaster, StudentMaster.class_id == ClassMaster.class_id)\
        .filter(
            ParentStudentMap.parent_id == parent_id,
            StudentMaster.is_active == True,
            StudentMaster.record_status == 'Active',
        ).all()

    result = []
    for student, class_info in children_query:
        result.append(MappedChildSchema(
            student_id=student.student_id,
            full_name=student.full_name,
            class_name=class_info.class_name if class_info else "Unknown Class",
            section=student.section or ""
        ))
    logger.info("[parents/children] parent_id=%s → %d children found", parent_id, len(result))
    return result

@router.get("/assignments/history/{student_id}", response_model=List[AssignmentSchema])
def get_assignments_history(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()
    if not student:
        logger.warning("[assignments/history] student_id=%s not found → returning []", student_id)
        return []

    assignments_query = db.query(
        AssignmentMaster, SubjectMaster.subject_name, ChapterMaster.chapter_name,
        UsersMaster.full_name, StudentSubmission
    ).select_from(AssignmentMaster)\
    .join(ChapterMaster, AssignmentMaster.chapter_id == ChapterMaster.chapter_id)\
    .join(SubjectMaster, ChapterMaster.subject_id == SubjectMaster.subject_id)\
    .outerjoin(UsersMaster, AssignmentMaster.assigned_by == UsersMaster.user_id)\
    .outerjoin(StudentSubmission, (StudentSubmission.assignment_id == AssignmentMaster.assignment_id) & (StudentSubmission.student_id == student_id))\
    .filter(SubjectMaster.class_id == student.class_id)\
    .order_by(AssignmentMaster.due_date.desc()).all()

    assignment_list = []
    today = date.today()
    for assign, subject_name, chapter_name, teacher_name, submission in assignments_query:
        if submission:
            status = "Graded" if submission.marks_obtained is not None else "Submitted"
        elif assign.due_date and assign.due_date < today:
            status = "Overdue"
        elif assign.due_date and (assign.due_date - today).days <= 7:
            status = "Ongoing"
        else:
            status = "Upcoming"
        assignment_list.append(AssignmentSchema(
            assignment_id=assign.assignment_id,
            assignment_title=assign.assignment_title,
            assignment_text=assign.assignment_text,
            subject=subject_name,
            chapter_name=chapter_name,
            teacher_name=teacher_name or "",
            teacher_user_id=assign.assigned_by,
            due_date=assign.due_date.isoformat() if assign.due_date else "",
            status=status,
            marks_obtained=submission.marks_obtained if submission else None,
            submitted_at=submission.submitted_at.isoformat() if submission and submission.submitted_at else None,
            submission_text=submission.submission_text if submission else None,
            teacher_remarks=submission.teacher_remarks if submission else None,
            file_path=submission.file_path if submission else None,
        ))
    logger.info("[assignments/history] student_id=%s → %d assignments", student_id, len(assignment_list))
    return assignment_list

@router.get("/assignments/analytics/{student_id}", response_model=AssignmentAnalyticsResponse)
def get_assignment_analytics(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()
    if not student:
        logger.warning("[assignments/analytics] student_id=%s not found → returning zeroes", student_id)
        return AssignmentAnalyticsResponse(total=0, submitted=0, pending=0, overdue=0, graded=0, completion_pct=0.0)

    rows = db.query(AssignmentMaster, StudentSubmission)\
        .select_from(AssignmentMaster)\
        .join(ChapterMaster, AssignmentMaster.chapter_id == ChapterMaster.chapter_id)\
        .join(SubjectMaster, ChapterMaster.subject_id == SubjectMaster.subject_id)\
        .outerjoin(StudentSubmission, (StudentSubmission.assignment_id == AssignmentMaster.assignment_id) & (StudentSubmission.student_id == student_id))\
        .filter(SubjectMaster.class_id == student.class_id).all()

    today = date.today()
    total = len(rows)
    submitted = sum(1 for a, s in rows if s and s.marks_obtained is None)
    graded = sum(1 for a, s in rows if s and s.marks_obtained is not None)
    overdue = sum(1 for a, s in rows if not s and a.due_date and a.due_date < today)
    ongoing = sum(1 for a, s in rows if not s and a.due_date and a.due_date >= today and (a.due_date - today).days <= 7)
    upcoming = sum(1 for a, s in rows if not s and (not a.due_date or (a.due_date >= today and (a.due_date - today).days > 7)))
    completion_pct = round((submitted + graded) / total * 100, 1) if total > 0 else 0.0
    return AssignmentAnalyticsResponse(total=total, submitted=submitted, pending=ongoing, overdue=overdue, graded=graded, completion_pct=completion_pct)

@router.get("/assignments/{assignment_id}/attachment", response_model=AttachmentResponse)
def get_assignment_attachment(
    assignment_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current: ParentMaster = Depends(get_current_parent_or_demo),
):
    """
    Return a presigned S3 URL for a teacher-uploaded assignment PDF.

    Authorization:
      1. verify_student_ownership — confirms the parent→student mapping in DB.
      2. Confirm the assignment belongs to the student's class — prevents a
         parent from fetching attachments for assignments in other classes even
         if they supply a valid student_id they own.

    The raw s3:// URI is never returned to the client.
    """
    # Step 1 — parent must own this student (DB-side check, not client trust)
    verify_student_ownership(db, current, student_id)

    # Step 2 — resolve the student's class
    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    # Step 3 — confirm assignment belongs to the student's class via chapter→subject→class chain
    assignment = (
        db.query(AssignmentMaster)
        .join(ChapterMaster, AssignmentMaster.chapter_id == ChapterMaster.chapter_id)
        .join(SubjectMaster, ChapterMaster.subject_id == SubjectMaster.subject_id)
        .filter(
            AssignmentMaster.assignment_id == assignment_id,
            SubjectMaster.class_id == student.class_id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found for this student.")

    # Step 4 — look up the attachment record
    attachment = (
        db.query(FileStorageMetadata)
        .filter(
            FileStorageMetadata.entity_type == "ASSIGNMENT_ATTACHMENT",
            FileStorageMetadata.entity_id == assignment_id,
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="No attachment found for this assignment.")

    # Step 5 — generate presigned URL (never expose the raw s3:// URI)
    from s3_utils import generate_presigned_url
    try:
        presigned = generate_presigned_url(attachment.file_url)
    except (ValueError, RuntimeError) as exc:
        logger.error("[attachment] presign failed assignment_id=%s: %s", assignment_id, exc)
        raise HTTPException(status_code=500, detail="Could not generate file link.")

    return AttachmentResponse(file_name=attachment.file_name, url=presigned)


@router.post("/assignments/submit", response_model=AssignmentSchema)
def submit_assignment(request: AssignmentSubmitRequest, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, request.student_id)
    existing = db.query(StudentSubmission).filter(
        StudentSubmission.assignment_id == request.assignment_id,
        StudentSubmission.student_id == request.student_id
    ).first()
    if existing:
        existing.submission_text = request.submission_text
        existing.file_path = request.file_path
        existing.submitted_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        sub = existing
    else:
        sub = StudentSubmission(
            assignment_id=request.assignment_id,
            student_id=request.student_id,
            submission_text=request.submission_text,
            file_path=request.file_path,
            submitted_at=datetime.utcnow()
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

    assign_row = db.query(AssignmentMaster, SubjectMaster.subject_name, ChapterMaster.chapter_name, UsersMaster.full_name)\
        .join(ChapterMaster, AssignmentMaster.chapter_id == ChapterMaster.chapter_id)\
        .join(SubjectMaster, ChapterMaster.subject_id == SubjectMaster.subject_id)\
        .outerjoin(UsersMaster, AssignmentMaster.assigned_by == UsersMaster.user_id)\
        .filter(AssignmentMaster.assignment_id == request.assignment_id).first()

    if not assign_row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    assign, subject_name, chapter_name, teacher_name = assign_row
    status = "Graded" if sub.marks_obtained is not None else "Submitted"
    return AssignmentSchema(
        assignment_id=assign.assignment_id, assignment_title=assign.assignment_title,
        assignment_text=assign.assignment_text, subject=subject_name,
        chapter_name=chapter_name, teacher_name=teacher_name or "",
        due_date=assign.due_date.isoformat() if assign.due_date else "",
        status=status, marks_obtained=sub.marks_obtained,
        submitted_at=sub.submitted_at.isoformat() if sub.submitted_at else None,
        submission_text=sub.submission_text, teacher_remarks=sub.teacher_remarks, file_path=sub.file_path
    )

@router.get("/quiz/history/{student_id}", response_model=List[QuizDetailResponse])
def get_quiz_history(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()
    if not student:
        logger.warning("[quiz/history] student_id=%s not found → returning []", student_id)
        return []

    quizzes_query = db.query(
        QuizMaster, SubjectMaster.subject_name, QuizResponse
    ).select_from(QuizMaster)\
    .join(ChapterMaster, QuizMaster.chapter_id == ChapterMaster.chapter_id)\
    .join(SubjectMaster, ChapterMaster.subject_id == SubjectMaster.subject_id)\
    .join(QuizResponse, (QuizResponse.quiz_id == QuizMaster.quiz_id) & (QuizResponse.student_id == student_id))\
    .all()
    # NOTE: class_id filter intentionally removed. The INNER JOIN on QuizResponse
    # already scopes results to this student's own responses. Filtering by
    # SubjectMaster.class_id == student.class_id caused all quiz records to
    # disappear when the student's class_id differs from the quiz's subject chain
    # class_id (confirmed on RDS: student class_id=15, quiz subject class_id=13).
        
    quiz_list = []
    for quiz, subject_name, response in quizzes_query:
        if not response or response.score is None:
            continue
            
        score = float(response.score)
        total = float(quiz.total_marks or 100)
        percentage = round((score / total) * 100, 1) if total > 0 else 0
        
        if percentage >= 85:
            status = "Excellent"
            suggestion = "Excellent consistency."
        elif percentage >= 70:
            status = "Good"
            suggestion = "Good performance. Minor improvement possible."
        elif percentage >= 50:
            status = "Average"
            suggestion = "Needs more revision practice."
        else:
            status = "Needs Improvement"
            suggestion = "Immediate academic attention recommended."
            
        quiz_list.append(QuizDetailResponse(
            subject=subject_name,
            score=str(score),
            total=str(total),
            quiz_id=quiz.quiz_id,
            quiz_title=quiz.quiz_title or f"{subject_name} Quiz",
            percentage=percentage,
            teacher_name="Course Instructor",
            remarks=suggestion,
            quiz_date=quiz.created_at.isoformat() if hasattr(quiz, 'created_at') and quiz.created_at else datetime.utcnow().isoformat(),
            status=status,
            suggestion=suggestion
        ))
    logger.info("[quiz/history] student_id=%s → %d quizzes", student_id, len(quiz_list))
    return quiz_list

@router.get("/remarks/history/{student_id}", response_model=List[RemarkSchema])
def get_remarks_history(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    # Source 1: teacher_remarks stored on submitted assignments (graded work).
    # JOIN uses UsersMaster (assigned_by → users_masters.user_id on production).
    submissions_remarks = db.query(StudentSubmission, UsersMaster.full_name, SubjectMaster.subject_name)\
        .join(AssignmentMaster, StudentSubmission.assignment_id == AssignmentMaster.assignment_id)\
        .outerjoin(UsersMaster, AssignmentMaster.assigned_by == UsersMaster.user_id)\
        .join(ChapterMaster, AssignmentMaster.chapter_id == ChapterMaster.chapter_id)\
        .join(SubjectMaster, ChapterMaster.subject_id == SubjectMaster.subject_id)\
        .filter(StudentSubmission.student_id == student_id)\
        .filter(StudentSubmission.teacher_remarks.isnot(None))\
        .filter(StudentSubmission.teacher_remarks != '').all()

    # Source 2: teacher replies in Communication Center tickets for this student.
    # Replaces TeacherParentInteractionV2 (table absent on SGS RDS).
    # sender_name is already stored on each TicketMessage; no extra join needed.
    teacher_msgs = db.query(TicketMessage, SupportTicket)\
        .join(SupportTicket, TicketMessage.ticket_id == SupportTicket.ticket_id)\
        .filter(SupportTicket.student_id == student_id)\
        .filter(TicketMessage.sender_type == "TEACHER")\
        .filter(TicketMessage.message.isnot(None))\
        .filter(TicketMessage.message != '').all()

    all_remarks = []
    idx = 1
    for sub, teacher_name, subject_name in submissions_remarks:
        remark_date = sub.submitted_at or datetime.utcnow()
        all_remarks.append({
            "remark_id": idx,
            "teacher_name": teacher_name or "Teacher",
            "subject": subject_name,
            "comment": sub.teacher_remarks.strip(),
            "date_obj": remark_date,
            "date": remark_date.strftime("%d %b %Y"),
            "ticket_id": None,
            "is_read": True,  # submission remarks are always considered read
        })
        idx += 1

    for msg, ticket in teacher_msgs:
        remark_date = msg.created_at or datetime.utcnow()
        all_remarks.append({
            "remark_id": idx,
            "teacher_name": msg.sender_name or "Teacher",
            "subject": ticket.subject or "General",
            "comment": msg.message.strip(),
            "date_obj": remark_date,
            "date": remark_date.strftime("%d %b %Y"),
            "ticket_id": ticket.ticket_id,
            "is_read": bool(msg.is_read),
        })
        idx += 1

    all_remarks.sort(key=lambda x: x["date_obj"], reverse=True)
    logger.info("[remarks/history] student_id=%s → %d remarks", student_id, len(all_remarks))
    return [RemarkSchema(**r) for r in all_remarks]

@router.get("/notices/history/{student_id}", response_model=List[NoticeSchema])
def get_notices_history(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)

    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()
    if not student:
        logger.warning("[notices/history] student_id=%s not found → returning []", student_id)
        return []

    class_info = db.query(ClassMaster).filter(ClassMaster.class_id == student.class_id).first()
    class_name = class_info.class_name if class_info else None

    notices_query = db.query(NoticeBoard, UsersMaster.full_name)\
        .outerjoin(UsersMaster, NoticeBoard.posted_by == UsersMaster.user_id)\
        .filter(NoticeBoard.notice_text.isnot(None))\
        .filter(NoticeBoard.notice_text != '')

    if class_name:
        notices_query = notices_query.filter(
            or_(
                NoticeBoard.applicable_class == class_name,
                NoticeBoard.applicable_class == 'All',
                NoticeBoard.applicable_class.is_(None),
            )
        )

    notices_query = notices_query.order_by(NoticeBoard.created_at.desc()).all()

    result = [
        NoticeSchema(
            notice_id=n.notice_id,
            notice_title=n.notice_title or "Notice",
            notice_text=n.notice_text.strip(),
            notice_date=n.notice_date.strftime("%d %b %Y") if n.notice_date else (n.created_at.strftime("%d %b %Y") if n.created_at else ""),
            applicable_class=n.applicable_class or "All",
            posted_by_name=t or "Admin"
        ) for n, t in notices_query
    ]
    logger.info("[notices/history] student_id=%s class=%s → %d notices", student_id, class_name, len(result))
    return result

# ── DISABLED: Call-request routes ────────────────────────────────────────
# GET /call-requests/history/{student_id} and POST /request-call had no
# frontend callers (api.ts exported fetchCallRequestsHistory and requestCall
# but no page imported them after the dashboard redesign). The CallRequest
# model and table remain intact. Restore if a PTM-request feature is added.
#
# @router.get("/call-requests/history/{student_id}", response_model=List[CallRequestResponse])
# def get_call_requests_history(student_id: int, db: Session = Depends(get_db)):
#     ...
#
# @router.post("/request-call", response_model=CallRequestResponse)
# def create_call_request(request: CallRequestCreate, db: Session = Depends(get_db)):
#     ...
# ──────────────────────────────────────────────────────────────────────────


# ── DISABLED: Old chat system routes ─────────────────────────────────────
# GET /chat/threads/{parent_id}/{student_id}, GET /chat/messages/{thread_id},
# POST /chat/messages — these served a thread-based Parent↔Teacher chat
# backed by ChatThread + ChatMessage tables. Replaced by the /comm/
# Communication Center (routers/communication.py). The ChatThread and
# ChatMessage DB tables remain intact (data preserved).
# ChatMessageSchema, ChatMessageCreate, ChatThreadSchema are also disabled
# in schemas.py. Restore this entire block to revive the old chat system.
#
# from models import ChatThread, ChatMessage
# from schemas import ChatThreadSchema, ChatMessageSchema, ChatMessageCreate
#
# @router.get("/chat/threads/{parent_id}/{student_id}", ...)
# @router.get("/chat/messages/{thread_id}", ...)
# @router.post("/chat/messages", ...)
# ──────────────────────────────────────────────────────────────────────────

# ── DISABLED: Old support-ticket routes ───────────────────────────────────
# GET /tickets/{parent_id}/{student_id}, POST /tickets,
# GET /tickets/{ticket_id}/messages, POST /tickets/{ticket_id}/messages —
# These were the original customer-support style ticket system. Two issues:
#   1. Route ordering caused 422 errors (FastAPI matched /{parent_id}/{student_id}
#      before /{ticket_id}/messages, failing integer parse on "messages").
#   2. Replaced wholesale by /comm/ routes (routers/communication.py) which
#      reuse the same SupportTicket + TicketMessage tables cleanly.
# SupportTicketSchema, TicketMessageSchema etc. are also disabled in schemas.py.
# The /notifications/ route below still queries SupportTicket/TicketMessage
# models directly, so those model imports remain active.
#
# from schemas import SupportTicketSchema, TicketMessageSchema, TicketCreateSchema, TicketMessageCreateSchema
#
# @router.get("/tickets/{parent_id}/{student_id}", ...)
# @router.post("/tickets", ...)
# @router.get("/tickets/{ticket_id}/messages", ...)
# @router.post("/tickets/{ticket_id}/messages", ...)
# ──────────────────────────────────────────────────────────────────────────

@router.get("/notifications/unread-count/{student_id}")
def get_unread_count(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    """Returns total unread teacher messages across all conversations for this student."""
    count = db.query(TicketMessage)\
        .join(SupportTicket, TicketMessage.ticket_id == SupportTicket.ticket_id)\
        .filter(
            SupportTicket.student_id == student_id,
            SupportTicket.parent_id == current.parent_id,
            TicketMessage.sender_type == "TEACHER",
            TicketMessage.is_read == False,
        ).count()
    return {"student_id": student_id, "unread_comm_count": count}


@router.get("/notifications/{student_id}", response_model=List[NotificationSchema])
def get_notifications(student_id: int, db: Session = Depends(get_db), current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    from services.parent_notifications import notification_history
    from sqlalchemy.exc import SQLAlchemyError
    try:
        notifications = [NotificationSchema(**row) for row in notification_history(db, student_id, current.parent_id, 10)]
    except SQLAlchemyError as error:
        raise HTTPException(503, 'Unable to load notifications. Please try again.') from error
    today = date.today()

    # 2. Unread Teacher remarks (new ticket messages of type TEACHER not yet read)
    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()

    # 3. Recent class notices (is_read tracked client-side via localStorage)
    if student:
    
        class_info = db.query(ClassMaster).filter(ClassMaster.class_id == student.class_id).first()
        class_name = class_info.class_name if class_info else None
        notice_q = db.query(NoticeBoard)\
            .filter(NoticeBoard.notice_text.isnot(None))\
            .filter(NoticeBoard.notice_text != '')
        if class_name:
            notice_q = notice_q.filter(
                or_(
                    NoticeBoard.applicable_class == class_name,
                    NoticeBoard.applicable_class == 'All',
                    NoticeBoard.applicable_class.is_(None),
                )
            )
        notices = notice_q.order_by(NoticeBoard.created_at.desc()).limit(5).all()
        for n in notices:
            notifications.append(NotificationSchema(
                id=f"not_{n.notice_id}",
                type="announcement",
                title=n.notice_title or "New Notice",
                message=(n.notice_text[:80] + "…") if n.notice_text and len(n.notice_text) > 80 else (n.notice_text or ""),
                date=n.created_at.isoformat() if n.created_at else today.isoformat(),
                is_read=False,  # read state tracked client-side
                link=f"/parent/notices?open={n.notice_id}",
            ))

    notifications.sort(key=lambda x: x.date, reverse=True)
    return notifications[:10]


# ── DISABLED: Attendance Endpoints ────────────────────────────────────────
# The Attendance module has been fully removed from the parent portal.
# These four routes (GET /attendance/{student_id},
# POST /attendance/leave-request, GET /attendance/leave-requests/{student_id},
# PATCH /attendance/leave-request/{leave_request_id}) have no frontend callers.
#
# The underlying DB tables (attendance_master, leave_requests) remain intact.
# The AttendanceMaster and LeaveRequest models in models.py are preserved.
# The schemas (AttendanceDaySchema, AttendanceOverviewSchema, AttendanceDataResponse,
# LeaveRequestCreate, LeaveRequestResponse, LeaveStatusUpdate) are disabled in
# schemas.py. The API helpers are disabled in frontend/src/lib/api.ts.
#
# Leave requests now exist ONLY as a Communication Center category/workflow
# routed through /comm/ (routers/communication.py).
#
# To restore the standalone attendance module, uncomment:
#   - These endpoints
#   - AttendanceMaster, LeaveRequest imports at the top of this file
#   - The corresponding schemas in schemas.py
#   - The API helpers in frontend/src/lib/api.ts
#   - The attendance page: frontend/src/app/parent/attendance/page.tsx
# ──────────────────────────────────────────────────────────────────────────
#
# @router.get("/attendance/{student_id}", response_model=AttendanceDataResponse)
# def get_attendance(student_id: int, db: Session = Depends(get_db)):
#     ... (full implementation preserved in git history)
#
# @router.post("/attendance/leave-request", response_model=LeaveRequestResponse)
# def create_leave_request(request: LeaveRequestCreate, db: Session = Depends(get_db)):
#     ... (full implementation preserved in git history)
#
# @router.get("/attendance/leave-requests/{student_id}", response_model=List[LeaveRequestResponse])
# def get_leave_requests(student_id: int, db: Session = Depends(get_db)):
#     ... (full implementation preserved in git history)
#
# @router.patch("/attendance/leave-request/{leave_request_id}", response_model=LeaveRequestResponse)
# def update_leave_status(leave_request_id: int, update: LeaveStatusUpdate, db: Session = Depends(get_db)):
#     ... (full implementation preserved in git history)
# ──────────────────────────────────────────────────────────────────────────

