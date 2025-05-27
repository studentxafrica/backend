from flask_appbuilder import ModelView  # type: ignore
from flask import flash, redirect, render_template  # type: ignore
from flask_appbuilder.models.sqla.interface import SQLAInterface  # type: ignore
from app import appbuilder
from app.models import Category  # type: ignore
from wtforms import FileField  # type: ignore
from werkzeug.datastructures import FileStorage  # type: ignore
from flask import request  # type: ignore
import cloudinary  # type: ignore
import cloudinary.uploader  # type: ignore
from app.fab_views.merchant_view import MerchantModelView # type: ignore
from markupsafe import Markup  # type: ignore


class CategoryModelView(ModelView):
    """
        Category model view for Flask App Builder.
        """
    datamodel = SQLAInterface(Category)
    list_columns = ['name', 'slug', 'offer_count', 'merchant_count', 'image_url']
    show_columns = ['name', 'slug', 'offer_count', 'merchant_count', 'image_url']

    add_form_extra_fields = {
        'image_upload': FileField(
            label='Image URL (optional)',
            render_kw={
                'placeholder': 'Upload image',
                'accept': '.png, .jpg, .jpeg',
            }
        )
    }

    edit_form_extra_fields = {
        'image_upload': FileField(
            label='Image URL (optional)',
            render_kw={
                'placeholder': 'Upload image',
                'accept': '.png, .jpg, .jpeg',
            }
        )
    }

    add_columns = ['name', 'slug', 'image_upload']
    edit_columns = ['name', 'slug', 'offer_count', 'merchant_count', 'image_upload']
    search_columns = ['name', 'slug', 'merchants']
    show_columns = ['name', 'slug', 'image_url']
    related_views = [MerchantModelView]


    def pre_add(self, item):
        self._upload_to_cloudinary(item)

    def pre_update(self, item):
        self._upload_to_cloudinary(item)

    def on_model_change(self, form, model: Category, is_created: bool = True):
        """
        Called when adding or editing a Category.
        Upload image file to Cloudinary if provided.
        """
        file = request.files.get('image_upload')  # match the form field name
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(
                file, folder='studentx/categories')
            model.image_url = upload_result.get('secure_url')

    def _upload_to_cloudinary(self, item):
        file: FileStorage = request.files.get('image_upload')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(file,
                                                       folder='studentx/categories')
            item.image_url = upload_result.get('secure_url')

    formatters_columns = {
        'image_url': lambda image: Markup(f'<img src="{image}" width="50" height="50" />') if image else '',
    }
