from typing import Tuple, Any  # type: ignore
from sqlalchemy import Row
from app.utils import roles_required
from urllib.parse import urlparse
import os
import json
from collections import defaultdict
from types import SimpleNamespace
from dateutil.relativedelta import relativedelta  # type: ignore
from datetime import datetime, timedelta
from sqlalchemy import func, extract, case, and_, or_, distinct  # type: ignore
from . import user
from flask import jsonify, request, g
from app import db
from app.models.merchant import Merchant
from app.models.category import Category  # type: ignore
from app.models.offer import Offer  # type: ignore
from app.models.coupon import Coupon  # type: ignore
from app.models.consumer import Consumer  # type: ignore
from app.models.store import Store  # type: ignore
from typing import List

STUDENT_OWNED_CATEGORY_SLUG = "student-owned"
STUDENT_OWNED_CATEGORY_NAME = "Student-Owned"
STUDENT_OWNED_CATEGORY_IMAGE = "https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80"


def _is_student_owned_merchant(merchant: Merchant | None) -> bool:
    if not merchant:
        return False
    return bool(
        getattr(merchant, "category", None)
        and getattr(merchant.category, "slug", None) == STUDENT_OWNED_CATEGORY_SLUG
    )


def _get_or_create_student_owned_category() -> Category:
    student_owned_category = db.session.query(Category).filter(
        Category.slug == STUDENT_OWNED_CATEGORY_SLUG
    ).first()
    if not student_owned_category:
        student_owned_category = Category(
            name=STUDENT_OWNED_CATEGORY_NAME,
            slug=STUDENT_OWNED_CATEGORY_SLUG,
            image_url=STUDENT_OWNED_CATEGORY_IMAGE,
            active=True,
        )
        db.session.add(student_owned_category)
        db.session.flush()
    return student_owned_category


@user.route('/merchant/me', methods=['GET'])
@roles_required('merchant')
def get_current_merchant_profile():
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 401
    merchant_data = {
        'id': merchant.id,
        'name': merchant.name,
        'email': merchant.email,
        'website': merchant.website,
        'phone': merchant.phone,
        'logo': merchant.logo,
        'joinDate': merchant.created_at.isoformat(),
        'preferredCurrency': merchant.preferred_currency,
        'address': merchant.address,
        'city': merchant.city,
        'country': merchant.country,
        'zipcode': merchant.zip_code,
        'isApproved': merchant.approved,
        'isStudentOwned': _is_student_owned_merchant(merchant),
        'offersCount': len(merchant.offers),
        'category': {
            'id': merchant.category.id if merchant.category else None,
            'name': merchant.category.name if merchant.category else None,
            'slug': merchant.category.slug if merchant.category else None,
        }
    }
    return jsonify({
        "message": "Merchant profile retrieved successfully",
        "data": merchant_data
    }), 200


