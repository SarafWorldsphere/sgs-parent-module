# Parent notification display (SGS main)

Local implementation only. No pushes, deployment, schema changes or school data
writes are part of this work.

Parent display follows the student dashboard's Latest Updates popup/ticker.
Unread teacher messages and class notices appear in a scrolling strip below the
header. Hover/focus pauses scrolling; clicking opens a full-message dialog. Close
marks the currently displayed updates as read. Reduced-motion users get a static,
horizontally scrollable strip. The existing bell remains; direct teacher alerts
open the same dialog and conversation replies open Communication Center.

There is no separate Notifications sidebar entry, page or Notices sub-tab.
Timetable remains immediately below Dashboard. Backend history/source reads are
retained so teacher alerts can be consumed without building another standalone UI.

Sources use the existing DB_TABLE_PREFIX (sgs_ on staging):

- parent_notifications: direct teacher alerts for the selected linked student.
- teacher_master: display names, with fallback when the teacher is missing.
- ticket_messages joined to support_tickets: TEACHER replies scoped to BOTH the
  authenticated parent and selected student. Another parent's conversation is
  never included, even if both parents are linked to the same child.

`GET /notification-history/{student_id}?limit=50&offset=0` verifies existing
parent-child ownership before accessing data. Maximum page size is 100.
Database failures return 503 rather than an empty history. No login bypass is
introduced. Pending SSO/JWT configuration still blocks authenticated staging QA.

The direct-alert source table has no parent_id or read-status column. Such alerts
are student-level messages visible to each authorized linked parent. Their read
state is browser-local, scoped by parent AND student. Conversation replies also
honor existing server is_read state. No read-receipt writes, extra tables or
migrations are introduced. Clearing browser storage or changing device resets
direct-alert read markers. Existing Communication Center behavior is preserved.

Notifications are refreshed when the bell mounts, the window regains focus, and
every 60 seconds while mounted. Child switches cancel or ignore stale requests.
This is polling, not push delivery.

Tests: `python -m unittest discover -s tests -p test_parent_notifications.py -v`
from backend. Optional real SQL tests require PARENT_NOTIFICATIONS_TEST_DATABASE_URL
pointing to local student_timetable_test; fixtures use temporary tables only.

Remaining verification: browser review and a real teacher send followed by an
authenticated parent login on staging. No test messages were sent to real users.
