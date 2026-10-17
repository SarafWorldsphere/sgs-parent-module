"""
Tests for token enforcement on data routes.

Scenarios covered:
  1. Authorized parent  — valid token + matching student → 200
  2. Unauthorized parent — valid token + wrong student   → 403
  3. Missing token (production) — no header             → 401
  4. Missing token (development) — no header + IS_DEV   → 200 (demo parent)

Uses FastAPI dependency overrides so no real database is required.
"""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Set test environment BEFORE importing app modules that read env vars at import time.
# DATABASE_URL must be a postgresql:// URL so SQLAlchemy accepts pool_size/max_overflow.
# get_db is fully overridden in every test so no real DB connection is ever made.
os.environ.setdefault("APP_ENV", "production")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")

TEST_TENANT = "11111111-1111-1111-1111-111111111111"

# Suppress startup checks — they should not hit the DB in tests.
with patch("startup_check.run_startup_checks", return_value=True):
    from main import app

from database import get_db
import auth
from models import ParentMaster, ParentStudentMap, StudentMaster, SupportTicket
from saraswati_tenant.types import School


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_parent(parent_id: int) -> ParentMaster:
    p = ParentMaster()
    p.parent_id = parent_id
    p.full_name = f"Test Parent {parent_id}"
    p.email = f"parent{parent_id}@test.com"
    return p


def _make_student(student_id: int) -> StudentMaster:
    s = StudentMaster()
    s.student_id = student_id
    s.full_name = f"Test Student {student_id}"
    s.is_active = True
    s.record_status = 'Active'
    return s


def _make_mapping(parent_id: int, student_id: int) -> ParentStudentMap:
    m = ParentStudentMap()
    m.id = 1
    m.parent_id = parent_id
    m.student_id = student_id
    return m


def _make_ticket(ticket_id: int, parent_id: int, student_id: int) -> SupportTicket:
    t = SupportTicket()
    t.ticket_id = ticket_id
    t.parent_id = parent_id
    t.student_id = student_id
    t.subject = "Test"
    t.status = "OPEN"
    return t


def _valid_token(parent_id: int) -> str:
    """Mint a real JWT for the given parent_id using the test JWT_SECRET."""
    from datetime import datetime, timedelta, timezone
    import jwt as pyjwt
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(parent_id),
        "parent_id": parent_id,
        "role": "parent",
        "tenant_id": TEST_TENANT,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return pyjwt.encode(claims, os.environ["JWT_SECRET"], algorithm="HS256")


# ── Fixtures ───────────────────────────────────────────────────────────────

AUTHORIZED_PARENT_ID = 10
AUTHORIZED_STUDENT_ID = 100
OTHER_PARENT_ID = 99


def _mock_db_session(parent_id: int, student_id: int):
    """Return a mock DB session that knows about one parent and one mapping."""
    db = MagicMock()

    def _query_side_effect(model):
        mock_q = MagicMock()
        instances = {
            ParentMaster: _make_parent(parent_id),
            ParentStudentMap: _make_mapping(parent_id, student_id),
            StudentMaster: _make_student(student_id),
        }
        mock_q.filter.return_value.first.return_value = instances.get(model)
        mock_q.filter.return_value.count.return_value = 0
        mock_q.filter.return_value.all.return_value = []
        mock_q.filter.return_value.order_by.return_value.all.return_value = []
        mock_q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_q.join.return_value = mock_q
        mock_q.outerjoin.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.limit.return_value = mock_q
        return mock_q

    db.query.side_effect = _query_side_effect
    return db


@pytest.fixture(autouse=True)
def _bind_test_school():
    school = School(
        tenant_id=TEST_TENANT,
        slug="sgs",
        status="active",
        isolation="rls",
        config={},
    )
    with patch("saraswati_tenant.middleware.resolve_school", return_value=school):
        yield


# ── Tests: /dashboard/{student_id} ────────────────────────────────────────

