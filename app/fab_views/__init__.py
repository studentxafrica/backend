from app import appbuilder, db  # type: ignore
from flask import render_template

# Import all views
from app.fab_views.user_views import ConsumerModelView
from app.fab_views.merchant_view import MerchantModelView  # type: ignore
from app.fab_views.coupon_views import CouponModelView, OfferModelView  # type: ignore
from app.fab_views.category_views import CategoryModelView  # type: ignore
from app.fab_views.store_view import StoreModelView  # type: ignore

appbuilder.add_view(
    StoreModelView,
    name='Stores',
    category_icon='fa fa-store',
    icon='fa fa-store',
)

appbuilder.add_view(
    ConsumerModelView,
    name='Consumers',
    category='Users',
    category_icon='fa fa-users',
    icon='fa fa-user',
)

appbuilder.add_view(
    CouponModelView,
    name='Coupons',
    category='Coupons',
    category_icon='fa fa-tags',
    icon='fa fa-tag',
)

appbuilder.add_view(
    OfferModelView,
    name='Offers',
    category='Coupons',
    category_icon='fa fa-tags',
    icon='fa fa-tag',
)

appbuilder.add_view(
    CategoryModelView,
	name='Categories',
	category_icon='fa fa-tags',
	icon='fa fa-tag',
)

appbuilder.add_view(
    MerchantModelView,
    "Merchants",
    icon="fa fa-users",
    category="Users",
    category_icon="fa fa-users",
)


@appbuilder.app.errorhandler(404)
def page_not_found(e):
    return (
        render_template(
            "404.html", base_template=appbuilder.base_template, appbuilder=appbuilder
        ),
        404,
    )


db.create_all()
