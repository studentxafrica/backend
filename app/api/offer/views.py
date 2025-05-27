from sqlalchemy.sql.expression import case  # type: ignore
from sqlalchemy import and_, or_, desc, asc, func  # type: ignore
from datetime import datetime, timezone, timedelta  # type: ignore
from flask import jsonify, request
from datetime import datetime, timezone
from sqlalchemy.orm import Session  # type: ignore

from app.api.offer import offer
from app.models.offer import Offer
from app.models.coupon import Coupon
from app.models.consumer import Consumer
from app.models.category import Category
from app import db
from flask_jwt_extended import jwt_required, current_user, get_jwt_identity
from app.utils import generate_coupon_code

session: Session = db.session


@offer.route('/<id>', methods=['GET'])
def get_offer_by_id(id):
    """
    Get offer by ID.
    Scenarios:
        - Get offer by ID
        - Offer not found
    """
    try:
        # Fetch offer by ID from the database
        offer = db.session.query(Offer).filter(Offer.id == id).first()
        if not offer:
            return jsonify({"message": "Offer not found"}), 404
        return jsonify({
            "message": "Successfully fetched offer",
            "data": {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                    'website': offer.merchant.website,
                },
                'coupons': {
                    'total': offer.coupon_limit,
                    'redeemed': len([coupon for coupon in offer.coupons if coupon.redeemed]),
                    'claimed': len([coupon for coupon in offer.coupons if coupon.active]),
                },
                'status': offer.status,
                'startDate': offer.start_date,
                'endDate': offer.end_date,
                'termsAndConditions': offer.terms_and_conditions
            }
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@offer.route('/<id>/coupons/create', methods=['POST'])
@jwt_required()
# @limiter.limit("1/sec")
def create_coupon(id):
    """
    Create a coupon for an offer.
    Scenarios:
        - Create a coupon
        - Offer not found
        - Coupon already exists
    """
    try:
        # Fetch offer by ID from the database
        offer = db.session.query(Offer).filter(Offer.id == id).first()
        if not offer:
            return jsonify({"message": "Offer not found"}), 404

        user_id = get_jwt_identity()
        user = db.session.query(Consumer).filter(
            Consumer.id == user_id).first()
        if not user:
            return jsonify({"message": "Couldn't not verify current user identity"}), 404
        print("Checking for existing coupon")
        user_coupon = db.session.query(Coupon).filter(
            Coupon.consumer_id == user.id,
        ).first()

        if user_coupon:
            print("Returning coupon")
            return jsonify({
                "message": "Coupon already claimed",
                "data": {
                    'code': user_coupon.coupon_code,
                    "qrCode": user_coupon.qr_code,
                    'expiryDate': user_coupon.expiry_date,
                    'status': user_coupon.status
                }
            }), 200

        # Logic to create a coupon for the offer
        print("generating coupon code")
        coupon_code = generate_coupon_code(offer.id, current_user.id)
        print("Creating coupon instance")
        coupon = Coupon(
            coupon_code=coupon_code,
            offer_id=offer.id,
            consumer_id=current_user.id,
            expiry_date=offer.end_date,
            status='active'
        )
        print("Saving coupon to database")
        coupon.save()

        return jsonify({
            "message": "Coupon created successfully",
            "description": "You can now use this coupon code to redeem the offer",
            "data": {
                'code': coupon.coupon_code,
                "qrCode": coupon.qr_code,
                'expiryDate': coupon.expiry_date,
                'status': coupon.status
            }
        }), 201
    except Exception as e:
        print(e)
        return jsonify({"message": str(e)}), 500


@offer.route('/categories', methods=['GET'])
def get_offer_categories():
    """
    Get all offer categories.
    """
    try:
        # Fetch offer categories from the database
        categories = db.session.query(Category).all()
        return jsonify({
            "message": "Successfully fetched all offer categories",
            "data": [{
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'imageURL': category.image_url,
            } for category in categories]
        }), 200
    except Exception as e:
        print(e)
        return jsonify({"message": str(e)}), 500


@offer.route('/featured', methods=['GET'])
def get_featured_offers():
    """
    Get all featured offers.
    """
    try:
        # Fetch featured non-expired offers from the database
        featured_offers = db.session.query(Offer).filter(
            Offer.featured_until > datetime.now(timezone.utc),
            Offer.status == 'active'
        ).order_by(Offer.featured_until.desc()
                   ).all()
        return jsonify([
            {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                },
                'status': offer.status,
                'startDate': offer.start_date,
                'endDate': offer.end_date,
                'termsAndConditions': offer.terms_and_conditions
            } for offer in featured_offers]), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@offer.route('/highlighted', methods=['GET'])
