#!/usr/bin/env python3
from app.models.base_model import BaseModel
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, String, DateTime, Enum  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
import enum

from app import db

class VerificationRequestStatus(enum.Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    REQUESTED = 'requested'
    APPROVED = 'completed'
    REJECTED = 'rejected'
    FAILED = 'failed'


class Consumer(BaseModel, db.Model):
    """
    Consumer model definition.
    """
    __tablename__ = 'consumers'
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False, unique=True, index=True)
    phone = Column(String(128), nullable=True, default=None)

    school = Column(String(128))
    year = Column(String(8), nullable=True, default=None)
    graduation_year = Column(String(8))
    major = Column(String(128))
    student_id = Column(String(128))
    bio = Column(String(512), nullable=True, default=None)
    location = Column(String(128), nullable=True, default=None)
    date_of_birth = Column(DateTime, nullable=True, default=None)
    profile_picture = Column(String(128), nullable=True, default=None)
    verified_at = Column(DateTime, nullable=True)
    verification_status = Column(Enum(VerificationRequestStatus), nullable=False, default=VerificationRequestStatus.PENDING)
    verification_reminder_sent_on = Column(DateTime, nullable=True, default=None)
    _password = Column(String(256), nullable=False)

    verification_requests = relationship(
        'VerificationRequest', back_populates='user', cascade='all, delete-orphan')
    saved_offers = relationship(
        'SavedOffer', back_populates='consumer', cascade='all, delete-orphan')

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.id.split('-')[0]}"

    @property
    def profile_complete(self) -> float:
        """
        Check if the consumer's profile is complete.
        A profile is considered complete if all required fields are filled.
        Returns a value indicating the percentage of profile completion.
        """
        required_fields = [
            self.first_name, self.last_name, self.email, self.phone,
            self.school, self.graduation_year, self.major, self.student_id,
            self.location, self.verified
        ]
        filled_fields = sum(1 for field in required_fields if field)
        return (filled_fields / len(required_fields)) * 100 or 0.0

    # *Many
    coupons = relationship(
        'Coupon',
        back_populates='consumer',
        cascade='all, delete-orphan'
    )

    @property
    def password(self) -> str:
        """
        Getter for the password attribute.
        """
        raise AttributeError("password is not accessible")

    @password.setter
    def password(self, value: Column[str]) -> None:
        """
        Setter for the password attribute.
        """
        if not isinstance(value, str):
            raise TypeError("Password must be a string")
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        self._password = generate_password_hash(value)

    @property
    def verified(self) -> bool:
        """
        Getter for the verified attribute.
        """
        return self.verified_at is not None and self.verification_status == VerificationRequestStatus.APPROVED

    def verify_password(self, password: str) -> bool:
        """
        Verify the provided password against the stored hashed password.
        """
        if not isinstance(password, str):
            raise TypeError("Password must be a string")
        return check_password_hash(str(self._password), password)
