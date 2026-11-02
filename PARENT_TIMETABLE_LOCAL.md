# Parent timetable

Page: `/parent/timetable`.

The page uses the existing parent session and child selector. The read-only
`GET /timetable/{student_id}` endpoint verifies parent ownership before deriving
the class and section from the child record. It accepts optional `academic_year`
and `schedule_type=full|half`; it does not accept a client-selected class.

Tables use the existing `DB_TABLE_PREFIX` setting: `period_master`, `timetable`,
and `teacher_master`, with the staging admin schema including `record_status`.
This is a staging/main implementation, not a SaaS schema port.
No new tables, sample records, migrations or writes to school data are included.

The screen shows Monday–Saturday, period timings, subjects, teacher names,
breaks, free periods and loading/error/unpublished states. Child switches cancel
old requests and hide the previous child's schedule.

Local commands:

```powershell
cd backend
python -m unittest discover -s tests -p test_parent_timetable.py
# Start the backend only with a verified local DATABASE_URL.
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In another terminal, run `npm run dev` in `frontend`, then open
`http://localhost:3000/parent/timetable`. Use a valid local parent session or the
existing development-only demo parent configuration. A linked active child and
admin period/timetable data must exist in the local database to display slots.
Do not copy staging credentials for local testing.

Pending: browser visual verification and a complete request against a seeded
local database containing the admin timetable tables.