class TestDashboardAuth:

    def _override_db(self, parent_id, student_id):
        db = _mock_db_session(parent_id, student_id)
        app.dependency_overrides[get_db] = lambda: db
        return db

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_authorized_parent_gets_200(self):
        """Scenario 1: valid token, student belongs to parent → 200."""
        from schemas import DashboardResponse, StudentSchema
        self._override_db(AUTHORIZED_PARENT_ID, AUTHORIZED_STUDENT_ID)
        student = StudentSchema(student_id=AUTHORIZED_STUDENT_ID, full_name="Test", **{"class": "X"}, section="A", roll_no="1")
        mock_response = DashboardResponse(student=student)
        with patch("routers.dashboard.get_dashboard_data", return_value=mock_response):
            token = _valid_token(AUTHORIZED_PARENT_ID)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                f"/dashboard/{AUTHORIZED_STUDENT_ID}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200, resp.text

    def test_unauthorized_parent_gets_403(self):
        """Scenario 2: valid token for parent 99 who does not own student 100 → 403."""
        db = _mock_db_session(OTHER_PARENT_ID, AUTHORIZED_STUDENT_ID)
        # No mapping for OTHER_PARENT_ID → student 100
        def _q(model):
            mock_q = MagicMock()
            if model is ParentMaster:
                mock_q.filter.return_value.first.return_value = _make_parent(OTHER_PARENT_ID)
            else:
                # No mapping
                mock_q.filter.return_value.first.return_value = None
            mock_q.filter.return_value.count.return_value = 0
            mock_q.filter.return_value.all.return_value = []
            mock_q.join.return_value = mock_q
            mock_q.outerjoin.return_value = mock_q
            return mock_q
        db.query.side_effect = _q
        app.dependency_overrides[get_db] = lambda: db

        token = _valid_token(OTHER_PARENT_ID)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            f"/dashboard/{AUTHORIZED_STUDENT_ID}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, resp.text

    def test_token_from_another_school_gets_401(self):
        self._override_db(AUTHORIZED_PARENT_ID, AUTHORIZED_STUDENT_ID)
        token = _valid_token(AUTHORIZED_PARENT_ID)
        import jwt as pyjwt
        claims = pyjwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        claims["tenant_id"] = "22222222-2222-2222-2222-222222222222"
        foreign = pyjwt.encode(claims, os.environ["JWT_SECRET"], algorithm="HS256")
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            f"/dashboard/{AUTHORIZED_STUDENT_ID}",
            headers={"Authorization": f"Bearer {foreign}"},
        )
        assert resp.status_code == 401, resp.text

    def test_missing_token_production_gets_401(self):
        """Scenario 3: no token, IS_DEV=False (production) → 401."""
        self._override_db(AUTHORIZED_PARENT_ID, AUTHORIZED_STUDENT_ID)
        with patch.object(auth, "IS_DEV", False):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(f"/dashboard/{AUTHORIZED_STUDENT_ID}")
        assert resp.status_code == 401, resp.text

    def test_missing_token_development_gets_demo_parent(self):
        """Scenario 4: no token, IS_DEV=True → demo parent (200 or at least not 401)."""
        db = _mock_db_session(AUTHORIZED_PARENT_ID, AUTHORIZED_STUDENT_ID)
        app.dependency_overrides[get_db] = lambda: db
        with patch.object(auth, "IS_DEV", True), \
             patch.object(auth, "DEMO_PARENT_ID", AUTHORIZED_PARENT_ID), \
             patch("routers.dashboard.get_dashboard_data") as mock_svc:
            mock_svc.return_value = {
                "student_id": AUTHORIZED_STUDENT_ID, "student_name": "Test",
                "class_name": "X", "section": "A",
                "assignments": [], "quizzes": [], "remarks": [],
                "notices": [], "attendance": None,
            }
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(f"/dashboard/{AUTHORIZED_STUDENT_ID}")
        assert resp.status_code != 401, f"Expected non-401 in dev mode, got {resp.status_code}: {resp.text}"


# ── Tests: /assessments/history/{student_id} ──────────────────────────────

class TestAssessmentsAuth:

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_missing_token_production_gets_401(self):
        db = _mock_db_session(AUTHORIZED_PARENT_ID, AUTHORIZED_STUDENT_ID)
        app.dependency_overrides[get_db] = lambda: db
        with patch.object(auth, "IS_DEV", False):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(f"/assessments/history/{AUTHORIZED_STUDENT_ID}")
        assert resp.status_code == 401, resp.text

    def test_unauthorized_parent_gets_403(self):
        db = MagicMock()
        def _q(model):
            mock_q = MagicMock()
            if model is ParentMaster:
                mock_q.filter.return_value.first.return_value = _make_parent(OTHER_PARENT_ID)
            else:
                mock_q.filter.return_value.first.return_value = None
            mock_q.filter.return_value.count.return_value = 0
            mock_q.filter.return_value.all.return_value = []
            mock_q.join.return_value = mock_q
            mock_q.outerjoin.return_value = mock_q
            return mock_q
        db.query.side_effect = _q
        app.dependency_overrides[get_db] = lambda: db
        token = _valid_token(OTHER_PARENT_ID)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            f"/assessments/history/{AUTHORIZED_STUDENT_ID}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, resp.text


# ── Tests: /comm/ routes ──────────────────────────────────────────────────

class TestCommunicationAuth:

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_list_conversations_missing_token_production_gets_401(self):
        db = _mock_db_session(AUTHORIZED_PARENT_ID, AUTHORIZED_STUDENT_ID)
        app.dependency_overrides[get_db] = lambda: db
        with patch.object(auth, "IS_DEV", False):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(f"/comm/conversations/{AUTHORIZED_STUDENT_ID}")
        assert resp.status_code == 401, resp.text

    def test_get_messages_wrong_parent_gets_403(self):
        """Conversation belongs to parent 10, parent 99 tries to read it → 403."""
        CONV_ID = 55
        db = MagicMock()
        def _q(model):
            mock_q = MagicMock()
            if model is ParentMaster:
                mock_q.filter.return_value.first.return_value = _make_parent(OTHER_PARENT_ID)
            elif model is ParentStudentMap:
                mock_q.filter.return_value.first.return_value = None
            elif model is SupportTicket:
                # Ticket owned by AUTHORIZED_PARENT_ID, not OTHER_PARENT_ID
                mock_q.filter.return_value.first.return_value = _make_ticket(CONV_ID, AUTHORIZED_PARENT_ID, AUTHORIZED_STUDENT_ID)
            else:
                mock_q.filter.return_value.first.return_value = None
            mock_q.filter.return_value.count.return_value = 0
            mock_q.filter.return_value.all.return_value = []
            mock_q.filter.return_value.order_by.return_value.all.return_value = []
            mock_q.filter.return_value.update.return_value = None
            mock_q.join.return_value = mock_q
            mock_q.outerjoin.return_value = mock_q
            return mock_q
        db.query.side_effect = _q
        app.dependency_overrides[get_db] = lambda: db

        token = _valid_token(OTHER_PARENT_ID)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            f"/comm/conversations/{CONV_ID}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, resp.text
