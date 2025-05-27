from flask_appbuilder import ModelView # type: ignore
from flask_appbuilder.models.sqla.interface import SQLAInterface  # type: ignore
from app.models.store import Store  # type: ignore


class StoreModelView(ModelView):
    datamodel = SQLAInterface(Store)
    list_columns = ['name', 'location',
                    'contact_email', 'contact_phone', 'merchant']
    show_columns = ['name', 'location',
                    'contact_email', 'contact_phone', 'merchant']
    add_columns = ['name', 'location',
                   'contact_email', 'contact_phone', 'merchant']
    edit_columns = ['name', 'location',
                    'contact_email', 'contact_phone', 'merchant']
    search_columns = ['name', 'location',
                      'contact_email', 'contact_phone', 'merchant']