@user.route('/merchant/profile', methods=['PUT'])
@roles_required('merchant')
def update_merchant_profile():
    """
    Update the merchant profile.
    Scenarios:
        - Update merchant profile with valid data
        - Update merchant profile with invalid data
        - Update merchant profile with missing fields
    """
    print(request.get_json())
    user_data = request.get_json()
    if not user_data:
        return jsonify({"error": "Missing JSON in request"}), 400
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 401
    raw_is_student_owned = user_data.pop(
        'isStudentOwned',
        user_data.pop('is_student_owned', None)
    )
    if raw_is_student_owned is not None:
        is_student_owned = str(raw_is_student_owned).lower() in {'1', 'true', 'yes', 'on'}
        if is_student_owned:
            student_owned_category = _get_or_create_student_owned_category()
            merchant.category_id = student_owned_category.id
        elif _is_student_owned_merchant(merchant):
            merchant.category_id = None

    ACCEPTED_PROFILE_UPDATE_FIELDS = [
        'name', 'email', 'website', 'phone', 'logo', 'preferredCurrency',
        'address', 'city', 'country', 'zipcode'
    ]
    print(user_data)
    for key, val in user_data.items():
        if hasattr(merchant, key) and key in ACCEPTED_PROFILE_UPDATE_FIELDS:
            if key == 'logo' and val and not val.startswith('http'):
                # If logo is a local file, upload it to Cloudinary
                import cloudinary.uploader  # type: ignore
                upload_result = cloudinary.uploader.upload(
                    val, folder='merchants/logos/')
                setattr(merchant, key, upload_result['secure_url'])
            else:
                setattr(merchant, key, val)
            if key == 'email' and val != merchant.email:
                merchant.email_verified_on = None

    merchant.save()
    merchant_data = {
        'id': merchant.id,
        'name': merchant.name,
        'email': merchant.email,
        'website': merchant.website,
        'phone': merchant.phone,
        'logo': merchant.logo,
        'joinDate': merchant.created_at.isoformat(),
        'preferredCurrency': merchant.preferred_currency,
        'address': merchant.address,
        'city': merchant.city,
        'country': merchant.country,
        'zipcode': merchant.zip_code,
        'isApproved': merchant.approved,
        'isStudentOwned': _is_student_owned_merchant(merchant),
        'emailVerified': merchant.email_verified,
        'offersCount': len(merchant.offers),
        'category': {
            'id': merchant.category.id if merchant.category else None,
            'name': merchant.category.name if merchant.category else None,
            'slug': merchant.category.slug if merchant.category else None,
        }
    }
    return jsonify({
        "message": "Update merchant profile",
        "data": merchant_data
    }), 200


@user.route('/merchant/dashboard', methods=['GET'])
@roles_required('merchant')
def get_merchant_dashboard():
    merchant: Merchant = g.user

    if not merchant:
        return jsonify({"error": "Merchant not found"}), 401

    # Get merchant offers
    merchant_offers = merchant.offers
    offer_ids = [offer.id for offer in merchant_offers]

    # Get all coupons for these offers
    merchant_coupons = db.session.query(Coupon).filter(
        Coupon.offer_id.in_(offer_ids)).all()

    # 1. Key Metrics
    active_offers = len([o for o in merchant_offers if o.status == 'active'])
    total_coupons = len(merchant_coupons)
    redeemed_coupons = len(
        [c for c in merchant_coupons if c.status == 'redeemed'])
    active_coupons = len([c for c in merchant_coupons if c.status == 'active'])
    expired_coupons = len(
        [c for c in merchant_coupons if c.status == 'expired'])

    redemption_rate = round(
        (redeemed_coupons / total_coupons * 100)) if total_coupons > 0 else 0

    # 2. Customer metrics
    consumer_ids = list(
        set([c.consumer_id for c in merchant_coupons if c.consumer_id]))
    unique_customers = len(consumer_ids)

    # Count repeat customers (have more than one coupon)
    consumer_coupon_counts = defaultdict(int)
    for coupon in merchant_coupons:
        if coupon.consumer_id:
            consumer_coupon_counts[coupon.consumer_id] += 1

    repeat_customers = len(
        [cid for cid, count in consumer_coupon_counts.items() if count > 1])

    # 3. Offer Performance
    offer_performance = []
    for offer in merchant_offers:
        offer_coupons = [c for c in merchant_coupons if c.offer_id == offer.id]
        redeemed = len([c for c in offer_coupons if c.status == 'redeemed'])
        offer_performance.append({
            'id': offer.id,
            'title': offer.title,
            'total': len(offer_coupons),
            'redeemed': redeemed,
            'redemptionRate': round((redeemed / len(offer_coupons) * 100)) if len(offer_coupons) > 0 else 0,
            'discountType': offer.discount_type,
            'discountValue': offer.discount_value
        })

    # Sort by most redeemed
    offer_performance.sort(key=lambda x: x['redeemed'], reverse=True)

    # 4. Customer Segmentation by School
    school_counts = defaultdict(int)
    for coupon in merchant_coupons:
        if coupon.consumer and coupon.consumer.school:
            school_counts[coupon.consumer.school] += 1

    school_data = [{'name': school, 'value': count}
                   for school, count in school_counts.items()]
    school_data.sort(key=lambda x: x['value'], reverse=True)

    # 5. Redemption Timeline (by hour)
    hour_counts = defaultdict(int)
    for coupon in merchant_coupons:
        if coupon.status == 'redeemed' and coupon.redeemed_at:
            hour = coupon.redeemed_at.hour
            hour_counts[hour] += 1

    timeline_data = [{'hour': f"{hour}:00", 'redemptions': hour_counts.get(hour, 0)}
                     for hour in range(24)]

    # 6. Discount Type Effectiveness
    discount_stats = defaultdict(lambda: {'total': 0, 'redeemed': 0})
    for coupon in merchant_coupons:
        offer = next(
            (o for o in merchant_offers if o.id == coupon.offer_id), None)
        if offer:
            discount_stats[offer.discount_type]['total'] += 1
            if coupon.status == 'redeemed':
                discount_stats[offer.discount_type]['redeemed'] += 1

    discount_data = [{
        'type': discount_type,
        'redemptionRate': round((stats['redeemed'] / stats['total'] * 100)) if stats['total'] > 0 else 0
    } for discount_type, stats in discount_stats.items()]

    response = {
        'keyMetrics': {
            'activeOffers': active_offers,
            'totalOffers': len(merchant_offers),
            'totalCoupons': total_coupons,
            'redeemedCoupons': redeemed_coupons,
            'activeCoupons': active_coupons,
            'expiredCoupons': expired_coupons,
            'redemptionRate': redemption_rate,
            'uniqueCustomers': unique_customers,
            'repeatCustomers': repeat_customers
        },
        'offerPerformance': offer_performance,
        'customerSegmentation': school_data[:5],  # Top 5 schools
        'redemptionTimeline': timeline_data,
        'discountEffectiveness': discount_data
    }

    return jsonify(response)


