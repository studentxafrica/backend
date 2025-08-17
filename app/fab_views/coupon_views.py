from flask import request, flash, redirect, url_for
import cloudinary  # type: ignore
import cloudinary.uploader  # type: ignore
from markupsafe import Markup  # type: ignore
from flask_appbuilder import ModelView, action  # type: ignore
from flask_appbuilder.models.sqla.interface import SQLAInterface  # type: ignore
from app import appbuilder
from wtforms import DateTimeField, FileField, SelectField, TextAreaField  # type: ignore
from wtforms.widgets import FileInput, DateTimeLocalInput, TextArea  # type: ignore
from wtforms.validators import DataRequired, Optional  # type: ignore
from datetime import datetime, timezone, timedelta  # type: ignore
from sqlalchemy import func  # type: ignore

from app.models import Coupon, Offer  # type: ignore


class CouponModelView(ModelView):
    """
    Enhanced Coupon model view for Flask App Builder.
    """
    datamodel = SQLAInterface(Coupon)
    list_columns = ['coupon_code', 'status', 'redeemed_at',
                    'expiry_date', 'offer', 'consumer', 'qr_code']
    show_columns = ['coupon_code', 'status', 'redeemed_at',
                    'expiry_date', 'offer', 'consumer', 'qr_code']
    add_columns = ['coupon_code', 'expiry_date', 'offer', 'consumer']
    edit_columns = ['coupon_code', 'status',
                    'redeemed_at', 'expiry_date', 'offer', 'consumer']
    search_columns = ['coupon_code', 'status',
                      'redeemed_at', 'expiry_date', 'offer', 'consumer']

    # Add custom actions
    @action("redeem", "Redeem Selected", "Are you sure you want to redeem the selected coupons?")
    def redeem(self, items):
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if item.status == 'active':
                item.status = 'redeemed'
                item.redeemed_at = datetime.now(timezone.utc)
                self.datamodel.session.commit()
        return redirect(self.get_redirect())

    # Enhanced form fields
    add_form_extra_fields = {
        'expiry_date': DateTimeField(
            format='%Y-%m-%dT%H:%M',
            label='Expiry Date',
            widget=DateTimeLocalInput(),
            validators=[DataRequired()],
            render_kw={
                'placeholder': 'Select expiry date',
                'required': 'required',
            }
        ),
    }

    edit_form_extra_fields = add_form_extra_fields

    # Enhanced column formatters
    formatters_columns = {
        'status': lambda m: Markup(
            f'<span class="badge {"badge-success" if m.status == "redeemed" else "badge-primary" if m.status == "active" else "badge-warning"}">{m.status}</span>'
        ),
        'redeemed_at': lambda m: m.redeemed_at.strftime('%Y-%m-%d %H:%M') if m.redeemed_at else None,
        'expiry_date': lambda m: m.expiry_date.strftime('%Y-%m-%d %H:%M') if m.expiry_date else None,
        'qr_code': lambda m: Markup(
            f'<img src="{m.qr_code}" width="100" class="img-preview">'
        ) if m.qr_code else '',
    }

    # Add list template
    list_template = 'coupon_list.html'

    def _list(self):
        # Get statistics for the list view
        total_coupons = self.datamodel.session.query(
            func.count(Coupon.id)).scalar()
        active_coupons = self.datamodel.session.query(func.count(
            Coupon.id)).filter(Coupon.status == 'active').scalar()
        redeemed_coupons = self.datamodel.session.query(func.count(
            Coupon.id)).filter(Coupon.status == 'redeemed').scalar()
        expired_coupons = self.datamodel.session.query(func.count(
            Coupon.id)).filter(Coupon.status == 'expired').scalar()

        # Get the base list view
        list_view = super()._list()

        # Add statistics to the template
        list_view.update({
            'total_coupons': total_coupons,
            'active_coupons': active_coupons,
            'redeemed_coupons': redeemed_coupons,
            'expired_coupons': expired_coupons,
        })

        return list_view


