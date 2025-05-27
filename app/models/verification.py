from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore

from app.models.base_model import BaseModel


class Verification(BaseModel):
    """
    Verification model definition.
    """
    __tablename__ = 'verifications'
    user_id = ForeignKey('users.id', nullable=False)

    reviewed_at = Column(DateTime, nullable=False)
    verification_type: Column[Enum] = Column(
        Enum('automatic', 'manual'),
        nullable=False)  # automatic, manual
    status: Column[Enum] = Column(
        Enum('pending', 'approved', 'rejected'),
        nullable=False)  # pending, approved, rejected
    reviewed_by = Column(Integer, ForeignKey('admins.id'), nullable=True)
    comments = Column(String(256), nullable=True)
