from flask_restx import Namespace, fields

api = Namespace('base', description='Base namespace for common models and utilities')

# Common response models
error_model = api.model('Error', {
    'message': fields.String(description='Error message'),
    'code': fields.Integer(description='Error code')
})

success_model = api.model('Success', {
    'message': fields.String(description='Success message'),
    'data': fields.Raw(description='Response data')
})

# Pagination models
pagination_model = api.model('Pagination', {
    'page': fields.Integer(description='Current page number'),
    'per_page': fields.Integer(description='Number of items per page'),
    'total': fields.Integer(description='Total number of items'),
    'pages': fields.Integer(description='Total number of pages')
})

# Common query parameters
pagination_params = api.parser()
pagination_params.add_argument('page', type=int, default=1, help='Page number')
pagination_params.add_argument('per_page', type=int, default=10, help='Items per page') 