@user.route('/merchant/profile/password', methods=['PUT'])
@roles_required('merchant')
def update_merchant_password():
    """
    Update the merchant password.
    Scenarios:
            - Update merchant password with valid data
            - Update merchant password with invalid data
            - Update merchant password with missing fields
    """
    user_data = request.get_json()
    if not user_data or 'password' not in user_data:
        return jsonify({"error": "Missing JSON in request or password field"}), 400
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 401
    if not merchant.verify_password(user_data.get('oldPassword')):
        return jsonify({"error": "Old password is incorrect"}), 401
    new_password = user_data.get('password')
    setattr(merchant, 'password', new_password)
    merchant.save()
    return jsonify({
        "message": "Merchant password updated successfully"
    }), 200


@user.route('/merchant/offers/<id>', methods=['PUT'])
@roles_required('merchant')
def edit_merchant_offer(id):
    """
    Get a specific offer for the merchant.
    Scenarios:
    - Get a valid offer
    - Offer not found
    """
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"message": "Merchant not found"}), 401
    from app.models.offer import Offer

    offer: Offer | None = db.session.query(Offer).filter_by(
        id=id, merchant_id=merchant.id).first()
    if not offer:
        return jsonify({"message": "Offer not found"}), 404

    ALLOWED_UPDATE_FIELDS: List[str] = [
        'title', 'description', 'slug', 'cover_image', 'discount_type',
        'discount_value', 'currency', 'category_id', 'coupon_limit',
        'status', 'start_date', 'end_date', 'terms_and_conditions', 'tags'
    ]

    data = request.get_json()

    import cloudinary.uploader  # type: ignore
    if 'cover_image' in data:
        cover_image = data['cover_image']
        if not cover_image.startswith('http'):
            # Delete the old image from Cloudinary if it exists
            if offer.cover_image and offer.cover_image.startswith('http'):
                # Extract public_id from the URL
                parsed_url = urlparse(offer.cover_image)
                public_id = os.path.splitext(
                    os.path.basename(parsed_url.path))[0]
                # If using folders, include them in public_id
                folder = 'offers/'
                if folder not in public_id:
                    public_id = f"{folder}{public_id}"
                try:
                    cloudinary.uploader.destroy(public_id)
                    print(cloudinary.config())
                except Exception:
                    pass  # Ignore errors if image does not exist
            # Upload the new image
            upload_result = cloudinary.uploader.upload(
                cover_image, folder='offers/')
            data['cover_image'] = upload_result['secure_url']

    if not data:
        return jsonify({"error": "No data provided"}), 400

    if data.get('event_url'):
        from app.api.offer.helpers import is_valid_event_url
        if not offer.is_event:
            return jsonify({"message": "An event link can only be set on event offers"}), 400
        if not is_valid_event_url(data['event_url']):
            return jsonify({
                "message": "Invalid event link. Provide a link starting with http:// or https://"
            }), 400
        event_url = data['event_url'].strip()
        if event_url != offer.event_url:
            from app.utils import generate_qr
            offer.event_url = event_url
            offer.event_qr_code = generate_qr(event_url)
            # Registrations already handed out carry this same QR code
            db.session.query(Coupon).filter(Coupon.offer_id == offer.id).update(
                {Coupon.qr_code: offer.event_qr_code}, synchronize_session=False)

    for field in data:
        if field in ALLOWED_UPDATE_FIELDS and (data[field] or field == 'tags'):
            # Update tag names if provided
            if field == 'tags':
                from app.models import Tag
                tags = db.session.query(Tag).filter(
                    Tag.name.in_(data[field])
                ).all()
                new_tags = [tag for tag in tags]
                for tag_name in data[field]:
                    if not (tag := next((t for t in tags if t.name == tag_name), None)):
                        tag = Tag(name=tag_name)
                        tag.save()
                        new_tags.append(tag)
                print("New tags for offer:", new_tags)
                offer.tags = new_tags

            else:
                setattr(offer, field, data[field])

    offer.save()

    return jsonify({
        "message": "Merchant offer updated successfully",
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
            'category': {
                'id': offer.merchant.category.id if offer.merchant.category else None,
                'name': offer.merchant.category.name if offer.merchant.category else None,
            },
            'merchant': {
                'id': offer.merchant.id,
                'name': offer.merchant.name,
                'logo': offer.merchant.logo,
                'website': offer.merchant.website,
                'isStudentOwned': _is_student_owned_merchant(offer.merchant),
            },
            'isStudentOwned': _is_student_owned_merchant(offer.merchant),
            'coupons': {
                'total': offer.coupon_limit,
                'redeemed': len([coupon for coupon in offer.coupons if coupon.redeemed]),
                'claimed': len([coupon for coupon in offer.coupons if coupon.active]),
            },
            'status': offer.status,
            'startDate': offer.start_date,
            'endDate': offer.end_date,
            'termsAndConditions': offer.terms_and_conditions,
            'tags': [tag.name for tag in offer.tags],
        }
    }), 200


