from datetime import datetime, timezone
from flask import request
from flask_appbuilder import ModelView  # type: ignore
from flask_appbuilder.models.sqla.interface import SQLAInterface  # type: ignore
from werkzeug.datastructures import FileStorage  # type: ignore
from wtforms import FileField, PasswordField, RadioField  # type: ignore
from flask_appbuilder.fieldwidgets import BS3PasswordFieldWidget  # type: ignore
import cloudinary  # type: ignore
import cloudinary.uploader  # type: ignore
from markupsafe import Markup

from app.fab_views.coupon_views import OfferModelView  # type: ignore
from app.fab_views.store_view import StoreModelView  # type: ignore

from app.models import Merchant  # type: ignore


class MerchantModelView(ModelView):
    """
    Merchant model view for Flask App Builder.
    """
    datamodel = SQLAInterface(Merchant)
    list_columns = ['name', 'email', 'website', 'category',
                    'preferred_currency', 'approved', 'approved_on', 'offers']
    show_columns = ['name', 'email', 'website', 'category',
                    'preferred_currency', 'approved', 'approved_on', 'logo']
    add_columns = ['name', 'email', 'password', 'logo',
                   'website', 'category', 'is_approved', 'preferred_currency']
    edit_columns = ['name', 'email', 'website', 'logo',
                    'category', 'preferred_currency', 'is_approved']
    search_columns = ['name', 'email', 'category', 'preferred_currency']

    related_views = [OfferModelView, StoreModelView]

    def get_logo_url(self, item):
        return item.logo if item and item.logo else None

    edit_form_extra_fields = {
        'logo': FileField(
            label='Logo',
            render_kw={
                'placeholder': 'Upload new logo (leave blank to keep current)',
                'accept': '.png, .jpg, .jpeg .webp',
            }
        ),
        'is_approved': RadioField(
            'Approve',
            choices=[('yes', 'Yes'), ('no', 'No')],
            default='no',
            render_kw={
                    'placeholder': 'Select approval status',
                    'required': 'required',
            }
        ),
    }

    add_form_extra_fields = {
        'logo': FileField(
            label='Logo (optional)',
            render_kw={
                'placeholder': 'Upload logo',
                'accept': '.png, .jpg, .jpeg',
            }
        ),
        'is_approved': RadioField(
            'Approved',
            choices=[('yes', 'Yes'), ('no', 'No')],
            render_kw={
                'placeholder': 'Select approval status',
                'required': 'required',
            }
        ),
        'password': PasswordField(
            'Password',
            widget=BS3PasswordFieldWidget(),
            render_kw={
                'placeholder': 'Enter password',
                'autocomplete': 'new-password',
                'required': 'required',
            }
        )
    }
    related_views = [OfferModelView, StoreModelView]

    formatters_columns = {
        'offers': lambda m: len(m),
        'approved': lambda m: 'Yes' if m else 'No',
        'approved_on': lambda m: m.strftime('%Y-%m-%d %H:%M:%S') if m else 'Not Approved',
        'logo': lambda m: Markup(
            f'<img src="{m}" width="100">'
        ) if m else ''
    }

    def pre_add(self, item):
        password = request.form.get('password')
        approved = request.form.get('is_approved')
        if password:
            item.password = password
        if approved == 'yes':
            item.approved_on = datetime.now(timezone.utc)
        self._upload_to_cloudinary(item)

    def pre_update(self, item):
        approved = request.form.get('is_approved')
        if approved:
            if approved == 'yes' and not item.approved:
                item.approved_on = datetime.now(timezone.utc)
            elif approved == 'no' and item.approved:
                item.approved_on = None

        file = request.files.get('logo')
        if file and file.filename:
            self._upload_to_cloudinary(item)

        form_data = request.form.to_dict()
        for field in ['name', 'email', 'website', 'category', 'preferred_currency']:
            if field in form_data and getattr(item, field) != form_data[field]:
                setattr(item, field, form_data[field])

    def _upload_to_cloudinary(self, item):
        file: FileStorage = request.files.get('logo')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(file)
            item.logo = upload_result.get('secure_url')
