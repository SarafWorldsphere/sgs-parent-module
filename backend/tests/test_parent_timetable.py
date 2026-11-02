"""No real database or startup hooks are used by these endpoint tests."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from routers import timetable


class ParentTimetableTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        app = FastAPI()
        app.include_router(timetable.router)
        self.app = app
        app.dependency_overrides[timetable.get_db] = lambda: self.db
        app.dependency_overrides[timetable.get_current_parent_or_demo] = lambda: SimpleNamespace(parent_id=7)
        self.client = TestClient(app)
        self.student = SimpleNamespace(student_id=8, class_id=6, section="A", full_name="Child")
        self.school_class = SimpleNamespace(section_name="A", academic_year="2026-2027", class_name="Class 6")
        self.db.query.return_value.filter.return_value.first.side_effect = [self.student, self.school_class]

    def test_unlinked_child_is_rejected_before_timetable_query(self):
        with patch.object(timetable, "verify_student_ownership", side_effect=HTTPException(403, "Access denied.")):
            self.assertEqual(self.client.get('/timetable/999').status_code, 403)
        self.db.execute.assert_not_called()

    def test_missing_mapping_does_not_read_schedule(self):
        self.student.class_id = None
        with patch.object(timetable, "verify_student_ownership"):
            self.assertEqual(self.client.get('/timetable/8').status_code, 409)
        self.db.execute.assert_not_called()

    def test_real_ownership_check_rejects_another_parents_child(self):
        self.db.query.return_value.filter.return_value.first.side_effect = [None]
        self.assertEqual(self.client.get('/timetable/999').status_code, 403)
        self.db.execute.assert_not_called()

    def test_real_ownership_check_rejects_inactive_child(self):
        self.db.query.return_value.filter.return_value.first.side_effect = [
            SimpleNamespace(parent_id=7, student_id=8),
            SimpleNamespace(is_active=False, record_status='Active'),
        ]
        self.assertEqual(self.client.get('/timetable/8').status_code, 403)
        self.db.execute.assert_not_called()

    def test_missing_session_is_rejected(self):
        self.app.dependency_overrides.pop(timetable.get_current_parent_or_demo)
        import auth
        with patch.object(auth, 'IS_DEV', False):
            self.assertEqual(self.client.get('/timetable/8').status_code, 401)
        self.db.execute.assert_not_called()

    def test_database_failure_is_reported_as_unavailable(self):
        from sqlalchemy.exc import SQLAlchemyError
        self.db.execute.side_effect = SQLAlchemyError('private database details')
        with patch.object(timetable, 'verify_student_ownership'):
            response = self.client.get('/timetable/8')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private database details', response.text)

    def test_slots_are_scoped_and_breaks_have_no_subjects(self):
        periods = [dict(period_id=1, period_no=1, period_label="Period 1", is_teaching=True),
                   dict(period_id=2, period_no=2, period_label="Break", is_teaching=False)]
        slots = [dict(period_no=1, day_of_week=1, subject_name="Maths"),
                 dict(period_no=2, day_of_week=1, subject_name="Ignored break slot")]
        results = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        results[0].scalars.return_value = ["2026-2027"]
        results[1].scalars.return_value = ["full"]
        results[2].mappings.return_value = periods
        results[3].mappings.return_value.all.return_value = slots
        self.db.execute.side_effect = results
        with patch.object(timetable, "verify_student_ownership") as ownership:
            response = self.client.get('/timetable/8')
        self.assertEqual(response.status_code, 200, response.text)
        ownership.assert_called_once()
        data = response.json()
        self.assertEqual(len(data['days']), 6)
        self.assertEqual(len(data['days'][0]['slots']), 1)
        self.assertEqual(data['days'][1]['slots'], [])
        params = self.db.execute.call_args.args[1]
        self.assertEqual((params['class_id'], params['section']), (6, 'A'))
        self.assertTrue(data['has_slots'])

    def test_empty_periods_do_not_invent_free_slots(self):
        days = timetable.build_days([], [dict(period_no=1, day_of_week=1)])
        self.assertFalse(any(day['slots'] for day in days))


if __name__ == '__main__':
    unittest.main()
