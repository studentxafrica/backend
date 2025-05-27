from flask import request  # type: ignore
import cloudinary  # type: ignore
import cloudinary.uploader  # type: ignore
from markupsafe import Markup  # type: ignore
from flask_appbuilder import ModelView  # type: ignore
from flask_appbuilder.models.sqla.interface import SQLAInterface  # type: ignore
from app import appbuilder
from wtforms import DateTimeField, FileField  # type: ignore
from wtforms.widgets import FileInput # type: ignore
from wtforms.widgets import DateTimeLocalInput  # type: ignore
from wtforms.validators import DataRequired, Optional  # type: ignore
from datetime import datetime, timezone, timedelta  # type: ignore

from app.models import Coupon, Offer  # type: ignore


class CouponModelView(ModelView):
    """
    Coupon model view for Flask App Builder.
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


class OfferModelView(ModelView):
    """
        Offer model view for Flask App Builder.
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

    add_form_extra_fields = {
        'cover_image': FileField(
            label='Cover Image',
            widget=FileInput(),
            # validators=[Optional()],
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
        )
    }

    edit_form_extra_fields = {
        # 'cover_image': FileField(
        #     label='Cover Image',
        #     widget=FileInput(),
        #     # validators=[Optional()],
        #     render_kw={
        #         'placeholder': 'Upload cover image',
        #         'accept': '.png, .jpg, .jpeg',
        #     }
        # ),
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
        )
    }

    def model_on_change(self, form, model: Offer, is_created: bool = True):
        """
        Called when adding or editing an Offer.
        Upload image file to Cloudinary if provided.
        """
        print(request.files)
        file = request.files.get('cover_image')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(
                file, folder='studentx/offers')
            model.cover_image = upload_result.get('secure_url')

    def _pre_add(self, item):
        """
        Pre-add hook to handle file upload.
        """
        file = request.files.get('cover_image')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(
                file, folder='studentx/offers')
            item.cover_image = upload_result.get('secure_url')

    def _pre_update(self, item):
        """
        Pre-update hook to handle file upload.
        """
        print(request.files)
        file = request.files.get('cover_image')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(
                file, folder='studentx/offers')
            item.cover_image = upload_result.get('secure_url')

    formatters_columns = {
        'c': lambda m: Markup(
            f'<img src="{m}" width="100">'
        ) if m else '',
        'start_date': lambda m: m.strftime('%d %B %Y %H:%M:%S') if m else None,
        'end_date': lambda m: m.strftime('%d %B %Y %H:%M:%S') if m else None,
        'featured_until': lambda m: m.strftime('%d %B %Y %H:%M:%S') if m else None,
        'highlighted_until': lambda m: m.strftime('%d %B %Y %H:%M:%S') if m else None,
    }
