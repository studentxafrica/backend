from datetime import datetime, timezone
from app import db
from app.models.base_model import BaseModel
from sqlalchemy import Column, String, Text, Integer, DateTime


class Testimonial(BaseModel, db.Model):
    __tablename__ = 'testimonials'

    name = Column(String(100), nullable=False, default='Anonymous')
    university = Column(String(100), nullable=True, default=None)
    review = Column(Text, nullable=False)
    rating = Column(Integer, nullable=False, default=4)
    approved_on = Column(DateTime, nullable=True, default=None)

    @property
    def approved(self):
        return self.approved_on is not None

    @approved.setter
    def approved(self, value: bool):
        if value:
            self.approved_on = datetime.now(timezone.utc)
        else:
            self.approved_on = None