def get_highlighted_offers():
    """
    Get all highlighted offers.
    """
    try:
        # Fetch highlighted offers from the database
        highlighted_offers = db.session.query(Offer).filter(
            Offer.highlighted_until > datetime.now(timezone.utc),
            Offer.status == 'active'
        ).all()
        return jsonify({
            "message": "Successfully fetched all highlighted offers",
            "data": [offer.to_json() for offer in highlighted_offers]
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@offer.route('/latest', methods=['GET'])
def get_latest_offers():
    """
    Get all latest offers.
    """
    try:
        # Fetch latest offers from the database
        latest_offers = db.session.query(Offer).order_by(
            Offer.start_date.desc()).limit(10).all()
        return jsonify({
            "message": "Successfully fetched all latest offers",
            "data": [{
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                },
                'status': offer.status,
                'startDate': offer.start_date,
                'endDate': offer.end_date,
                'termsAndConditions': offer.terms_and_conditions
            } for offer in latest_offers]
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@offer.route('/recommended', methods=['GET'])
def get_recommended_offers():
    """
    Get recommended offers with filtering and sorting capabilities.
    Query parameters:
        - filters: comma-separated list of filter IDs (categories, discount types, etc.)
        - search: search query string
        - sort: sorting option (newest, highest-discount, expiring-soon)
    """
    try:
        # Get query parameters
        filters = request.args.get('filters', '').split(
            ',') if request.args.get('filters') else []
        search_query = request.args.get('search', '').lower()
        sort_option = request.args.get('sort', 'newest')

        # Base query
        query = session.query(Offer).filter(
            Offer.status == 'active',
            Offer.end_date > datetime.now(timezone.utc)
        )

        # Apply filters
        if filters:
            # Separate filter types
            category_filters = []
            discount_type_filters = []
            special_filters = []

            for f in filters:
                if f in ['percentage', 'fixed', 'bogo', 'free-item']:
                    discount_type_filters.append(f)
                elif f in ['expiring-soon', 'new-arrivals']:
                    special_filters.append(f)
                else:
                    category_filters.append(f)

            # Build filter conditions
            conditions = []

            if category_filters:
                conditions.append(Offer.category_id.in_(category_filters))

            if discount_type_filters:
                conditions.append(
                    Offer.discount_type.in_(discount_type_filters))

            if special_filters:
                for sf in special_filters:
                    if sf == 'expiring-soon':
                        # Offers expiring in the next 7 days
                        conditions.append(
                            Offer.end_date < datetime.now(timezone.utc) + timedelta(days=7))
                    elif sf == 'new-arrivals':
                        # Offers created in the last 7 days
                        conditions.append(
                            Offer.start_date > datetime.now(timezone.utc) - timedelta(days=7))

            if conditions:
                query = query.filter(or_(*conditions))

        # Apply search
        if search_query:
            query = query.filter(
                or_(
                    func.lower(Offer.title).contains(search_query),
                    func.lower(Offer.description).contains(search_query),
                    Offer.merchant.has(func.lower(
                        Consumer.name).contains(search_query))
                )
            )

        # Apply sorting
        if sort_option == 'newest':
            query = query.order_by(desc(Offer.start_date))
        elif sort_option == 'highest-discount':
            discount_value_case = case(
                [
                    (Offer.discount_type == 'percentage', Offer.discount_value),
                    (Offer.discount_type == 'fixed', Offer.discount_value * 100),
                    (Offer.discount_type == 'bogo', 50),
                    (Offer.discount_type == 'free-item', 100)
                ],
                else_=0
            )
            query = query.order_by(desc(discount_value_case))
        elif sort_option == 'expiring-soon':
            query = query.order_by(asc(Offer.end_date))

        # Execute query
        recommended_offers = query.limit(50).all()

        return jsonify({
            "message": "Successfully fetched recommended offers",
            "data": [{
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                },
                'category': offer.category.id if offer.category else None,
                'status': offer.status,
                'couponLimit': offer.coupon_limit,
                'startDate': offer.start_date.isoformat(),
                'endDate': offer.end_date.isoformat(),
                'termsAndConditions': offer.terms_and_conditions
            } for offer in recommended_offers]
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
