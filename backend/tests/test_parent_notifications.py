"""Parent notification access tests and optional temporary PostgreSQL fixtures."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')
from routers import notifications
from services.parent_notifications import notification_history, DB_PREFIX


class NotificationAccessTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(notifications.router)
        self.db = MagicMock()
        self.app.dependency_overrides[notifications.get_db] = lambda: self.db
        self.app.dependency_overrides[notifications.get_current_parent_or_demo] = lambda: SimpleNamespace(parent_id=7)
        self.client = TestClient(self.app)

    def test_unlinked_child_is_denied_before_reading_notifications(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        self.assertEqual(self.client.get('/notification-history/9').status_code, 403)
        self.db.execute.assert_not_called()

    def test_missing_session_is_denied(self):
        import auth
        self.app.dependency_overrides.pop(notifications.get_current_parent_or_demo)
        with patch.object(auth, 'IS_DEV', False):
            self.assertEqual(self.client.get('/notification-history/9').status_code, 401)
        self.db.execute.assert_not_called()

    def test_pagination_bounds_are_validated(self):
        for query in ['limit=0', 'limit=101', 'offset=-1']:
            self.assertEqual(self.client.get('/notification-history/9?' + query).status_code, 422)

    def test_database_failure_is_not_an_empty_inbox(self):
        with patch.object(notifications, 'verify_student_ownership'), patch.object(notifications, 'notification_history', side_effect=SQLAlchemyError('sensitive details')):
            response = self.client.get('/notification-history/9')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('sensitive details', response.text)

    def test_pagination_has_more_and_authenticated_parent_scope(self):
        with patch.object(notifications, 'verify_student_ownership'), patch.object(notifications, 'notification_history', return_value=[{'id': 'a'}, {'id': 'b'}]) as read:
            response = self.client.get('/notification-history/9?limit=1&offset=2')
        self.assertEqual(response.json(), dict(items=[dict(id='a')], has_more=True))
        self.assertEqual(read.call_args.args[1:], (9, 7, 2, 2))

    def test_existing_bell_includes_teacher_alerts_and_class_notices(self):
        from datetime import datetime
        from routers import dashboard
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            SimpleNamespace(class_id=6), SimpleNamespace(class_name='Class 6')]
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(notice_id=3, notice_title='Class notice', notice_text='Notice text', created_at=datetime(2026, 11, 1))]
        alert = dict(id='teacher_1', type='teacher_notification', title='Teacher alert',
                     message='Complete message', date='2026-11-02T10:00:00', is_read=False, link='/parent/notifications')
        with patch.object(dashboard, 'verify_student_ownership'), patch('services.parent_notifications.notification_history', return_value=[alert]) as read:
            result = dashboard.get_notifications(9, db, SimpleNamespace(parent_id=7))
        self.assertEqual([n.id for n in result], ['teacher_1', 'not_3'])
        self.assertEqual(read.call_args.args[1:], (9, 7, 10))


URL = os.getenv('PARENT_NOTIFICATIONS_TEST_DATABASE_URL')


@unittest.skipUnless(URL, 'Set a local PARENT_NOTIFICATIONS_TEST_DATABASE_URL for SQL fixtures')
class NotificationSqlTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in ('127.0.0.1', 'localhost') or url.database != 'student_timetable_test':
            self.fail('Only the disposable local student_timetable_test DB is permitted')
        self.engine = create_engine(url)
        self.db = self.engine.connect()
        self.tx = self.db.begin()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.addCleanup(self.tx.rollback)
        p = DB_PREFIX
        fields = {
            'parent_notifications': 'notification_id bigint,teacher_id text,student_id bigint,notification_type text,message_text text,sent_at timestamp,sent_via text,record_status text',
            'teacher_master': 'teacher_id bigint,full_name text',
            'support_tickets': 'ticket_id int,parent_id int,student_id bigint',
            'ticket_messages': 'message_id int,ticket_id int,sender_name text,sender_type text,message text,created_at timestamp,is_read boolean',
        }
        for name, ddl in fields.items():
            self.db.execute(text(f'CREATE TEMP TABLE "{p}{name}" ({ddl}) ON COMMIT DROP'))
        self.db.execute(text(f'''INSERT INTO "{p}teacher_master" VALUES (12,'Teacher A');
            INSERT INTO "{p}parent_notifications" VALUES
            (1,'12',9,'general','Full teacher alert','2026-11-01','manual','Active'),
            (2,'12',10,'general','Other child','2026-11-02','manual','Active'),
            (3,'missing',9,'general','Hidden inactive','2026-11-03','manual','Inactive'),
            (4,'missing',9,'general','Missing teacher still visible','2026-11-04','manual','Active');
            INSERT INTO "{p}support_tickets" VALUES (1,7,9),(2,8,9),(3,7,10);
            INSERT INTO "{p}ticket_messages" VALUES
            (1,1,'Teacher B','TEACHER','Private reply','2026-11-02',true),
            (2,2,'Teacher B','TEACHER','Other parent private reply','2026-11-05',false),
            (3,3,'Teacher B','TEACHER','Other child reply','2026-11-05',false),
            (4,1,'Parent','PARENT','Own outgoing message','2026-11-05',false);'''))

    def test_existing_teacher_alerts_and_private_replies_are_scoped_and_sorted(self):
        rows = notification_history(self.db, 9, 7)
        self.assertEqual([r['id'] for r in rows], ['teacher_4', 'msg_1', 'teacher_1'])
        self.assertEqual(rows[0]['teacher_name'], 'Teacher')
        self.assertTrue(rows[1]['is_read'])
        self.assertEqual(rows[2]['message'], 'Full teacher alert')
        self.assertEqual(rows[2]['teacher_name'], 'Teacher A')

    def test_other_parent_sees_only_own_private_reply(self):
        rows = notification_history(self.db, 9, 8)
        self.assertIn('msg_2', [r['id'] for r in rows])
        self.assertNotIn('msg_1', [r['id'] for r in rows])

    def test_pagination_and_empty_history(self):
        self.assertEqual([r['id'] for r in notification_history(self.db, 9, 7, 1, 1)], ['msg_1'])
        self.assertEqual(notification_history(self.db, 999, 7), [])


if __name__ == '__main__':
    unittest.main()
