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
                    'school', 'major', 'student_id', 'location', 'verified_at']
    search_columns = ['first_name', 'last_name', 'email']

    add_form_extra_fields = {
        'profile_picture': FileField('Profile Picture'),
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

    def pre_add(self, item):
        self._upload_to_cloudinary(item)
        password = request.form.get('password')
        if password:
            item.password = password  # This will trigger the @password.setter

    def pre_update(self, item):
        self._upload_to_cloudinary(item)

    def _upload_to_cloudinary(self, item):
        file: FileStorage = request.files.get('profile_picture')
        if file and file.filename:
            upload_result = cloudinary.uploader.upload(file)
            item.profile_picture = upload_result.get('secure_url')

    column_formatters = {
        'profile_picture': lambda v, c, m, p: f'<img src="{m.profile_picture}" width="100">' if m.image_url else ''
    }