@user.route('/merchant/offers', methods=['GET'])
@roles_required('merchant')
def get_merchant_offers():
    """
    Get all offers for the merchant.
    Scenarios:
    - Get all offers for the merchant
    - No offers found for the merchant
    """
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"message": "Merchant not found"}), 401
    from typing import List
    from app.models.offer import Offer  # type: ignore
    offers: List[Offer] = merchant.offers
    if not offers:
        return jsonify({"message": "No offers found for this merchant"}), 200
    offer_data = [{
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
        'category': {
            'id': offer.merchant.category.id if offer.merchant.category else None,
            'name': offer.merchant.category.name if offer.merchant.category else None,
        },
        'merchant': {
            'id': offer.merchant.id,
            'name': offer.merchant.name,
            'logo': offer.merchant.logo,
            'website': offer.merchant.website,
            'isStudentOwned': _is_student_owned_merchant(offer.merchant),
        },
        'isStudentOwned': _is_student_owned_merchant(offer.merchant),
        'coupons': {
            'total': offer.coupon_limit,
            'redeemed': len([coupon for coupon in offer.coupons if coupon.redeemed]),
            'claimed': len([coupon for coupon in offer.coupons if coupon.active]),
        },
        'status': offer.status,
        'startDate': offer.start_date,
        'endDate': offer.end_date,
        'termsAndConditions': offer.terms_and_conditions,
        'tags': [tag.name for tag in offer.tags],
    } for offer in offers]
    return jsonify({
        "message": "Merchant offers retrieved successfully",
        "data": offer_data
    }), 200


