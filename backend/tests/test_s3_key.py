import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")

import pytest
from saraswati_tenant.context import school_context
from saraswati_tenant.s3keys import TenantKeyError
from saraswati_tenant.types import School

from s3_utils import generate_presigned_url

SCHOOL = School(
    tenant_id="11111111-1111-1111-1111-111111111111",
    slug="sgs",
    status="active",
    isolation="rls",
    config={},
)


def test_presign_rejects_a_key_from_another_school():
    with school_context(SCHOOL):
        with pytest.raises(TenantKeyError):
            generate_presigned_url(
                "s3://sgs-bucket-images/22222222-2222-2222-2222-222222222222/assignments/file.pdf"
            )
