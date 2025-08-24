from flask import jsonify, request, g, current_app
from . import admin
from .helpers import get_category_color, format_timesince
from flask import jsonify
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, extract, case, and_, or_, distinct
from sqlalchemy.sql import label
from app.models import Administrator, Consumer, Merchant, Coupon, Offer, Category, Store, OfferView
from app import db
from typing import List
from app.utils import roles_required
from app.email import send_email
from config import config as config_class

from app.models.offer import OFFER_STATUS

from app.models.consumer import VerificationRequestStatus

from itsdangerous import URLSafeTimedSerializer
import string
import random
import os

# Configure this with your secret key
config = config_class[os.environ.get('FLASK_ENV', 'default')]
serializer = URLSafeTimedSerializer(config.SECRET_KEY)


def generate_temp_password(length=12):
    """Generate a random temporary password"""
    chars = string.ascii_letters + string.digits + '!@#$%^&*'
    return ''.join(random.choice(chars) for _ in range(length))


@admin.route('/merchants/register', methods=['POST'])
def register_merchant():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400

    # Check if merchant already exists
    existing_merchant = db.session.query(
        Merchant).filter_by(email=email).first()
    if existing_merchant:
        return jsonify({'message': 'Merchant with this email already exists'}), 400

    # Generate temporary credentials
    temp_password = generate_temp_password()

    # Create merchant with "pending" status
    merchant = Merchant(
        # Use email prefix as default name
        name=data.get('name', email.split('@')[0]),
        email=email,
        password=temp_password,
        # status='pending',
        # is_active=False,
        # temp_password=temp_password,  # Store temporarily for the email
        # temp_password_expires=datetime.now(timezone.utc) + timedelta(days=1)
    )

    merchant.save()

    try:
        # Send email with credentials
        send_merchant_credentials(email, temp_password)

        return jsonify({
            'message': 'Merchant registration initiated. Credentials sent to email.',
            'merchant_id': merchant.id
        }), 201
    except Exception as e:
        # Rollback if email fails
        db.session.rollback()
        current_app.logger.error(
            f"Failed to send merchant credentials: {str(e)}")
        return jsonify({'error': 'Failed to send email with credentials'}), 500


def send_merchant_credentials(email, temp_password):
    """Send email with temporary credentials to merchant"""
    subject = "Your Merchant Account Credentials"

    send_email(
        to=[email],
        subject=subject,
        template='email/merchant_credentials',
        context={
            'email': email,
            'temp_password': temp_password,
            'login_url': 'https://merchant.studentx.co.ke/login'
        })