@user.route('/merchant/coupons', methods=['GET'])
@roles_required('merchant')
def get_merchant_coupons():
    """
    Get all coupons for the merchant.
    Scenarios:
    - Get all coupons for the merchant
    - No coupons found for the merchant
    """
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({"error": "Merchant not found"}), 401
    from typing import List
    from app.models.coupon import Coupon

    merchant_offers = merchant.offers
    if not merchant_offers:
        return jsonify({"message": "No offers found for this merchant"}), 404
    coupons: List[Coupon] = []
    for offer in merchant_offers:
        coupons.extend(offer.coupons)

    if not coupons:
        return jsonify({"message": "No coupons found for this merchant"}), 404
    coupon_data = [{
        'id': coupon.id,
        'couponCode': coupon.coupon_code,
        'offer': {
            'id': coupon.offer.id,
            'title': coupon.offer.title,
            'slug': coupon.offer.slug,
            'coverImage': coupon.offer.cover_image,
            'offerKind': coupon.offer.offer_kind,
            'eventUrl': coupon.offer.event_url,
            'discountType': coupon.offer.discount_type,
            'discountValue': coupon.offer.discount_value,
            'currency': coupon.offer.currency,
        },
        'consumer': {
            'id': coupon.consumer.id,
            'name': coupon.consumer.first_name + ' ' + coupon.consumer.last_name,
            'email': coupon.consumer.email,
        } if coupon.consumer else None,
        'redeemedAt': coupon.redeemed_at.isoformat() if coupon.redeemed_at else None,
        'expiryDate': coupon.expiry_date.isoformat(),
        'status': coupon.status,
        'qrCode': coupon.qr_code
    } for coupon in coupons]
    return jsonify({
        "message": "Merchant coupons retrieved successfully",
        "data": coupon_data
    }), 200


