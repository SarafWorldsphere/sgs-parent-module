"""
SQLAlchemy ORM models — Parent Dashboard

Alignment strategy
──────────────────
• Table names are unprefixed. Row-level security isolates each school.

• Column aliasing:  attr = Column('rds_col_name', Type, …)
  Maps the physical RDS column name to the existing Python
  attribute name so backend routes, Pydantic schemas, service
  math and React JSON keys are all unchanged.

• BigInteger IDs promoted only where the RDS schema uses bigint.
  Integer stays where RDS explicitly keeps integer
  (parent_master, support_tickets PKs, ticket_messages PK).

• Audit columns (record_status, version_no, modified_datetime, …)
  added as nullable=True — zero impact on existing rows.

• Columns that existed in the physical DB but were absent from the
  prior model (admission_no, subject_code, chapter_no, …) are now
  declared so the ORM can read/write them correctly.

• Production FK alignment (v004):
  subject_master.teacher_id, class_master.class_teacher_id,
  assignment_master.assigned_by, and notice_board.posted_by
  all reference users_masters.user_id, not teacher_master.
  UsersMaster is therefore the FK root for teacher-type lookups.
"""

from sqlalchemy import (
    Column, Integer, BigInteger, String, Numeric,
    ForeignKey, TIMESTAMP, Date, Text, Boolean, DateTime,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


# ── 0. UsersMaster ───────────────────────────────────────────────────────────
# Production table: users_masters  (note the plural suffix)
# Every teacher / staff member is a USER FIRST.  The FK columns
#   subject_master.teacher_id
#   class_master.class_teacher_id
#   assignment_master.assigned_by
#   notice_board.posted_by
# all reference users_masters.user_id, not teacher_master.teacher_id.
#
# role_id is a plain column. The kit has roles, and this model does not
# declare that foreign key. school_id is a plain column. The kit has no schools table.

class UsersMaster(Base):
    __tablename__ = "users_masters"

    user_id       = Column(BigInteger, primary_key=True, index=True)
    login_id      = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(Text, nullable=True)
    full_name     = Column(String, index=True)
    # Physical RDS column is 'email_id' — aliased to 'email' for consistency
    # with TeacherMaster, so service/route code uses the same attribute name.
    email         = Column('email_id', String, nullable=True)
    mobile_no     = Column(String, nullable=True)  # VARCHAR on RDS
    # No FK constraints here. roles is not linked, and the kit has no schools table.
    role_id       = Column(BigInteger, nullable=True)
    school_id     = Column(BigInteger, nullable=True)
    is_active     = Column(Boolean, nullable=True)
    # Audit
    created_datetime  = Column(TIMESTAMP, nullable=True)
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)


# ── 1. ClassMaster ────────────────────────────────────────────────────────────

class ClassMaster(Base):
    __tablename__ = "class_master"

    class_id         = Column(BigInteger, primary_key=True, index=True)
    # school_id: plain column. The kit has no schools table.
    school_id        = Column(BigInteger, nullable=True)
    class_name       = Column(String, index=True)
    section_name     = Column(String)
    academic_year    = Column(String)
    # FK target corrected: production references users_masters.user_id,
    # not teacher_master.teacher_id.  Nullable so the column can be NULL
    # before teacher users are seeded.
    class_teacher_id = Column(BigInteger, ForeignKey("users_masters.user_id"), nullable=True)
    # Audit
    created_datetime  = Column(TIMESTAMP, nullable=True)
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)


# ── 2. StudentMaster ──────────────────────────────────────────────────────────

class StudentMaster(Base):
    __tablename__ = "student_master"

    student_id     = Column(BigInteger, primary_key=True, index=True)
    # admission_no was in the physical DB but missing from the prior model
    admission_no   = Column(String, nullable=True)
    full_name      = Column(String, index=True)
    class_id       = Column(BigInteger, ForeignKey("class_master.class_id"), index=True)
    section        = Column(String)
    roll_no        = Column(String)
    # RDS enrichment fields
    student_phone  = Column(String, nullable=True)
    student_email  = Column(String, nullable=True)
    guardian_name  = Column(String, nullable=True)
    guardian_phone = Column(String, nullable=True)
    guardian_email = Column(String, nullable=True)
    is_active      = Column(Boolean, nullable=True)
    # Audit
    created_datetime  = Column(TIMESTAMP, nullable=True)
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)

    class_info = relationship("ClassMaster")


# ── 3. ParentMaster ───────────────────────────────────────────────────────────
# parent_master matches the kit column names.

