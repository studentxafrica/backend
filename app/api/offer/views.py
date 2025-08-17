from sqlalchemy.sql.expression import case  # type: ignore
from sqlalchemy import and_, or_, desc, asc, func  # type: ignore
from flask import jsonify, request, current_app
from datetime import datetime, timezone, timedelta  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from typing import List  # type: ignore
from app.models.offer import DISCOUNT_TYPES


from app.api.offer import offer
from app.api.offer.helpers import track_offer_view  # type: ignore
from app.models.offer import Offer
from app.models.coupon import Coupon
from app.models.consumer import Consumer
from app.models.category import Category
from app import db
from flask_jwt_extended import jwt_required, current_user, get_jwt_identity
from app.utils import generate_coupon_code
from flasgger import swag_from  # type: ignore
import os
from flask import g
from app.utils import roles_required  # type: ignore


session: Session = db.session


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
    offer: Offer = db.session.query(Offer).filter(Offer.id == id).first()
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
    try:
        user: Consumer = g.user
        if not user:
            return jsonify({"message": "Couldn't not verify current user identity"}), 404

        if not user.verified:
            return jsonify({
                "message": "User not verified",
                "description": "You need to verify your account before claiming a coupon"
            }), 403

        # Fetch offer by ID from the database
        offer: Offer = db.session.query(Offer).filter(Offer.id == id).first()
        if not offer:
            return jsonify({"message": "Offer not found"}), 404

        user_coupon: Coupon = db.session.query(Coupon).filter(
            Coupon.offer_id == offer.id,
            Coupon.consumer_id == user.id,
        ).first()

        if user_coupon:
            return jsonify({
                "message": "Coupon already claimed",
                "description": "You have already claimed a coupon for this offer",
                "data": {
                    'code': user_coupon.coupon_code,
                    "qrCode": user_coupon.qr_code,
                    'expiryDate': user_coupon.expiry_date,
                    'status': user_coupon.status
                }
            }), 409

        # Logic to create a coupon for the offer
        coupon_code = generate_coupon_code(offer.id, current_user.id)
        coupon = Coupon(
            coupon_code=coupon_code,
            offer_id=offer.id,
            consumer_id=current_user.id,
            expiry_date=offer.end_date,
            status='active'
        )
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
        current_app.logger.info(f"Error creating coupon: {str(e)}")
        return jsonify({"message": str(e)}), 500


@offer.route('/categories', methods=['GET'])
def get_offer_categories():
    """
    Get all offer categories.
    """
    # Fetch offer categories from the database
    try:
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
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'redemptionType': offer.redemption_type,
                'couponLimit': offer.coupon_limit,
                'category': {
                    'id': offer.category.id if offer.category else None,
                    'name': offer.category.name if offer.category else None,
                    'slug': offer.category.slug if offer.category else None,
                },
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
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'redemptionType': offer.redemption_type,
                'couponLimit': offer.coupon_limit,
                'category': {
                    'id': offer.category.id if offer.category else None,
                    'name': offer.category.name if offer.category else None,
                    'slug': offer.category.slug if offer.category else None,
                } if offer.category else None,
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
        from app.models.merchant import Merchant  # type: ignore
        if search_query:
            query = query.filter(
                or_(
                    func.lower(Offer.title).contains(search_query),
                    func.lower(Offer.description).contains(search_query),
                    Offer.merchant.has(func.lower(
                        Merchant.name).contains(search_query)),
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
                [
                    (Offer.discount_type == 'percentage', Offer.discount_value),
                    (Offer.discount_type == 'fixed_amount',
                     Offer.discount_value * 100),
                    (Offer.discount_type == 'buy_one_get_one', 50),
                    (Offer.discount_type == 'free_item', 100)
                ],
                else_=0
            )
            query = query.order_by(desc(discount_value_case))
        elif sort_option == 'expiring-soon':
            query = query.order_by(asc(Offer.end_date))

        # Execute query
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        recommended_offers: List[Offer] = query.limit(limit).offset(offset).all()

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

                'redemptionType': offer.redemption_type,
                'couponLimit': offer.coupon_limit,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                },
                'category': {
                    'id': offer.category.id,
                    'name': offer.category.name,
                } if offer.category else None,
                'status': offer.status,
                'couponLimit': offer.coupon_limit,
                'startDate': offer.start_date.isoformat(),
                'endDate': offer.end_date.isoformat(),
                'termsAndConditions': offer.terms_and_conditions
            } for offer in recommended_offers]
        }), 200
    except Exception as e:
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
                'discountType': similar_offer.discount_type,
                'discountValue': similar_offer.discount_value,
                'currency': similar_offer.currency,
                'merchant': {
                    'id': similar_offer.merchant.id,
                    'name': similar_offer.merchant.name,
                    'logo': similar_offer.merchant.logo,
                },
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
        required_fields = [
            'title', 'description', 'slug', 'cover_image', 'discount_type',
            'discount_value', 'currency', 'coupon_limit', 'redemption_type',
            'start_date', 'end_date'
        ]
        if not data:
            return jsonify({"message": "No data provided"}), 400

        from app.models.merchant import Merchant  # type: ignore
        merchant: Merchant = g.user
        if not merchant:
            return jsonify({"message": "Merchant not found"}), 401

        # Validate required fields
        required_fields = [
            'title', 'description', 'slug', 'cover_image', 'discount_type',
            'discount_value', 'currency', 'coupon_limit', 'redemption_type',
            'start_date', 'end_date'
        ]
        optional_fields = [
            'category_id', 'featured_until', 'highlighted_until', 'terms_and_conditions', 'tags', 'stores'
        ]
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"message": f"Missing required field: {field}"}), 400
        # upload cover image to cloudinary
        import cloudinary.uploader  # type: ignore
        if 'cover_image' in data:
            cover_image = data['cover_image']
            if not cover_image.startswith('http'):
                # Assuming cover_image is a file path or base64 string
                upload_result = cloudinary.uploader.upload(
                    cover_image, folder='offers/')
                data['cover_image'] = upload_result['secure_url']
        else:
            return jsonify({"message": "Missing required field: cover_image"}), 400
        # Create the offer instance
        offer = Offer(
            title=data.get('title'),
            description=data.get('description'),
            slug=data.get('slug'),
            cover_image=data.get('cover_image'),
            discount_type=data['discount_type'],
            discount_value=data.get('discount_value'),
            currency=data.get('currency'),
            coupon_limit=data.get('coupon_limit'),
            start_date=datetime.fromisoformat(data.get('start_date')),
            end_date=datetime.fromisoformat(data.get('end_date')),
            terms_and_conditions=data.get('terms_and_conditions', ''),
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
        offer: Offer = db.session.query(Offer).filter(Offer.id == id).first()
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
                'discountType': offer.discount_type,
                'discountValue': offer.discount_value,
                'currency': offer.currency,
                'merchant': {
                    'id': offer.merchant.id,
                    'name': offer.merchant.name,
                    'logo': offer.merchant.logo,
                    'website': offer.merchant.website,
                },
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
    query = query.with_hint(Offer, 'USE INDEX (idx_featured_status)')

    # Execute pagination
    pagination = query.paginate(page=page, per_page=per_page)
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
        offer: Offer = db.session.query(Offer).filter(
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