@admin.route('/dashboard', methods=['GET'])
@roles_required('admin')
def get_dashboard_data():
    """Endpoint to fetch all dashboard data in a single optimized query"""
    # Get current time and calculate time ranges
    user = g.user
    if not user or not isinstance(user, Administrator):
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403
    now = datetime.now()
    last_6_months = now - timedelta(days=180)
    last_30_days = now - timedelta(days=30)

    # Query for basic stats
    stats = {
        'totalStudents': db.session.query(func.count(Consumer.id)).scalar(),
        'activeMerchants': db.session.query(func.count(Merchant.id))
        .filter(Merchant.approved_on.isnot(None)).scalar(),
        'couponsRedeemed': db.session.query(func.count(Coupon.id))
        .filter(Coupon.status == 'redeemed').scalar(),
        'totalRevenue': db.session.query(func.coalesce(func.sum(Coupon.redeemed_amount), 0)).scalar() or 0
    }

    # Monthly revenue and coupon data
    monthly_data = db.session.query(
        extract('month', Coupon.redeemed_at).label('month'),
        func.sum(Coupon.redeemed_amount).label('revenue'),
        func.count(Coupon.id).label('coupons')
    ).filter(
        Coupon.redeemed_at >= last_6_months,
        Coupon.status == 'redeemed'
    ).group_by(
        extract('month', Coupon.redeemed_at)
    ).order_by(
        extract('month', Coupon.redeemed_at)
    ).all()

    # Format monthly data for chart
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May',
                   'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    revenue_data = [{
        'month': month_names[int(data.month) - 1],
        'revenue': (data.revenue or 0) / 100,  # Convert cents to dollars
        'coupons': data.coupons or 0
    } for data in monthly_data]

    # Category distribution
    category_distribution = db.session.query(
        Category.name,
        func.count(Coupon.id).label('count'),
        Category.id
    ).join(
        Offer, Offer.category_id == Category.id
    ).join(
        Coupon, Coupon.offer_id == Offer.id
    ).filter(
        Coupon.redeemed_at >= last_30_days,
        Coupon.status == 'redeemed'
    ).group_by(
        Category.name, Category.id
    ).order_by(
        func.count(Coupon.id).desc()
    ).limit(5).all()

    total_coupons = sum([cd.count for cd in category_distribution]) or 1
    category_data = [{
        'name': cd.name,
        'value': round((cd.count / total_coupons) * 100, 1),
        'color': get_category_color(cd.name)
    } for cd in category_distribution]

    # Recent activity (combines multiple event types)
    import re
    from collections import defaultdict

    recent_activity = []

    # Parse logs from file app.log and extract meaningful recent activity
    log_path = 'app.log'
    log_pattern = re.compile(
        r'(?P<datetime>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+-\s+(?P<logger>\w+)\s+-\s+(?P<level>\w+)\s+-\s+(?P<message>.+)'
    )
    http_pattern = re.compile(
        r'(?P<ip>\d+\.\d+\.\d+\.\d+) - - \[(?P<date>.+?)\] "(?P<method>GET|POST|OPTIONS|PUT|DELETE) (?P<path>.+?) HTTP/[\d.]+" (?P<status>\d+)'
    )

    activity_by_ip = defaultdict(list)
    try:
        # Open the log file and process each line
        with open(log_path, 'r') as f:
            for line in f:
                match = log_pattern.match(line)
                if not match:
                    continue
                logger = match.group('logger')
                level = match.group('level')
                message = match.group('message')
                dt = match.group('datetime')

                # Only interested in HTTP requests for recent activity
                http_match = http_pattern.search(message)
                if http_match:
                    activity = {
                        'timestamp': dt,
                        'ip': http_match.group('ip'),
                        'method': http_match.group('method'),
                        'path': http_match.group('path'),
                        'status': int(http_match.group('status')),
                        'type': 'http'
                    }
                    # Group by IP
                    activity_by_ip[activity['ip']].insert(0, activity)
                # You can add more parsing for other log types here (e.g., redemptions, logins, errors)
    except FileNotFoundError:
        # Log file not found, skip
        pass

    recent_activity = dict(activity_by_ip)

    # Pending merchant approvals
    pending_merchants = db.session.query(
        Merchant.id,
        Merchant.name,
        Merchant.created_at,
        Category.name.label('category'),
        Merchant.email
    ).filter(
        Merchant.approved_on.is_(None),
        Merchant.email_verified_on.isnot(None)
    ).outerjoin(
        Category, Merchant.category_id == Category.id
    ).order_by(
        Merchant.created_at.desc()
    ).limit(5).all()

    pending_merchants_data = [{
        'id': m.id,
        'name': m.name,
        'submitted': format_timesince(m.created_at),
        'category': m.category or 'Other',
        'email': m.email
    } for m in pending_merchants]

    return jsonify({
        'stats': stats,
        'revenueData': revenue_data,
        'categoryData': category_data,
        'pendingMerchants': pending_merchants_data,
        'recentActivity': recent_activity,
        'success': True
    })


