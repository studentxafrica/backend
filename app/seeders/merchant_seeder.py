from sqlalchemy.exc import IntegrityError  # type: ignore
from app.models.merchant import Merchant
from app.models.category import Category
from faker import Faker
from typing import List
from random import randint
from app import db
from sqlalchemy.exc import IntegrityError  # type: ignore
from . import get_random_pexels_image

categories = db.session.query(Category).all()

fake = Faker()


fake = Faker()

def edit_merchants():
    merchants: List[Merchant] = db.session.query(Merchant).all()
    for merchant in merchants:
        merchant.preferred_currency = fake.random_choices(['USD', 'EUR', 'GBP', 'KES', 'ZAR'], length=1)[0]
        merchant.save()


def seed_merchants(number: int = 10):
    """
    Seed the database with sample merchants.
    """
    for _ in range(number):
        merchant = {
            "category_id": categories[randint(0, len(categories)-1)].id,
            "email": fake.email(),
            "name": fake.company(),
            "logo": get_random_pexels_image(query='company logo'),
            "password": "Pa$$word1",
            "website": fake.url(),
            "preferred_currency": fake.currency_code(),
        }

        try:
            merchant_instance = Merchant(**merchant)
            db.session.add(merchant_instance)
            db.session.commit()
        except IntegrityError as e:
            print(e)
            db.session.rollback()
            print(f"Duplicate email found: {merchant['email']}, skipping...")

    print("Merchant seeder completed successfully.")
