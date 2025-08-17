from sqlalchemy import Column, Integer, String, DateTime # type: ignore
from uuid import uuid4 # type: ignore
from datetime import datetime, timezone
import json

# Base = declarative_base()

fmt_time = '%Y-%m-%d %H:%M:%S'

class BaseModel:
    id = Column(String(64), primary_key=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    def __init__(self, **kwargs):
        self.id = str(uuid4())
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        for key, value in kwargs.items():
            if key not in ['id', 'created_at', 'updated_at']:
                setattr(self, key, value)
        from app import db
        db.session.add(self)

    def save(self):
        from app import db
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    def delete(self):
        from app import db
        db.session.delete(self)
        self.save()

    def to_json(self):
        """
            returns json representation of self
        """
        obj_dict = {
            column.name: getattr(self, column.name) if column.name != 'verification_status' else getattr(self, column.name).value
            for column in self.__table__.columns
            if not column.name.startswith('_')
        }
        return obj_dict
