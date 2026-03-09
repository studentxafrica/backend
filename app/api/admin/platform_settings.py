# app/api/platform_settings.py
from flask import Blueprint, request, jsonify
from app.models import Category, Tag
from app import db
# from app.utils import admin_required
from . import admin, current_app
from app.utils import roles_required

# General Settings Endpoints


@admin.route('/general', methods=['GET', 'PUT'])
@roles_required('admin')
def general_settings():
    try:
        if request.method == 'GET':
            # Return current platform settings
            return jsonify({
                'platformName': 'StudentX',
                'platformDescription': 'The ultimate student discount platform',
                'platformUrl': 'studentx.co.ke',
                'featureSettings': {
                    'autoApproveMerchants': False,
                    'emailVerification': True,
                    'studentIdVerification': True,
                    'merchantApprovalNotifications': True,
                    'featuredOffers': True,
                    'socialSharing': True
                },
                'platform_limits': {
                    'maxOffersPerMerchant': 25,
                    'maxCouponsPerOffer': 1000,
                    'couponExpiryDays': 30
                }
            })

        if request.method == 'PUT':
            # Update platform settings
            UPDATEABLE_SETTINGS = ['platformName', 'platformDescription',
                                   'platformUrl', 'featureSettings', 'platform_limits']
            data = request.get_json()
            # Here you would save to database
            return jsonify({'message': 'Settings updated successfully'}), 200
    except Exception as e:
        current_app.logger.error(f"Error in general_settings: {str(e)}")
        return jsonify({
            'message': 'An error occurred',
            'description': "An error occurred while processing general settings"
        }), 500


@admin.route('/categories', methods=['GET', 'POST'])
@roles_required('admin')
def manage_categories():
    try:
        if request.method == 'GET':
            categories = db.session.query(Category).all()
            return jsonify([{
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'merchantCount': category.merchant_count,
                'offerCount': category.offer_count,
                'active': True  # You might want to add this field to your model
            } for category in categories])

        if request.method == 'POST':
            data = request.get_json()
            if not data.get('name'):
                return jsonify({'message': 'Category name is required'}), 400

            if db.session.query(Category).filter_by(name=data['name']).first():
                return jsonify({'message': 'Category already exists'}), 400

            category = Category(
                name=data['name'],
                slug=data.get(
                    'slug') or data['name'].lower().replace(' ', '-'),
                merchant_count=0,
                offer_count=0
            )
            category.save()
            return jsonify({
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'merchantCount': category.merchant_count,
                'offerCount': category.offer_count,
                'active': True
            }), 201
    except:
        current_app.logger.error(f"Error in general_settings: {str(e)}")
        return jsonify({
            "message": "Internal server error",
            "description": "An error occurred while processing categories data"
        })


@admin.route('/categories/<string:category_id>', methods=['PUT', 'DELETE'])
@roles_required('admin')
def manage_category(category_id):
    category = db.session.query(Category).get_or_404(category_id)

    if request.method == 'PUT':
        data = request.get_json()
        if 'name' in data:
            category.name = data['name']
        if 'slug' in data:
            category.slug = data['slug']
        # Add active status if you implement it
        category.save()
        return jsonify({'message': 'Category updated successfully'}), 200

    if request.method == 'DELETE':
        category.delete()
        return jsonify({'message': 'Category deleted successfully'}), 200


@admin.route('/tags', methods=['GET', 'POST'])
@roles_required('admin')
def manage_tags():
    if request.method == 'GET':
        tags = db.session.query(Tag).all()
        return jsonify([{
            'id': tag.id,
            'name': tag.name,
            # Assuming you want to count offers using this tag
            'useCount': len(tag.offers)
        } for tag in tags])

    if request.method == 'POST':
        data = request.get_json()
        if not data.get('name'):
            return jsonify({'message': 'Tag name is required'}), 400

        tag = Tag(name=data['name'].lower().strip())
        tag.save()
        return jsonify({
            'id': tag.id,
            'name': tag.name,
            'useCount': len(tag.offers)
        }), 201


@admin.route('/tags/<string:tag_id>', methods=['DELETE'])
@roles_required('admin')
def delete_tag(tag_id):
    tag = db.session.query(Tag).get_or_404(tag_id)
    tag.delete()
    return jsonify({'message': 'Tag deleted successfully'}), 200


@admin.route('/categories/<string:category_id>/toggle', methods=['PUT'])
@roles_required('admin')
def toggle_category(category_id):
    category = db.session.query(Category).get_or_404(category_id)
    category.active = not category.active
    category.save()
    return jsonify({
        'message': 'Category status updated',
        'active': category.active
    }), 200