@user.route('/merchant/offers/analytics', methods=['GET'])
@roles_required('merchant')
def get_merchant_offer_analytics():
    merchant: Merchant = g.user
    if not merchant:
        return jsonify({'error': 'Merchant ID is required'}), 401

    # Time period for analytics (default: last 6 months)
    time_period = int(request.args.get('time_period', 6))  # in months

    # Get base query for merchant's offers
    offers_query = db.session.query(Offer).filter_by(merchant_id=merchant.id)

    # 1. Basic Counts
    total_offers = offers_query.count()
    active_offers = offers_query.filter_by(status='active').count()
    expired_offers = offers_query.filter_by(status='expired').count()

    # 2. Coupon Statistics
    coupon_stats = db.session.query(
        func.sum(Offer.coupon_limit).label('total_coupons'),
        func.sum(Coupon.id.isnot(None)).label('claimed_coupons'),
        func.sum(case((Coupon.status == 'redeemed', 1), else_=0)).label(
            'redeemed_coupons')
    ).join(Coupon, Coupon.offer_id == Offer.id, isouter=True).filter(
        Offer.merchant_id == merchant.id
    ).first()
    if not coupon_stats:
        coupon_stats = SimpleNamespace(
            total_coupons=0,
            claimed_coupons=0,
            redeemed_coupons=0
        )

    # 3. Revenue Calculations
    revenue_stats = db.session.query(
        func.sum(Offer.revenue_generated).label('total_revenue'),
        func.avg(Offer.revenue_generated).label('avg_revenue_per_offer'),
        func.avg(case((Coupon.status == 'redeemed', Offer.revenue_generated /
                 Coupon.id.isnot(None)), else_=0)).label('avg_revenue_per_redemption')
    ).join(Coupon, Coupon.offer_id == Offer.id, isouter=True).filter(
        Offer.merchant_id == merchant.id
    ).first()
    if not revenue_stats:
        revenue_stats = SimpleNamespace(
            total_revenue=0,
            avg_revenue_per_offer=0,
            avg_revenue_per_redemption=0
        )

    # 4. Performance Metrics
    performance_metrics = db.session.query(
        func.sum(Offer.view_count).label('total_views'),
        func.sum(Offer.unique_visitors).label('unique_visitors'),
        func.avg(case((Offer.view_count > 0, Offer.unique_visitors /
                 Offer.view_count * 100), else_=0)).label('click_through_rate'),
        func.avg(Offer.avg_redemption_time_hours).label('avg_redemption_time')
    ).filter(
        Offer.merchant_id == merchant.id
    ).first()
    if not performance_metrics:
        performance_metrics = SimpleNamespace(
            total_views=0,
            unique_visitors=0,
            click_through_rate=0,
            avg_redemption_time=0
        )

    # 5. Category Distribution
    category_distribution = db.session.query(
        Category.name,
        func.count(Offer.id).label('offer_count')
    ).join(Offer, Offer.category_id == Category.id).filter(
        Offer.merchant_id == merchant.id
    ).group_by(Category.name).all()
    # Format category distribution

    # 6. Redemption Trends (last 6 months)
    end_date = datetime.now()
    start_date = end_date - relativedelta(months=time_period)

    redemption_trends = db.session.query(
        extract('year', Coupon.created_at).label('year'),
        extract('month', Coupon.created_at).label('month'),
        func.count(Coupon.id).label('claimed'),
        func.count(case((Coupon.status == 'redeemed', 1),
                   else_=None)).label('redeemed')
    ).join(Offer, Offer.id == Coupon.offer_id).filter(
        Offer.merchant_id == merchant.id,
        Coupon.created_at >= start_date,
        Coupon.created_at <= end_date
    ).group_by(
        extract('year', Coupon.created_at),
        extract('month', Coupon.created_at)
    ).order_by(
        extract('year', Coupon.created_at),
        extract('month', Coupon.created_at)
    ).all()

    # Format redemption trends by month name
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May',
                   'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    formatted_redemption_trends = []
    for trend in redemption_trends:
        formatted_redemption_trends.append({
            'name': f"{month_names[int(trend.month)-1]} {int(trend.year)}",
            'claimed': trend.claimed,
            'redeemed': trend.redeemed
        })

    # 7. Top Performing Offers (by claims)
    top_performing_offers: List[Row[Tuple]] = db.session.query(
        Offer.title,
        Offer.view_count,
        Offer.unique_visitors,
        func.count(Coupon.id).label('claims'),
        func.count(case((Coupon.status == 'redeemed', 1),
                   else_=None)).label('redeemed'),
        Offer.revenue_generated
    ).join(Coupon, Coupon.offer_id == Offer.id, isouter=True).filter(
        Offer.merchant_id == merchant.id,
    ).group_by(Offer.id).order_by(
        func.count(Coupon.id).desc()
    ).limit(5).all()

    # Format the response
    response = {
        'totalOffers': total_offers,
        'activeOffers': active_offers,
        'expiredOffers': expired_offers,
        'couponStats': {
            'total': coupon_stats.total_coupons or 0,
            'claimed': coupon_stats.claimed_coupons or 0,
            'redeemed': coupon_stats.redeemed_coupons or 0,
            'redemptionRate': (coupon_stats.redeemed_coupons / coupon_stats.claimed_coupons * 100) if coupon_stats.claimed_coupons else 0
        },
        'revenueStats': {
            # Convert cents to dollars
            'totalRevenue': (revenue_stats.total_revenue or 0) / 100,
            'avgRevenuePerOffer': (revenue_stats.avg_revenue_per_offer or 0) / 100,
            'avgRevenuePerRedemption': (revenue_stats.avg_revenue_per_redemption or 0) / 100
        },
        'performanceMetrics': {
            'totalViews': performance_metrics.total_views or 0,
            'uniqueVisitors': performance_metrics.unique_visitors or 0,
            'clickThroughRate': performance_metrics.click_through_rate or 0,
            'avgRedemptionTime': performance_metrics.avg_redemption_time or 0
        },
        'categoryDistribution': [
            {'name': cat, 'value': count}
            for cat, count in category_distribution
        ] if category_distribution else [],
        'redemptionTrends': formatted_redemption_trends,
        'topPerformingOffers': [
            {
                'title': offer.title,
                'views': offer.view_count,
                'uniqueVisitors': offer.unique_visitors,
                'claims': offer.claims,
                'redeemed': offer.redeemed,
                'revenue': (offer.revenue_generated or 0) / 100,
                'conversionRate': (offer.claims / offer.view_count * 100) if offer.view_count else 0
            }
            for offer in top_performing_offers
        ]
    }

    return jsonify(response)


