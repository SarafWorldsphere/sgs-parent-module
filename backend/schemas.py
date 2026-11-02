from pydantic import BaseModel, Field, ConfigDict, validator
from typing import List, Optional
from datetime import date, datetime
from urllib.parse import urlparse

_ALLOWED_GOOGLE_HOSTS = frozenset({'drive.google.com', 'docs.google.com'})

def _validate_google_drive_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Please enter a valid Google Drive link.")
    if parsed.scheme != 'https':
        raise ValueError("Please enter a valid Google Drive link.")
    if parsed.hostname not in _ALLOWED_GOOGLE_HOSTS:
        raise ValueError("Please enter a valid Google Drive link.")
    p = parsed.path
    import re
    valid = (
        re.match(r'^/file/d/[^/]+', p) or
        re.match(r'^/drive/folders/[^/]+', p) or
        (re.match(r'^/open$', p) and 'id=' in (parsed.query or '')) or
        re.match(r'^/document/d/[^/]+', p) or
        re.match(r'^/spreadsheets/d/[^/]+', p) or
        re.match(r'^/presentation/d/[^/]+', p)
    )
    if not valid:
        raise ValueError("Please enter a valid Google Drive link.")
    return url

class StudentSchema(BaseModel):
    student_id: int
    full_name: str
    class_name: str = Field(alias="class")
    section: str
    roll_no: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class AssignmentSchema(BaseModel):
    assignment_id: Optional[int] = None
    assignment_title: str
    assignment_text: Optional[str] = None
    subject: str
    chapter_name: Optional[str] = None
    teacher_name: Optional[str] = None
    teacher_user_id: Optional[int] = None
    due_date: str
    status: str
    marks_obtained: Optional[float] = None
    total_marks: Optional[float] = None
    submitted_at: Optional[str] = None
    submission_text: Optional[str] = None
    teacher_remarks: Optional[str] = None
    file_path: Optional[str] = None

class AttachmentResponse(BaseModel):
    file_name: str
    url: str

class AssignmentSubmitRequest(BaseModel):
    assignment_id: int
    student_id: int
    submission_text: str
    file_path: Optional[str] = None

    @validator('file_path', pre=True, always=True)
    @classmethod
    def validate_file_path(cls, v):
        if v is None or v == '':
            return v
        return _validate_google_drive_url(v)

class AssignmentAnalyticsResponse(BaseModel):
    total: int
    submitted: int
    pending: int
    overdue: int
    graded: int
    completion_pct: float

class QuizSchema(BaseModel):
    subject: str
    score: str
    total: str

class QuizDetailResponse(QuizSchema):
    quiz_id: int
    quiz_title: str
    percentage: float
    teacher_name: str
    remarks: str
    quiz_date: str
    status: str
    suggestion: str

class RemarkSchema(BaseModel):
    remark_id: int
    teacher_name: str
    subject: Optional[str] = "General"
    comment: str
    date: str
    ticket_id: Optional[int] = None
    is_read: bool = False

class NoticeSchema(BaseModel):
    notice_id: int
    notice_title: str
    notice_text: str
    notice_date: str
    applicable_class: str
    posted_by_name: str
    is_read: bool = False

# ── DISABLED: Old chat system schemas ─────────────────────────────────────
# These belonged to the /chat/ thread-based messaging system (ChatThread +
# ChatMessage models). That system was replaced by the /comm/ Communication
# Center (SupportTicket + TicketMessage repurposed). Safe to restore if
# the old chat system is ever revived.
#
# class ChatMessageCreate(BaseModel):
#     thread_id: int
#     sender_type: str
#     sender_id: int
#     message: str
#     translated_message: Optional[str] = None
#
# class ChatMessageSchema(BaseModel):
#     id: int
#     thread_id: int
#     sender_type: str
#     sender_id: int
#     message: str
#     translated_message: Optional[str] = None
#     created_at: str
#     is_read: bool
#
# class ChatThreadSchema(BaseModel):
#     id: int
#     teacher_id: int
#     teacher_name: str
#     student_id: int
#     student_name: str
#     created_at: str
#     latest_message: Optional[ChatMessageSchema] = None
#     unread_count: int = 0
# ──────────────────────────────────────────────────────────────────────────

# ── DISABLED: Communication timeline schema ────────────────────────────────
# Used by GET /communication/timeline/{student_id} which has no frontend
# caller. The new Communication Center uses /comm/ routes instead.
# Restore if a timeline view is added back to the frontend.
#
# class TimelineItemSchema(BaseModel):
#     id: str
#     type: str # "Announcement", "PTM Request", "Parent Note", "Teacher Remark"
#     title: str
#     message: str
#     date: str
#     author: str
# ──────────────────────────────────────────────────────────────────────────

class EventSchema(BaseModel):
    title: str
    description: str
    event_date: str
    event_type: str

class ChatMessageSchema(BaseModel):
    id: int
    thread_id: int
    sender_type: str
    sender_id: int
    message: str
    translated_message: Optional[str] = None
    created_at: str
    is_read: bool

