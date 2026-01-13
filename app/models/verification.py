from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime  # type: ignore
from sqlalchemy.orm import relationship, Mapped  # type: ignore
from datetime import datetime, timezone

from app.models.base_model import BaseModel
from app.models.consumer import Consumer  # type: ignore
from app.models.admin import Administrator  # type: ignore
from app import db


class VerificationReviewNote(BaseModel, db.Model):
    """
    Verification review note model definition.
    """
    __tablename__ = 'verification_review_notes'

    review_id = Column(String(64), ForeignKey(
        'verification_reviews.id'), nullable=False)
    comment = Column(String(256), nullable=False)

    review = relationship('VerificationReview', back_populates='notes')


class VerificationDocument(BaseModel, db.Model):
    __tablename__ = 'verification_documents'

    request_id = Column(String(64), ForeignKey(
        'verification_requests.id'), nullable=False)
    document_name = Column(String(128), nullable=True)
    document_type = Column(
        Enum('student_id', 'enrollment_proof', 'transcript', 'other'), nullable=False)
    document_url = Column(String(256), nullable=False)
    upload_date = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    verified = Column(Enum('pending', 'approved', 'rejected'), nullable=False, default='pending')
    size = Column(String(8), nullable=False)

    request = relationship(
        'VerificationRequest', back_populates='documents')


class VerificationReview(BaseModel, db.Model):
    """
    Verification review model definition.
    """
    __tablename__ = 'verification_reviews'
    request_id = Column(String(64), ForeignKey(
        'verification_requests.id'), nullable=False)
    reviewer_id = Column(String(64), ForeignKey(
        'administrators.id'), nullable=False)
    review_date = Column(DateTime, nullable=False)
    status = Column(Enum('approved', 'rejected', 'request'), nullable=False)
    feedback = Column(String(256), nullable=True)

    request = relationship(
        'VerificationRequest', back_populates='reviews')
    reviewer: Mapped[Administrator] = relationship(
        'Administrator', back_populates='verification_reviews')

    notes: Mapped[list[VerificationReviewNote]] = relationship(
        'VerificationReviewNote', back_populates='review', cascade='all, delete-orphan')


class VerificationRequest(BaseModel, db.Model):
    """
    Verification model definition.
    """
    __tablename__ = 'verification_requests'
    user_id = Column(String(64), ForeignKey('consumers.id'), nullable=False)

    reviewed_at = Column(DateTime, nullable=True, default=None)
    verification_type: Column[Enum] = Column(
        Enum('automatic', 'manual'),
        nullable=False)  # automatic, manual
    status: Column[Enum] = Column(
        Enum('pending', 'requested', 'approved', 'rejected'),
        nullable=False, default='pending')  # pending, approved, rejected

    documents: Mapped[list[VerificationDocument]] = relationship(
        'VerificationDocument', back_populates='request', cascade='all, delete-orphan')
    reviews: Mapped[list[VerificationReview]] = relationship(
        'VerificationReview', back_populates='request', cascade='all, delete-orphan')

    user: Mapped[Consumer] = relationship(
        'Consumer', back_populates='verification_requests')
