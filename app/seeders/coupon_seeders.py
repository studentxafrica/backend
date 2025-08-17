from faker import Faker
from app.models.offer import Offer
from app.models.consumer import Consumer
from app.models.coupon import Coupon
from app.utils import generate_coupon_code

from app import db

fake = Faker()

offers = db.session.query(Offer).filter_by(
    merchant_id="009e6cc4-4216-41c9-83ac-611dafc52f9a").all()
consumers = db.session.query(Consumer).all()


def seed_coupons(count: int = 10):
    """
    Seed the database with coupons.
    :param count: Number of coupons to seed.
    """
    for _ in range(count):
        offer = fake.random_element(elements=offers)
        consumer = fake.random_element(elements=consumers)
        coupon_code = generate_coupon_code(offer.id, consumer.id)
        expiry_date = fake.date_time_between(
            start_date='+1d', end_date='+1y')
        
        coupon = Coupon(
            offer_id=offer.id,
            consumer_id=consumer.id,
            coupon_code=coupon_code,
            expiry_date=expiry_date
        )
        coupon.save()
