from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Enum, DateTime, ForeignKey, JSON  # type: ignore
from sqlalchemy.orm import relationship, Mapped, mapped_column  # type: ignore

from app.models.base_model import BaseModel
from app import db

UPLOAD_STATUS = {
    "PENDING": "pending",
    "PROCESSING": "processing",
    "COMPLETED": "completed",
    "FAILED": "failed",
}


class UploadJob(BaseModel, db.Model):
    """
    Tracks coupon CSV upload processing.
    """
    __tablename__ = 'upload_jobs'

    merchant_id: Mapped[str] = mapped_column(String(64), ForeignKey('merchants.id'), nullable=False)
    offer_id: Mapped[str] = mapped_column(String(64), ForeignKey('offers.id'), nullable=False)
    status: Mapped[str] = mapped_column(Enum(*UPLOAD_STATUS.values()), nullable=False,
                                  default=UPLOAD_STATUS["PENDING"])

    file_path: Mapped[str] = mapped_column(String(256), nullable=False)

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    merchant = relationship('Merchant')
    offer = relationship('Offer')

    def mark_completed(self):
        self.status = UPLOAD_STATUS["COMPLETED"]
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self):
        self.status = UPLOAD_STATUS["FAILED"]
        self.completed_at = datetime.now(timezone.utc)