@user.route('/merchant/analytics', methods=['GET'])
@roles_required('merchant')
def get_general_merchant_analytics():
    days = int(request.args.get('days', 30))  # Default to 30 days

    merchant: Merchant = g.user
    if not merchant:
        return jsonify({'error': 'Merchant ID is required'}), 401

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # 1. Basic offer statistics
    offers: List[Row[Tuple[str, str, int, int, Any]]] = db.session.query(
        Offer.id,
        Offer.title,
        func.count(Coupon.id).label('redemptions'),
        Offer.view_count,
        func.sum(case((Coupon.status == 'redeemed',
                 Offer.revenue_generated), else_=0)).label('revenue')
    ).join(Coupon, Coupon.offer_id == Offer.id, isouter=True).filter(
        Offer.merchant_id == merchant.id,
    ).group_by(Offer.id).all()

    # 2. School distribution
    schools = db.session.query(
        Consumer.school,
        func.count(Coupon.id).label('redemptions')
    ).join(Coupon, Coupon.consumer_id == Consumer.id).join(
        Offer, Offer.id == Coupon.offer_id
    ).filter(
        Offer.merchant_id == merchant.id,
        Coupon.status == 'redeemed',
        Coupon.redeemed_at >= start_date,
        Coupon.redeemed_at <= end_date
    ).group_by(Consumer.school).all()

    school_data = {school: count for school, count in schools}

    # 3. Location redemption data
    locations = db.session.query(
        Store.name,
        func.count(Coupon.id).label('redemptions')
    ).join(Offer, Offer.merchant_id == Store.merchant_id).join(
        Coupon, Coupon.offer_id == Offer.id
    ).filter(
        Offer.merchant_id == merchant.id,
        Coupon.status == 'redeemed',
        Coupon.redeemed_at >= start_date,
        Coupon.redeemed_at <= end_date,
    ).group_by(Store.name).all()

    total_redemptions = sum(loc.redemptions for loc in locations) or 0
    location_data = [{
        'name': loc.name,
        'redemptions': loc.redemptions or 0,
        'percent': round((loc.redemptions / total_redemptions) * 100)
    } for loc in locations]

    # 4. Daily redemption trends
    redemption_days = db.session.query(
        func.date(Coupon.redeemed_at).label('day'),
        func.count(Coupon.id).label('redemptions')
    ).join(Offer, Offer.id == Coupon.offer_id).filter(
        Offer.merchant_id == merchant.id,
        Coupon.status == 'redeemed',
        Coupon.redeemed_at >= start_date,
        Coupon.redeemed_at <= end_date
    ).group_by(
        func.date(Coupon.redeemed_at)
    ).order_by(
        func.date(Coupon.redeemed_at)
    ).all()

    # Fill in missing days and calculate cumulative
    date_redemptions = defaultdict(int)
    for day in redemption_days:
        date_redemptions[day.day] = day.redemptions

    lifecycle_data = []
    cumulative = 0
    current_date = start_date.date()
    end_date = end_date.date()

    while current_date <= end_date:
        redemptions = date_redemptions.get(current_date, 0)
        cumulative += redemptions
        lifecycle_data.append({
            'day': (current_date - start_date.date()).days + 1,
            'redemptions': redemptions,
            'cumulative': cumulative
        })
        current_date += timedelta(days=1)

    # 5. Revenue data
    revenue_days = db.session.query(
        func.date(Coupon.redeemed_at).label('date'),
        func.sum(Offer.revenue_generated).label('amount')
    ).join(Offer, Offer.id == Coupon.offer_id).filter(
        Offer.merchant_id == merchant.id,
        Coupon.status == 'redeemed',
        Coupon.redeemed_at >= start_date,
        Coupon.redeemed_at <= end_date
    ).group_by(
        func.date(Coupon.redeemed_at)
    ).order_by(
        func.date(Coupon.redeemed_at)
    ).all()

    revenue_data = [{
        'date': day.date,
        'amount': day.amount / 100 if not day.amount is None else 0  # Convert cents to dollars
    } for day in revenue_days]

    # 6. Customer metrics
    customer_metrics = db.session.query(
        func.count(distinct(Coupon.consumer_id)).label('total_customers'),
        func.count(case((
            Consumer.created_at >= start_date,
            1
        ), else_=None)).label('new_customers'),
        func.count(case((
            and_(
                Consumer.created_at < start_date,
                Coupon.redeemed_at >= start_date
            ),
            1
        ), else_=None)).label('repeat_customers')
    ).join(Consumer, Consumer.id == Coupon.consumer_id).join(
        Offer, Offer.id == Coupon.offer_id
    ).filter(
        Offer.merchant_id == merchant.id,
        Coupon.status == 'redeemed',
        Coupon.redeemed_at >= start_date,
        Coupon.redeemed_at <= end_date
    ).first()

    if not customer_metrics:
        customer_metrics = SimpleNamespace(
            total_customers=0,
            new_customers=0,
            repeat_customers=0
        )

    # 7. Individual redemptions for detailed view
    individual_redemptions = db.session.query(
        Coupon.id.label('redemption_id'),
        Offer.id.label('offer_id'),
        Coupon.redeemed_at,
        Offer.revenue_generated.label('amount')
    ).join(Offer, Offer.id == Coupon.offer_id).filter(
        Offer.merchant_id == merchant.id,
        Coupon.status == 'redeemed',
        Coupon.redeemed_at >= start_date,
        Coupon.redeemed_at <= end_date
    ).order_by(
        Coupon.redeemed_at.desc()
    ).limit(days * 10).all()  # Roughly 10 per day

    # Format the response
    response = {
        'revenue': revenue_data,
        'redemptions': [{
            'id': f"redemption-{r.redemption_id}",
            'offer_id': r.offer_id,
            'redeemed_at': r.redeemed_at.isoformat(),
            'amount': r.amount / 100 if not r.amount is None else 0  # Convert cents to dollars
        } for r in individual_redemptions],
        'views': sum(offer.view_count if offer.view_count is not None else 0 for offer in offers),
        'newCustomers': customer_metrics.new_customers or 0,
        'repeatCustomers': customer_metrics.repeat_customers or 0,
        'inactiveCustomers': (customer_metrics.total_customers or 0) -
        (customer_metrics.repeat_customers or 0) -
        (customer_metrics.new_customers or 0),
        'offers': [{
            'id': offer.id,
            'title': offer.title,
            'redemptions': offer.redemptions,
            'views': offer.view_count or 0,
            'revenue': (offer.revenue or 0) / 100  # Convert cents to dollars
        } for offer in offers],
        'schools': school_data,
        'locations': location_data,
        'lifecycle': lifecycle_data
    }

    return jsonify(response)
