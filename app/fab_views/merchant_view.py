from datetime import datetime, timezone
from flask import request, flash, redirect, url_for
from flask_appbuilder import ModelView, action
from flask_appbuilder.models.sqla.interface import SQLAInterface
from werkzeug.datastructures import FileStorage
from wtforms import FileField, PasswordField, RadioField, SelectField
from flask_appbuilder.fieldwidgets import BS3PasswordFieldWidget
import cloudinary
import cloudinary.uploader
from markupsafe import Markup
from sqlalchemy import func

from app.fab_views.coupon_views import OfferModelView
from app.fab_views.store_view import StoreModelView
from app.models import Merchant, Offer, Store

class MerchantModelView(ModelView):
    """
    Enhanced Merchant model view for Flask App Builder.
    """
    datamodel = SQLAInterface(Merchant)
    list_columns = ['name', 'email', 'website', 'category',
                    'preferred_currency', 'approved', 'approved_on', 'offers', 'stores']
    show_columns = ['name', 'email', 'website', 'category',
                    'preferred_currency', 'approved', 'approved_on', 'logo', 'stores', 'offers']
    add_columns = ['name', 'email', 'password', 'logo',
                   'website', 'category', 'is_approved', 'preferred_currency']
    edit_columns = ['name', 'email', 'website', 'logo',
                    'category', 'preferred_currency', 'is_approved']
    search_columns = ['name', 'email', 'category', 'preferred_currency']
    
    # Add custom actions
    @action("approve", "Approve Selected", "Are you sure you want to approve the selected merchants?", single=False)
    def approve(self, items):
        if not isinstance(items, list):
            items = [items]
        for item in items:
            item.approved = True
            item.approved_on = datetime.now(timezone.utc)
            self.datamodel.edit(item)
            item.save()
        return redirect(self.get_redirect())

    @action("reject", "Reject Selected", "Are you sure you want to reject the selected merchants?", single=False)
    def reject(self, items):
        if not isinstance(items, list):
            items = [items]
        for item in items:
            item.approved = False
            item.approved_on = None
            self.datamodel.edit(item)
        return redirect(self.get_redirect())

    @action("view_offers", "View Offers", "View offers for selected merchant")
    def view_offers(self, item):
        return redirect(url_for('OfferModelView.list', filters=[('merchant_id', 'eq', item.id)]))

    @action("view_stores", "View Stores", "View stores for selected merchant")
    def view_stores(self, item):
        return redirect(url_for('StoreModelView.list', filters=[('merchant_id', 'eq', item.id)]))

    # Enhanced form fields
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
        ),
        'preferred_currency': SelectField(
            'Preferred Currency',
            choices=[
                ('USD', 'US Dollar'),
                ('EUR', 'Euro'),
                ('GBP', 'British Pound'),
                ('JPY', 'Japanese Yen'),
                ('CAD', 'Canadian Dollar'),
                ('AUD', 'Australian Dollar'),
            ],
            render_kw={
                'placeholder': 'Select preferred currency',
            }
        )
    }

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
        'preferred_currency': SelectField(
            'Preferred Currency',
            choices=[
                ('USD', 'US Dollar'),
                ('EUR', 'Euro'),
                ('GBP', 'British Pound'),
                ('JPY', 'Japanese Yen'),
                ('CAD', 'Canadian Dollar'),
                ('AUD', 'Australian Dollar'),
            ],
            render_kw={
                'placeholder': 'Select preferred currency',
            }
        )
    }

    # Enhanced column formatters
    formatters_columns = {
        'offers': lambda m: len(m),
        'stores': lambda m: len(m),
        'approved': lambda m: 'Yes' if m else 'No',
        'approved_on': lambda m: m.strftime('%Y-%m-%d %H:%M:%S') if m else 'Not Approved',
        'logo': lambda m: Markup(
            f'<img src="{m}" width="100" class="img-preview">'
        ) if m else ''
    }

    # Add list template
    list_template = 'merchant_list.html'

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

    def _upload_to_cloudinary(self, item):
        file: FileStorage = request.files.get('logo')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(file)
            item.logo = upload_result.get('secure_url')

    # Add custom list view
    def _list(self):
        # Get statistics for the list view
        total_merchants = self.datamodel.session.query(func.count(Merchant.id)).scalar()
        approved_merchants = self.datamodel.session.query(func.count(Merchant.id)).filter(Merchant.approved == True).scalar()
        total_offers = self.datamodel.session.query(func.count(Offer.id)).scalar()
        total_stores = self.datamodel.session.query(func.count(Store.id)).scalar()

        # Get the base list view
        list_view = super()._list()
        
        # Add statistics to the template
        list_view.update({
            'total_merchants': total_merchants or 100,
            'approved_merchants': approved_merchants,
            'total_offers': total_offers,
            'total_stores': total_stores,
        })
        
        return list_view