class OfferModelView(ModelView):
    """
    Enhanced Offer model view for Flask App Builder.
    """
    datamodel = SQLAInterface(Offer)
    list_columns = ['title', 'description', 'slug', 'discount_type', 'discount_value', 'currency', 'merchant', 'cover_image', 'coupon_limit',
                    'status', 'start_date', 'end_date', 'terms_and_conditions', 'featured_until', 'highlighted_until']
    show_columns = ['title', 'description', 'slug', 'discount_type', 'discount_value', 'currency', 'merchant', 'cover_image', 'coupon_limit',
                    'status', 'start_date', 'end_date', 'terms_and_conditions', 'featured_until', 'highlighted_until']
    add_columns = ['title', 'description', 'slug', 'discount_type', 'discount_value', 'currency', 'cover_image', 'coupon_limit',
                   'status', 'merchant', 'start_date', 'end_date', 'terms_and_conditions', 'featured_until', 'highlighted_until']
    edit_columns = ['title', 'description', 'slug', 'discount_type', 'discount_value', 'currency', 'cover_image', 'coupon_limit',
                    'status', 'start_date', 'end_date', 'terms_and_conditions', 'featured_until', 'highlighted_until']
    search_columns = ['title', 'discount_type', 'currency', 'status',
                      'start_date', 'end_date', 'featured_until', 'highlighted_until']

    # Add custom actions
    @action("feature", "Feature Selected", "Are you sure you want to feature the selected offers?", single=False)
    def feature(self, items):
        if not isinstance(items, list):
            items = [items]
        for item in items:
            item.featured_until = datetime.now(
                timezone.utc) + timedelta(days=7)
            self.datamodel.session.commit()
        return redirect(self.get_redirect())

    @action("highlight", "Highlight Selected", "Are you sure you want to highlight the selected offers?")
    def highlight(self, items):
        if not isinstance(items, list):
            items = [items]
        for item in items:
            item.highlighted_until = datetime.now(
                timezone.utc) + timedelta(days=3)
            self.datamodel.session.commit()
        return redirect(self.get_redirect())

    @action("view_coupons", "View Coupons", "View coupons for selected offer")
    def view_coupons(self, item):
        return redirect(url_for('CouponModelView.list', filters=[('offer_id', 'eq', item.id)]))

    # Enhanced form fields
    add_form_extra_fields = {
        'cover_image': FileField(
            label='Cover Image',
            widget=FileInput(),
            render_kw={
                'placeholder': 'Upload cover image',
                'accept': '.png, .jpg, .jpeg',
            }
        ),
        'start_date': DateTimeField(
            format='%Y-%m-%dT%H:%M',
            label='Start Date',
            widget=DateTimeLocalInput(),
            default=datetime.now(),
            validators=[DataRequired()],
            render_kw={
                'placeholder': 'Select start date',
                'required': 'required',
            }
        ),
        'end_date': DateTimeField(
            format='%Y-%m-%dT%H:%M',
            label='End Date',
            widget=DateTimeLocalInput(),
            validators=[DataRequired()],
            render_kw={
                'placeholder': 'Select end date',
                'required': 'required',
            }
        ),
        'featured_until': DateTimeField(
            format='%Y-%m-%dT%H:%M',
            label='Featured Until',
            widget=DateTimeLocalInput(),
            validators=[Optional()],
            render_kw={
                'placeholder': 'Select featured until date',
            }
        ),
        'highlighted_until': DateTimeField(
            format='%Y-%m-%dT%H:%M',
            label='Highlighted Until',
            widget=DateTimeLocalInput(),
            validators=[Optional()],
            render_kw={
                'placeholder': 'Select highlighted until date',
            }
        ),
        'discount_type': SelectField(
            'Discount Type',
            choices=[
                ('percentage', 'Percentage'),
                ('fixed', 'Fixed Amount'),
                ('free_shipping', 'Free Shipping'),
                ('buy_one_get_one', 'Buy One Get One'),
            ],
            validators=[DataRequired()],
            render_kw={
                'placeholder': 'Select discount type',
                'required': 'required',
            }
        ),
        'currency': SelectField(
            'Currency',
            choices=[
                ('USD', 'US Dollar'),
                ('EUR', 'Euro'),
                ('GBP', 'British Pound'),
                ('JPY', 'Japanese Yen'),
                ('CAD', 'Canadian Dollar'),
                ('AUD', 'Australian Dollar'),
            ],
            validators=[DataRequired()],
            render_kw={
                'placeholder': 'Select currency',
                'required': 'required',
            }
        ),
        'terms_and_conditions': TextAreaField(
            'Terms and Conditions',
            widget=TextArea(),
            render_kw={
                'placeholder': 'Enter terms and conditions',
                'rows': 4,
            }
        )
    }

    edit_form_extra_fields = add_form_extra_fields

    # Enhanced column formatters
    formatters_columns = {
        'cover_image': lambda m: Markup(
            f'<img src="{m}" width="100" class="img-preview">'
        ) if m else '',
        'start_date': lambda m: m.strftime('%Y-%m-%d %H:%M') if m else None,
        'end_date': lambda m: m.strftime('%Y-%m-%d %H:%M') if m else None,
        'featured_until': lambda m: m.strftime('%Y-%m-%d %H:%M') if m else None,
        'highlighted_until': lambda m: m.strftime('%Y-%m-%d %H:%M') if m else None,
        'status': lambda m: Markup(
            f'<span class="badge {"badge-success" if m == "active" else "badge-warning"}">{m}</span>'
        ),
        'discount_type': lambda m: m.replace('_', ' ').title(),
    }

    # Add list template
    list_template = 'offer_list.html'

    def _list(self):
        # Get the base list view data first
        list_view = super()._list()

        # Get statistics for the list view
        total_offers = self.datamodel.session.query(
            func.count(Offer.id)).scalar()
        active_offers = self.datamodel.session.query(func.count(
            Offer.id)).filter(Offer.end_date > datetime.now(timezone.utc)).scalar()
        featured_offers = self.datamodel.session.query(func.count(Offer.id)).filter(
            Offer.featured_until > datetime.now(timezone.utc)).scalar()
        total_coupons = self.datamodel.session.query(
            func.count(Coupon.id)).scalar()

        # Add statistics to the template context
        list_view.update({
            'total_offers': total_offers,
            'active_offers': active_offers,
            'featured_offers': featured_offers,
            'total_coupons': total_coupons,
        })

        return list_view

    def pre_add(self, item):
        self._upload_to_cloudinary(item)

    def pre_update(self, item):
        self._upload_to_cloudinary(item)

    def _upload_to_cloudinary(self, item):
        file = request.files.get('cover_image')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(
                file, folder='studentx/offers')
            item.cover_image = upload_result.get('secure_url')
