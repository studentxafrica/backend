from sqlalchemy import Column, String, DateTime, ForeignKey  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event

from app.models.base_model import BaseModel
from app.models.category import Category  # type: ignore
from app import db  # type: ignore


class Merchant(BaseModel, db.Model):
    """
    Vendor model definition.
    """
    __tablename__ = 'merchants'
    # Foreign keys
    category_id = Column(String(64), ForeignKey(
        'categories.id', ondelete='SET NULL'), nullable=True)

    # Attributes
    email = Column(String(128), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    logo = Column(String(128), nullable=True, default=None)
    website = Column(String(128), nullable=True, default=None)
    phone = Column(String(128), nullable=True, default=None)
    address = Column(String(256), nullable=True, default=None)
    city = Column(String(128), nullable=True, default=None)
    country = Column(String(128), nullable=True, default=None)
    zip_code = Column(String(16), nullable=True, default=None)
    _password = Column(String(256), nullable=False)
    preferred_currency = Column(String(8), nullable=True, default=None)
    email_verified_on = Column(DateTime, nullable=True)
    approved_on = Column(DateTime, nullable=True)

    # *One
    category = relationship('Category', back_populates='merchants')

    # *Many
    stores = relationship('Store', back_populates='merchant')
    offers = relationship(
        'Offer', back_populates='merchant')

    def __str__(self):
        return self.name

    @property
    def email_verified(self) -> bool:
        """
        Check if the merchant's email is verified.
        Returns True if email is verified, False otherwise.
        """
        return self.email_verified_on is not None

    @property
    def approved(self) -> bool:
        """
        Getter for the approved attribute.
        """
        return self.approved_on is not None

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


@event.listens_for(Merchant, 'before_insert')
def increment_merchant_count(mapper, connection, target):
    """
        Increment the merchant count in the category before inserting a new merchant.
        """
    CategoryTbl = Category.__table__
    connection.execute(
        CategoryTbl.update().where(CategoryTbl.c.id == target.category_id).values(
            merchant_count=CategoryTbl.c.merchant_count + 1)
    )