@admin.route('/users', methods=['GET'])
@roles_required('admin')
def get_user_management_data():
    """Endpoint to fetch all user management data"""

    # Get query parameters
    search_term = request.args.get('search', '')
    # 'students' or 'merchants'
    user_type = request.args.get('type', 'students')

    # Base stats
    stats = {
        'totalStudents': db.session.query(func.count(Consumer.id)).scalar(),
        'verifiedStudents': db.session.query(func.count(Consumer.id))
        .filter(Consumer.verified_at.isnot(None)).scalar(),
        'activeMerchants': db.session.query(func.count(Merchant.id))
        .filter(Merchant.approved_on.isnot(None)).scalar(),
        'pendingMerchants': db.session.query(func.count(Merchant.id))
        .filter(
            Merchant.approved_on.is_(None),
            Merchant.email_verified_on.is_(None)
        ).scalar()
    }

    # Calculate growth rates (simplified example)
    last_month = datetime.now() - timedelta(days=30)
    stats['studentGrowth'] = db.session.query(
        func.round(100.0 * func.count(Consumer.id) /
                   db.session.query(func.count(Consumer.id))
                   .filter(Consumer.created_at < last_month).scalar(), 1)
    ).filter(Consumer.created_at >= last_month).scalar() or 0

    # Get either students or merchants based on type
    if user_type == 'students':
        # Students query
        query = db.session.query(
            Consumer.id,
            Consumer.first_name,
            Consumer.last_name,
            Consumer.profile_picture,
            Consumer.email,
            Consumer.school,
            Consumer.major,
            Consumer.graduation_year,
            Consumer.verified_at,
            Consumer.verification_status,
            Consumer.verification_reminder_sent_on,
            Consumer.created_at,
            func.count(Coupon.id).label('coupons_used'),
            func.coalesce(func.sum(Coupon.redeemed_amount),
                          0).label('total_savings'),
            func.round(
                case([
                    (Consumer.phone.isnot(None), 10),
                    (Consumer.student_id.isnot(None), 10),
                    (Consumer.school.isnot(None), 10),
                    (Consumer.major.isnot(None), 10),
                    (Consumer.graduation_year.isnot(None), 10),
                    (Consumer.location.isnot(None), 10),
                    (Consumer.profile_picture.isnot(None), 10),
                    (Consumer.bio.isnot(None), 10),
                    (Consumer.verified_at.isnot(None), 10)
                ], else_=0)
            ).label('profile_complete')
        ).outerjoin(
            Coupon, Coupon.consumer_id == Consumer.id
        )

        if search_term:
            query = query.filter(
                or_(
                    Consumer.first_name.ilike(f'%{search_term}%'),
                    Consumer.last_name.ilike(f'%{search_term}%'),
                    Consumer.email.ilike(f'%{search_term}%'),
                    Consumer.school.ilike(f'%{search_term}%')
                )
            )
        users: List[Consumer] = query.group_by(Consumer.id).order_by(
            Consumer.created_at.desc()).limit(100).all()

        user_data = [{
            'id': s.id,
            'name': f"{s.first_name} {s.last_name}",
            'email': s.email,
            'school': s.school,
            'major': s.major,
            'year': s.graduation_year,
            'verified': s.verified_at is not None and s.verification_status == VerificationRequestStatus.APPROVED,
            'avatar': s.profile_picture or '',
            'profileComplete': s.profile_complete,
            'verificationStatus': s.verification_status.value if s.verification_status else 'pending',
            'verificationReminderSentOn': s.verification_reminder_sent_on.replace(tzinfo=timezone.utc).isoformat() if s.verification_reminder_sent_on else None,
            'verificationReminderSent': s.verification_reminder_sent_on is not None and s.verification_reminder_sent_on.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) - timedelta(days=7),
            'couponsUsed': s.coupons_used,
            # Convert cents to dollars
            'totalSavings': (s.total_savings or 0) / 100,
            'joinDate': s.created_at.isoformat(),
            'type': 'student'
        } for s in users]

    else:
        # Merchants query
        query = db.session.query(
            Merchant.id,
            Merchant.name,
            Merchant.email,
            Merchant.logo,
            Category.name.label('category'),
            Merchant.phone,
            Merchant.address,
            Merchant.approved_on,
            Merchant.email_verified_on,
            Merchant.created_at,
            func.count(Offer.id).label('active_offers'),
            func.coalesce(
                db.session.query(func.sum(Coupon.redeemed_amount))
                .join(Offer, Offer.id == Coupon.offer_id)
                .filter(Offer.merchant_id == Merchant.id)
                .scalar(), 0
            ).label('total_revenue')
        ).outerjoin(
            Category, Merchant.category_id == Category.id
        ).outerjoin(
            Offer, Offer.merchant_id == Merchant.id
        )

        if search_term:
            query = query.filter(
                or_(
                    Merchant.name.ilike(f'%{search_term}%'),
                    Merchant.email.ilike(f'%{search_term}%'),
                    Category.name.ilike(f'%{search_term}%')
                )
            )

        merchants = query.group_by(Merchant.id, Category.name).order_by(
            Merchant.created_at.desc()).limit(100).all()

        user_data = [{
            'id': m.id,
            'name': m.name,
            'logo': m.logo or '',
            'email': m.email,
            'category': m.category or 'Other',
            'phone': m.phone,
            'address': m.address,
            'approved': m.approved_on is not None,
            'emailVerified': m.email_verified_on is not None,
            'activeOffers': m.active_offers,
            # Convert cents to dollars
            'totalRevenue': (m.total_revenue or 0) / 100,
            'joinDate': m.created_at.isoformat(),
            'type': 'merchant'
        } for m in merchants]

    return jsonify({
        'stats': stats,
        'users': user_data,
        'success': True
    })


