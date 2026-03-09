from sqlalchemy.orm import Mapped
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime  # type: ignore
from sqlalchemy.orm import relationship, mapped_column  # type: ignore
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

    review_id = mapped_column(String(64), ForeignKey(
        'verification_reviews.id'), nullable=False)
    comment = mapped_column(String(256), nullable=False)

    review = relationship('VerificationReview', back_populates='notes')


class VerificationDocument(BaseModel, db.Model):
    __tablename__ = 'verification_documents'

    request_id = mapped_column(String(64), ForeignKey(
        'verification_requests.id'), nullable=False)
    document_name = mapped_column(String(128), nullable=True)
    document_type = mapped_column(
        Enum('student_id', 'enrollment_proof', 'transcript', 'other'), nullable=False)
    document_url = mapped_column(String(256), nullable=False)
    upload_date = mapped_column(DateTime, nullable=False,
                         default=datetime.now(timezone.utc))
    verified = mapped_column(Enum('pending', 'approved', 'rejected'),
                      nullable=False, default='pending')
    size = mapped_column(String(8), nullable=False)

    request = relationship(
        'VerificationRequest', back_populates='documents')


class VerificationReview(BaseModel, db.Model):
    """
    Verification review model definition.
    """
    __tablename__ = 'verification_reviews'
    request_id = mapped_column(String(64), ForeignKey(
        'verification_requests.id'), nullable=False)
    reviewer_id = mapped_column(String(64), ForeignKey(
        'administrators.id'), nullable=False)
    review_date = mapped_column(DateTime, nullable=False)
    status = mapped_column(Enum('approved', 'rejected', 'request'), nullable=False)
    feedback = mapped_column(String(256), nullable=True)

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
    user_id = mapped_column(String(64), ForeignKey('consumers.id'), nullable=False)

    reviewed_at = mapped_column(DateTime, nullable=True, default=None)
    verification_type: Mapped[str] = mapped_column(
        Enum('automatic', 'manual'),
        nullable=False)  # automatic, manual
    status: Mapped[str] = mapped_column(
        Enum('pending', 'requested', 'approved', 'rejected'),
        nullable=False, default='pending')  # pending, approved, rejected

    documents: Mapped[list[VerificationDocument]] = relationship(
        'VerificationDocument', back_populates='request', cascade='all, delete-orphan')
    reviews = relationship(
        'VerificationReview', back_populates='request', cascade='all, delete-orphan')

    user: Mapped[Consumer] = relationship(
        'Consumer', back_populates='verification_requests')
