from datetime import datetime, timezone
from app import db
from app.models.base_model import BaseModel
from sqlalchemy import Column, String, Text, Integer, DateTime
from sqlalchemy.orm import mapped_column, Mapped

class Testimonial(BaseModel, db.Model):
    __tablename__ = 'testimonials'

    name: Mapped[str] = mapped_column(String(100), nullable=False, default='Anonymous')
    university: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    review: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    approved_on: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    @property
    def approved(self):
        return self.approved_on is not None

    @approved.setter
    def approved(self, value: bool):
        if value:
            self.approved_on = datetime.now(timezone.utc)
        else:
            self.approved_on = None
