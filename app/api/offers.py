from flask_restx import Namespace, Resource, fields
from .base import api as base_api, pagination_params, pagination_model

api = Namespace('offers', description='Offer operations')

# Models
offer_model = api.model('Offer', {
    'id': fields.Integer(description='Offer ID'),
    'title': fields.String(description='Offer title'),
    'description': fields.String(description='Offer description'),
    'merchant_id': fields.Integer(description='Merchant ID'),
    'category': fields.String(description='Offer category'),
    'status': fields.String(description='Offer status'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp')
})

offer_list_model = api.model('OfferList', {
    'items': fields.List(fields.Nested(offer_model)),
    'pagination': fields.Nested(pagination_model)
})

@api.route('/')
class OfferList(Resource):
    @api.doc('list_offers')
    @api.expect(pagination_params)
    @api.marshal_with(offer_list_model)
    def get(self):
        """List all offers"""
        pass

    @api.doc('create_offer')
    @api.expect(offer_model)
    @api.marshal_with(offer_model)
    def post(self):
        """Create a new offer"""
        pass

@api.route('/<int:id>')
@api.param('id', 'The offer identifier')
class Offer(Resource):
    @api.doc('get_offer')
    @api.marshal_with(offer_model)
    def get(self, id):
        """Get an offer by ID"""
        pass

    @api.doc('update_offer')
    @api.expect(offer_model)
    @api.marshal_with(offer_model)
    def put(self, id):
        """Update an offer"""
        pass

    @api.doc('delete_offer')
    @api.response(204, 'Offer deleted')
    def delete(self, id):
        """Delete an offer"""
        pass 