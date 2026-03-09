from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, String, Text, DateTime  # type: ignore
from sqlalchemy.orm import Mapped, mapped_column, relationship  # type: ignore

from app import db
from app.models.base_model import BaseModel

APPLICATION_STATUS = {
    "PENDING": "pending",
    "REQUESTED": "requested",
    "APPROVED": "approved",
    "REJECTED": "rejected",
}

APPLICATION_DOCUMENT_TYPES = {
    "OWNERSHIP_PROOF": "ownership_proof",
    "REGISTRATION_CERTIFICATE": "registration_certificate",
    "TAX_DOCUMENT": "tax_document",
    "OTHER": "other",
}


class StudentBusinessApplication(BaseModel, db.Model):
    __tablename__ = "student_business_applications"

    consumer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("consumers.id"), nullable=False, index=True
    )
    merchant_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("merchants.id"), nullable=True, index=True
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("administrators.id"), nullable=True, index=True
    )

    business_name: Mapped[str] = mapped_column(String(128), nullable=False)
    business_type: Mapped[str] = mapped_column(String(128), nullable=False)
    business_description: Mapped[str] = mapped_column(Text, nullable=False)
    business_email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    business_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(256), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    additional_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        Enum(*APPLICATION_STATUS.values()),
        nullable=False,
        default=APPLICATION_STATUS["PENDING"],
        index=True,
    )
    review_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    consumer = relationship("Consumer", back_populates="student_business_applications")
    merchant = relationship("Merchant")
    reviewer = relationship("Administrator")
    documents = relationship(
        "StudentBusinessApplicationDocument",
        back_populates="application",
        cascade="all, delete-orphan",
    )


class StudentBusinessApplicationDocument(BaseModel, db.Model):
    __tablename__ = "student_business_application_documents"

    application_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("student_business_applications.id"), nullable=False, index=True
    )
    document_name: Mapped[str] = mapped_column(String(128), nullable=False)
    document_type: Mapped[str] = mapped_column(
        Enum(*APPLICATION_DOCUMENT_TYPES.values()), nullable=False
    )
    document_url: Mapped[str] = mapped_column(String(256), nullable=False)
    size: Mapped[str | None] = mapped_column(String(16), nullable=True)
    verified: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected"),
        nullable=False,
        default="pending",
    )
    upload_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )

    application = relationship("StudentBusinessApplication", back_populates="documents")
