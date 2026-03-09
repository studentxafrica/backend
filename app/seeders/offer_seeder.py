from datetime import datetime, timedelta, timezone
from faker import Faker
from typing import List, Dict, Any
from sqlalchemy.exc import IntegrityError  # type: ignore
from app.models.offer import Offer, DISCOUNT_TYPES, OFFER_STATUS, USAGE_TYPES
from app.models.merchant import Merchant
from app.models import Category
from app import db
from . import get_random_pexels_image
import random
import uuid

fake = Faker()

merchants = db.session.query(Merchant).all()

cover_images = [
    "https://images.pexels.com/photos/745365/pexels-photo-745365.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/6207910/pexels-photo-6207910.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/6279794/pexels-photo-6279794.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/6207911/pexels-photo-6207911.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/6238109/pexels-photo-6238109.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/4939661/pexels-photo-4939661.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/22498607/pexels-photo-22498607/free-photo-of-girl-holding-american-football-ball.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/7563653/pexels-photo-7563653.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/7957753/pexels-photo-7957753.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/7957747/pexels-photo-7957747.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/5662852/pexels-photo-5662852.png?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/5705523/pexels-photo-5705523.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/5625001/pexels-photo-5625001.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997553/pexels-photo-3997553.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997552/pexels-photo-3997552.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997551/pexels-photo-3997551.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997550/pexels-photo-3997550.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997549/pexels-photo-3997549.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997548/pexels-photo-3997548.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997547/pexels-photo-3997547.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997546/pexels-photo-3997546.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997545/pexels-photo-3997545.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997544/pexels-photo-3997544.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997543/pexels-photo-3997543.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997542/pexels-photo-3997542.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997541/pexels-photo-3997541.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997540/pexels-photo-3997540.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997539/pexels-photo-3997539.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997538/pexels-photo-3997538.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997537/pexels-photo-3997537.jpeg?auto=compress&cs=tinysrgb&w=600",
    "https://images.pexels.com/photos/3997536/pexels-photo-3997536.jpeg?auto=compress&cs=tinysrgb&w=600",
]


def edit_offers(field):
    """
    Edit existing offers to ensure they meet the constraints.
    """
    offers: List[Offer] = db.session.query(Offer).all()
    for offer in offers:
        if field == "cover_image":
            offer.cover_image = get_random_pexels_image()
        elif field == "start_date":
            offer.start_date = fake.date_time_between(
                start_date='-1y', end_date='now', tzinfo=timezone.utc)
        elif field == "end_date":
            offer.end_date = datetime.now(tz=timezone.utc) + \
                timedelta(days=random.randint(3, 60))
        elif field == 'category':
            # Randomly assign a new category from the existing categories
            from app.models.category import Category
            categories = db.session.query(Category).all()
            offer.category = random.choice(
                categories) if categories else None
        elif field == "highlighted_until":
            if random.choice([True, False]):
                offer.highlighted_until = offer.start_date + \
                    timedelta(days=random.randint(1, 10))
            else:
                offer.highlighted_until = None
        elif field == "featured_until":
            if random.choice([True, False]):
                base = offer.highlighted_until or offer.start_date
                offer.featured_until = base + \
                    timedelta(days=random.randint(1, 5))
            else:
                offer.featured_until = None
        offer.save()


CURRENCIES = ['BBD', 'LBP', 'KHR', 'PEN', 'SEK', 'TZS', 'CLP', 'NAD', 'EUR']
CATEGORIES = db.session.query(Category).all()