class TimelineItemSchema(BaseModel):
    id: str
    type: str # "Announcement", "PTM Request", "Parent Note", "Teacher Remark"
    title: str
    message: str
    date: str
    author: str

class ChatThreadSchema(BaseModel):
    id: int
    teacher_id: int
    teacher_name: str
    student_id: int
    student_name: str
    created_at: str
    latest_message: Optional[ChatMessageSchema] = None
    unread_count: int = 0

class DailySummarySchema(BaseModel):
    assignments_pending: int
    notices_today: int
    upcoming_quizzes: int

class PerformanceSummarySchema(BaseModel):
    improvement_percent: str
    strongest_subject: str
    weakest_subject: str
    avg_score: Optional[float] = None

class AttendanceTrendSchema(BaseModel):
    percentage: str
    trend: str # e.g. "up", "down", "stable"
    monthly_data: List[dict] # { "month": "Jan", "present": 20, "absent": 2 }

class AlertSchema(BaseModel):
    type: str  # warning, info, success, error
    message: str
    priority: Optional[str] = None   # HIGH, MEDIUM, LOW
    subject: Optional[str] = None
    due: Optional[str] = None

class AcademicHealthSchema(BaseModel):
    status: str
    description: str

class EngagementIndicatorSchema(BaseModel):
    score: int
    level: str
    description: str

class DeadlineSchema(BaseModel):
    title: str
    type: str
    due_date: str
    days_left: int

# ── DISABLED: Old support-ticket API schemas ───────────────────────────────
# These served the /tickets/ CRUD routes (GET /tickets/{parent_id}/{student_id},
# POST /tickets, GET /tickets/{ticket_id}/messages, etc.) which were the
# original customer-support style system. That system was replaced by the
# /comm/ Communication Center. The underlying DB tables (support_tickets,
# ticket_messages) are still active — repurposed by the /comm/ router.
# Restore these schemas if the old /tickets/ routes are ever re-enabled.
#
# class TicketMessageSchema(BaseModel):
#     message_id: int
#     ticket_id: int
#     sender_type: str
#     sender_name: str
#     message: str
#     created_at: str
#     is_read: bool
#
# class SupportTicketSchema(BaseModel):
#     ticket_id: int
#     ticket_number: str
#     parent_id: int
#     student_id: int
#     subject: str
#     category: str
#     priority: str
#     status: str
#     created_at: str
#     updated_at: str
#     latest_message: Optional[TicketMessageSchema] = None
#
# class TicketCreateSchema(BaseModel):
#     parent_id: int
#     student_id: int
#     subject: str
#     category: str
#     priority: str
#     message: str
#
# class TicketMessageCreateSchema(BaseModel):
#     ticket_id: int
#     sender_type: str
#     sender_name: str
#     message: str
# ──────────────────────────────────────────────────────────────────────────

class NotificationSchema(BaseModel):
    id: str
    type: str # 'ticket_reply', 'announcement', 'ptm_update'
    title: str
    message: str
    date: str
    is_read: bool
    link: str

class WeeklyProgressSchema(BaseModel):
    trend_percentage: str
    description: str

class SmartRecommendationSchema(BaseModel):
    type: str
    message: str
    action_text: str

class ClassRankSchema(BaseModel):
    percentile: str
    description: str

class SubjectPerformanceData(BaseModel):
    subject: str
    score: float
    class_average: float

class DashboardResponse(BaseModel):
    student: StudentSchema
    assignments: List[AssignmentSchema] = []
    quiz: List[QuizSchema] = []
    remarks: List[RemarkSchema] = []
    notices: List[NoticeSchema] = []
    call_requests: List['CallRequestResponse'] = []
    attendance_trend: Optional[AttendanceTrendSchema] = None
    performance_summary: Optional[PerformanceSummarySchema] = None
    subject_performance: List[SubjectPerformanceData] = []
    upcoming_events: List[EventSchema] = []
    daily_summary: Optional[DailySummarySchema] = None
    alerts: List[AlertSchema] = []
    motivational_message: Optional[str] = None
    academic_health: Optional[AcademicHealthSchema] = None
    engagement_indicator: Optional[EngagementIndicatorSchema] = None
    upcoming_deadlines: List[DeadlineSchema] = []
    health_score: Optional[int] = None
    smart_recommendations: List[SmartRecommendationSchema] = []
    academic_streak: List[str] = []
    attendance_heat: Optional[str] = None
    weekly_progress: Optional[WeeklyProgressSchema] = None
    class_rank: Optional[ClassRankSchema] = None
    notifications: List['NotificationSchema'] = []
    assignment_completion_pct: Optional[float] = None
    action_required_count: Optional[int] = None

