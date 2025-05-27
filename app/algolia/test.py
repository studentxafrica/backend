from algoliasearch.search.client import SearchClientSync
from app.models.offer import Offer
from app.models.merchant import Merchant
from app.models.consumer import Consumer
from app import db
import json
from flask import jsonify


# Fetch sample dataset
offers = db.session.query(Offer).all()
merchants = db.session.query(Merchant).all()
consumers = db.session.query(Consumer).all()

offers_dicts = [
    {
        "id": offer.id,
        "title": offer.title,
        "description": offer.description,
        "slug": offer.slug,
        "cover_image": offer.cover_image,
        "discount_type": offer.discount_type,
        "discount_value": offer.discount_value,
        "currency": offer.currency,
        "coupon_limit": offer.coupon_limit,
        "status": offer.status,
        "start_date": offer.start_date.isoformat(),
        "end_date": offer.end_date.isoformat(),
        "terms_and_conditions": offer.terms_and_conditions,
        "featured_until": offer.featured_until.isoformat() if offer.featured_until else None,
        "highlighted_until": offer.highlighted_until.isoformat() if offer.highlighted_until else None
    }
    for offer in offers
]

merchants_dicts = [
    {
        "id": merchant.id,
        "name": merchant.name,
        "slug": merchant.slug,
        "logo": merchant.logo,
        "cover_image": merchant.cover_image,
        "website": merchant.website,
        "email": merchant.email,
    }
    for merchant in merchants
]
consumers_dicts = [
    {
        "id": consumer.id,
        "first_name": consumer.first_name,
        "last_name": consumer.last_name,
        "email": consumer.email,
    }
    for consumer in consumers
]

# Connect and authenticate with your Algolia app
_client = SearchClientSync("3T4VZP4G9X", "a4cc508bdc6bef329f8fc17eba5f250b")

# Save records in Algolia index
_client.save_objects(
    index_name="movies_index",
    objects=offers_dicts + merchants_dicts + consumers_dicts,
)
