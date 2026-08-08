from sqlalchemy.sql.expression import case  # type: ignore
from sqlalchemy import and_, or_, desc, asc, func  # type: ignore
from sqlalchemy.exc import IntegrityError  # type: ignore
from flask import jsonify, request, current_app
from datetime import datetime, timezone, timedelta  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from sqlalchemy.orm.scoping import scoped_session  # type: ignore
from typing import List  # type: ignore
from app.models.offer import DISCOUNT_TYPES, USAGE_TYPES, OFFER_KINDS
from uuid import uuid4


from app.api.offer import offer
from app.api.offer.helpers import (  # type: ignore
    track_offer_view, serialize_claim, is_valid_event_url, prepare_offer_fields
)
from app.models.offer import Offer
from app.models.coupon import Coupon, COUPON_STATUS
from app.models.consumer import Consumer
from app.models.category import Category
from app.models.merchant import Merchant
from app import db
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils import generate_coupon_code
from flasgger import swag_from  # type: ignore
import os
from flask import g
from app.utils import roles_required  # type: ignore


session: scoped_session = db.session

STUDENT_OWNED_CATEGORY_SLUG = "student-owned"
STUDENT_OWNED_FILTER_ID = "student-owned"
STUDENT_OWNED_CATEGORY_NAME = "Student-Owned"
STUDENT_OWNED_CATEGORY_IMAGE = "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80"


def is_student_owned_merchant(merchant: Merchant | None) -> bool:
    if not merchant:
        return False
    category = getattr(merchant, "category", None)
    return bool(category and getattr(category, "slug", None) == STUDENT_OWNED_CATEGORY_SLUG)


def serialize_offer_category(category: Category | None):
    if not category:
        return None
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
    }


