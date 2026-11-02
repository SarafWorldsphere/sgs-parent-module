"""Read-only timetable, scoped to the authenticated parent's linked child."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from auth import get_current_parent_or_demo, verify_student_ownership
from database import get_db
from models import ClassMaster, ParentMaster, StudentMaster

router = APIRouter(tags=["Timetable"])
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def build_days(periods, slots):
    teaching = {p["period_no"] for p in periods if p["is_teaching"]}
    days = [dict(day_of_week=i, day_name=name, slots=[]) for i, name in enumerate(DAYS, 1)]
    for slot in slots:
        if slot["period_no"] in teaching and 1 <= slot["day_of_week"] <= 6:
            days[slot["day_of_week"] - 1]["slots"].append(dict(slot))
    return days


@router.get("/timetable/{student_id}")
def get_timetable(student_id: int,
                  academic_year: str | None = Query(None, min_length=1, max_length=30),
                  schedule_type: str = Query("full", pattern="^(full|half)$"),
                  db: Session = Depends(get_db),
                  current: ParentMaster = Depends(get_current_parent_or_demo)):
    verify_student_ownership(db, current, student_id)
    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()
    school_class = db.query(ClassMaster).filter(ClassMaster.class_id == student.class_id).first()
    section = str(student.section or (school_class.section_name if school_class else "") or "").strip()
    if not student.class_id or not section:
        raise HTTPException(409, "Your child's class or section has not been assigned yet.")
    params = dict(class_id=student.class_id, section=section, schedule_type=schedule_type)
    periods_table, slots_table, teachers_table = [f'"{name}"' for name in ("period_master", "timetable", "teacher_master")]
    try:
        years = list(db.execute(text(f"""
            SELECT academic_year FROM {periods_table}
            WHERE NULLIF(TRIM(academic_year),'') IS NOT NULL
            UNION SELECT academic_year FROM {slots_table}
            WHERE class_id=:class_id AND LOWER(TRIM(section))=LOWER(:section)
            AND NULLIF(TRIM(academic_year),'') IS NOT NULL
            ORDER BY academic_year DESC"""), params).scalars())
        if academic_year and academic_year not in years:
            raise HTTPException(404, "No timetable is available for this academic year.")
        class_year = school_class.academic_year if school_class else None
        year = academic_year or (class_year if class_year in years else next(iter(years), None))
        params["year"] = year
        schedules = list(db.execute(text(f"""SELECT DISTINCT schedule_type FROM {periods_table}
            WHERE academic_year=:year
            ORDER BY schedule_type"""), params).scalars())
        periods = [dict(p) for p in db.execute(text(f"""SELECT period_id, period_no, period_label,
            start_time, end_time, is_teaching FROM {periods_table}
            WHERE academic_year=:year AND schedule_type=:schedule_type
            ORDER BY start_time, period_no"""), params).mappings()]
        slots = db.execute(text(f"""SELECT t.timetable_id, t.day_of_week, t.period_no,
            t.subject_name, t.teacher_id, teacher.full_name AS teacher_name
            FROM {slots_table} t LEFT JOIN {teachers_table} teacher
            ON CAST(teacher.teacher_id AS TEXT)=CAST(t.teacher_id AS TEXT)
            WHERE t.academic_year=:year AND t.class_id=:class_id
            AND LOWER(TRIM(t.section))=LOWER(:section)
            ORDER BY t.day_of_week, t.period_no"""), params).mappings().all()
    except SQLAlchemyError as error:
        raise HTTPException(503, "Unable to load the timetable. Please try again later.") from error
    days = build_days(periods, slots)
    has_slots = any(d["slots"] for d in days)
    return dict(student=dict(student_id=student_id, full_name=student.full_name, class_id=student.class_id,
                             class_name=school_class.class_name if school_class else ""),
                section=section, academic_year=year, academic_years=years, schedule_type=schedule_type,
                schedule_types=schedules, periods=periods, days=days, has_slots=has_slots,
                message=None if has_slots else "Your child's timetable has not been published yet.")
