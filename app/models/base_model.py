from enum import Enum
from sqlalchemy import Column, String, DateTime  # type: ignore
from sqlalchemy.orm import Mapped, mapped_column  # type: ignore
from sqlalchemy.inspection import inspect  # type: ignore
from uuid import uuid4  # type: ignore
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
import json

if TYPE_CHECKING:
    from sqlalchemy import Table

# Base = declarative_base()

fmt_time = '%Y-%m-%d %H:%M:%S'


class BaseModel:
    __table__: "Table"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

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
            column.name: getattr(self, column.name) if column.name != 'verification_status' else getattr(
                self, column.name).value
            for column in self.__table__.columns
            if not column.name.startswith('_')
        }
        return obj_dict

    def to_dict(
        self,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        include_relationships: bool = False,
    ) -> dict:

        mapper = inspect(self.__class__)
        data = {}

        if mapper is None:
            raise ValueError(f"Class {self.__class__.__name__} is not mapped to a database table")

        for column in mapper.columns:
            key = column.key

            if include and key not in include:
                continue

            if exclude and key in exclude:
                continue

            value = getattr(self, key)
            data[key] = self._serialize(value)

        if include_relationships:
            for name, relation in mapper.relationships.items():
                value = getattr(self, name)

                if value is None:
                    data[name] = None
                elif relation.uselist:
                    data[name] = [item.to_dict() for item in value]
                else:
                    data[name] = value.to_dict()

        return data

    @staticmethod
    def _serialize(value):
        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, Enum):
            return value.value

        return value