class ParentMaster(Base):
    __tablename__ = "parent_master"

    parent_id     = Column(Integer, primary_key=True, index=True)
    full_name     = Column(String)
    email         = Column(String, index=True)
    phone         = Column(String)
    profile_image = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── 4. ParentStudentMap ───────────────────────────────────────────────────────
# RDS schema matches local — student_id promoted to bigint locally for FK
# consistency with student_master.student_id (bigint).

class ParentStudentMap(Base):
    __tablename__ = "parent_student_map"

    id                = Column(Integer, primary_key=True, index=True)
    parent_id         = Column(Integer, ForeignKey("parent_master.parent_id"), index=True)
    student_id        = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
    relationship_type = Column(String)

    parent_info  = relationship("ParentMaster")
    student_info = relationship("StudentMaster")


# ── 5. TeacherMaster ──────────────────────────────────────────────────────────

class TeacherMaster(Base):
    __tablename__ = "teacher_master"

    teacher_id = Column(BigInteger, primary_key=True, index=True)
    full_name  = Column(String, index=True)

    # Physical RDS column is 'email_id'; Python attr stays 'email'
    # so all backend code and API responses are unchanged.
    email      = Column('email_id', String)

    # phone is BIGINT on teacher_master.
    # Model changed from String → BigInteger to match RDS exactly.
    # Seed script generates 10-digit integers (9_000_000_000 – 9_999_999_999).
    # Local PostgreSQL column is VARCHAR — PostgreSQL silently casts an integer
    # literal to varchar on INSERT, and SQLAlchemy coerces the returned varchar
    # back to int on SELECT, so both local and RDS work correctly.
    phone      = Column(BigInteger, nullable=True)

    # These columns existed in the physical DB but were absent from model
    subject_name = Column(String, nullable=True)
    class_id     = Column(BigInteger, nullable=True)   # no FK — local usage only
    section_1    = Column(String, nullable=True)
    section_2    = Column(String, nullable=True)
    role         = Column(String, nullable=True)
    # RDS addition
    is_active    = Column(Boolean, nullable=True)
    created_at   = Column(TIMESTAMP, nullable=True)


# ── 6. SubjectMaster ──────────────────────────────────────────────────────────

class SubjectMaster(Base):
    __tablename__ = "subject_master"

    subject_id   = Column(BigInteger, primary_key=True, index=True)
    class_id     = Column(BigInteger, ForeignKey("class_master.class_id"))
    subject_name = Column(String)
    # subject_code was in the physical DB but missing from prior model
    subject_code = Column(String, nullable=True)
    # FK target corrected: subject_master.teacher_id references
    # users_masters.user_id, not teacher_master.teacher_id.
    teacher_id   = Column(BigInteger, ForeignKey("users_masters.user_id"), nullable=True)
    # Audit
    created_datetime  = Column(TIMESTAMP, nullable=True)
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)


# ── 7. ChapterMaster ──────────────────────────────────────────────────────────

class ChapterMaster(Base):
    __tablename__ = "chapter_master"

    chapter_id = Column(BigInteger, primary_key=True, index=True)
    subject_id = Column(BigInteger, ForeignKey("subject_master.subject_id"), index=True)
    # chapter_no and chapter_description were in DB but missing from prior model
    chapter_no          = Column(Integer, nullable=True)
    chapter_name        = Column(String)
    chapter_description = Column(Text, nullable=True)
    chapter_order       = Column(Integer)
    # Audit
    created_datetime  = Column(TIMESTAMP, nullable=True)
    created_user_id   = Column(String, nullable=True)
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)

    subject_info = relationship("SubjectMaster")


# ── 8. AssignmentMaster ───────────────────────────────────────────────────────

class AssignmentMaster(Base):
    __tablename__ = "assignment_master"

    assignment_id    = Column(BigInteger, primary_key=True, index=True)
    chapter_id       = Column(BigInteger, ForeignKey("chapter_master.chapter_id"), index=True)
    assignment_title = Column(String)
    assignment_text  = Column(Text)
    due_date         = Column(Date)
    # FK target corrected: assignment_master.assigned_by
    # references users_masters.user_id, not teacher_master.teacher_id.
    assigned_by      = Column(BigInteger, ForeignKey("users_masters.user_id"), nullable=True)

    # Physical RDS column is 'created_datetime'; Python attr stays 'created_at'
    # preserving all service, schema, and frontend references unchanged.
    created_at = Column('created_datetime', TIMESTAMP, default=datetime.utcnow)

    # Full audit set required by RDS
    created_user_id     = Column(String, nullable=True)
    created_ip_address  = Column(String, nullable=True)
    modified_datetime   = Column(TIMESTAMP, nullable=True)
    modified_user_id    = Column(String, nullable=True)
    modified_ip_address = Column(String, nullable=True)
    record_status       = Column(String, nullable=True)
    version_no          = Column(Integer, nullable=True)

    chapter_info = relationship("ChapterMaster")