@admin.route('/users/<user_id>/request-verification', methods=['POST'])
@roles_required('admin')
def request_verification(user_id):
    """Endpoint to request verification for a student"""
    student: Consumer = db.session.query(Consumer).get_or_404(user_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    if student.verified_at:
        if student.verification_status == VerificationRequestStatus.PENDING:
            student.verified_at = None
        else:
            return jsonify({'success': False, 'message': 'Student already verified'}), 400

    # if student.verification_reminder_sent_on is not None and \
    #         student.verification_reminder_sent_on > datetime.now() - timedelta(days=7):
    #     return jsonify({'success': False, 'message': 'Verification reminder already sent within the last 7 days'}), 400

    student.verification_reminder_sent_on = datetime.now(timezone.utc)
    student.save()

    send_email(
        to=[student.email],
        subject='Reminder: Verify Your StudentX Account',
        template='email/verification_reminder',
        context={
            'student_name': student.first_name,
        }
    )

    return jsonify({
        'success': True,
        'message': f'Student {student.first_name} {student.last_name} verification reminder sent successfully'
    })


@admin.route('/merchants/<merchant_id>/approve', methods=['POST'])
@roles_required('admin')
def approve_merchant(merchant_id):
    """Endpoint to approve a merchant"""
    merchant = db.session.query(Merchant).get_or_404(merchant_id)
    if merchant.approved_on:
        return jsonify({'success': False, 'message': 'Merchant already approved'}), 400

    merchant.approved_on = datetime.now()
    merchant.save()

    return jsonify({
        'success': True,
        'message': f'Merchant {merchant.name} approved successfully'
    })


@admin.route('/merchants/<merchant_id>/reject', methods=['POST'])
@roles_required('admin')
def reject_merchant(merchant_id):
    """Endpoint to reject a merchant"""
    merchant = db.session.query(Merchant).get_or_404(merchant_id)
    if not merchant:
        return jsonify({'success': False, 'message': 'The specified merchant could not be found'}), 404

    merchant.approved_on = None
    merchant.save()

    return jsonify({
        'success': True,
        'message': f'Merchant {merchant.name} rejected successfully'
    })


@admin.route('/offers', methods=['GET'])
@roles_required('admin')
def get_offer_management_data():
    """Endpoint to fetch all offer and coupon data in optimized queries"""

    # Get query parameters
    search_term = request.args.get('search', '')
    status_filter = request.args.get('status', 'all')
    tab = request.args.get('tab', 'offers')  # 'offers' or 'coupons'

    # Base stats
    stats = {
        'totalOffers': db.session.query(func.count(Offer.id)).scalar(),
        'activeOffers': db.session.query(func.count(Offer.id))
        .filter(Offer.end_date > datetime.now(timezone.utc)).scalar(),
        'totalCouponsGenerated': db.session.query(func.count(Coupon.id)).scalar(),
        'avgRedemptionRate': 0  # Will be calculated below
    }

    # Calculate average redemption rate
    redeemed_count = db.session.query(func.count(Coupon.id)).filter(
        Coupon.status == 'redeemed').scalar()
    stats['avgRedemptionRate'] = round(
        (redeemed_count / stats['totalCouponsGenerated']
         * 100) if stats['totalCouponsGenerated'] else 0
    )

    if tab == 'offers':
        # Offers query
        query = db.session.query(
            Offer.id,
            Offer.title,
            Merchant.name.label('merchant'),
            Category.name.label('category'),
            Offer.discount_type,
            Offer.discount_value,
            Offer.coupon_limit,
            label('claimed', func.count(Coupon.id)),
            label('redeemed', func.count(
                case([(Coupon.status == 'redeemed', Coupon.id)], else_=None)
            )),
            Offer.start_date,
            Offer.end_date,
            Offer.status,
            label('revenue', func.coalesce(
                func.sum(Coupon.redeemed_amount), 0)),
            Offer.view_count,
            Offer.cover_image,
            Offer.description
        ).join(
            Merchant, Offer.merchant_id == Merchant.id
        ).outerjoin(
            Category, Offer.category_id == Category.id
        ).outerjoin(
            Coupon, Coupon.offer_id == Offer.id
        ).group_by(
            Offer.id, Merchant.name, Category.name
        )

        # Apply filters
        if search_term:
            query = query.filter(
                or_(
                    Offer.title.ilike(f'%{search_term}%'),
                    Merchant.name.ilike(f'%{search_term}%'),
                    Category.name.ilike(f'%{search_term}%')
                )
            )

        if status_filter != 'all':
            query = query.filter(
                Offer.status == status_filter
            )

        offers: List[Offer] = query.order_by(
            Offer.start_date.desc()).limit(100).all()

        offer_data = [{
            'id': o.id,
            'title': o.title,
            'merchant': {
                'name': o.merchant,
                'id': o.merchant_id if hasattr(o, 'merchant_id') else None,
                'logo': o.merchant.logo if hasattr(o.merchant, 'logo') else None
            },
            'category': {
                'name': o.category.name if hasattr(o.category, 'name') else None,
                'id': o.category.id if hasattr(o.category, 'id') else None
            } if o.category else None,
            'discountType': o.discount_type,
            'discountValue': o.discount_value,
            'couponLimit': o.coupon_limit,
            'claimed': len([coupon for coupon in o.coupons if coupon.status == 'active']) if hasattr(o, 'coupons') else 0,
            'redeemed': len([coupon for coupon in o.coupons if coupon.status == 'redeemed']) if hasattr(o, 'coupons') else 0,
            'startDate': o.start_date.isoformat(),
            'currency:': o.currency if hasattr(o, 'currency') else 'USD',
            'endDate': o.end_date.isoformat(),
            'status': o.status,
            'revenue': (o.revenue or 0) / 100,
            'views': o.view_count,
            'coverImage': o.cover_image,
            'description': o.description
        } for o in offers]

        return jsonify({
            'stats': stats,
            'data': offer_data,
            'success': True
        })

    else:  # Coupons tab
        # Coupons query
        query = db.session.query(
            Coupon.id,
            Coupon.coupon_code,
            Offer.title.label('offer'),
            Offer.id.label('offerId'),
            Consumer.first_name,
            Consumer.last_name,
            Consumer.email.label('studentEmail'),
            Coupon.status,
            Coupon.created_at.label('claimedDate'),
            Coupon.redeemed_at.label('redeemedDate'),
            Coupon.expiry_date.label('expiryDate'),
            Coupon.redeemed_amount,
            Store.name.label('storeName')
        ).join(
            Offer, Coupon.offer_id == Offer.id
        ).outerjoin(
            Consumer, Coupon.consumer_id == Consumer.id
        ).outerjoin(
            Store, Coupon.redemption_location_id == Store.id
        )

        # Apply filters
        if search_term:
            query = query.filter(
                or_(
                    Coupon.coupon_code.ilike(f'%{search_term}%'),
                    Offer.title.ilike(f'%{search_term}%'),
                    Consumer.first_name.ilike(f'%{search_term}%'),
                    Consumer.last_name.ilike(f'%{search_term}%'),
                    Consumer.email.ilike(f'%{search_term}%')
                )
            )

        coupons = query.order_by(Coupon.created_at.desc()).limit(100).all()

        coupon_data = [{
            'id': c.id,
            'code': c.coupon_code,
            'offer': c.offer,
            'offerId': c.offerId,
            'student': f"{c.first_name} {c.last_name}" if c.first_name else 'Anonymous',
            'studentEmail': c.studentEmail,
            'status': c.status,
            'claimedDate': c.claimedDate.isoformat(),
            'redeemedDate': c.redeemedDate.isoformat() if c.redeemedDate else None,
            'expiryDate': c.expiryDate.isoformat() if c.expiryDate else None,
            # Convert cents to dollars
            'amountSaved': (c.redeemed_amount or 0) / 100,
            'store': f"{c.storeName}" if c.storeName else None
        } for c in coupons]

        return jsonify({
            'stats': stats,
            'data': coupon_data,
            'success': True
        })


@admin.route('/offers/<offer_id>/activate', methods=['POST'])
@roles_required('admin')
def activate_offer(offer_id):
    """Endpoint to activate an offer"""
    offer: Offer = db.session.query(Offer).get_or_404(offer_id)
    if not offer:
        return jsonify({
            'message': 'Offer not found',
            'description': 'The specified offer does not exist'
        }), 404

    if offer.end_date < datetime.now():
        return jsonify({
            'message': 'Offer has already ended',
            'description': 'Cannot activate an offer that has already ended'
        }), 400

    if offer.status == OFFER_STATUS['ACTIVE']:
        return jsonify({
            'message': 'Offer already active',
            'description': 'This offer is already active and cannot be activated again'
        }), 400

    if offer.status == OFFER_STATUS['SUSPENDED']:
        return jsonify({
            'message': 'Offer is suspended',
            'description': 'Cannot activate a suspended offer. Please resolve the issue first.'
        }), 400

    offer.status = OFFER_STATUS['ACTIVE']
    offer.save()
    return jsonify({
        'success': True,
        'message': f'Offer "{offer.title}" activated successfully'
    })


@admin.route('/offers/<offer_id>/deactivate', methods=['POST'])
@roles_required('admin')
def deactivate_offer(offer_id):
    """Endpoint to deactivate an offer"""
    offer: Offer = db.session.query(Offer).get_or_404(offer_id)
    if not offer:
        return jsonify({
            'message': 'Offer not found',
            'description': 'The specified offer does not exist'
        }), 404

    if offer.end_date < datetime.now():
        return jsonify({
            'message': 'Offer has already ended',
            'description': 'Cannot activate an offer that has already ended'
        }), 400

    if offer.status == OFFER_STATUS['INACTIVE']:
        return jsonify({
            'message': 'Offer already inactive',
            'description': 'This offer is already inactive and cannot be deactivated'
        }), 400

    if offer.status == OFFER_STATUS['SUSPENDED']:
        return jsonify({
            'message': 'Offer is suspended',
            'description': 'Cannot modify a suspended offer. Please resolve the issue first.'
        }), 400

    offer.status = OFFER_STATUS['INACTIVE']
    offer.save()
    return jsonify({
        'success': True,
        'message': f'Offer "{offer.title}" deactivated successfully'
    })


@admin.route('/offers/<offer_id>', methods=['DELETE'])
@roles_required('admin')
def delete_offer(offer_id):
    """Endpoint to delete an offer"""
    user = g.user
    user_role = g.user_role
    offer = db.session.query(Offer).filter_by(
        Offer.merchant_id == user.id if user_role == 'merchant' else None
    ).get_or_404(offer_id)
    if not offer:
        return jsonify({
            'message': 'Offer not found',
            'description': 'The specified offer does not exist'
        })

    db.session.delete(offer)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Offer "{offer.title}" deleted successfully'
    })