def generate_coupon_title_desc(record: Offer):
    """Generate realistic title/description using existing record values"""
    discount_type = record.discount_type
    discount_value = record.discount_value
    currency = record.currency
    category_name = next(
        (cat.name for cat in CATEGORIES if cat.id == record.category_id), 'selected items')
    title = ""
    desc = ""

    # Percentage discounts
    if discount_type == 'percentage':
        title = f"{discount_value}% Off {category_name}"
        desc = f"Save {discount_value}% on {category_name}. Limited time offer."

        # Add seasonal/flash sale variants
        if discount_value >= 30:
            title = f"Clearance Sale: {discount_value}% Off {category_name}"
            desc = f"Massive {discount_value}% discount on clearance {category_name}. While stocks last."
        elif random.random() > 0.7:
            title = f"Flash Sale: {discount_value}% Off {category_name}"
            desc = f"Today only! {discount_value}% off all {category_name}."

    # Fixed amount discounts
    elif discount_type == 'fixed_amount':
        title = f"{discount_value} {currency} Off {category_name}"
        min_spend = discount_value * random.choice([2, 3, 4])
        desc = f"Save {discount_value} {currency} when you spend {min_spend} {currency} or more on {category_name}."

        if discount_value < 20:
            title = f"Instant {discount_value} {currency} Savings"
        elif currency == 'EUR' and discount_value > 50:
            title = f"Big Savings: {discount_value}€ Off"

    # BOGO deals
    elif discount_type == 'buy_one_get_one':
        if discount_value == 50:
            title = f"Buy One {category_name}, Get One Half Price"
        elif discount_value == 100:
            title = f"Buy One {category_name}, Get One Free"
        else:
            title = f"Buy One, Get One {discount_value}% Off"

    # Free item promotions
    elif discount_type == 'free_item':
        free_items = {
            'Education': ['book', 'stationery', 't-shirt'],
            'Electronics & Tech': ['headphones', 'charger', 'case', 'earbuds'],
            'Food & Drink': ['drink', 'snack', 'dessert'],
            'Entertainment': ['movie ticket', 'game', 'merchandise'],
            'Fashion': ['accessory', 'hat', 'socks', 'scarf'],
            'Health & Beauty': ['sample', 'cosmetic', 'skincare'],
            'Sports & Outdoors': ['water bottle', 'towel', 'cap'],
            'Travel': ['luggage tag', 'travel pillow', 'snack pack'],
            'Home & Accessories': ['kitchen gadget', 'decor item', 'candle'],
        }
        item = random.choice(free_items.get(category_name, ['gift']))
        title = f"Free {item.replace('_', ' ').title()} with Purchase"
        desc = f"Get a free {item} with any {category_name} purchase over {discount_value} {currency}."

    # Add expiration awareness if end_date is near
    if record.end_date and (record.end_date - datetime.now()).days < 7:
        title = f"Last Chance! {title}"
        desc = f"{desc.split('.')[0]}. Offer ends soon!"

    # return title, desc
    record.title = title
    record.description = desc
    record.save()


def seed_offers(number: int = 10):
    """
    Seed the database with sample offers.
    """
    for _ in range(number):
        start_date = fake.date_time_between(
            start_date='-1y', end_date='now', tzinfo=timezone.utc)

        # Optional highlighted_until (after start)
        highlighted_until = None
        if random.choice([True, False]):
            highlighted_until = start_date + \
                timedelta(days=random.randint(1, 10))

        # Optional featured_until (after highlighted or start)
        featured_until = None
        if random.choice([True, False]):
            base = highlighted_until or start_date
            featured_until = base + timedelta(days=random.randint(1, 5))

        # Ensure end_date is after featured/highlighted/start
        end_base = max(
            filter(None, [start_date, highlighted_until, featured_until]))
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
            "discount_type": fake.random_element(elements=tuple(DISCOUNT_TYPES.values())),
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


