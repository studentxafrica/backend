from . import coupon

from datetime import datetime, timezone
from flask import request, jsonify, g

from app.models.coupon import Coupon
from app.models.consumer import Consumer
from app.models.merchant import Merchant
# from app.models.offer import Offer
from app import db
from app.api.offer.helpers import track_coupon_redemption
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils import roles_required


@coupon.route('/<id>/redeem', methods=['POST'])
@roles_required('merchant')
def redeem_coupon(id):
    """
    Redeem a coupon.
    Scenarios:
    - Redeem a valid coupon
    - Redeem an already redeemed coupon
    - Redeem a non-existent coupon
    """
    coupon: Coupon = db.session.query(
        Coupon).filter_by(id=id).first()
    if not coupon:
        return jsonify({"message": "Coupon not found or does not belong to the user"}), 404

    if coupon.redeemed:
        return jsonify({"message": "Coupon already redeemed"}), 400
    user = g.user
    if not user:
        return jsonify({"message": "Unauthorized"}), 401

    if coupon.offer.merchant_id != user.id:
        return jsonify({"message": "Coupon does not belong to this merchant"}), 403

    coupon.status = 'redeemed'
    coupon.redeemed_at = datetime.now(
        timezone.utc)  # Set the redeemed timestamp

    # coupon.save()
    track_coupon_redemption(coupon.id)

    return jsonify({
        "message": "Coupon redeemed successfully",
        "data": {
            'id': coupon.id,
            'couponCode': coupon.coupon_code,
            'offer': {
                'id':  coupon.offer.id,
                'title': coupon.offer.title,
                'slug': coupon.offer.slug,
                'coverImage': coupon.offer.cover_image,
                'discountType': coupon.offer.discount_type,
                'discountValue': coupon.offer.discount_value,
                'currency': coupon.offer.currency,
            },
            'consumer': {
                'id': coupon.consumer.id,
                'name': coupon.consumer.first_name + ' ' + coupon.consumer.last_name,
                'email': coupon.consumer.email,
            },
            'redeemedAt': coupon.redeemed_at if coupon.redeemed_at else None,
            'expiryDate': coupon.expiry_date if coupon.expiry_date else None,
            'status': coupon.status,
            'qrCode': coupon.qr_code if coupon.qr_code else None,
        }
    }), 200