# ── 9. StudentSubmission ──────────────────────────────────────────────────────

class StudentSubmission(Base):
    __tablename__ = "student_submission"

    submission_id   = Column(BigInteger, primary_key=True, index=True)
    assignment_id   = Column(BigInteger, ForeignKey("assignment_master.assignment_id"))
    student_id      = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
    submission_text = Column(Text)
    file_path       = Column(Text)
    marks_obtained  = Column(Numeric(5, 2))
    teacher_remarks = Column(Text)
    # submitted_at kept as-is — RDS also carries this field alongside created_datetime
    submitted_at      = Column(TIMESTAMP, default=datetime.utcnow)
    # Audit
    created_datetime  = Column(TIMESTAMP, nullable=True)
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)

    assignment_info = relationship("AssignmentMaster")


# ── 10. QuizMaster ────────────────────────────────────────────────────────────

class QuizMaster(Base):
    __tablename__ = "quiz_master"

    quiz_id          = Column(BigInteger, primary_key=True, index=True)
    chapter_id       = Column(BigInteger, ForeignKey("chapter_master.chapter_id"), index=True)
    quiz_title       = Column(String)
    total_marks      = Column(Integer)
    duration_minutes = Column(Integer)

    # Physical RDS column is 'created_datetime'; Python attr stays 'created_at'
    created_at = Column('created_datetime', TIMESTAMP, default=datetime.utcnow)

    # Audit
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)

    chapter_info = relationship("ChapterMaster")


# ── 11. QuizResponse ──────────────────────────────────────────────────────────

class QuizResponse(Base):
    __tablename__ = "quiz_response"

    response_id    = Column(BigInteger, primary_key=True, index=True)
    quiz_id        = Column(BigInteger, ForeignKey("quiz_master.quiz_id"))
    student_id     = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
    score          = Column(Numeric(5, 2))
    completed_flag = Column(Boolean, default=False)
    # Audit
    created_datetime  = Column(TIMESTAMP, nullable=True)
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)

    quiz_info = relationship("QuizMaster")


# ── 12. NoticeBoard ───────────────────────────────────────────────────────────

class NoticeBoard(Base):
    __tablename__ = "notice_board"

    notice_id        = Column(BigInteger, primary_key=True, index=True)
    notice_title     = Column(String(200))
    notice_text      = Column(Text)
    notice_date      = Column(Date)
    applicable_class = Column(String(50))
    # FK target corrected: notice_board.posted_by references
    # users_masters.user_id, not teacher_master.teacher_id.
    posted_by        = Column(BigInteger, ForeignKey("users_masters.user_id"), nullable=True)

    # Physical RDS column is 'created_datetime'; Python attr stays 'created_at'
    # dashboard_service.py uses NoticeBoard.created_at and notice.created_at —
    # both still resolve correctly via SQLAlchemy's key/name aliasing.
    created_at = Column('created_datetime', TIMESTAMP, default=datetime.utcnow)

    # Audit
    modified_datetime = Column(TIMESTAMP, nullable=True)
    record_status     = Column(String, nullable=True)
    version_no        = Column(Integer, nullable=True)

    # teacher_info relationship removed — posted_by now FKs to users_masters,
    # not teacher_master.  Dashboard queries do explicit outerjoin on UsersMaster.


# ── 13. SupportTicket ─────────────────────────────────────────────────────────
# support_tickets matches the kit. recipient_name is already on that table.
# student_id promoted to BigInteger locally for FK constraint consistency.

class SupportTicket(Base):
    __tablename__ = "support_tickets"

    ticket_id      = Column(Integer, primary_key=True, index=True)
    ticket_number  = Column(String, unique=True, index=True)
    parent_id      = Column(Integer, ForeignKey("parent_master.parent_id"), index=True)
    student_id     = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
    subject        = Column(String)
    category       = Column(String)
    priority       = Column(String)
    status         = Column(String, default="OPEN")
    recipient_name = Column(String, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent_info  = relationship("ParentMaster")
    student_info = relationship("StudentMaster")


# ── 14. TicketMessage ─────────────────────────────────────────────────────────
# ticket_messages matches the kit.

class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    message_id  = Column(Integer, primary_key=True, index=True)
    ticket_id   = Column(Integer, ForeignKey("support_tickets.ticket_id"), index=True)
    sender_type = Column(String)
    sender_name = Column(String)
    message     = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow)
    is_read     = Column(Boolean, default=False)

    ticket_info = relationship("SupportTicket")


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY MODELS  —  preserved as comments; excluded from Base.metadata.create_all
# ══════════════════════════════════════════════════════════════════════════════

