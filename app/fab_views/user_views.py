from flask_appbuilder.models.sqla.interface import SQLAInterface  # type: ignore
from flask_appbuilder import ModelView  # type: ignore
from werkzeug.datastructures import FileStorage  # type: ignore
from wtforms import FileField  # type: ignore
from flask_appbuilder.fieldwidgets import BS3PasswordFieldWidget  # type: ignore
from wtforms.fields import PasswordField, RadioField  # type: ignore
from wtforms.widgets import RadioInput  # type: ignore
import cloudinary  # type: ignore
import cloudinary.uploader  # type: ignore
from flask import request  # type: ignore
from datetime import datetime, timezone  # type: ignore
from flask_appbuilder.forms import DynamicForm  # type: ignore

from app import appbuilder

from flask_appbuilder import ModelView  # type: ignore
from flask_appbuilder.models.sqla.interface import SQLAInterface  # type: ignore
from app.models import Consumer, Merchant


class ConsumerModelView(ModelView):
    """
        Consumer model view for Flask App Builder.
        """
    datamodel = SQLAInterface(Consumer)
    list_columns = ['first_name', 'last_name', 'email', 'phone', 'graduation_year',
                    'school', 'major', 'student_id', 'location', 'verified', 'verified_at']
    show_columns = ['first_name', 'last_name', 'email', 'phone', 'graduation_year',
                    'school', 'major', 'student_id', 'location', 'verified', 'verified_at']
    add_columns = ['first_name', 'last_name', 'email', 'phone', 'graduation_year', 'password',
                   'school', 'major', 'student_id', 'location', 'verified_at']
    edit_columns = ['first_name', 'last_name', 'email', 'phone', 'graduation_year',
                    'school', 'major', 'student_id', 'location', 'is_verified']
    search_columns = ['first_name', 'last_name', 'email']

    edit_form_extra_fields = {
        'profile_picture': FileField(
            label='Profile Picture',
            render_kw={
                'placeholder': 'Upload new avatar (leave blank to keep current)',
                'accept': '.png, .jpg, .jpeg .webp',
            }
        ),
        'is_verified': RadioField(
            'Verified',
            choices=[('yes', 'Yes'), ('no', 'No')],
            render_kw={
                'placeholder': 'Select approval status',
                'required': 'required',
            }
        ),
    }

    add_form_extra_fields = {
        'profile_picture': FileField(
            label='Profile Picture',
            render_kw={
                'placeholder': 'Upload new avatar',
                'accept': '.png, .jpg, .jpeg .webp',
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
        'is_verified': RadioField(
            'Verified',
            choices=[('yes', 'Yes'), ('no', 'No')],
            render_kw={
                'placeholder': 'Select approval status',
                'required': 'required',
            }
        ),
    }

    def pre_add(self, item: Consumer):
        password = request.form.get('password')
        if password:
            item.password = password  # This will trigger the @password.setter
        verified = request.form.get('is_verified')
        if verified:
            if verified == 'yes' and not item.verified:
                item.verified_at = datetime.now(timezone.utc)
            elif verified == 'no' and item.verified:
                item.verified_at = None

        file = request.files.get('profile_picture')
        if file and file.filename:
            self._upload_to_cloudinary(item)

    def pre_update(self, item: Consumer):
        verified = request.form.get('is_verified')
        if verified:
            if verified == 'yes' and not item.verified:
                item.verified_at = datetime.now(timezone.utc)
            elif verified == 'no' and item.verified:
                item.verified_at = None

        file = request.files.get('profile_picture')
        if file and file.filename:
            self._upload_to_cloudinary(item)

    def _upload_to_cloudinary(self, item):
        file: FileStorage = request.files.get('profile_picture')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(file)
            item.profile_picture = upload_result.get('secure_url')

    column_formatters = {
        'profile_picture': lambda v, c, m, p: f'<img src="{m.profile_picture}" width="100">' if m.image_url else ''
    }
