from sqlalchemy import Column, String, Integer, Boolean  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore

from app.models.base_model import BaseModel
from app import db


class Category(BaseModel, db.Model):
    """
    Category model definition.
    """
    __tablename__ = 'categories'
    name = Column(String(64), nullable=False, unique=True)
    slug = Column(String(64), nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)  # 1 for active, 0 for inactive
    image_url = Column(String(128))

    # TODO: Move this later to redis for better performance optimization
    offer_count = Column(Integer, nullable=False, default=0)
    merchant_count = Column(Integer, nullable=False, default=0)

    # *Many
    merchants = relationship('Merchant', back_populates='category')
    offers = relationship('Offer', back_populates='category')

    def __str__(self):
        return f'{self.name}'