@admin.route('/coupons/<coupon_id>/expire', methods=['POST'])
@roles_required('admin')
def expire_coupon(coupon_id):
    """Endpoint to manually expire a coupon"""
    coupon = db.session.query(Coupon).get_or_404(coupon_id)
    if coupon.status != 'active':
        return jsonify({'success': False, 'message': 'Coupon is not active'}), 400

    coupon.status = 'expired'
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Coupon {coupon.coupon_code} expired successfully'
    })


@admin.route('/analytics', methods=['GET'])
@roles_required('admin')
def get_analytics_data():
    """Endpoint to fetch all analytics data in optimized queries"""

    # Calculate date ranges
    now = datetime.now()
    last_6_months = now - timedelta(days=180)
    last_30_days = now - timedelta(days=30)

    # Base metrics
    metrics = {
        'totalRevenue': db.session.query(func.coalesce(func.sum(Coupon.redeemed_amount), 0)).scalar() or 0,
        'avgRedemptionRate': 0,
        'avgCouponValue': 0,
        'avgTimeToRedeem': None
    }

    # Calculate average redemption rate
    total_coupons = db.session.query(func.count(Coupon.id)).scalar() or 1
    redeemed_coupons = db.session.query(func.count(Coupon.id)) .filter(
        Coupon.status == 'redeemed').scalar()
    metrics['avgRedemptionRate'] = round(
        (redeemed_coupons / total_coupons) * 100, 1)

    # Calculate average coupon value
    if redeemed_coupons > 0:
        metrics['avgCouponValue'] = round(
            (metrics['totalRevenue'] / redeemed_coupons) /
            100, 2  # Convert cents to dollars
        )

    # Calculate average time to redeem (in hours)
    from sqlalchemy import text
    from calendar import monthrange
    avg_time = db.session.query(
        func.avg(
            func.timestampdiff(
                text("SECOND"),
                Coupon.created_at,
                Coupon.redeemed_at
            ) / 3600
        )
    ).filter(
        Coupon.status == 'redeemed',
        Coupon.redeemed_at.isnot(None)
    ).scalar()

    metrics['avgTimeToRedeem'] = round(avg_time, 1) if avg_time else None

    # Monthly revenue and growth data
    # Get all months in the last 6 months

    months = []
    for i in range(6, 1, -1):
        month_date = now
        for _ in range(i - 1):
            # Move to the previous month
            month_date = (month_date - timedelta(days=1)).replace(day=1)
        months.append(month_date)
    print([month.isoformat() for month in months])

    # Query revenue/coupons per month (as before)
    coupon_data = db.session.query(
        extract('year', Coupon.redeemed_at).label('year'),
        extract('month', Coupon.redeemed_at).label('month'),
        func.sum(Coupon.redeemed_amount).label('revenue'),
        func.count(Coupon.id).label('coupons')
    ).filter(
        Coupon.redeemed_at >= last_6_months,
        Coupon.status == 'redeemed'
    ).group_by(
        extract('year', Coupon.redeemed_at),
        extract('month', Coupon.redeemed_at)
    ).all()

    # Query total students per month (cumulative)
    student_counts = db.session.query(
        extract('year', Consumer.created_at).label('year'),
        extract('month', Consumer.created_at).label('month'),
        func.count(Consumer.id).label('students')
    ).filter(
        Consumer.created_at >= months[0]
    ).group_by(
        extract('year', Consumer.created_at),
        extract('month', Consumer.created_at)
    ).order_by(
        extract('year', Consumer.created_at),
        extract('month', Consumer.created_at)
    ).all()

    # Query total merchants per month (cumulative)
    merchant_counts = db.session.query(
        extract('year', Merchant.created_at).label('year'),
        extract('month', Merchant.created_at).label('month'),
        func.count(Merchant.id).label('merchants')
    ).filter(
        Merchant.created_at >= months[0]
    ).group_by(
        extract('year', Merchant.created_at),
        extract('month', Merchant.created_at)
    ).order_by(
        extract('year', Merchant.created_at),
        extract('month', Merchant.created_at)
    ).all()

    # Build a dict for fast lookup
    coupon_dict = {(int(row.year), int(row.month)): row for row in coupon_data}
    student_dict = {}
    merchant_dict = {}

    # Build cumulative counts for students and merchants
    cumulative_students = 0
    cumulative_merchants = 0
    student_months = {(int(row.year), int(row.month)): row.students for row in student_counts}
    merchant_months = {(int(row.year), int(row.month)): row.merchants for row in merchant_counts}

    # Prepare monthly_data with all months in the last 6 months
    monthly_data = []
    for m in months:
        year, month = m.year, m.month
        # Revenue/coupons
        c = coupon_dict.get((year, month))
        revenue = c.revenue if c else 0
        coupons = c.coupons if c else 0

        # Cumulative students
        cumulative_students += student_months.get((year, month), 0)
        # Cumulative merchants
        cumulative_merchants += merchant_months.get((year, month), 0)

        # Compose row
        class Row:
            pass
        row = Row()
        row.month = month
        row.revenue = revenue
        row.coupons = coupons
        row.students = cumulative_students
        row.merchants = cumulative_merchants
        monthly_data.append(row)

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May',
                   'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    revenue_data = [{
        'month': month_names[int(data.month) - 1],
        'revenue': (data.revenue or 0) / 100,  # Convert cents to dollars
        'coupons': data.coupons or 0,
        'students': data.students or 0,
        'merchants': data.merchants or 0
    } for data in monthly_data]

    # Weekly redemption patterns
    redemption_trends = db.session.query(
        func.dayofweek(Coupon.redeemed_at).label('day_of_week'),
        func.count(Coupon.id).label('redemptions'),
        func.count(
            case([(Coupon.created_at.isnot(None), Coupon.id)], else_=0)
        ).label('claims')
    ).filter(
        Coupon.redeemed_at >= last_30_days
    ).group_by(
        func.dayofweek(Coupon.redeemed_at)
    ).order_by(
        func.dayofweek(Coupon.redeemed_at)
    ).all()

    print(redemption_trends)

    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    redemption_data = [{
        # Adjust for 1-based index
        'day': day_names[int(data.day_of_week) - 1],
        'redemptions': data.redemptions or 0,
        'claims': data.claims or 0
    } for data in redemption_trends]

    print()
    print(redemption_data)

    # Category performance - simplified redemption_rate calculation
    category_performance = db.session.query(
        Category.name,
        func.count(Coupon.id).label('coupons'),
        func.sum(Coupon.redeemed_amount).label('revenue'),
        (func.sum(case([(Coupon.status == 'redeemed', 1)], else_=0)) /
         func.count(Coupon.id) * 100)
    ).join(
        Offer, Offer.category_id == Category.id
    ).join(
        Coupon, Coupon.offer_id == Offer.id
    ).filter(
        Coupon.created_at >= last_30_days
    ).group_by(
        Category.name
    ).order_by(
        func.sum(Coupon.redeemed_amount).desc()
    ).limit(5).all()

    category_data = [{
        'name': cp.name,
        'coupons': cp.coupons or 0,
        'revenue': (cp.revenue or 0) / 100,  # Convert cents to dollars
        # Access the 4th element (index 3) and round
        'redemptionRate': round(float(cp[3] or 0), 1)
    } for cp in category_performance]

    # Top merchants - simplified redemption_rate calculation
    top_merchants = db.session.query(
        Merchant.name,
        func.sum(Coupon.redeemed_amount).label('revenue'),
        func.count(Coupon.id).label('coupons'),
        (func.sum(case([(Coupon.status == 'redeemed', 1)], else_=0)) /
         func.count(Coupon.id) * 100)
    ).join(
        Offer, Offer.merchant_id == Merchant.id
    ).join(
        Coupon, Coupon.offer_id == Offer.id
    ).filter(
        Coupon.created_at >= last_30_days
    ).group_by(
        Merchant.name
    ).order_by(
        func.sum(Coupon.redeemed_amount).desc()
    ).limit(5).all()

    merchant_data = [{
        'name': tm.name,
        'revenue': (tm.revenue or 0) / 100,  # Convert cents to dollars
        'coupons': tm.coupons or 0,
        # Access the 4th element (index 3) and round
        'redemptionRate': round(float(tm[3] or 0), 1)
    } for tm in top_merchants]

    # Conversion funnel
    total_visits = db.session.query(func.count(Consumer.id)).scalar() or 1
    offer_views = db.session.query(func.count(OfferView.id)).scalar()
    coupons_claimed = total_coupons
    coupons_redeemed = redeemed_coupons

    conversion_data = [
        {'stage': 'Platform Visits', 'count': total_visits, 'percentage': 100},
        {'stage': 'Offer Views', 'count': offer_views,
            'percentage': round((offer_views / total_visits) * 100, 1)},
        {'stage': 'Coupons Claimed', 'count': coupons_claimed,
            'percentage': round((coupons_claimed / total_visits) * 100, 1)},
        {'stage': 'Coupons Redeemed', 'count': coupons_redeemed,
            'percentage': round((coupons_redeemed / total_visits) * 100, 1)}
    ]

    return jsonify({
        'metrics': metrics,
        'revenueData': revenue_data,
        'redemptionData': redemption_data,
        'categoryData': category_data,
        'merchantData': merchant_data,
        'conversionData': conversion_data,
        'success': True
    })
