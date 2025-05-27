from faker import Faker
from sqlalchemy.exc import IntegrityError
from datetime import timedelta, datetime, timezone
from app.models.offer import Offer
from app.models.merchant import Merchant
from app import db
from . import get_random_pexels_image
import random

fake = Faker()

merchants = db.session.query(Merchant).all()

cover_images = [
    "https://images.pexels.com/photos/745365/pexels-photo-745365.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/6207910/pexels-photo-6207910.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/6279794/pexels-photo-6279794.jpeg?auto=compress&cs=tinysrgb&w=600",
    
]

def seed_offers(number: int = 10):
    """
    Seed the database with sample offers.
    """
    for _ in range(number):
        start_date = fake.date_time_between(start_date='-1y', end_date='now', tzinfo=timezone.utc)

        # Optional highlighted_until (after start)
        highlighted_until = None
        if random.choice([True, False]):
            highlighted_until = start_date + timedelta(days=random.randint(1, 10))

        # Optional featured_until (after highlighted or start)
        featured_until = None
        if random.choice([True, False]):
            base = highlighted_until or start_date
            featured_until = base + timedelta(days=random.randint(1, 5))

        # Ensure end_date is after featured/highlighted/start
        end_base = max(filter(None, [start_date, highlighted_until, featured_until]))
        end_date = end_base + timedelta(days=random.randint(1, 10))

        # Constraint: featured > highlighted (if both exist)
        if featured_until and highlighted_until and featured_until <= highlighted_until:
            # Force featured > highlighted
            featured_until = highlighted_until + timedelta(days=1)
            end_date = max(end_date, featured_until + timedelta(days=1))

        offer = {
            "title": fake.sentence(nb_words=5),
            "description": fake.text(max_nb_chars=200),
            "slug": fake.slug(),
            "cover_image": get_random_pexels_image(),
            "discount_type": fake.random_element(elements=("percentage", "fixed_amount", "buy_one_get_one", "free_item")),
            "discount_value": fake.random_int(min=5, max=50),
            "currency": fake.currency_code(),
            "coupon_limit": fake.random_int(min=10, max=100),
            "status": fake.random_element(elements=("active", "inactive")),
            "start_date": start_date,
            "end_date": end_date,
            "terms_and_conditions": fake.text(max_nb_chars=150),
            "featured_until": featured_until,
            "highlighted_until": highlighted_until,
            "merchant_id": fake.random_element(elements=[merchant.id for merchant in merchants])
        }

        try:
            offer_instance = Offer(**offer)
            db.session.add(offer_instance)
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            print(f"Integrity error: {e}. Skipping duplicate or invalid offer.")

    print("Offer seeder completed successfully.")