# ── CallRequest ───────────────────────────────────────────────────────────────
# Replaced by Communication Center (SupportTicket category).
# Restore by un-commenting and re-enabling routes.
#
# class CallRequest(Base):
#     __tablename__ = "call_requests"
#     id = Column(Integer, primary_key=True, index=True)
#     parent_id = Column(Integer, ForeignKey("parent_master.parent_id"), index=True)
#     student_id = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
#     teacher_id = Column(BigInteger, ForeignKey("teacher_master.teacher_id"), nullable=True)
#     message = Column(Text)
#     status = Column(String, default="pending")
#     created_at = Column(DateTime, default=datetime.utcnow)
#     parent_info = relationship("ParentMaster")
#     student_info = relationship("StudentMaster")
#     teacher_info = relationship("TeacherMaster")

# ── AttendanceMaster ──────────────────────────────────────────────────────────
# Attendance module fully removed from parent portal.
# Restore by un-commenting and re-enabling endpoints/schemas.
#
# class AttendanceMaster(Base):
#     __tablename__ = "attendance_master"
#     attendance_id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
#     class_id = Column(BigInteger, ForeignKey("class_master.class_id"), index=True)
#     attendance_date = Column(Date)
#     status = Column(String)
#     academic_year = Column(String)
#     student_info = relationship("StudentMaster")

# ── SchoolEvent ───────────────────────────────────────────────────────────────
# Events/calendar feature not in current scope.
#
# class SchoolEvent(Base):
#     __tablename__ = "school_events"
#     event_id = Column(Integer, primary_key=True, index=True)
#     title = Column(String)
#     description = Column(Text)
#     event_date = Column(Date)
#     class_id = Column(BigInteger, ForeignKey("class_master.class_id"), nullable=True)
#     academic_year = Column(String)
#     event_type = Column(String)

# ── ChatThread / ChatMessage ──────────────────────────────────────────────────
# Thread-based chat replaced by Communication Center.
# Restore ChatThread + ChatMessage together.
#
# class ChatThread(Base):
#     __tablename__ = "chat_threads"
#     id = Column(Integer, primary_key=True, index=True)
#     parent_id = Column(Integer, ForeignKey("parent_master.parent_id"), index=True)
#     teacher_id = Column(BigInteger, ForeignKey("teacher_master.teacher_id"), index=True)
#     student_id = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     parent_info = relationship("ParentMaster")
#     teacher_info = relationship("TeacherMaster")
#     student_info = relationship("StudentMaster")
#
# class ChatMessage(Base):
#     __tablename__ = "chat_messages"
#     id = Column(Integer, primary_key=True, index=True)
#     thread_id = Column(Integer, ForeignKey("chat_threads.id"), index=True)
#     sender_type = Column(String)
#     sender_id = Column(Integer)
#     message = Column(Text)
#     translated_message = Column(Text, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     is_read = Column(Boolean, default=False)
#     thread_info = relationship("ChatThread")

# ── TeacherParentInteractionV2 ────────────────────────────────────────────────
# REMOVED FROM ACTIVE MODELS: teacher_parent_interaction is not a kit table.
# Keeping this class active would make create_all create a table the schema does not have.
#
# Remarks feature is now served by TicketMessage (sender_type='TEACHER')
# joined through SupportTicket.student_id.
#
# class TeacherParentInteractionV2(Base):
#     __tablename__ = "teacher_parent_interaction"
#     id         = Column(Integer, primary_key=True, index=True)
#     teacher_id = Column(BigInteger, ForeignKey("teacher_master.teacher_id"))
#     student_id = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
#     class_id   = Column(BigInteger, ForeignKey("class_master.class_id"))
#     section    = Column(String)
#     comments   = Column(Text)
#     created_at = Column(TIMESTAMP, default=datetime.utcnow)
#     teacher_info = relationship("TeacherMaster")
#     student_info = relationship("StudentMaster")

