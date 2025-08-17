from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, JSON
)
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
import enum
from app.models.base_model import BaseModel
from app import db

# Enum for role types


class AdminRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    SYSTEM_ADMIN = "system_admin"
    USER_ADMIN = "user_admin"
    MODERATOR = "moderator"
    AUDITOR = "auditor"
    SUPPORT = "support"


class Administrator(BaseModel, db.Model):
    __tablename__ = 'administrators'

    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    _password = Column(String(255), nullable=False)

    # Role and access
    role = Column(Enum(AdminRole), nullable=False, default=AdminRole.SUPPORT)
    is_superuser = Column(Boolean, default=False)
    # permissions = Column(JSON, default={})

    # Meta data
    first_name = Column(String(64))
    last_name = Column(String(64))
    phone_number = Column(String(20))
    profile_image = Column(String(255))
    last_login = Column(DateTime)

    # Relationships
    activity_logs = relationship(
        "AdminActivityLog", back_populates="admin", cascade="all, delete-orphan")
    notifications = relationship(
        "AdminNotification", back_populates="admin", cascade="all, delete-orphan")
    verification_reviews = relationship(
        'VerificationReview', back_populates='reviewer', cascade='all, delete-orphan')

    def _repr_(self):
        return f"<Administrator(id={self.id}, username='{self.username}', role='{self.role.value}')>"

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

    def verify_password(self, password: str) -> bool:
        """
        Verify the provided password against the stored hashed password.
        """
        if not isinstance(password, str):
            raise TypeError("Password must be a string")
        return check_password_hash(str(self._password), password)


class AdminActivityLog(BaseModel, db.Model):
    __tablename__ = 'admin_activity_logs'

    admin_id = Column(String(64), ForeignKey('administrators.id'), nullable=False)
    action_type = Column(String(100))
    target_resource = Column(String(255))  # e.g., "user:123", "report:45"
    action_details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    ip_address = Column(String(45))  # IPv4 or IPv6

    admin = relationship("Administrator", back_populates="activity_logs")

    def _repr_(self):
        return f"<AdminActivityLog(action={self.action_type}, admin_id={self.admin_id})>"


class AdminNotification(BaseModel, db.Model):
    __tablename__ = 'admin_notifications'

    admin_id = Column(String(64), ForeignKey('administrators.id'), nullable=False)
    message = Column(Text)
    is_read = Column(Boolean, default=False)

    admin = relationship("Administrator", back_populates="notifications")
