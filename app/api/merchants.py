"""Public merchant listings for the student site."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify
from sqlalchemy import func

from app import db
from app.models import Merchant, Offer

merchants = Blueprint('merchants', __name__)


@merchants.get('/featured')
def featured_merchants():
    """
    Approved merchants with at least one live offer, most offers first. Fills
    the "Partners" section of the home page.
    """
    now = datetime.now(timezone.utc)
    rows = (db.session.query(Merchant, func.count(Offer.id).label('live'))
            .join(Offer, Offer.merchant_id == Merchant.id)
            .filter(Merchant.approved_on.isnot(None), Offer.status == 'active', Offer.end_date > now)
            .group_by(Merchant.id)
            .order_by(func.count(Offer.id).desc(), Merchant.name)
            .limit(15).all())
    return jsonify({"data": [{
        "id": m.id, "name": m.name, "logo": m.logo, "isApproved": True, "liveOffers": live,
    } for m, live in rows]}), 200
