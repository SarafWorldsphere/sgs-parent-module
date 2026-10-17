"""
Parent identity — token minting and verification.

The login portal (sgs-frontend) authenticates the parent with Google, then
asks this backend for a token via POST /auth/sso-token, authorised by a shared
secret. The token is handed to the dashboard in the redirect URL, and every
request the dashboard makes afterwards carries it as a Bearer header.

This backend signs and verifies its own tokens. No JWT secret is shared with
any other service — only SSO_SECRET, which merely authorises the login portal
to *ask* for a token.

Env:
  SSO_SECRET        must equal SGS_SSO_SECRET in the login portal
  JWT_SECRET        this service's own signing key — long and random
  JWT_EXPIRE_HOURS  token lifetime (default 24)
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from saraswati_tenant import current_school
from sqlalchemy.orm import Session

from database import get_db
from models import ParentMaster, ParentStudentMap, StudentMaster, SupportTicket

logger = logging.getLogger(__name__)

SSO_SECRET = os.getenv("SSO_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# Development-only demo parent fallback.
# Set APP_ENV=development in .env to enable. NEVER set in production.
_APP_ENV = os.getenv("APP_ENV", "production").lower()
IS_DEV = _APP_ENV in ("development", "dev", "local")
DEMO_PARENT_ID = 10


def create_parent_token(parent: ParentMaster) -> str:
    if not JWT_SECRET:
        # Refuse rather than sign with an empty key.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured",
        )
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(parent.parent_id),
        "parent_id": parent.parent_id,
        "role": "parent",
        "tenant_id": current_school().tenant_id,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session.")


def _require_this_school(claims: dict) -> None:
    if claims.get("tenant_id") != current_school().tenant_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is for another school.")


def get_current_parent(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ParentMaster:
    """
    FastAPI dependency: resolves the Bearer token to a ParentMaster row.

    Add `parent: ParentMaster = Depends(get_current_parent)` to any route that
    must only serve the logged-in parent's own data, and compare the path's
    parent_id against `parent.parent_id`.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in.")

    claims = decode_token(authorization.split(" ", 1)[1].strip())
    if claims.get("role") != "parent":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a parent session.")
    _require_this_school(claims)

    parent = db.query(ParentMaster).filter(ParentMaster.parent_id == claims["parent_id"]).first()
    if not parent:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Parent account not found.")
    return parent


def get_current_parent_or_demo(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> ParentMaster:
    """
    Like get_current_parent but allows unauthenticated access in development.

    In production (APP_ENV != development/dev/local) a missing token always
    returns 401.  In development a missing token returns demo parent id=10 so
    the frontend works on a laptop without a login portal.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        if IS_DEV:
            parent = db.query(ParentMaster).filter(ParentMaster.parent_id == DEMO_PARENT_ID).first()
            if not parent:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Demo parent not found in DB.")
            logger.debug("Dev fallback: using demo parent %d", DEMO_PARENT_ID)
            return parent
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in.")

    claims = decode_token(authorization.split(" ", 1)[1].strip())
    if claims.get("role") != "parent":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a parent session.")
    _require_this_school(claims)

    parent = db.query(ParentMaster).filter(ParentMaster.parent_id == claims["parent_id"]).first()
    if not parent:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Parent account not found.")
    return parent


def verify_student_ownership(db: Session, current: ParentMaster, student_id: int) -> None:
    """
    Raise 403 if the student does not belong to this parent, or if the student
    is inactive or deleted.

    Both checks are enforced here so that every data endpoint (all 18 routes
    that call this function) blocks access to inactive/deleted students, even
    when a parent crafts a direct API request bypassing the ChildSelector.

    Active rule: is_active=True AND record_status='Active'
    """
    mapping = (
        db.query(ParentStudentMap)
        .filter(
            ParentStudentMap.parent_id == current.parent_id,
            ParentStudentMap.student_id == student_id,
        )
        .first()
    )
    if not mapping:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied.")

    student = db.query(StudentMaster).filter(StudentMaster.student_id == student_id).first()
    if not student or not student.is_active or student.record_status != 'Active':
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied.")


def verify_conversation_ownership(db: Session, current: ParentMaster, conv_id: int) -> None:
    """Raise 403/404 if this conversation does not belong to this parent."""
    ticket = db.query(SupportTicket).filter(SupportTicket.ticket_id == conv_id).first()
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    if ticket.parent_id != current.parent_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied.")