@offer.route('/<id>', methods=['GET'])
@swag_from('docs/get-offer.yml')
@roles_required('consumer')
def get_offer_by_id(id: str):
    """
    Get offer by ID.
    Scenarios:
        - Get offer by ID
        - Offer not found
    """
    # try:
    # # Fetch offer by ID from the database
    user = g.user
    if not user:
        return jsonify({"message": "Couldn't verify current user identity"}), 401
    offer: Offer | None = db.session.query(Offer).filter(
        Offer.id == id).first()  # type: ignore[arg-type]
    if not offer:
        return jsonify({"message": "Offer not found"}), 404

    track_offer_view(offer.id, user.id)
    return jsonify({
        "message": "Successfully fetched offer",
        "data": {
            'id': offer.id,
            'title': offer.title,
            'description': offer.description,
            'slug': offer.slug,
            'coverImage': offer.cover_image,
            'offerKind': offer.offer_kind,
            'discountType': offer.discount_type,
            'discountValue': offer.discount_value,
            'currency': offer.currency,
            'usage_type': offer.usage_type,
            'merchant': {
                'id': offer.merchant.id,
                'name': offer.merchant.name,
                'logo': offer.merchant.logo,
                'website': offer.merchant.website,
                'isStudentOwned': is_student_owned_merchant(offer.merchant),
            },
            "isStudentOwned": is_student_owned_merchant(offer.merchant),
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


@offer.route('/<id>/coupons/create', methods=['POST'])
# @limiter.limit("1/sec")
@roles_required('consumer')
def create_coupon(id):
    """
    Create a coupon for an offer.
    Scenarios:
        - Create a coupon
        - Offer not found
        - Coupon already exists
    """
    user: Consumer = g.user
    if not user:
        return jsonify({"message": "Couldn't verify current user identity"}), 401

    if not user.verified:
        return jsonify({
            "message": "User not verified",
            "description": "You need to verify your account before claiming a coupon"
        }), 403

    session = db.session
    now = datetime.now(timezone.utc)

    try:

        offer: Offer | None = session.query(Offer).filter(
            Offer.id == id).with_for_update().first()
        if not offer:
            session.rollback()
            return jsonify({"message": "Offer not found"}), 404

        cannot_claim = "Cannot register for event" if offer.is_event \
            else "Cannot claim coupon"

        if offer.usage_type == USAGE_TYPES["TIERED"]:
            session.rollback()
            return jsonify({
                "message": cannot_claim,
                "description": "Tiered offers are not supported"
            }), 400

        if offer.status == 'sold_out':
            session.rollback()
            return jsonify({
                "message": cannot_claim,
                "description": "Event is fully booked" if offer.is_event else "Coupons sold out"
            }), 400
        if offer.status != 'active':
            session.rollback()
            return jsonify({
                "message": cannot_claim,
                "description": "Offer is not active"
            }), 400

        offer_end = offer.end_date
        if offer_end.tzinfo is None:
            offer_end = offer_end.replace(tzinfo=timezone.utc)
        if offer_end <= now:
            session.rollback()
            return jsonify({
                "message": cannot_claim,
                "description": "Offer has expired"
            }), 400

        if offer.is_event and not offer.ensure_event_qr_code():
            session.rollback()
            return jsonify({
                "message": cannot_claim,
                "description": "This event has no event link yet. Please try again later."
            }), 400

        existing_coupon = session.query(Coupon).filter(
            Coupon.offer_id == offer.id,
            Coupon.consumer_id == user.id,
            Coupon.status == COUPON_STATUS["ACTIVE"]
        ).with_for_update().first()

        if existing_coupon:
            existing_expiry = existing_coupon.expiry_date
            if existing_expiry.tzinfo is None:
                existing_expiry = existing_expiry.replace(tzinfo=timezone.utc)
            if existing_expiry <= now:
                existing_coupon.status = COUPON_STATUS["EXPIRED"]
                session.flush()
            else:
                session.rollback()
                return jsonify({
                    "message": "Already registered" if offer.is_event
                    else "Coupon already claimed",
                    "description": "You are already registered for this event"
                    if offer.is_event
                    else "You already have an active coupon for this offer",
                    "data": serialize_claim(offer, existing_coupon)
                }), 200

        from app.models.user_offer_usage import UserOfferUsage
        usage = session.query(UserOfferUsage).filter(
            UserOfferUsage.consumer_id == user.id,
            UserOfferUsage.offer_id == offer.id
        ).with_for_update().first()

        if not usage:
            usage = UserOfferUsage(
                consumer_id=user.id,
                offer_id=offer.id,
                usage_count=0,
                total_savings=0,
                total_redemptions=0
            )
            session.add(usage)
            session.flush()

        # Coupon availability check (claimed + redeemed)
        claimed_redeemed_count = None
        if offer.usage_type != USAGE_TYPES["UNLIMITED"]:
            coupon_limit = offer.coupon_limit or 0
            if coupon_limit <= 0:
                session.rollback()
                return jsonify({
                    "message": cannot_claim,
                    "description": "Event is fully booked" if offer.is_event else "Coupons sold out"
                }), 400
            claimed_redeemed_count = session.query(func.count(Coupon.id)).filter(
                Coupon.offer_id == offer.id,
                Coupon.status.in_([COUPON_STATUS["ACTIVE"],
                                   COUPON_STATUS["REDEEMED"]])
            ).scalar() or 0

        from app.api.offer.usage_helpers import evaluate_claim_rules, calculate_tiered_discount
        can_claim, reason = evaluate_claim_rules(
            offer=offer,
            usage=usage,
            has_active_coupon=False,
            claimed_redeemed_count=claimed_redeemed_count,
            now=now
        )
        if not can_claim:
            session.rollback()
            return jsonify({
                "message": cannot_claim,
                "description": reason
            }), 400

        usage.record_claim(commit=False)

        if offer.is_event:
            # Everyone who claims an event offer is handed the same link and the
            # same QR code, so nothing is generated per student. The stored code
            # is an internal registration reference and is never shown to them.
            coupon = Coupon(
                coupon_code=str(uuid4()),
                offer_id=offer.id,
                consumer_id=user.id,
                expiry_date=offer.end_date,
                status=COUPON_STATUS["ACTIVE"],
                qr_code=offer.event_qr_code
            )
        else:
            coupon = Coupon(
                coupon_code=generate_coupon_code(offer.id, user.id),
                offer_id=offer.id,
                consumer_id=user.id,
                expiry_date=offer.end_date,
                status=COUPON_STATUS["ACTIVE"]
            )
        session.add(coupon)

        discount_info = calculate_tiered_discount(
            offer, usage.usage_count - 1)

        session.commit()

        return jsonify({
            "message": "Registration confirmed" if offer.is_event
            else "Coupon created successfully",
            "description": "You are registered. Use the event link to join."
            if offer.is_event
            else f"You can now use this coupon code to redeem the offer. This is your {usage.usage_count} claim for this offer.",
            "data": {
                **serialize_claim(offer, coupon),
                'discount': discount_info,
                'usage_stats': {
                    'total_claims': usage.usage_count,
                    'total_savings': usage.total_savings,
                    'can_claim_more': usage.can_claim_more,
                    'next_available_claim': usage.next_available_claim.isoformat() if usage.next_available_claim else None
                }
            }
        }), 201
    except IntegrityError:
        session.rollback()
        existing_coupon = session.query(Coupon).filter(
            Coupon.offer_id == id,
            Coupon.consumer_id == user.id,
            Coupon.status == COUPON_STATUS["ACTIVE"]
        ).first()
        if existing_coupon:
            existing_offer = existing_coupon.offer
            return jsonify({
                "message": "Already registered" if existing_offer.is_event
                else "Coupon already claimed",
                "description": "You are already registered for this event"
                if existing_offer.is_event
                else "You already have an active coupon for this offer",
                "data": serialize_claim(existing_offer, existing_coupon)
            }), 409
        return jsonify({
            "message": "Cannot claim coupon",
            "description": "Unable to create coupon"
        }), 400
    except Exception as e:
        session.rollback()
        current_app.logger.info(f"Error creating coupon: {str(e)}")
        return jsonify({"message": 'Internal Server Error'}), 500


@offer.route('/categories', methods=['GET'])
def get_offer_categories():
    """
    Get all offer categories.
    """
    # Fetch offer categories from the database
    try:
        categories = db.session.query(Category).order_by(asc(Category.name)).all()
        category_payload = [{
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'imageURL': category.image_url,
        } for category in categories]

        student_owned_index = next(
            (idx for idx, category in enumerate(category_payload)
             if category.get("slug") == STUDENT_OWNED_CATEGORY_SLUG),
            None
        )

        if student_owned_index is None:
            category_payload.insert(0, {
                "id": STUDENT_OWNED_FILTER_ID,
                "name": STUDENT_OWNED_CATEGORY_NAME,
                "slug": STUDENT_OWNED_CATEGORY_SLUG,
                "imageURL": STUDENT_OWNED_CATEGORY_IMAGE,
            })
        elif student_owned_index != 0:
            student_owned = category_payload.pop(student_owned_index)
            category_payload.insert(0, student_owned)

        return jsonify({
            "message": "Successfully fetched all offer categories",
            "data": category_payload
        }), 200
    except Exception as e:
        return jsonify({
            "message": "Internal Server Error",
            "description": "Something went wrong while fetching categories. Please try again or contact support."
        }), 500


@offer.route('/featured', methods=['GET'])
def get_featured_offers():
    """
    Get all featured offers.
    """
    try:
        current_datetime = datetime.now(timezone.utc)
        # Fetch featured non-expired offers from the database
        featured_offers: List[Offer] = db.session.query(Offer).filter(
            # Offer.featured_until > datetime.now(timezone.utc),
            Offer.end_date > current_datetime
        ).order_by(
            Offer.featured_until.desc()
        ).limit(8).all()
        return jsonify([
            {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'offerKind': offer.offer_kind,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'redemptionType': offer.redemption_type,
                'couponLimit': offer.coupon_limit,
                'category': serialize_offer_category(offer.category),
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                    'isStudentOwned': is_student_owned_merchant(offer.merchant),
                },
                'isStudentOwned': is_student_owned_merchant(offer.merchant),
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
            Offer.end_date > datetime.now(timezone.utc)
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
        current_datetime = datetime.now(timezone.utc)
        latest_offers: List[Offer] = db.session.query(Offer).filter(
            Offer.end_date > current_datetime,
            # Offer.start_date >= current_datetime - timedelta(weeks=1),
        ).order_by(
            Offer.start_date
        ).limit(10).all()
        return jsonify({
            "message": "Successfully fetched all latest offers",
            "data": [{
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'offerKind': offer.offer_kind,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'redemptionType': offer.redemption_type,
                'couponLimit': offer.coupon_limit,
                'category': serialize_offer_category(offer.category),
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                    'isStudentOwned': is_student_owned_merchant(offer.merchant),
                },
                'isStudentOwned': is_student_owned_merchant(offer.merchant),
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
            Offer.end_date > datetime.now(timezone.utc),
            Offer.status == 'active',
        )

        # Apply filters
        if filters:
            # Separate filter types
            category_filters = []
            discount_type_filters = []
            special_filters = []

            for f in filters:
                if f in DISCOUNT_TYPES.values():
                    discount_type_filters.append(f)
                elif f in ['expiring-soon', 'new-arrivals', STUDENT_OWNED_FILTER_ID]:
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
                    elif sf == STUDENT_OWNED_FILTER_ID:
                        conditions.append(
                            Offer.merchant.has(
                                Merchant.category.has(Category.slug == STUDENT_OWNED_CATEGORY_SLUG)
                            )
                        )

            if conditions:
                query = query.filter(or_(*conditions))

        # Apply search
        if search_query:
            query = query.join(Merchant, Offer.merchant_id == Merchant.id).filter(
                or_(
                    func.lower(Offer.title).contains(search_query),
                    func.lower(Offer.description).contains(search_query),
                    func.lower(Merchant.name).contains(search_query),
                    Offer.tags.any(func.lower(
                        'name').contains(search_query)
                    ),
                    func.lower(Offer.currency).ilike(f'%{search_query}%')
                )
            )

        # Apply sorting
        if sort_option == 'newest':
            query = query.order_by(desc(Offer.start_date))
        elif sort_option == 'highest-discount':
            discount_value_case = case(
                (Offer.discount_type == 'percentage', Offer.discount_value),
                (Offer.discount_type == 'fixed_amount',
                 Offer.discount_value * 100),
                (Offer.discount_type == 'buy_one_get_one', 50),
                (Offer.discount_type == 'free_item', 100),
                else_=0
            )
            query = query.order_by(desc(discount_value_case))
        elif sort_option == 'expiring-soon':
            query = query.order_by(asc(Offer.end_date))

        # Execute query
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        recommended_offers: List[Offer] = query.limit(
            limit).offset(offset).all()

        return jsonify({
            "message": "Successfully fetched recommended offers",
            "data": [{
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'offerKind': offer.offer_kind,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,

                'usage_type': offer.usage_type,
                'max_claims_per_user': offer.max_claims_per_user,
                'cooldown_period_hours': offer.cooldown_period_hours,
                'tier_progression': offer.tier_progression,

                'redemptionType': offer.redemption_type,
                'couponLimit': offer.coupon_limit,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                    'isStudentOwned': is_student_owned_merchant(offer.merchant),
                },
                'category': serialize_offer_category(offer.category),
                'isStudentOwned': is_student_owned_merchant(offer.merchant),
                'status': offer.status,
                'couponLimit': offer.coupon_limit,
                'startDate': offer.start_date.isoformat(),
                'endDate': offer.end_date.isoformat(),
                'termsAndConditions': offer.terms_and_conditions
            } for offer in recommended_offers]
        }), 200
    except Exception as e:
        current_app.logger.error(
            f"Error fetching recommended offers: {str(e)}")
        return jsonify({"message": str(e)}), 500


@offer.route('/<id>/similar', methods=['GET'])
def get_similar_offers(id):
    """
    Get similar offers based on the category of the given offer ID.
    Scenarios:
    - Get similar offers
    - Offer not found
    """
    try:
        # Fetch the offer by ID
        offer = db.session.query(Offer).filter(Offer.id == id).first()
        if not offer:
            return jsonify({"message": "Offer not found"}), 404

        # Fetch similar offers based on the same category
        similar_offers: List[Offer] = db.session.query(Offer).filter(
            Offer.category_id == offer.category_id,
            Offer.id != id,
            Offer.end_date > datetime.now(timezone.utc)
        ).limit(10).all()

        return jsonify({
            "message": "Successfully fetched similar offers",
            "data": [{
                'id': similar_offer.id,
                'title': similar_offer.title,
                'description': similar_offer.description,
                'slug': similar_offer.slug,
                'coverImage': similar_offer.cover_image,
                'offerKind': similar_offer.offer_kind,
                'discountType': similar_offer.discount_type,
                'discountValue': similar_offer.discount_value,
                'currency': similar_offer.currency,
                'merchant': {
                    'id': similar_offer.merchant.id,
                    'name': similar_offer.merchant.name,
                    'logo': similar_offer.merchant.logo,
                    'isStudentOwned': is_student_owned_merchant(similar_offer.merchant),
                },
                'category': serialize_offer_category(similar_offer.category),
                'isStudentOwned': is_student_owned_merchant(similar_offer.merchant),
                'status': similar_offer.status,
                'startDate': similar_offer.start_date.isoformat(),
                'endDate': similar_offer.end_date.isoformat(),
                'termsAndConditions': similar_offer.terms_and_conditions
            } for similar_offer in similar_offers]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching similar offers: {str(e)}")
        return jsonify({"message": str(e)}), 500


@offer.route('/new', methods=['POST'])
@roles_required('merchant')
def create_offer():
    """
    Create a new offer.
    Scenarios:
        - Create a new offer
        - Missing required fields
        - Invalid data types
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "No data provided"}), 400

        from app.models.merchant import Merchant  # type: ignore
        merchant: Merchant = g.user
        if not merchant:
            return jsonify({"message": "Merchant not found"}), 401

        fields, error = prepare_offer_fields(data)
        if error:
            body, status = error
            return jsonify(body), status

        offer = Offer(
            **fields,
            merchant_id=merchant.id,
            category_id=merchant.category_id
        )

        if data.get('tags'):
            # Assuming tags is a list of tag names
            from app.models.offer import Tag
            tags = []
            for tag_name in data['tags']:
                tag = db.session.query(Tag).filter(
                    Tag.name == tag_name.lower().strip()).first()
                if not tag:
                    # Create a new tag if it doesn't exist
                    tag = Tag(name=tag_name.lower().strip())
                    tag.save()
                tags.append(tag)
            offer.tags = tags
        else:
            offer.tags = []

        # Save the offer to the database
        offer.save()

        return jsonify({
            "message": "Offer created successfully",
            "data": {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'offerKind': offer.offer_kind,
                'eventUrl': offer.event_url,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                    'website': offer.merchant.website,
                    'isStudentOwned': is_student_owned_merchant(offer.merchant),
                },
                "isStudentOwned": is_student_owned_merchant(offer.merchant),
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
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error creating offer: {str(e)}")
        return jsonify({"message": str(e)}), 500


@offer.route('/<id>/save', methods=['POST'])
@roles_required('consumer')
def save_offer(id):
    """
    Save an offer for the current user.
    Scenarios:
        - Save an offer
        - Offer not found
        - Offer already saved
    """
    try:
        # Fetch offer by ID from the database
        offer: Offer | None = db.session.query(
            Offer).filter(Offer.id == id).first()
        if not offer:
            return jsonify({"message": "Offer not found"}), 404

        # Get the current user from the request context
        user: Consumer = g.user
        if not user:
            return jsonify({"message": "Couldn't verify current user identity"}), 401

        # Check if the offer is already saved by the user
        from app.models.offer import SavedOffer  # type: ignore
        existing_saved_offer = db.session.query(SavedOffer).filter(
            SavedOffer.consumer_id == user.id).first()
        if existing_saved_offer:
            return jsonify({
                "message": "Offer already saved",
                "description": "You have already saved this offer"
            }), 409

        # Logic to save the offer for the user
        saved_offer = SavedOffer(
            offer_id=offer.id,
            consumer_id=user.id
        )
        saved_offer.save()

        return jsonify({
            "message": "Offer saved successfully",
            "data": {
                'id': offer.id,
                'title': offer.title,
                'description': offer.description,
                'slug': offer.slug,
                'coverImage': offer.cover_image,
                'offerKind': offer.offer_kind,
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                    'website': offer.merchant.website,
                    'isStudentOwned': is_student_owned_merchant(offer.merchant),
                },
                "isStudentOwned": is_student_owned_merchant(offer.merchant),
                'status': offer.status,
                'startDate': offer.start_date.isoformat(),
                'endDate': offer.end_date.isoformat(),
                'termsAndConditions': offer.terms_and_conditions
            }
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error saving offer: {str(e)}")
        return jsonify({"message": str(e)}), 500


@offer.route('/', methods=['GET'])
@swag_from(os.path.join('offer', 'docs', 'list-offers.yml'))
def list_offers():
    """List offers with optional filters"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        category = request.args.get('category')
        merchant = request.args.get('merchant')
        status = request.args.get('status')
        search = request.args.get('search')
        featured = request.args.get('featured', 'false').lower() == 'true'

        # Start with a base query
        query = Offer.query

        # Add filters
        if category:
            query = query.filter(Offer.category == category)
        if merchant:
            query = query.filter(Offer.merchant_id == merchant)
        if status:
            query = query.filter(Offer.status == status)
        if search:
            query = query.filter(
                (Offer.title.ilike(f'%{search}%')) |
                (Offer.description.ilike(f'%{search}%'))
            )
        if featured:
            current_time = datetime.now(timezone.utc)
            query = query.filter(
                and_(
                    Offer.featured_until > current_time,
                    Offer.end_date > datetime.now(timezone.utc)
                )
            ).order_by(Offer.featured_until.desc())

        # Add index hints for MySQL
        # query = query.with_hint(Offer, 'USE INDEX (idx_featured_status)')

        # Execute pagination
        pagination = query.paginate(page=page, per_page=per_page)
        print(f"Executed query: {str(query)}")  # Debugging line to check the generated SQL
        print(f"Total offers found: {pagination.total}")  # Debugging line to check total results
        offers = [offer.to_dict() for offer in pagination.items]

        return jsonify({
            'message': 'Successfully fetched offers',
            'data': offers,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }), 200
    except:
        current_app.logger.error("Error fetching offers", exc_info=True)
        return jsonify({
            "message": "Internal Server Error",
            "description": "An error occurred while trying to fetch offers"
        }), 500


@offer.route('/<id>', methods=['DELETE'])
@roles_required('merchant')
def delete_offer(id):
    """
    Delete an offer by ID.
    Scenarios:
        - Delete an offer
        - Offer not found
        - Unauthorized user
    """
    try:
        user = g.user
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

        # Fetch offer by ID from the database
        offer: Offer | None = db.session.query(Offer).filter(
            Offer.id == id,
            Offer.merchant_id == user.id
        ).first()
        if not offer:
            return jsonify({"message": "Offer not found"}), 404

        # Logic to delete the offer
        offer.delete()

        return jsonify({
            "message": "Offer deleted successfully"
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error deleting offer: {str(e)}")
        return jsonify({"message": str(e)}), 500


@offer.route('/<id>/usage-stats', methods=['GET'])
@roles_required('consumer')
def get_offer_usage_stats(id):
    """
    Get usage statistics for a specific offer for the current user.
    """
    try:
        user: Consumer = g.user
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

        # Check if offer exists
        offer: Offer | None = db.session.query(
            Offer).filter(Offer.id == id).first()
        if not offer:
            return jsonify({"message": "Offer not found"}), 404

        from app.api.offer.usage_helpers import get_user_usage_stats, get_next_available_claim_time

        # Get usage stats for this specific offer
        usage_stats = get_user_usage_stats(user.id, id)
        next_claim_time = get_next_available_claim_time(user.id, id)

        return jsonify({
            "message": "Successfully fetched usage statistics",
            "data": {
                "offer": {
                    "id": offer.id,
                    "title": offer.title,
                    "usage_type": offer.usage_type,
                    "max_claims_per_user": offer.max_claims_per_user,
                    "cooldown_period_hours": offer.cooldown_period_hours
                },
                "usage_stats": usage_stats,
                "next_available_claim": next_claim_time.isoformat() if next_claim_time else None
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching usage stats: {str(e)}")
        return jsonify({"message": str(e)}), 500


@offer.route('/user/savings-summary', methods=['GET'])
@roles_required('consumer')
def get_user_savings_summary():
    """
    Get comprehensive savings summary for the current user across all offers.
    """
    try:
        user: Consumer = g.user
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

        from app.api.offer.usage_helpers import get_user_usage_stats
        from app.models.user_offer_usage import UserOfferUsage

        # Get aggregate stats across all offers
        aggregate_stats = get_user_usage_stats(user.id)

        # Get top offers by savings
        top_offers = db.session.query(UserOfferUsage).filter(
            UserOfferUsage.consumer_id == user.id,
            UserOfferUsage.total_savings > 0
        ).order_by(UserOfferUsage.total_savings.desc()).limit(5).all()

        top_offers_data = []
        for usage in top_offers:
            top_offers_data.append({
                "offer": {
                    "id": usage.offer.id,
                    "title": usage.offer.title,
                    "merchant_name": usage.offer.merchant.name
                },
                "total_savings": usage.total_savings,
                "usage_count": usage.usage_count,
                "total_redemptions": usage.total_redemptions
            })

        # Get recent activity
        recent_activity = db.session.query(UserOfferUsage).filter(
            UserOfferUsage.consumer_id == user.id,
            UserOfferUsage.last_claimed_at != None
        ).order_by(UserOfferUsage.last_claimed_at.desc()).limit(10).all()

        recent_activity_data = []
        for usage in recent_activity:
            recent_activity_data.append({
                "offer": {
                    "id": usage.offer.id,
                    "title": usage.offer.title,
                    "merchant_name": usage.offer.merchant.name
                },
                "last_claimed_at": usage.last_claimed_at.isoformat() if usage.last_claimed_at else None,
                "usage_count": usage.usage_count
            })

        return jsonify({
            "message": "Successfully fetched savings summary",
            "data": {
                "aggregate_stats": aggregate_stats,
                "top_offers_by_savings": top_offers_data,
                "recent_activity": recent_activity_data
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching savings summary: {str(e)}")
        return jsonify({"message": str(e)}), 500


@offer.route('/<id>/available-claims', methods=['GET'])
@roles_required('consumer')
def check_available_claims(id):
    """
    Check how many more times a user can claim a specific offer.
    """
    try:
        user: Consumer = g.user
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

        # Check if offer exists
        offer: Offer | None = db.session.query(
            Offer).filter(Offer.id == id).first()
        if not offer:
            return jsonify({"message": "Offer not found"}), 404

        from app.api.offer.usage_helpers import can_user_claim_offer, get_or_create_user_usage

        if offer.usage_type == USAGE_TYPES["TIERED"]:
            return jsonify({
                "message": "Tiered offers are not supported"
            }), 400

        can_claim, reason = can_user_claim_offer(user.id, id)
        usage = get_or_create_user_usage(
            user.id, id, create_if_missing=False)
        usage_count = usage.usage_count if usage else 0
        last_claimed_at = usage.last_claimed_at if usage else None

        # Calculate remaining claims based on usage type
        remaining_claims = None
        if offer.usage_type == 'single_use':
            remaining_claims = 1 - usage_count if usage_count == 0 else 0
        elif offer.usage_type == 'multi_use':
            remaining_claims = max(
                0, offer.max_claims_per_user - usage_count)
        elif offer.usage_type == 'unlimited':
            remaining_claims = "unlimited"

        # What the user already holds, so a claimed offer can show its code or
        # event link again instead of a dead end
        active_coupon = db.session.query(Coupon).filter(
            Coupon.offer_id == offer.id,
            Coupon.consumer_id == user.id,
            Coupon.status == COUPON_STATUS["ACTIVE"],
            Coupon.expiry_date > datetime.now(timezone.utc)
        ).order_by(Coupon.created_at.desc()).first()

        return jsonify({
            "message": "Successfully checked claim availability",
            "data": {
                "can_claim_now": can_claim,
                "reason": reason if not can_claim else None,
                "existing_claim": serialize_claim(offer, active_coupon) if active_coupon else None,
                "remaining_claims": remaining_claims,
                "current_usage_count": usage_count,
                "next_available_claim": usage.next_available_claim.isoformat() if usage and usage.next_available_claim else None,
                "offer_details": {
                    "usage_type": offer.usage_type,
                    "max_claims_per_user": offer.max_claims_per_user,
                    "cooldown_period_hours": offer.cooldown_period_hours
                }
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error checking available claims: {str(e)}")
        return jsonify({"message": str(e)}), 500