# ── 15. Assessment ────────────────────────────────────────────────────────────
# Mirrors assessments — column names unchanged.
# assessment_type: PostgreSQL ENUM that already exists on RDS.
# create_type=False → SQLAlchemy never attempts CREATE TYPE; it uses the
# existing type and emits the correct cast on INSERT.

class Assessment(Base):
    __tablename__ = "assessments"

    assessment_id   = Column(BigInteger, primary_key=True, index=True)
    teacher_id      = Column(BigInteger, ForeignKey("teacher_master.teacher_id"), nullable=False)
    title           = Column(String(300))
    assessment_type = Column(
        PgEnum('quiz', 'test', 'exam', 'assignment', name='assessment_type', create_type=False),
        nullable=False,
        server_default='test',
    )
    chapter_id      = Column(BigInteger, ForeignKey("chapter_master.chapter_id"), nullable=True)
    chapter         = Column(String(300), nullable=True)   # denormalized chapter name
    assessment_date = Column(Date, nullable=True)
    max_marks       = Column(Numeric(6, 2), nullable=True)
    class_name      = Column(String(10), nullable=False)
    section         = Column(String(5), nullable=False)
    total_students  = Column(Integer, nullable=True)
    submitted       = Column(Integer, nullable=True)
    class_average   = Column(Numeric(5, 2), nullable=True)
    created_at      = Column(TIMESTAMP, nullable=True)
    updated_at      = Column(TIMESTAMP, nullable=True)
    record_status   = Column(String(20), nullable=True)
    version_no      = Column(Integer, nullable=True)

    teacher_info = relationship("TeacherMaster")
    chapter_info = relationship("ChapterMaster")


# ── 16. AssessmentResult ──────────────────────────────────────────────────────
# Mirrors assessment_results — column names unchanged.

class AssessmentResult(Base):
    __tablename__ = "assessment_results"

    result_id      = Column(BigInteger, primary_key=True, index=True)
    assessment_id  = Column(BigInteger, ForeignKey("assessments.assessment_id"), index=True)
    student_id     = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
    roll_number    = Column(String(20), nullable=False)   # NOT NULL on RDS
    student_name   = Column(String(150), nullable=True)
    marks_obtained = Column(Numeric(6, 2), nullable=True)
    percentage     = Column(Numeric(5, 2), nullable=True)
    is_absent      = Column(Boolean, nullable=False, default=False)
    created_at     = Column(TIMESTAMP, nullable=True)
    updated_at     = Column(TIMESTAMP, nullable=True)
    record_status  = Column(String(20), nullable=True)
    version_no     = Column(Integer, nullable=True)

    assessment_info = relationship("Assessment")


# ── 17. FileStorageMetadata ───────────────────────────────────────────────────
# Read-only mapping of file_storage_metadata.
# Used to retrieve teacher-uploaded assignment PDFs stored in S3.
# entity_type values present on RDS: 'ASSIGNMENT_ATTACHMENT', 'CHAPTER_STUDY_MATERIAL'.
# No writes are performed via this model.

class FileStorageMetadata(Base):
    __tablename__ = "file_storage_metadata"

    file_id     = Column(BigInteger, primary_key=True, index=True)
    entity_type = Column(String(100), nullable=False)
    entity_id   = Column(BigInteger, nullable=False, index=True)
    file_name   = Column(String(200), nullable=False)
    file_url    = Column(Text, nullable=False)
    uploaded_by = Column(BigInteger, nullable=True)
    created_at  = Column(TIMESTAMP, nullable=True)
    # Audit columns — read-only, not used in queries
    record_status = Column(String(20), nullable=True)
    version_no    = Column(Integer, nullable=True)
    updated_at    = Column(TIMESTAMP, nullable=True)


# ── LeaveRequest ──────────────────────────────────────────────────────────────
# Leave requests now handled as Communication Center category.
# Restore by un-commenting and re-enabling endpoints/schemas.
#
# class LeaveRequest(Base):
#     __tablename__ = "leave_requests"
#     leave_request_id = Column(Integer, primary_key=True, index=True)
#     student_id = Column(BigInteger, ForeignKey("student_master.student_id"), index=True)
#     parent_id = Column(Integer, ForeignKey("parent_master.parent_id"), index=True)
#     from_date = Column(Date)
#     to_date = Column(Date)
#     reason = Column(String)
#     parent_note = Column(Text, nullable=True)
#     status = Column(String, default="Pending")
#     reviewed_by = Column(BigInteger, ForeignKey("teacher_master.teacher_id"), nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)
#     student_info = relationship("StudentMaster")
#     parent_info = relationship("ParentMaster")