# ── DISABLED: Analytics module response schema ─────────────────────────────
# Used by GET /analytics/{student_id} and analytics_service.py. The entire
# Analytics page (/parent/analytics) was removed from the frontend. The
# backend route is also disabled. Restore both if an analytics module is
# re-introduced. analytics_service.py is preserved on disk as a reference.
#
# class AnalyticsResponse(BaseModel):
#     student: StudentSchema
#     subject_performance: List[SubjectPerformanceData]
#     monthly_trends: List[dict]
#     assignment_completion: dict
#     attendance_heatmap: List[dict]
#     strongest_subject: str
#     weakest_subject: str
#     growth_percent: str
# ──────────────────────────────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str
    target_lang: str

class TranslateResponse(BaseModel):
    translated_text: str
    original_text: str

class CallRequestCreate(BaseModel):
    parent_id: int
    student_id: int
    message: str

class CallRequestResponse(BaseModel):
    id: int
    message: str
    status: str
    created_at: str
    teacher_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class MappedChildSchema(BaseModel):
    student_id: int
    full_name: str
    class_name: str
    section: str

    model_config = ConfigDict(from_attributes=True)

# ── DISABLED: Attendance Module Schemas ───────────────────────────────────
# These schemas served the attendance endpoints in routers/dashboard.py:
#   GET  /attendance/{student_id}
#   POST /attendance/leave-request
#   GET  /attendance/leave-requests/{student_id}
#   PATCH /attendance/leave-request/{leave_request_id}
# All four endpoints are now commented out. The attendance module has been
# fully removed from the parent portal. Leave requests now exist only as a
# Communication Center category (routers/communication.py).
# DB tables (attendance_master, leave_requests) are preserved for rollback.
# Restore this block together with the endpoints in routers/dashboard.py.
#
# class AttendanceDaySchema(BaseModel):
#     date: str
#     status: str  # Present, Absent, HalfDay, Holiday
#
# class AttendanceOverviewSchema(BaseModel):
#     percentage: float
#     present_days: int
#     absent_days: int
#     half_days: int
#     total_school_days: int
#
# class AttendanceDataResponse(BaseModel):
#     overview: AttendanceOverviewSchema
#     records: List[AttendanceDaySchema]
#
# class LeaveRequestCreate(BaseModel):
#     student_id: int
#     parent_id: int
#     from_date: date
#     to_date: date
#     reason: str
#     parent_note: Optional[str] = None
#
# class LeaveRequestResponse(BaseModel):
#     leave_request_id: int
#     student_id: int
#     from_date: str
#     to_date: str
#     reason: str
#     parent_note: Optional[str] = None
#     status: str
#     created_at: str
#     model_config = ConfigDict(from_attributes=True)
#
# class LeaveStatusUpdate(BaseModel):
#     status: str  # Approved or Rejected
#     reviewed_by: int
# ──────────────────────────────────────────────────────────────────────────

# ── Communication Module ───────────────────────────────────────────────────

class TeacherOptionSchema(BaseModel):
    teacher_id: Optional[int] = None
    name: str
    role: str

class ConversationSummarySchema(BaseModel):
    conv_id: int
    subject: str
    category: str
    recipient_name: str
    status: str
    created_at: str
    updated_at: str
    latest_message: Optional[str] = None
    latest_message_time: Optional[str] = None
    latest_sender: Optional[str] = None
    unread_count: int = 0

class ConversationMessageSchema(BaseModel):
    message_id: int
    conv_id: int
    sender_type: str   # PARENT or TEACHER
    sender_name: str
    message: str
    created_at: str
    is_read: bool

class CreateConversationSchema(BaseModel):
    student_id: int
    parent_id: int
    subject: str
    category: str
    recipient_name: str
    # The teacher_id the recipient picker already returns — a users_masters
    # user_id. Optional so an older client that sends only the name keeps
    # working; without it the conversation cannot be routed to a teacher.
    recipient_user_id: Optional[int] = None
    first_message: str

class SendConversationMessageSchema(BaseModel):
    sender_type: str   # PARENT or TEACHER
    sender_name: str
    message: str


# ── Assessment Module ──────────────────────────────────────────────────────────

class AssessmentResultSchema(BaseModel):
    result_id:         int
    assessment_id:     int
    title:             str
    assessment_type:   str
    subject:           str
    chapter_name:      str
    teacher_name:      str
    assessment_date:   str   # "15 Jan 2025" — display
    date_iso:          str   # "2025-01-15"   — used by frontend for filter math
    marks_obtained:    float
    max_marks:         float
    percentage:        float
    performance_badge: str   # Excellent | Good | Average | Needs Improvement


class AssessmentTrendPoint(BaseModel):
    date:       str
    percentage: float
    label:      str   # short x-axis label: "15 Jan"


class AssessmentSubjectSlice(BaseModel):
    subject:        str
    avg_percentage: float


class AssessmentAnalyticsResponse(BaseModel):
    total_assessments:  int
    average_percentage: float
    highest_score:      float
    lowest_score:       float
    trend_data:         List[AssessmentTrendPoint]
    subject_data:       List[AssessmentSubjectSlice]
    subjects:           List[str]

