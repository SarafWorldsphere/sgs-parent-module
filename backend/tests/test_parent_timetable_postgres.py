"""Exercise timetable SQL with temporary tables in an explicitly local test DB."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import timetable

URL = os.environ.get('PARENT_TIMETABLE_TEST_DATABASE_URL')


@unittest.skipUnless(URL, 'Set PARENT_TIMETABLE_TEST_DATABASE_URL to a local test database')
class TimetablePostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in ('localhost', '127.0.0.1') or url.database != 'student_timetable_test':
            self.fail('This test only permits the local student_timetable_test database')
        self.engine = create_engine(url)
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.connection.close)
        self.addCleanup(self.transaction.rollback)
        self.prefix = getattr(timetable, 'DB_PREFIX', '')
        # The SaaS snapshot has no record_status on these three tables.
        audit = ', record_status text DEFAULT \'Active\'' if hasattr(timetable, 'DB_PREFIX') else ''
        ddl = {
            'period_master': 'period_id bigint, academic_year text, schedule_type text, period_no int, period_label text, start_time time, end_time time, is_teaching boolean',
            'timetable': 'timetable_id bigint, academic_year text, class_id bigint, section text, day_of_week int, period_no int, subject_name text, teacher_id text',
            'teacher_master': 'teacher_id bigint, full_name text',
        }
        for name, fields in ddl.items():
            self.connection.execute(text(f'CREATE TEMP TABLE "{self.prefix}{name}" ({fields}{audit}) ON COMMIT DROP'))
        self.connection.execute(text(f'''INSERT INTO "{self.prefix}period_master"
            (period_id,academic_year,schedule_type,period_no,period_label,start_time,end_time,is_teaching) VALUES
            (1,'2026-2027','full',1,'Period 1','09:00','09:45',true),
            (2,'2026-2027','full',2,'Break','09:45','10:00',false),
            (3,'2026-2027','half',1,'Period 1','09:00','09:30',true)'''))
        self.connection.execute(text(f'''INSERT INTO "{self.prefix}teacher_master" (teacher_id,full_name) VALUES (12,'Teacher A')'''))
        self.connection.execute(text(f'''INSERT INTO "{self.prefix}timetable"
            (timetable_id,academic_year,class_id,section,day_of_week,period_no,subject_name,teacher_id) VALUES
            (1,'2026-2027',6,' A ',1,1,'Maths','12'),
            (2,'2026-2027',6,'B',1,1,'Wrong section','12'),
            (3,'2026-2027',8,'A',1,1,'Wrong class','12'),
            (4,'2026-2027',6,'A',2,1,'Science','missing')'''))
        db = MagicMock()
        db.execute.side_effect = self.connection.execute
        db.query.return_value.filter.return_value.first.side_effect = lambda: self.child if db.query.call_args.args[0] is timetable.StudentMaster else self.school_class
        self.child = SimpleNamespace(class_id=6, section='a', full_name='Child')
        self.school_class = SimpleNamespace(section_name='A', class_name='Class 6', academic_year='2026-2027')
        app = FastAPI()
        app.include_router(timetable.router)
        app.dependency_overrides[timetable.get_db] = lambda: db
        app.dependency_overrides[timetable.get_current_parent_or_demo] = lambda: SimpleNamespace(parent_id=7)
        self.client = TestClient(app)
        mock = patch.object(timetable, 'verify_student_ownership')
        mock.start()
        self.addCleanup(mock.stop)

    def test_class_section_teacher_and_half_day_queries(self):
        response = self.client.get('/timetable/8?schedule_type=half')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data['periods']), 1)
        self.assertEqual(data['periods'][0]['end_time'], '09:30:00')
        self.assertEqual([s['subject_name'] for d in data['days'] for s in d['slots']], ['Maths', 'Science'])
        self.assertEqual(data['days'][0]['slots'][0]['teacher_name'], 'Teacher A')
        self.assertIsNone(data['days'][1]['slots'][0]['teacher_name'])

    def test_unpublished_and_unknown_year(self):
        self.child.section = 'Z'
        response = self.client.get('/timetable/8')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['has_slots'])
        self.assertTrue(all(not d['slots'] for d in response.json()['days']))
        self.assertEqual(self.client.get('/timetable/8?academic_year=1999').status_code, 404)


if __name__ == '__main__':
    unittest.main()
