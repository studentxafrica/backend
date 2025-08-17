from flask_appbuilder import BaseView, expose  # type: ignore
from flask import render_template
from app import db
from app.models import Consumer, Merchant, Offer, Coupon, Category, Store
from sqlalchemy import func, extract, case, distinct  # type: ignore
from datetime import datetime, timedelta
from collections import defaultdict


class DashboardView(BaseView):
    route_base = "/dashboard"
    default_view = "index"

    @expose("/")
    def index(self):
        # Current time for dashboard
        current_time = datetime.now()

        # Get total counts
        total_consumers = db.session.query(func.count(Consumer.id)).scalar()
        total_merchants = db.session.query(func.count(Merchant.id)).scalar()
        total_offers = db.session.query(func.count(Offer.id)).scalar()
        total_coupons = db.session.query(func.count(Coupon.id)).scalar()

        # Get recent activity for the activity feed
        recent_activities = self._get_recent_activities()

        # Get statistics for the last 30 days
        thirty_days_ago = current_time - timedelta(days=30)

        new_consumers = db.session.query(func.count(Consumer.id)).filter(
            Consumer.created_at >= thirty_days_ago
        ).scalar()

        new_merchants = db.session.query(func.count(Merchant.id)).filter(
            Merchant.created_at >= thirty_days_ago
        ).scalar()

        new_offers = db.session.query(func.count(Offer.id)).filter(
            Offer.created_at >= thirty_days_ago
        ).scalar()

        redeemed_coupons = db.session.query(func.count(Coupon.id)).filter(
            Coupon.redeemed_at >= thirty_days_ago
        ).scalar()

        # Calculate growth trend (month-over-month)
        prev_month_start = thirty_days_ago - timedelta(days=30)
        prev_month_consumers = db.session.query(func.count(Consumer.id)).filter(
            Consumer.created_at >= prev_month_start,
            Consumer.created_at < thirty_days_ago
        ).scalar()

        growth_trend = 0
        if prev_month_consumers > 0:
            growth_trend = (
                (new_consumers - prev_month_consumers) / prev_month_consumers) * 100

        # Get top performing offer
        top_offer = db.session.query(
            Offer.title,
            (func.count(Coupon.id) / func.nullif(func.count(distinct(Offer.id)),
             1.0) * 100).label('redemption_rate')
        ).select_from(Offer)\
            .outerjoin(Coupon, Offer.id == Coupon.offer_id)\
            .group_by(Offer.id)\
            .order_by(func.count(Coupon.id).desc())\
            .first()

        # Get top merchants with additional stats
        # For the top merchants query
        top_merchants = db.session.query(
            Merchant.name,
            func.count(Offer.id).label('offer_count'),
            func.count(Coupon.id).label('redemption_count'),
            (func.count(Coupon.id) / func.nullif(func.count(Offer.id), 1.0)
             * 100).label('redemption_rate'),
            Category.name.label('category')
        ).select_from(Merchant)\
            .join(Offer, Merchant.id == Offer.merchant_id)\
            .join(Category, Offer.category_id == Category.id)\
            .outerjoin(Coupon, Offer.id == Coupon.offer_id)\
            .group_by(Merchant.id, Category.name)\
            .order_by(func.count(Coupon.id).desc())\
            .limit(5).all()

        # Get top merchant for insights
        top_merchant = top_merchants[0] if top_merchants else None

        # Get recent coupons with more context
        recent_coupons = db.session.query(Coupon).join(Offer).join(Consumer).order_by(
            Coupon.created_at.desc()
        ).limit(5).all()

        # Chart data - last 30 days daily breakdown
        date_range = [current_time -
                      timedelta(days=x) for x in range(30, -1, -1)]
        date_labels = [d.strftime('%b %d') for d in date_range[:-1]]

        # Offers created per day
        offer_creation = defaultdict(int)
        offers_data = db.session.query(
            func.date(Offer.created_at).label('date'),
            func.count(Offer.id).label('count')
        ).filter(
            Offer.created_at >= thirty_days_ago
        ).group_by(func.date(Offer.created_at)).all()

        for date, count in offers_data:
            offer_creation[date.strftime('%b %d')] = count

        offer_creation_data = [offer_creation.get(
            label, 0) for label in date_labels]

        # Coupons redeemed per day
        coupon_redemption = defaultdict(int)
        coupons_data = db.session.query(
            func.date(Coupon.redeemed_at).label('date'),
            func.count(Coupon.id).label('count')
        ).filter(
            Coupon.redeemed_at >= thirty_days_ago
        ).group_by(func.date(Coupon.redeemed_at)).all()

        for date, count in coupons_data:
            coupon_redemption[date.strftime('%b %d')] = count

        coupon_redemption_data = [coupon_redemption.get(
            label, 0) for label in date_labels]

        # Category distribution
        category_stats = db.session.query(
            Category.name,
            func.count(Offer.id)
        ).join(Offer).group_by(Category.name).all()

        category_labels = [cat[0] for cat in category_stats]
        category_data = [cat[1] for cat in category_stats]

        # Redemption rate by category
        redemption_stats = db.session.query(
            Category.name,
            (func.count(Coupon.id) / func.nullif(func.count(Offer.id), 1.0)
             * 100).label('redemption_rate')
        ).select_from(Category)\
            .join(Offer, Category.id == Offer.category_id)\
            .outerjoin(Coupon, Offer.id == Coupon.offer_id)\
            .group_by(Category.name)\
            .all()

        redemption_labels = [stat[0] for stat in redemption_stats]
        redemption_data = [round(stat[1], 1) for stat in redemption_stats]

        return self.render_template(
            "dashboard.html",
            current_time=current_time,
            total_consumers=total_consumers,
            total_merchants=total_merchants,
            total_offers=total_offers,
            total_coupons=total_coupons,
            new_consumers=new_consumers,
            new_merchants=new_merchants,
            new_offers=new_offers,
            redeemed_coupons=redeemed_coupons,
            recent_activities=recent_activities,
            top_offer=top_offer,
            top_merchant=top_merchant,
            top_merchants=top_merchants,
            recent_coupons=recent_coupons,
            growth_trend=round(growth_trend, 1),
            offer_performance_labels=date_labels,
            offer_creation_data=offer_creation_data,
            coupon_redemption_data=coupon_redemption_data,
            category_labels=category_labels,
            category_data=category_data,
            redemption_labels=redemption_labels,
            redemption_data=redemption_data
        )

    def _get_recent_activities(self):
        """Generate recent activity feed items"""
        activities = []

        # Recent coupon redemptions
        redemptions = db.session.query(Coupon, Offer, Consumer).join(Offer).join(Consumer).filter(
            Coupon.status == 'redeemed'
        ).order_by(Coupon.redeemed_at.desc()).limit(3).all()

        for coupon, offer, consumer in redemptions:
            activities.append({
                'icon': 'check-circle',
                'message': f"Coupon redeemed for {offer.title} by {consumer.email}",
                'time': coupon.redeemed_at,
                'highlight': True
            })

        # New offers
        new_offers = db.session.query(Offer, Merchant).join(Merchant).order_by(
            Offer.created_at.desc()
        ).limit(2).all()

        for offer, merchant in new_offers:
            activities.append({
                'icon': 'tag',
                'message': f"New offer '{offer.title}' by {merchant.name}",
                'time': offer.created_at,
                'highlight': False
            })

        # New merchants
        new_merchants = db.session.query(Merchant).order_by(
            Merchant.created_at.desc()
        ).limit(1).all()

        for merchant in new_merchants:
            activities.append({
                'icon': 'store',
                'message': f"New merchant onboarded: {merchant.name}",
                'time': merchant.created_at,
                'highlight': False
            })

        # Sort all activities by time
        activities.sort(key=lambda x: x['time'], reverse=True)
        return activities[:5]