def seed_offer_variants():
    """
    Seed the database with all possible offer variants based on known enums.
    """
    merchants = db.session.query(Merchant).all()
    if not merchants:
        return

    categories = db.session.query(Category).all()

    discount_values = {
        DISCOUNT_TYPES["PERCENTAGE"]: 20,
        DISCOUNT_TYPES["FIXED_AMOUNT"]: 10,
        DISCOUNT_TYPES["BUY_ONE_GET_ONE"]: 50,
        DISCOUNT_TYPES["FREE_ITEM"]: 25,
    }

    redemption_types = ["in-store", "online", "both"]
    featured_modes = ["none", "highlighted", "featured", "both"]

    abbrev = {
        "discount": {
            DISCOUNT_TYPES["PERCENTAGE"]: "pct",
            DISCOUNT_TYPES["FIXED_AMOUNT"]: "fix",
            DISCOUNT_TYPES["BUY_ONE_GET_ONE"]: "bogo",
            DISCOUNT_TYPES["FREE_ITEM"]: "free",
        },
        "status": {
            OFFER_STATUS["ACTIVE"]: "act",
            OFFER_STATUS["INACTIVE"]: "ina",
            OFFER_STATUS["EXPIRED"]: "exp",
            OFFER_STATUS["SOLD_OUT"]: "sold",
            OFFER_STATUS["SUSPENDED"]: "susp",
        },
        "redeem": {"in-store": "store", "online": "onl", "both": "both"},
        "usage": {
            USAGE_TYPES["SINGLE_USE"]: "sng",
            USAGE_TYPES["MULTI_USE"]: "mul",
            USAGE_TYPES["UNLIMITED"]: "unl",
            USAGE_TYPES["TIERED"]: "trd",
        },
        "feature": {"none": "n", "highlighted": "h", "featured": "f", "both": "b"},
    }

    def usage_fields(usage_type: str) -> Dict[str, Any]:
        if usage_type == USAGE_TYPES["SINGLE_USE"]:
            return {
                "usage_type": usage_type,
                "max_claims_per_user": 1,
                "cooldown_period_hours": None,
                "tier_progression": None,
            }
        if usage_type == USAGE_TYPES["MULTI_USE"]:
            return {
                "usage_type": usage_type,
                "max_claims_per_user": 3,
                "cooldown_period_hours": 24,
                "tier_progression": None,
            }
        if usage_type == USAGE_TYPES["UNLIMITED"]:
            return {
                "usage_type": usage_type,
                "max_claims_per_user": None,
                "cooldown_period_hours": 12,
                "tier_progression": None,
            }
        if usage_type == USAGE_TYPES["TIERED"]:
            return {
                "usage_type": usage_type,
                "max_claims_per_user": 6,
                "cooldown_period_hours": None,
                "tier_progression": {
                    "tiers": [
                        {"min_usage": 0, "discount_multiplier": 1.0, "name": "Bronze"},
                        {"min_usage": 3, "discount_multiplier": 1.5, "name": "Silver"},
                        {"min_usage": 5, "discount_multiplier": 2.0, "name": "Gold"},
                    ]
                },
            }
        return {
            "usage_type": usage_type,
            "max_claims_per_user": 1,
            "cooldown_period_hours": None,
            "tier_progression": None,
        }

    offers_to_create: List[Offer] = []
    now = datetime.now(timezone.utc)
    idx = 0

    for discount_type in DISCOUNT_TYPES.values():
        for status in OFFER_STATUS.values():
            for redemption_type in redemption_types:
                for usage_type in USAGE_TYPES.values():
                    for feature_mode in featured_modes:
                        merchant = merchants[idx % len(merchants)]
                        category_id = merchant.category_id or (categories[idx % len(categories)].id if categories else None)

                        if status == OFFER_STATUS["EXPIRED"]:
                            start_date = now - timedelta(days=30)
                            highlighted_until = start_date + timedelta(days=2) if feature_mode in ["highlighted", "both"] else None
                            featured_base = highlighted_until or start_date
                            featured_until = featured_base + timedelta(days=1) if feature_mode in ["featured", "both"] else None
                            end_base = max(filter(None, [start_date, highlighted_until, featured_until]))
                            end_date = end_base + timedelta(days=2)
                        else:
                            start_date = now - timedelta(days=5)
                            highlighted_until = start_date + timedelta(days=2) if feature_mode in ["highlighted", "both"] else None
                            featured_base = highlighted_until or start_date
                            featured_until = featured_base + timedelta(days=1) if feature_mode in ["featured", "both"] else None
                            end_base = max(filter(None, [start_date, highlighted_until, featured_until]))
                            end_date = end_base + timedelta(days=30)

                        currency = merchant.preferred_currency or random.choice(CURRENCIES)
                        slug_suffix = uuid.uuid4().hex[:6]
                        slug = (
                            f"{abbrev['discount'][discount_type]}-"
                            f"{abbrev['status'][status]}-"
                            f"{abbrev['redeem'][redemption_type]}-"
                            f"{abbrev['usage'][usage_type]}-"
                            f"{abbrev['feature'][feature_mode]}-"
                            f"{idx}-{slug_suffix}"
                        )[:64]

                        title = f"{discount_type.replace('_', ' ').title()} ({status})"
                        description = (
                            f"{title} for {merchant.name}. Redemption: {redemption_type}. "
                            f"Usage: {usage_type.replace('_', ' ')}."
                        )[:250]

                        offer_data: Dict[str, Any] = {
                            "title": title[:64],
                            "description": description,
                            "slug": slug,
                            "cover_image": random.choice(cover_images),
                            "discount_type": discount_type,
                            "discount_value": discount_values[discount_type],
                            "currency": currency,
                            "redemption_type": redemption_type,
                            "coupon_limit": 0 if status == OFFER_STATUS["SOLD_OUT"] else 100,
                            "status": status,
                            "start_date": start_date,
                            "end_date": end_date,
                            "terms_and_conditions": "Standard terms and conditions apply.",
                            "featured_until": featured_until,
                            "highlighted_until": highlighted_until,
                            "merchant_id": merchant.id,
                            "category_id": category_id,
                        }
                        offer_data.update(usage_fields(usage_type))

                        offers_to_create.append(Offer(**offer_data))
                        idx += 1

    try:
        db.session.add_all(offers_to_create)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
