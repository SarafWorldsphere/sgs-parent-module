"""Read existing teacher alerts and parent-specific conversation replies."""
import re
from sqlalchemy import text
from database import DB_PREFIX

if DB_PREFIX and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', DB_PREFIX):
    raise ValueError('Invalid DB_TABLE_PREFIX')


def notification_history(db, student_id, parent_id, limit=50, offset=0):
    p = DB_PREFIX
    rows = db.execute(text(f'''
        SELECT * FROM (
            SELECT 'teacher_' || CAST(n.notification_id AS text) AS id,
                   'teacher_notification' AS type,
                   COALESCE(NULLIF(t.full_name, ''), 'Teacher') AS teacher_name,
                   CAST(n.notification_type AS text) AS notification_type,
                   n.message_text AS message, n.sent_at AS sent_at,
                   CAST(n.sent_via AS text) AS channel,
                   '/parent/notifications' AS link, false AS is_read
            FROM "{p}parent_notifications" n
            LEFT JOIN "{p}teacher_master" t
              ON CAST(t.teacher_id AS text) = CAST(n.teacher_id AS text)
            WHERE n.student_id=:student_id
              AND LOWER(COALESCE(n.record_status, 'Active'))='active'
              AND NULLIF(TRIM(n.message_text), '') IS NOT NULL
            UNION ALL
            SELECT 'msg_' || CAST(m.message_id AS text), 'ticket_reply',
                   COALESCE(NULLIF(m.sender_name, ''), 'Teacher'), 'message',
                   m.message, m.created_at, 'communication', '/parent/communication', COALESCE(m.is_read, false)
            FROM "{p}ticket_messages" m
            JOIN "{p}support_tickets" s ON s.ticket_id=m.ticket_id
            WHERE s.student_id=:student_id AND s.parent_id=:parent_id
              AND UPPER(m.sender_type)='TEACHER'
              AND NULLIF(TRIM(m.message), '') IS NOT NULL
        ) alerts ORDER BY sent_at DESC NULLS LAST, id DESC
        LIMIT :limit OFFSET :offset
    '''), dict(student_id=student_id, parent_id=parent_id, limit=limit, offset=offset)).mappings()
    return [dict(id=r['id'], type=r['type'], title=f"Message from {r['teacher_name']}",
                 teacher_name=r['teacher_name'], notification_type=r['notification_type'],
                 message=r['message'], date=r['sent_at'].isoformat() if r['sent_at'] else '',
                 channel=r['channel'], link=r['link'], is_read=bool(r['is_read'])) for r in rows]
