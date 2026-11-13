"""Read canonical local tenant-kit tables using the complete Parent ORM models."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
import models

URL = os.getenv('PARENT_SCHEMA_TEST_DATABASE_URL', '')


@unittest.skipUnless(URL, 'Set local PARENT_SCHEMA_TEST_DATABASE_URL')
class CanonicalModelTests(unittest.TestCase):
    def test_class_and_user_models_read_canonical_schema(self):
        url=make_url(URL)
        if url.host not in ('localhost','127.0.0.1') or url.database != 'saraswati_sample':
            raise RuntimeError('Tests require local saraswati_sample, never a deployed DB')
        engine=create_engine(URL)
        try:
            with engine.connect() as connection:
                connection.execute(text('SET TRANSACTION READ ONLY'))
                connection.execute(text("SELECT set_config('app.tenant_id',:tenant,true)"),
                                   {'tenant':'11111111-1111-1111-1111-111111111111'})
                with Session(bind=connection) as session:
                    # Selecting the full models catches nonexistent columns even
                    # when an isolated school has no corresponding user rows.
                    session.query(models.UsersMaster).limit(1).all()
                    session.query(models.ClassMaster).limit(1).all()
                    session.query(models.StudentMaster,models.ClassMaster).outerjoin(
                        models.ClassMaster,models.StudentMaster.class_id==models.ClassMaster.class_id).limit(1).all()
        finally:
            engine.dispose()
